import os
import asyncio
from datetime import datetime
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
from typing import Dict, Any

# Import the workflow components
from src.workflow_v3 import KGWorkflow
from llama_index.core.workflow import StartEvent
from src.logger import kg_logger

app = Flask(__name__)
app.config["SECRET_KEY"] = "your-secret-key-here"
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Store active workflows
active_workflows = {}


class WorkflowEventHandler:
    """Handler to capture and emit workflow events via WebSocket"""

    def __init__(self, session_id: str, socketio_instance):
        self.session_id = session_id
        self.socketio = socketio_instance
        self.events_log = []

    def emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit event to the client"""
        self.events_log.append(
            {"timestamp": datetime.now().isoformat(), "type": event_type, "data": data}
        )
        self.socketio.emit(
            "workflow_event", {"type": event_type, "data": data}, room=self.session_id
        )


async def process_workflow_with_events(query: str, session_id: str, socketio_instance):
    """Process workflow and emit events via WebSocket"""
    handler = WorkflowEventHandler(session_id, socketio_instance)

    try:
        # Initialize workflow
        workflow = KGWorkflow(timeout=1000, verbose=False)

        # Emit start event
        handler.emit_event(
            "workflow_status",
            {
                "message": "🔍 正在分析查询...",
                "status": "matching",
                "step": "match_mapping",
            },
        )

        # Start workflow
        start_event = StartEvent(query=query)
        workflow_handler = workflow.run(start_event=start_event)

        # Process events
        matched_cypher = None
        report_started = False
        current_report = ""
        executed_queries = []
        query_execution_started = False

        async for event in workflow_handler.stream_events():
            event_type = type(event).__name__
            
            # Handle MatchingCompletedEvent
            if event_type == "MatchingCompletedEvent":
                # Emit matching completed event with detailed information
                handler.emit_event(
                    "matching_completed",
                    {
                        "matched_query": event.matched_query,
                        "similarity_score": round(event.similarity_score, 4),
                        "cypher": event.cypher,
                        "message": f"✅ 查询匹配完成 (相似度: {event.similarity_score:.4f})",
                        "status": "completed",
                    },
                )
                
                # Update matching step to completed with simple message
                handler.emit_event(
                    "workflow_status",
                    {
                        "message": "✅ 查询分析完成",
                        "status": "completed",
                        "step": "match_mapping",
                    },
                )
            
            # Handle CypherEvent
            elif event_type == "CypherEvent":
                matched_cypher = event.cypher
                
                # Emit cypher matched event with the cypher
                handler.emit_event(
                    "cypher_matched",
                    {
                        "cypher": matched_cypher,
                        "message": "✅ 已匹配到最佳查询语句",
                        "status": "matched",
                    },
                )
                
                # Update matching step to completed with cypher display
                print(f"[DEBUG] Emitting match_mapping completion with cypher: {matched_cypher[:100]}...")
                handler.emit_event(
                    "workflow_status",
                    {
                        "message": "✅ 查询分析完成",
                        "status": "completed",
                        "step": "match_mapping",
                        "cypher": matched_cypher,  # Include cypher for display
                    },
                )
                
                # Start executing status
                handler.emit_event(
                    "workflow_status",
                    {
                        "message": "📊 准备执行知识图谱查询...",
                        "status": "executing",
                        "step": "execute_query",
                        "cypher": matched_cypher,
                    },
                )
            
            # Handle QueryExecutingEvent
            elif event_type == "QueryExecutingEvent":
                if not query_execution_started:
                    query_execution_started = True
                    # Create queries execution section
                    handler.emit_event(
                        "workflow_status",
                        {
                            "message": "🔄 正在执行知识图谱查询...",
                            "status": "executing",
                            "step": "query_execution",
                        },
                    )
                
                handler.emit_event(
                    "query_executing",
                    {
                        "index": event.index,
                        "cypher": event.cypher,
                    },
                )
            
            # Handle QueryExecutedEvent
            elif event_type == "QueryExecutedEvent":
                executed_queries.append({
                    "index": event.index,
                    "cypher": event.cypher,
                    "result": event.result
                })
                
                handler.emit_event(
                    "query_executed",
                    {
                        "index": event.index,
                        "cypher": event.cypher,
                        "result": event.result,  # This is already a string from workflow_v3
                        "total": len(executed_queries)
                    },
                )
                
                # Update execute_query status with count
                handler.emit_event(
                    "workflow_status",
                    {
                        "message": f"✅ 已执行 {len(executed_queries)} 个查询",
                        "status": "completed",
                        "step": "execute_query",
                    },
                )
            
            # Handle ReportChunkEvent
            elif event_type == "ReportChunkEvent":
                if not report_started:
                    report_started = True
                    handler.emit_event(
                        "workflow_status",
                        {
                            "message": "📝 正在生成分析报告...",
                            "status": "generating",
                            "step": "generate_report",
                        },
                    )
                
                current_report += event.chunk
                handler.emit_event("report_chunk", {"chunk": event.chunk})

        # Get final result
        final_result = await workflow_handler
        
        # If no report chunks were streamed, the result might be the full report
        if not report_started and final_result:
            handler.emit_event(
                "workflow_status",
                {
                    "message": "📝 正在生成分析报告...",
                    "status": "generating",
                    "step": "generate_report",
                },
            )
            handler.emit_event("report_chunk", {"chunk": str(final_result)})

        # Update report generation to completed
        if report_started:
            handler.emit_event(
                "workflow_status",
                {
                    "message": "✅ 分析报告生成完成",
                    "status": "completed",
                    "step": "generate_report",
                },
            )
        
        handler.emit_event(
            "workflow_complete",
            {
                "status": "success",
                "message": "✅ 分析完成",
                "final_report": str(final_result) if final_result else current_report,
            },
        )

    except Exception as e:
        kg_logger.log_error(f"Workflow error: {str(e)}")
        handler.emit_event(
            "workflow_error",
            {
                "error": str(e),
                "status": "error",
                "message": f"❌ 处理过程中出现错误: {str(e)}",
            },
        )


@app.route("/")
def index():
    """Serve the main page"""
    return render_template("index_v3.html")


@socketio.on("connect")
def handle_connect():
    """Handle client connection"""
    session_id = request.sid
    print(f"Client connected: {session_id}")
    emit("connected", {"session_id": session_id})


@socketio.on("disconnect")
def handle_disconnect():
    """Handle client disconnection"""
    session_id = request.sid
    print(f"Client disconnected: {session_id}")
    # Clean up any active workflows
    if session_id in active_workflows:
        del active_workflows[session_id]


@socketio.on("submit_query")
def handle_submit_query(data):
    """Handle query submission"""
    session_id = request.sid
    query = data.get("query", "")

    if not query:
        emit("error", {"message": "Query cannot be empty"})
        return

    # Run workflow in a separate thread
    def run_async_workflow():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(
            process_workflow_with_events(query, session_id, socketio)
        )
        loop.close()

    thread = threading.Thread(target=run_async_workflow)
    thread.start()
    active_workflows[session_id] = thread

    emit("query_submitted", {"query": query, "timestamp": datetime.now().isoformat()})


if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    os.makedirs("templates", exist_ok=True)

    # Run the app
    socketio.run(app, debug=True, host="0.0.0.0", port=7688)  # Use different port from v2
