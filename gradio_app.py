import gradio as gr
from rich.console import Console
from src.context.manager import ContextManager
from src.prompts import KG_AGENT_PROMPT, DYNAMIC_KG_AGENT_PROMPT
from src.core import FunctionCallingAgent
from src.tools import query_neo4j

console = Console()
agent = FunctionCallingAgent(
    model="qwen-max-latest",
    tools=[query_neo4j],
    console=console,
)
# Disable tool call display for web mode
agent.show_tool_calls = False
with open("/Users/ruipu/projects/KG_Demo/config/graph_schema.md") as f:
    schema = f.read()
context_manager = ContextManager(
    resources=["mapping"],
    schema=schema,  # No static schema in dynamic mode
    llm_client=agent.client,
    schema_mode="static",
)
# Set initial system prompt for dynamic mode
agent.set_history(
    [{"role": "system", "content": KG_AGENT_PROMPT.format(schema=schema)}]
)


async def chat(message, history):
    """
    Chat function that works exactly like the pipeline console.
    The context is loaded internally and not displayed in the chat interface.
    """
    # Load context internally (this won't appear in the UI)
    try:
        context_messages = await context_manager.load_context(message, ["mapping"])

        # Add context to agent's history if available
        if context_messages:
            current_history = agent.get_history()
            enhanced_history = context_manager.add_context_to_history(
                current_history, context_messages
            )
            agent.set_history(enhanced_history)
    except Exception as e:
        print(f"Warning: Context loading failed: {e}")

    # Stream the response and collect it
    response_text = ""
    async for chunk in agent.run_query_stream(message):
        response_text += chunk
        # Yield the current state: the updated history with the partial response
        yield history + [{"role": "assistant", "content": response_text}]

    # Final yield with complete response
    yield history + [{"role": "assistant", "content": response_text}]


demo = gr.ChatInterface(fn=chat, type="messages")

demo.launch()
