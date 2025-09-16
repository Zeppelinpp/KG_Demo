import os
import json
import asyncio
from datetime import datetime
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import threading
from typing import Dict, Any, List

# Import the workflow components
from src.workflow_v2 import (
    KGWorkflow,
    StreamMessageEvent,
    ReportChunkEvent,
    ToolCallEvent,
    AnalyzeResultEvent,
)
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

        # Start workflow
        workflow_handler = workflow.run(query=query)

        # Track state
        current_agent = None
        current_query_type = None
        tool_calls = {}

        # Stream events
        async for event in workflow_handler.stream_events():
            if isinstance(event, AnalyzeResultEvent):
                # Analysis complete event
                handler.emit_event(
                    "analysis_complete",
                    {
                        "main_query": event.result.main_query,
                        "insights_queries": event.result.insights_queries,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

            elif isinstance(event, StreamMessageEvent):
                # Stream message events
                if event.metadata:
                    step = event.metadata.get("step", "")

                    if step == "analysis":
                        status = event.metadata.get("status", "pending")
                        handler.emit_event(
                            "analysis_status",
                            {
                                "message": event.message,
                                "status": status,
                                "metadata": event.metadata,
                            },
                        )

                        # If analysis is done, also send the complete event with queries
                        if status == "done" and "main_query" in event.metadata:
                            handler.emit_event(
                                "analysis_complete",
                                {
                                    "main_query": event.metadata.get("main_query"),
                                    "insights_queries": event.metadata.get(
                                        "insights_queries", []
                                    ),
                                    "timestamp": datetime.now().isoformat(),
                                },
                            )

                    elif step == "execution":
                        if "query" in event.metadata:
                            # Individual query execution result
                            query_type = event.metadata.get("query_type", "")
                            current_query_type = query_type  # Track current query type

                            handler.emit_event(
                                "query_executed",
                                {
                                    "query_type": query_type,
                                    "query": event.metadata.get("query", ""),
                                    "result_preview": event.metadata.get(
                                        "result_preview", ""
                                    ),
                                    "status": "completed",
                                },
                            )

                            # Track which agent is executing
                            if query_type == "main":
                                current_agent = "Main Query Agent"
                            else:
                                idx = (
                                    query_type.split("_")[1]
                                    if "_" in query_type
                                    else "0"
                                )
                                current_agent = f"Insight Agent {idx}"

                        else:
                            handler.emit_event(
                                "execution_status",
                                {
                                    "message": event.message,
                                    "status": event.metadata.get("status", "pending"),
                                    "total_queries": event.metadata.get(
                                        "queries_count", 0
                                    ),
                                },
                            )

                    elif step == "report":
                        handler.emit_event(
                            "report_status",
                            {
                                "message": event.message,
                                "status": event.metadata.get("status", "pending"),
                            },
                        )

                else:
                    handler.emit_event("status_update", {"message": event.message})

            elif isinstance(event, ReportChunkEvent):
                # Stream report chunks
                handler.emit_event("report_chunk", {"chunk": event.chunk})

            elif isinstance(event, ToolCallEvent):
                # Tool call events - use the tracked query type to determine agent
                if current_query_type:
                    if current_query_type == "main":
                        agent_name = "Main Query Agent"
                    else:
                        idx = (
                            current_query_type.split("_")[1]
                            if "_" in current_query_type
                            else "0"
                        )
                        agent_name = f"Insight Agent {idx}"
                else:
                    agent_name = current_agent or "Unknown Agent"

                tool_key = (
                    f"{agent_name}_{event.tool_name}_{datetime.now().timestamp()}"
                )

                # Convert tool_result to string for better display
                tool_result_str = str(event.tool_result) if event.tool_result else ""

                handler.emit_event(
                    "tool_call",
                    {
                        "agent": agent_name,
                        "query_type": current_query_type,  # Add query type for frontend mapping
                        "tool_name": event.tool_name,
                        "tool_args": event.tool_args,
                        "tool_result": tool_result_str,
                        "tool_key": tool_key,
                    },
                )

        # Wait for completion
        final_result = await workflow_handler

        handler.emit_event(
            "workflow_complete", {"status": "success", "final_report": final_result}
        )

    except Exception as e:
        kg_logger.log_error(f"Workflow error: {str(e)}")
        handler.emit_event("workflow_error", {"error": str(e), "status": "error"})


@app.route("/")
def index():
    """Serve the main page"""
    return render_template("index.html")


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
    socketio.run(app, debug=True, host="0.0.0.0", port=7687)
