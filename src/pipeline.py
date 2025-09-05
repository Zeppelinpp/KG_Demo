import os
import asyncio
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.markdown import Markdown
from rich.rule import Rule
from src.model.graph import GraphSchema
from src.tools import query_neo4j
from src.prompts import KG_AGENT_PROMPT
from src.core import FunctionCallingAgent, Neo4jSchemaExtractor

load_dotenv()

console = Console()

console.print("[dim]Initializing connection to Neo4j...[/dim]")
extractor = Neo4jSchemaExtractor(
    uri=os.getenv("NEO4J_URI"),
    database=os.getenv("NEO4J_DATABASE"),
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),
)
schema = extractor.extract_full_schema(return_structured=True)
schema_md = schema.to_md()

console.print("[dim]Initializing AI agent...[/dim]")
agent = FunctionCallingAgent(
    model="qwen-max-latest",
    tools=[query_neo4j],
    console=console,
)


async def run(user_query: str):
    """Run a single query"""
    response = ""
    async for chunk in agent.run_query_stream(
        user_query=user_query,
        system_prompt=KG_AGENT_PROMPT.format(schema=schema_md),
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
        # Set initial system prompt
        agent.set_history(
            [{"role": "system", "content": KG_AGENT_PROMPT.format(schema=schema)}]
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
                            "content": KG_AGENT_PROMPT.format(schema=schema),
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


def main():
    """Main entry point for the chat session"""
    try:
        asyncio.run(chat_session())
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
