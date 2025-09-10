import os
import asyncio
import argparse
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.rule import Rule
from src.model.graph import ExtractedGraphSchema, GraphSchema
from src.tools import query_neo4j, get_schema_info
from src.prompts import KG_AGENT_PROMPT, DYNAMIC_KG_AGENT_PROMPT
from src.core import FunctionCallingAgent, Neo4jSchemaExtractor
from src.context.manager import ContextManager
from src.context.retriever import SchemaRetriever
from src.logger import kg_logger

load_dotenv()

console = Console()

# Global variables to be initialized based on mode
agent = None
context_manager = None
schema_retriever = None
static_schema_md = None


class SchemaLoader:
    """Utility class for loading schema information"""

    @staticmethod
    def load_graph_schema_from_md(file_path: str = "config/graph_schema.md") -> str:
        """Load graph schema content directly from markdown file

        Args:
            file_path: Path to the graph_schema.md file

        Returns:
            str: Content of the graph schema markdown file
        """
        try:
            full_path = os.path.join(os.getcwd(), file_path)
            with open(full_path, "r", encoding="utf-8") as f:
                content = f.read()
            return content
        except FileNotFoundError:
            console.print(
                f"[bold red]❌ Graph schema file not found: {file_path}[/bold red]"
            )
            console.print(
                "[yellow]Please run the node schema extraction script first to generate the file.[/yellow]"
            )
            raise
        except Exception as e:
            console.print(f"[bold red]❌ Error loading graph schema: {e}[/bold red]")
            raise


def init_static_schema():
    """Initialize static schema mode"""
    global agent, context_manager, static_schema_md

    console.print("[dim]Initializing static schema mode...[/dim]")
    console.print("[dim]Loading schema from graph_schema.md...[/dim]")

    try:
        # Load schema directly from markdown file
        static_schema_md = SchemaLoader.load_graph_schema_from_md()
        console.print("[dim]✓ Schema loaded from graph_schema.md[/dim]")
    except Exception as e:
        # Fallback to extracting from Neo4j if file doesn't exist
        console.print("[yellow]Falling back to Neo4j extraction...[/yellow]")
        console.print("[dim]Extracting schema from Neo4j...[/dim]")

        extractor = Neo4jSchemaExtractor(
            uri=os.getenv("NEO4J_URI"),
            database=os.getenv("NEO4J_DATABASE"),
            username=os.getenv("NEO4J_USER"),
            password=os.getenv("NEO4J_PASSWORD"),
        )
        schema = extractor.extract_full_schema("config/schema", format="yaml")
        schema = GraphSchema.from_extracted_schema(
            ExtractedGraphSchema.from_extraction_result(schema)
        )
        static_schema_md = schema.to_md()

    # Log the schema information
    kg_logger.log_schema_usage(static_schema_md)

    console.print("[dim]Initializing AI agent...[/dim]")
    agent = FunctionCallingAgent(
        model="qwen-max",
        tools=[query_neo4j],
        console=console,
    )

    console.print("[dim]Initializing context manager...[/dim]")
    context_manager = ContextManager(
        resources=["mapping"],
        schema=static_schema_md,
        llm_client=agent.client,
        schema_mode="static",
    )

    console.print("[bold green]✓ Static schema mode initialized![/bold green]")


def init_dynamic_schema():
    """Initialize dynamic schema mode"""
    global agent, context_manager, schema_retriever

    console.print("[dim]Initializing dynamic schema mode...[/dim]")

    console.print("[dim]Initializing AI agent...[/dim]")
    agent = FunctionCallingAgent(
        model="qwen-max",
        tools=[query_neo4j],
        console=console,
    )

    console.print("[dim]Initializing context manager...[/dim]")
    context_manager = ContextManager(
        resources=["mapping"],
        schema=None,  # No static schema in dynamic mode
        llm_client=agent.client,
        schema_mode="dynamic",
    )

    console.print("[dim]Initializing schema retriever...[/dim]")
    schema_retriever = SchemaRetriever()

    console.print("[bold green]✓ Dynamic schema mode initialized![/bold green]")


async def run(user_query: str, schema_mode: str = "static"):
    """Run a single query"""
    if schema_mode == "static":
        system_prompt = KG_AGENT_PROMPT.format(schema=static_schema_md)
    else:
        system_prompt = DYNAMIC_KG_AGENT_PROMPT

    response = ""
    async for chunk in agent.run_query_stream(
        user_query=user_query,
        system_prompt=system_prompt,
    ):
        response += chunk
        print(chunk, end="")
    print()  # New line after streaming
    return response


async def chat_session(schema_mode: str = "static"):
    """Interactive multi-turn chat session with Rich formatting

    Args:
        schema_mode: "static" for pre-loaded schema, "dynamic" for on-demand schema retrieval
    """
    # Welcome message
    console.print()
    console.rule("[bold green]🚀 Knowledge Graph Chat Assistant", style="green")
    console.print()

    schema_mode_text = (
        "📊 Static Schema" if schema_mode == "static" else "🔄 Dynamic Schema"
    )
    console.print(
        Panel(
            f"[bold cyan]Welcome to the Knowledge Graph Chat Assistant![/bold cyan]\n\n"
            f"[yellow]Mode: {schema_mode_text}[/yellow]\n\n"
            "• Ask questions about your Neo4j knowledge graph\n"
            "• Type 'quit', 'exit', or 'bye' to end the session\n"
            "• Type 'clear' to clear chat history\n"
            "• Type 'help' for more information",
            title="[bold blue]Getting Started",
            border_style="blue",
        )
    )
    console.print()

    # Initialize components based on mode
    try:
        if schema_mode == "static":
            init_static_schema()
            # Set initial system prompt with static schema
            agent.set_history(
                [
                    {
                        "role": "system",
                        "content": KG_AGENT_PROMPT.format(schema=static_schema_md),
                    }
                ]
            )
        else:
            init_dynamic_schema()
            # Set initial system prompt for dynamic mode
            agent.set_history([{"role": "system", "content": DYNAMIC_KG_AGENT_PROMPT}])

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
                if schema_mode == "static":
                    agent.set_history(
                        [
                            {
                                "role": "system",
                                "content": KG_AGENT_PROMPT.format(
                                    schema=static_schema_md
                                ),
                            }
                        ]
                    )
                else:
                    agent.set_history(
                        [
                            {
                                "role": "system",
                                "content": DYNAMIC_KG_AGENT_PROMPT,
                            }
                        ]
                    )
                console.print()
                console.print("[bold green]✓ Chat history cleared![/bold green]")
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

            # Load context before processing query
            try:
                console.print("[dim]Loading context...[/dim]")
                context_messages = await context_manager.load_context(
                    query=user_input, from_resources=["mapping"]
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

            # Stream the response
            response_text = ""
            async for chunk in agent.run_query_stream(user_query=user_input):
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
    parser = argparse.ArgumentParser(description="Knowledge Graph Chat Assistant")
    parser.add_argument(
        "--schema-mode",
        choices=["static", "dynamic"],
        default="static",
        help="Schema loading mode: 'static' for pre-loaded schema, 'dynamic' for on-demand retrieval",
    )

    args = parser.parse_args()

    try:
        asyncio.run(chat_session(schema_mode=args.schema_mode))
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
