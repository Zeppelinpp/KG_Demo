import os
import json
from neo4j import GraphDatabase
from dotenv import load_dotenv
from typing import List, Callable, Dict, Any, Union
from openai import AsyncOpenAI
from tools import tools_to_openai_schema
from rich.console import Console
from rich.panel import Panel
from pathlib import Path
import datetime

load_dotenv()


class FunctionCallingAgent:
    def __init__(self, model: str, tools: List[Callable]):
        self.model = model
        self.tool_functions = {
            tool.__name__: tool for tool in tools
        }  # Map tool names to functions

        # Use updated tools_to_openai_schema function that accepts callable list directly
        self.tools = tools_to_openai_schema(tools)
        self.client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL")
        )
        self.max_iterations = 10  # Prevent infinite loops

    async def _handle_tool_call(self, tool_call: Dict[str, Any]) -> str:
        """Execute a tool call and return the result"""
        try:
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])

            # Get the actual function
            if function_name not in self.tool_functions:
                return f"Error: Tool '{function_name}' not found"

            tool_function = self.tool_functions[function_name]

            # Execute the function
            if hasattr(tool_function, "__call__"):
                result = tool_function(**function_args)
                # Handle async functions if needed
                if hasattr(result, "__await__"):
                    result = await result
                return str(result)
            else:
                return f"Error: '{function_name}' is not callable"

        except Exception as e:
            return f"Error executing tool call: {str(e)}"

    async def run(self, messages: List[Dict[str, Any]]) -> str:
        """Run the agent with tool calling until a final answer is reached"""
        current_messages = messages.copy()
        iteration = 0

        while iteration < self.max_iterations:
            try:
                # Make API call to OpenAI
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=current_messages,
                    tools=self.tools,
                    tool_choice="auto",
                )

                assistant_message = response.choices[0].message

                # Add assistant message to conversation
                current_messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.content,
                        "tool_calls": assistant_message.tool_calls,
                    }
                )

                # Check if there are tool calls to execute
                if assistant_message.tool_calls:
                    # Execute each tool call
                    for tool_call in assistant_message.tool_calls:
                        tool_result = await self._handle_tool_call(
                            tool_call.model_dump()
                        )

                        # Add tool result to conversation
                        current_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_result,
                            }
                        )

                    # Continue the loop to let the model process tool results
                    iteration += 1
                    continue

                else:
                    # No tool calls, return the final response
                    return assistant_message.content or "No response generated"

            except Exception as e:
                return f"Error in agent execution: {str(e)}"

        return "Maximum iterations reached without final answer"


class Neo4jSchemaExtractor:
    """Neo4j Schema Extractor"""

    def __init__(
        self,
        uri: str,
        database: str,
        username: str = "neo4j",
        password: str = "password",
        console: Console = None,
    ):
        self.uri = uri
        self.database = database
        self.username = username
        self.password = password
        self.console = console or Console()
        self.driver = None

    def connect(self) -> bool:
        """Connect to Neo4j database"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.username, self.password)
            )

            # Test connection
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")

            self.console.print(
                Panel(
                    f"[green]✓[/green] Successfully connected to Neo4j database!\n"
                    f"[bold cyan]Connection URI:[/bold cyan] {self.uri}\n"
                    f"[bold cyan]Database:[/bold cyan] {self.database}",
                    title="[bold green]Database Connection",
                    border_style="green",
                )
            )
            return True

        except Exception as e:
            self.console.print(
                Panel(
                    f"[bold red]❌ Failed to connect to Neo4j database![/bold red]\n"
                    f"[yellow]Error message:[/yellow] {str(e)}",
                    title="[bold red]Connection Failed",
                    border_style="red",
                )
            )
            return False

    def close(self):
        """Close database connection"""
        if self.driver:
            self.driver.close()

    def extract_node_labels_and_properties(self) -> Dict[str, Dict]:
        """Extract node labels and properties"""
        node_schema = {}

        try:
            with self.driver.session(database=self.database) as session:
                # Get all node labels
                result = session.run("CALL db.labels()")
                labels = [record["label"] for record in result]

                for label in labels:
                    # Get properties for this label
                    query = f"""
                    MATCH (n:{label})
                    WITH keys(n) as props
                    UNWIND props as prop
                    RETURN DISTINCT prop, 
                           apoc.meta.type(prop) as type,
                           COUNT(*) as frequency
                    ORDER BY frequency DESC
                    """

                    # Use basic query if APOC plugin is not available
                    basic_query = f"""
                    MATCH (n:{label})
                    WITH keys(n) as props
                    UNWIND props as prop
                    RETURN DISTINCT prop, COUNT(*) as frequency
                    ORDER BY frequency DESC
                    """

                    try:
                        result = session.run(query)
                        properties = []
                        for record in result:
                            properties.append(
                                {
                                    "name": record["prop"],
                                    "type": record.get("type", "unknown"),
                                    "frequency": record["frequency"],
                                }
                            )
                    except:
                        # fallback to basic query
                        result = session.run(basic_query)
                        properties = []
                        for record in result:
                            properties.append(
                                {
                                    "name": record["prop"],
                                    "type": "unknown",
                                    "frequency": record["frequency"],
                                }
                            )

                    # Get node count
                    count_result = session.run(
                        f"MATCH (n:{label}) RETURN COUNT(n) as count"
                    )
                    node_count = count_result.single()["count"]

                    # Get sample data
                    sample_result = session.run(f"MATCH (n:{label}) RETURN n LIMIT 3")
                    samples = []
                    for record in sample_result:
                        node = record["n"]
                        sample = dict(node)
                        # Convert values to strings for JSON serialization
                        for key, value in sample.items():
                            if (
                                isinstance(value, (int, float, str, bool))
                                or value is None
                            ):
                                continue
                            else:
                                sample[key] = str(value)
                        samples.append(sample)

                    node_schema[label] = {
                        "count": node_count,
                        "properties": properties,
                        "samples": samples,
                    }

        except Exception as e:
            self.console.print(f"[bold red]❌ Failed to extract node schema: {e}[/bold red]")

        return node_schema

    def extract_relationship_types_and_properties(self) -> Dict[str, Dict]:
        """Extract relationship types and properties"""
        relationship_schema = {}

        try:
            with self.driver.session(database=self.database) as session:
                # Get all relationship types
                result = session.run("CALL db.relationshipTypes()")
                rel_types = [record["relationshipType"] for record in result]

                for rel_type in rel_types:
                    # Get relationship properties
                    query = f"""
                    MATCH ()-[r:{rel_type}]-()
                    WITH keys(r) as props
                    UNWIND props as prop
                    RETURN DISTINCT prop, COUNT(*) as frequency
                    ORDER BY frequency DESC
                    """

                    result = session.run(query)
                    properties = []
                    for record in result:
                        properties.append(
                            {"name": record["prop"], "frequency": record["frequency"]}
                        )

                    # Get relationship count
                    count_result = session.run(
                        f"MATCH ()-[r:{rel_type}]-() RETURN COUNT(r) as count"
                    )
                    rel_count = count_result.single()["count"]

                    # Get source and target node types for relationships
                    pattern_result = session.run(f"""
                    MATCH (source)-[r:{rel_type}]->(target)
                    RETURN DISTINCT labels(source) as source_labels, 
                           labels(target) as target_labels,
                           COUNT(*) as frequency
                    ORDER BY frequency DESC
                    LIMIT 10
                    """)

                    patterns = []
                    for record in pattern_result:
                        patterns.append(
                            {
                                "source_labels": record["source_labels"],
                                "target_labels": record["target_labels"],
                                "frequency": record["frequency"],
                            }
                        )

                    # Get sample relationships
                    sample_result = session.run(f"""
                    MATCH (source)-[r:{rel_type}]->(target)
                    RETURN labels(source) as source_labels, 
                           labels(target) as target_labels,
                           r as relationship
                    LIMIT 3
                    """)

                    samples = []
                    for record in sample_result:
                        rel_data = dict(record["relationship"])
                        # Convert values to strings for JSON serialization
                        for key, value in rel_data.items():
                            if (
                                isinstance(value, (int, float, str, bool))
                                or value is None
                            ):
                                continue
                            else:
                                rel_data[key] = str(value)

                        samples.append(
                            {
                                "source_labels": record["source_labels"],
                                "target_labels": record["target_labels"],
                                "properties": rel_data,
                            }
                        )

                    relationship_schema[rel_type] = {
                        "count": rel_count,
                        "properties": properties,
                        "patterns": patterns,
                        "samples": samples,
                    }

        except Exception as e:
            self.console.print(f"[bold red]❌ Failed to extract relationship schema: {e}[/bold red]")

        return relationship_schema

    def extract_database_constraints_and_indexes(self) -> Dict[str, List]:
        """Extract database constraints and indexes"""
        constraints_indexes = {"constraints": [], "indexes": []}

        try:
            with self.driver.session(database=self.database) as session:
                # Get constraints
                try:
                    result = session.run("SHOW CONSTRAINTS")
                    for record in result:
                        constraints_indexes["constraints"].append(dict(record))
                except:
                    # Older Neo4j version
                    try:
                        result = session.run("CALL db.constraints()")
                        for record in result:
                            constraints_indexes["constraints"].append(dict(record))
                    except:
                        pass

                # Get indexes
                try:
                    result = session.run("SHOW INDEXES")
                    for record in result:
                        constraints_indexes["indexes"].append(dict(record))
                except:
                    # Older Neo4j version
                    try:
                        result = session.run("CALL db.indexes()")
                        for record in result:
                            constraints_indexes["indexes"].append(dict(record))
                    except:
                        pass

        except Exception as e:
            self.console.print(
f"[bold yellow]⚠️ Failed to extract constraints and indexes: {e}[/bold yellow]"
            )

        return constraints_indexes

    def extract_full_schema(self, output_file: str = None) -> Dict:
        """Extract complete database schema"""
        self.console.print()
        self.console.rule("[bold green]🔍 Neo4j Schema Extraction", style="green")

        if not self.connect():
            return {}

        try:
            self.console.print("[bold cyan]Extracting node schema...[/bold cyan]")
            nodes_schema = self.extract_node_labels_and_properties()

            self.console.print("[bold cyan]Extracting relationship schema...[/bold cyan]")
            relationships_schema = self.extract_relationship_types_and_properties()

            self.console.print("[bold cyan]Extracting constraints and indexes...[/bold cyan]")
            constraints_indexes = self.extract_database_constraints_and_indexes()

            # Combine complete schema
            full_schema = {
                "database_info": {
                    "uri": self.uri,
                    "database": self.database,
                    "extraction_time": str(__import__("datetime").datetime.now()),
                },
                "nodes": nodes_schema,
                "relationships": relationships_schema,
                "constraints": constraints_indexes["constraints"],
                "indexes": constraints_indexes["indexes"],
            }

            # Save to file
            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(exist_ok=True)

                # Save schema in JSON format
                json_file = output_path.with_suffix(".json")
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(full_schema, f, ensure_ascii=False, indent=2)

                self.console.print(
                    Panel(
                        f"[green]✓[/green] Schema extraction completed!\n"
                        f"[bold cyan]JSON file:[/bold cyan] {json_file}\n"
                        f"[bold cyan]Node types:[/bold cyan] {len(nodes_schema)}\n"
                        f"[bold cyan]Relationship types:[/bold cyan] {len(relationships_schema)}",
                        title="[bold green]Extraction Complete",
                        border_style="green",
                    )
                )

            return full_schema

        except Exception as e:
            self.console.print(f"[bold red]❌ Schema extraction failed: {e}[/bold red]")
            return {}

        finally:
            self.close()
