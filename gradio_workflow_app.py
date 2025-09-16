import gradio as gr
from gradio import ChatMessage
import asyncio
from typing import List, Dict, Any
import json
from datetime import datetime

# Import the enhanced workflow
from src.workflow_v2 import (
    KGWorkflow, 
    StreamMessageEvent, 
    ReportChunkEvent,
    ToolCallEvent
)

async def process_workflow(message: str, history: List):
    """
    Process the workflow and yield ChatMessage updates for Gradio interface
    """
    workflow = KGWorkflow(timeout=1000, verbose=False)
    
    # Start the workflow
    handler = workflow.run(query=message)
    
    # Track messages
    messages = []
    report_content = ""
    is_streaming_report = False
    
    try:
        # Stream events from workflow
        async for event in handler.stream_events():
            
            # Handle stream messages (analysis, execution updates)
            if isinstance(event, StreamMessageEvent):
                # Create ChatMessage with metadata
                if event.metadata:
                    if event.metadata.get("step") == "analysis" and event.metadata.get("main_query"):
                        # Show analysis results
                        messages.append(
                            ChatMessage(
                                role="assistant",
                                content=event.message,
                                metadata={
                                    "title": "🔍 Query Analysis",
                                    "id": "analysis",
                                    "status": event.metadata.get("status", "pending")
                                }
                            )
                        )
                        
                        # Add sub-queries as nested message
                        queries_text = "**Main Query:**\n" + event.metadata.get("main_query", "")
                        if event.metadata.get("insights_queries"):
                            queries_text += "\n\n**Insight Queries:**\n"
                            for q in event.metadata.get("insights_queries", []):
                                queries_text += f"• {q}\n"
                        
                        messages.append(
                            ChatMessage(
                                role="assistant",
                                content=queries_text,
                                metadata={
                                    "title": "Query Details",
                                    "parent_id": "analysis"
                                }
                            )
                        )
                        
                    elif event.metadata.get("step") == "execution":
                        if "query" in event.metadata:
                            # Individual query result
                            messages.append(
                                ChatMessage(
                                    role="assistant",
                                    content=f"✓ Completed: {event.metadata.get('query', '')[:100]}...",
                                    metadata={
                                        "title": f"Query Result - {event.metadata.get('query_type', '')}",
                                        "id": f"query_{event.metadata.get('query_type', '')}",
                                        "log": event.metadata.get("result_preview", "")[:500]
                                    }
                                )
                            )
                        else:
                            # Execution status
                            # Check if we need to update previous execution status
                            execution_msg_index = -1
                            for i, msg in enumerate(messages):
                                if (isinstance(msg, ChatMessage) and 
                                    msg.metadata and 
                                    msg.metadata.get("title") == "📊 Execution Status" and
                                    msg.metadata.get("status") == "pending"):
                                    execution_msg_index = i
                                    break
                            
                            if execution_msg_index >= 0 and event.metadata.get("status") == "done":
                                # Update existing message
                                messages[execution_msg_index] = ChatMessage(
                                    role="assistant",
                                    content=event.message,
                                    metadata={
                                        "title": "📊 Execution Status",
                                        "status": "done"
                                    }
                                )
                            else:
                                # Add new message
                                messages.append(
                                    ChatMessage(
                                        role="assistant",
                                        content=event.message,
                                        metadata={
                                            "title": "📊 Execution Status",
                                            "status": event.metadata.get("status", "")
                                        }
                                    )
                                )
                    elif event.metadata.get("step") == "report":
                        is_streaming_report = True
                        messages.append(
                            ChatMessage(
                                role="assistant",
                                content=event.message,
                                metadata={"title": "📝 Report Generation", "status": "pending"}
                            )
                        )
                else:
                    # Simple status message
                    messages.append(
                        ChatMessage(role="assistant", content=event.message)
                    )
                
                yield messages
            
            # Handle report chunks (streaming final report)
            elif isinstance(event, ReportChunkEvent):
                report_content += event.chunk
                
                # Update Report Generation status to done when we start streaming
                if is_streaming_report:
                    # First, update the "Report Generation" message status to done
                    for i, msg in enumerate(messages):
                        if (isinstance(msg, ChatMessage) and 
                            msg.metadata and 
                            msg.metadata.get("title") == "📝 Report Generation" and
                            msg.metadata.get("status") == "pending"):
                            messages[i] = ChatMessage(
                                role="assistant",
                                content=msg.content,
                                metadata={"title": "📝 Report Generation", "status": "done"}
                            )
                            break
                    
                    # Check if we already have a report message
                    report_exists = False
                    for i, msg in enumerate(messages):
                        if isinstance(msg, ChatMessage) and msg.metadata and msg.metadata.get("title") == "📝 Final Report":
                            messages[i] = ChatMessage(
                                role="assistant",
                                content=report_content,
                                metadata={"title": "📝 Final Report", "status": "done"}
                            )
                            report_exists = True
                            break
                    
                    if not report_exists:
                        messages.append(
                            ChatMessage(
                                role="assistant",
                                content=report_content,
                                metadata={"title": "📝 Final Report", "status": "done"}
                            )
                        )
                    
                    yield messages
            
            # Handle tool calls
            elif isinstance(event, ToolCallEvent):
                messages.append(
                    ChatMessage(
                        role="assistant",
                        content=f"🔧 Using tool: {event.tool_name}",
                        metadata={
                            "title": f"Tool: {event.tool_name}",
                            "log": json.dumps(event.tool_args, indent=2) if event.tool_args else ""
                        }
                    )
                )
                yield messages
        
        # Ensure we have the final result
        await handler
        
    except Exception as e:
        messages.append(
            ChatMessage(
                role="assistant",
                content=f"❌ An error occurred: {str(e)}",
                metadata={
                    "title": "Error",
                    "log": str(e)
                }
            )
        )
        yield messages

async def chat_function(message, history):
    """
    Main chat function for Gradio ChatInterface
    """
    # Process the workflow and stream results
    async for messages in process_workflow(message, history):
        # Return only the new messages (not including history)
        yield messages

# Create the Gradio interface using ChatInterface
demo = gr.ChatInterface(
    fn=chat_function,
    type="messages",
    title="🧠 Knowledge Graph Assistant",
    description=None,  # No description for clean interface
    examples=[
        "分析苹果公司2023年的财务状况",
        "比较腾讯和阿里巴巴的市场表现",
        "查询特斯拉的主要竞争对手",
        "分析半导体行业的发展趋势",
    ],
    cache_examples=False,
    fill_height=True,
    analytics_enabled=False,
    theme=gr.themes.Soft()
)

if __name__ == "__main__":
    demo.queue(max_size=10).launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        show_error=True,
        show_api=False
    )