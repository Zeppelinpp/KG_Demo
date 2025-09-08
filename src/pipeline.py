import os
import asyncio
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.rule import Rule
from src.model.graph import ExtractedGraphSchema, GraphSchema
from src.tools import query_neo4j
from src.prompts import KG_AGENT_PROMPT
from src.core import FunctionCallingAgent, Neo4jSchemaExtractor
from src.context.manager import ContextManager
from src.dynamic_schema import DynamicSchemaExtractor
from src.logger import kg_logger

load_dotenv()

console = Console()

console.print("[dim]Initializing dynamic schema extractor...[/dim]")
dynamic_extractor = DynamicSchemaExtractor(
    uri=os.getenv("NEO4J_URI"),
    database=os.getenv("NEO4J_DATABASE"),
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),
    console=console
)

# 初始化时不提取完整schema，而是在查询时动态提取
schema_md = ""  # 将在查询时动态生成

console.print("[dim]Initializing AI agent...[/dim]")
agent = FunctionCallingAgent(
    model="qwen-max",
    tools=[query_neo4j],
    console=console,
)

console.print("[dim]Initializing context manager...[/dim]")
context_manager = ContextManager(
    resources=["mapping"],
    schema="",  # 将在查询时动态设置
    llm_client=agent.client,  # Share LLM client with agent
)


async def run(user_query: str):
    """Run a single query with dynamic schema"""
    # 动态提取相关schema
    console.print("[dim]Extracting dynamic schema...[/dim]")
    dynamic_schema = await dynamic_extractor.extract_dynamic_schema(user_query)
    dynamic_schema_md = dynamic_schema.to_md()
    
    # Log the dynamic schema usage
    kg_logger.log_schema_usage(dynamic_schema_md)
    
    response = ""
    async for chunk in agent.run_query_stream(
        user_query=user_query,
        system_prompt=KG_AGENT_PROMPT.format(schema=dynamic_schema_md),
    ):
        response += chunk
        print(chunk, end="")
    print()  # New line after streaming
    return response


async def chat_session():
    """Interactive multi-turn chat session with Rich formatting"""
    # Welcome message
    console.print()
    console.rule("[bold green]🚀 Knowledge Graph Chat Assistant", style="green")
    console.print()
    console.print(
        Panel(
            "[bold cyan]Welcome to the Knowledge Graph Chat Assistant![/bold cyan]\n\n"
            "• Ask questions about your Neo4j knowledge graph\n"
            "• Type 'quit', 'exit', or 'bye' to end the session\n"
            "• Type 'clear' to clear chat history\n"
            "• Type 'help' for more information",
            title="[bold blue]Getting Started",
            border_style="blue",
        )
    )
    console.print()

    # Initialize components
    try:
        # Set initial system prompt with empty schema (will be updated per query)
        agent.set_history(
            [{"role": "system", "content": KG_AGENT_PROMPT.format(schema="")}]
        )

        console.print("[bold green]✓ Ready to chat![/bold green]")
        console.print()

    except Exception as e:
        console.print(f"[bold red]❌ Initialization failed: {e}[/bold red]")
        return

    # Main chat loop
    while True:
        try:
            # Get user input with Rich prompt
            user_input = Prompt.ask(
                "\n[bold blue]You[/bold blue]", default="", show_default=False
            ).strip()

            # Handle special commands
            if user_input.lower() in ["quit", "exit", "bye"]:
                console.print()
                console.print(
                    Panel(
                        "[bold yellow]👋 Thanks for using the Knowledge Graph Chat Assistant![/bold yellow]\n"
                        "Goodbye! 🌟",
                        title="[bold blue]Session Ended",
                        border_style="blue",
                    )
                )
                break

            elif user_input.lower() == "clear":
                agent.clear_history()
                agent.set_history(
                    [
                        {
                            "role": "system",
                            "content": KG_AGENT_PROMPT.format(schema=""),
                        }
                    ]
                )
                # 清空动态schema缓存
                dynamic_extractor.clear_cache()
                console.print()
                console.print("[bold green]✓ Chat history and schema cache cleared![/bold green]")
                continue

            elif user_input.lower() == "help":
                console.print()
                console.print(
                    Panel(
                        "[bold cyan]Available Commands:[/bold cyan]\n\n"
                        "• [yellow]quit/exit/bye[/yellow] - End the chat session\n"
                        "• [yellow]clear[/yellow] - Clear chat history\n"
                        "• [yellow]help[/yellow] - Show this help message\n\n"
                        "[bold cyan]Tips:[/bold cyan]\n"
                        "• Ask questions about your Neo4j database\n"
                        "• The assistant can generate and execute Cypher queries\n"
                        "• Use natural language to describe what you're looking for",
                        title="[bold blue]Help",
                        border_style="blue",
                    )
                )
                continue

            elif not user_input:
                continue

            # Display user message
            console.print()
            console.print(
                Panel(
                    f"[white]{user_input}[/white]",
                    title="[bold blue]You",
                    border_style="blue",
                    width=None,
                )
            )

            # Display assistant response header
            console.print()
            console.print("[bold green]🤖 Assistant[/bold green]")
            console.print()

            # Extract dynamic schema for this query
            try:
                console.print("[dim]Extracting dynamic schema...[/dim]")
                dynamic_schema = await dynamic_extractor.extract_dynamic_schema(user_input)
                dynamic_schema_md = dynamic_schema.to_md()
                
                # Log the dynamic schema usage
                kg_logger.log_schema_usage(dynamic_schema_md)
                
                # Update context manager with dynamic schema
                context_manager.schema = dynamic_schema_md
                
                console.print(f"[dim]✓ Dynamic schema extracted ({len(dynamic_schema.nodes)} node types, {len(dynamic_schema.relationships)} relationships)[/dim]")
                
            except Exception as e:
                console.print(f"[dim]Warning: Dynamic schema extraction failed: {e}[/dim]")
                dynamic_schema_md = ""

            # Load context before processing query
            try:
                console.print("[dim]Loading context...[/dim]")
                context_messages = context_manager.load_context(
                    query=user_input,
                    from_resources=["mapping"]
                )
                
                # Add context to agent's history if available
                if context_messages:
                    current_history = agent.get_history()
                    enhanced_history = context_manager.add_context_to_history(
                        current_history, context_messages
                    )
                    agent.set_history(enhanced_history)
                    console.print("[dim]✓ Context loaded[/dim]")
                else:
                    console.print("[dim]No relevant context found[/dim]")
                    
            except Exception as e:
                console.print(f"[dim]Warning: Context loading failed: {e}[/dim]")

            # Stream the response with dynamic schema
            response_text = ""
            async for chunk in agent.run_query_stream(
                user_query=user_input,
                system_prompt=KG_AGENT_PROMPT.format(schema=dynamic_schema_md)
            ):
                response_text += chunk
                console.print(chunk, end="")

            console.print()  # New line after streaming

        except KeyboardInterrupt:
            console.print()
            console.print("\n[bold yellow]Chat interrupted by user[/bold yellow]")
            break
        except Exception as e:
            console.print()
            console.print(f"[bold red]❌ Error: {e}[/bold red]")
            continue
    
    # Cleanup resources
    try:
        context_manager.cleanup()
    except Exception as e:
        console.print(f"[dim]Warning: Cleanup failed: {e}[/dim]")


def main():
    """Main entry point for the chat session"""
    try:
        asyncio.run(chat_session())
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
