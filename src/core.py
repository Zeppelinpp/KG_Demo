import os
import json
import datetime
import yaml
from neo4j import GraphDatabase
from neo4j.time import DateTime, Date, Time, Duration
from dotenv import load_dotenv
from typing import List, Callable, Dict, Any, AsyncGenerator, Optional, Union
from openai import AsyncOpenAI
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from pathlib import Path
from pydantic import ValidationError
from src.tools import get_node_properties, get_relation_count, get_relation_patterns, get_relation_properties, get_sample_relationships
from src.utils import tools_to_openai_schema
from src.model.graph import (
    ExtractedGraphSchema, 
    GraphSchema, 
    NodesInfo, 
    RelationsInfo, 
    DatabaseInfo,
    IndexInfo,
    ConstraintInfo
)

load_dotenv()


def serialize_neo4j_value(value):
    """Convert Neo4j values to JSON-serializable format"""
    if isinstance(value, (DateTime, Date, Time)):
        return str(value)
    elif isinstance(value, Duration):
        return str(value)
    elif isinstance(value, (int, float, str, bool)) or value is None:
        return value
    elif isinstance(value, list):
        return [serialize_neo4j_value(item) for item in value]
    elif isinstance(value, dict):
        return {k: serialize_neo4j_value(v) for k, v in value.items()}
    else:
        # For any other type, convert to string
        return str(value)


def convert_schema_to_yaml_format(extracted_schema: Dict) -> Dict:
    """Convert extracted Neo4j schema to YAML format similar to schema.yaml"""
    yaml_schema = {
        "schema": {
            "nodeLabels": [],
            "relationships": [],
            "nodeProperties": {},
            "indexes": []
        }
    }
    
    # Extract node labels
    if "nodes" in extracted_schema:
        yaml_schema["schema"]["nodeLabels"] = list(extracted_schema["nodes"].keys())
        
        # Extract node properties
        for node_label, node_info in extracted_schema["nodes"].items():
            properties = []
            if "properties" in node_info:
                for prop in node_info["properties"]:
                    prop_name = prop
                    # Try to infer type from samples
                    prop_type = infer_property_type(node_info.get("samples", []), prop_name)
                    # Create as dict to avoid YAML quoting issues
                    prop_entry = {prop_name: prop_type}
                    properties.append(prop_entry)
            yaml_schema["schema"]["nodeProperties"][node_label] = properties
    
    # Extract relationships
    if "relationships" in extracted_schema:
        for rel_type, rel_info in extracted_schema["relationships"].items():
            relationship = {"type": rel_type}
            
            # Determine from and to node labels from patterns
            if "patterns" in rel_info and rel_info["patterns"]:
                pattern = rel_info["patterns"][0]  # Use most frequent pattern
                if pattern["source_labels"]:
                    relationship["from"] = pattern["source_labels"][0]
                if pattern["target_labels"]:
                    relationship["to"] = pattern["target_labels"][0]
            
            # Extract relationship properties
            if "properties" in rel_info and rel_info["properties"]:
                rel_properties = {}
                for prop in rel_info["properties"]:
                    prop_name = prop["name"]
                    # Try to infer type from samples
                    prop_type = infer_property_type(rel_info.get("samples", []), prop_name, is_relationship=True)
                    rel_properties[prop_name] = prop_type
                if rel_properties:
                    relationship["properties"] = rel_properties
            
            yaml_schema["schema"]["relationships"].append(relationship)
    
    # Extract indexes and constraints
    if "indexes" in extracted_schema:
        for index in extracted_schema["indexes"]:
            # Skip system indexes (LOOKUP type)
            if index.get("type") == "LOOKUP":
                continue
                
            # Format index description
            if index.get("labelsOrTypes") and index.get("properties"):
                labels = index["labelsOrTypes"]
                properties = index["properties"]
                if labels and properties:
                    label = labels[0]
                    prop = properties[0]
                    yaml_schema["schema"]["indexes"].append(f"INDEX ON :{label}({prop})")
    
    if "constraints" in extracted_schema:
        for constraint in extracted_schema["constraints"]:
            # Format constraint description
            constraint_desc = format_constraint(constraint)
            if constraint_desc:
                yaml_schema["schema"]["indexes"].append(constraint_desc)
    
    return yaml_schema


def infer_property_type(samples: List[Dict], prop_name: str, is_relationship: bool = False) -> str:
    """Infer property type from sample data"""
    if not samples:
        return "string"
    
    for sample in samples:
        if is_relationship:
            properties = sample.get("properties", {})
        else:
            properties = sample
            
        if prop_name in properties:
            value = properties[prop_name]
            if isinstance(value, int):
                return "integer"
            elif isinstance(value, float):
                return "float"
            elif isinstance(value, bool):
                return "boolean"
            elif isinstance(value, str):
                # Check if it looks like a datetime
                if any(keyword in value.lower() for keyword in ["date", "time", "t"]) and len(value) > 10:
                    return "datetime"
                return "string"
    
    return "string"


def format_constraint(constraint: Dict) -> str:
    """Format constraint information into readable string"""
    try:
        # This is a simplified formatter - actual format depends on Neo4j version
        constraint_type = constraint["type"]
        labelsOrTypes = constraint["labelsOrTypes"]
        properties = constraint["properties"]
        if labelsOrTypes and properties:
            label = labelsOrTypes[0]
            prop = properties[0]
            return f"CONSTRAINT '{constraint_type}' ON :{label}(PROPERTY {prop})"
        else:
            return ""
    except:
        return ""


class FunctionCallingAgent:
    def __init__(self, model: str, tools: List[Callable], console: Console = None):
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
        self.chat_history = []  # Store conversation history
        self.console = console or Console()

    async def _handle_tool_call(self, tool_call: Dict[str, Any]) -> str:
        """Execute a tool call and return the result"""
        try:
            function_name = tool_call["function"]["name"]
            function_args = json.loads(tool_call["function"]["arguments"])

            # Display tool call information
            self.console.print()
            self.console.print(
                Panel(
                    f"[bold cyan]🔧 Tool Call: {function_name}[/bold cyan]",
                    border_style="cyan",
                )
            )

            # Special handling for Neo4j query tool to display Cypher
            if function_name == "query_neo4j" and "cypher_query" in function_args:
                cypher_query = function_args["cypher_query"]
                self.console.print()
                self.console.print(
                    Panel(
                        Syntax(
                            cypher_query, "cypher", theme="monokai", line_numbers=True
                        ),
                        title="[bold yellow]🔍 Executing Cypher Query",
                        border_style="yellow",
                    )
                )

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

                # Display result summary
                self.console.print()
                if isinstance(result, list):
                    self.console.print(
                        f"[dim green]✓ Query returned {len(result)} records[/dim green]"
                    )
                else:
                    self.console.print(
                        f"[dim green]✓ Tool execution completed[/dim green]"
                    )

                return str(result)
            else:
                return f"Error: '{function_name}' is not callable"

        except Exception as e:
            self.console.print(f"[bold red]❌ Tool execution failed: {e}[/bold red]")
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

    async def run_stream(
        self, messages: List[Dict[str, Any]]
    ) -> AsyncGenerator[str, None]:
        """Run the agent with streaming output and tool calling"""
        current_messages = messages.copy()
        iteration = 0

        while iteration < self.max_iterations:
            try:
                # Make API call to OpenAI with streaming
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=current_messages,
                    tools=self.tools,
                    tool_choice="auto",
                    stream=True,
                )

                assistant_content = ""
                tool_calls = []
                current_tool_call = None

                async for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta:
                        delta = chunk.choices[0].delta

                        # Handle content streaming
                        if delta.content:
                            assistant_content += delta.content
                            yield delta.content

                        # Handle tool calls
                        if delta.tool_calls:
                            for tool_call_delta in delta.tool_calls:
                                # Initialize new tool call
                                if (
                                    current_tool_call is None
                                    or tool_call_delta.index
                                    != current_tool_call.get("index")
                                ):
                                    if current_tool_call is not None:
                                        tool_calls.append(current_tool_call)
                                    current_tool_call = {
                                        "index": tool_call_delta.index,
                                        "id": tool_call_delta.id or "",
                                        "type": tool_call_delta.type or "function",
                                        "function": {
                                            "name": tool_call_delta.function.name or "",
                                            "arguments": tool_call_delta.function.arguments
                                            or "",
                                        },
                                    }
                                else:
                                    # Append to existing tool call
                                    if tool_call_delta.function:
                                        if tool_call_delta.function.name:
                                            current_tool_call["function"]["name"] += (
                                                tool_call_delta.function.name
                                            )
                                        if tool_call_delta.function.arguments:
                                            current_tool_call["function"][
                                                "arguments"
                                            ] += tool_call_delta.function.arguments

                # Add the last tool call if exists
                if current_tool_call is not None:
                    tool_calls.append(current_tool_call)

                # Add assistant message to conversation
                assistant_message = {
                    "role": "assistant",
                    "content": assistant_content,
                    "tool_calls": tool_calls if tool_calls else None,
                }
                current_messages.append(assistant_message)

                # Check if there are tool calls to execute
                if tool_calls:
                    # Execute each tool call
                    for tool_call in tool_calls:
                        tool_result = await self._handle_tool_call(tool_call)

                        # Add tool result to conversation
                        current_messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": tool_result,
                            }
                        )

                    # Continue the loop to let the model process tool results
                    iteration += 1
                    continue

                else:
                    # No tool calls, we're done
                    return

            except Exception as e:
                yield f"\n\nError in agent execution: {str(e)}"
                return

        yield f"\n\nMaximum iterations reached without final answer"

    async def run_query(self, user_query: str, system_prompt: str = None) -> str:
        """
        Run a single user query with automatic chat history management.

        Args:
            user_query (str): The user's query string
            system_prompt (str, optional): System prompt to set context. If provided,
                                         it will replace any existing system message.

        Returns:
            str: The agent's response
        """
        # Add or update system prompt if provided
        if system_prompt:
            # Remove existing system message if any
            self.chat_history = [
                msg for msg in self.chat_history if msg["role"] != "system"
            ]
            # Add new system message at the beginning
            self.chat_history.insert(0, {"role": "system", "content": system_prompt})

        # Add user query to chat history
        self.chat_history.append({"role": "user", "content": user_query})

        # Run the agent with current chat history
        response = await self.run(self.chat_history)

        # Add assistant response to chat history
        self.chat_history.append({"role": "assistant", "content": response})

        return response

    async def run_query_stream(
        self, user_query: str, system_prompt: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Run a single user query with streaming output and automatic chat history management.

        Args:
            user_query (str): The user's query string
            system_prompt (str, optional): System prompt to set context. If provided,
                                         it will replace any existing system message.

        Yields:
            str: Streaming response chunks
        """
        # Add or update system prompt if provided
        if system_prompt:
            # Remove existing system message if any
            self.chat_history = [
                msg for msg in self.chat_history if msg["role"] != "system"
            ]
            # Add new system message at the beginning
            self.chat_history.insert(0, {"role": "system", "content": system_prompt})

        # Add user query to chat history
        self.chat_history.append({"role": "user", "content": user_query})

        # Collect the full response for history
        full_response = ""

        # Stream the agent response
        async for chunk in self.run_stream(self.chat_history):
            full_response += chunk
            yield chunk

        # Add assistant response to chat history
        self.chat_history.append({"role": "assistant", "content": full_response})

    def clear_history(self):
        """Clear the chat history"""
        self.chat_history = []

    def get_history(self) -> List[Dict[str, Any]]:
        """Get the current chat history"""
        return self.chat_history.copy()

    def set_history(self, history: List[Dict[str, Any]]):
        """Set the chat history"""
        self.chat_history = history.copy()


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

    def validate_extraction_result(self, extraction_result: Dict) -> tuple[bool, Optional[ExtractedGraphSchema], Optional[str]]:
        """
        Validate extraction result using Pydantic models
        
        Args:
            extraction_result: Raw extraction result dictionary
            
        Returns:
            tuple: (is_valid, validated_schema, error_message)
        """
        try:
            # Validate the complete extraction result
            validated_schema = ExtractedGraphSchema.from_extraction_result(extraction_result)
            
            # Additional validation - check that nodes and relationships have expected structure
            validation_errors = []
            
            # Validate node structure
            for node_label, node_data in validated_schema.nodes.items():
                try:
                    NodesInfo.from_extracted_data(node_label, node_data)
                except ValidationError as e:
                    validation_errors.append(f"Node '{node_label}' validation error: {e}")
                except Exception as e:
                    validation_errors.append(f"Node '{node_label}' unexpected error: {e}")
            
            # Validate relationship structure
            for rel_type, rel_data in validated_schema.relationships.items():
                try:
                    RelationsInfo.from_extracted_data(rel_type, rel_data)
                except ValidationError as e:
                    validation_errors.append(f"Relationship '{rel_type}' validation error: {e}")
                except Exception as e:
                    validation_errors.append(f"Relationship '{rel_type}' unexpected error: {e}")
            
            # Validate indexes and constraints
            try:
                for index_data in validated_schema.indexes:
                    IndexInfo(**index_data)
            except ValidationError as e:
                validation_errors.append(f"Index validation error: {e}")
            except Exception as e:
                validation_errors.append(f"Index unexpected error: {e}")
                
            try:
                for constraint_data in validated_schema.constraints:
                    ConstraintInfo(**constraint_data)
            except ValidationError as e:
                validation_errors.append(f"Constraint validation error: {e}")
            except Exception as e:
                validation_errors.append(f"Constraint unexpected error: {e}")
            
            if validation_errors:
                error_msg = "; ".join(validation_errors)
                self.console.print(f"[yellow]⚠️ Validation warnings: {error_msg}[/yellow]")
                return True, validated_schema, error_msg  # Still valid but with warnings
            
            self.console.print("[green]✓ Schema validation successful[/green]")
            return True, validated_schema, None
            
        except ValidationError as e:
            error_msg = f"Schema validation failed: {e}"
            self.console.print(f"[bold red]❌ {error_msg}[/bold red]")
            return False, None, error_msg
        except Exception as e:
            error_msg = f"Unexpected validation error: {e}"
            self.console.print(f"[bold red]❌ {error_msg}[/bold red]")
            return False, None, error_msg

    def extract_node_labels_and_properties(self) -> Dict[str, Dict]:
        """Extract node labels and properties"""
        node_schema = {}

        try:
            with self.driver.session(database=self.database) as session:
                # Get all node labels
                result = session.run("CALL db.labels()").data()
                labels = [record["label"] for record in result]

                for label in labels:
                    # Get properties for this label
                    try:
                        properties = get_node_properties(label)
                    except Exception as e:
                        self.console.print(
                            f"[bold red]❌ Failed to get node properties: {e}[/bold red]"
                        )

                    # Get node count
                    count_result = session.run(
                        f"MATCH (n:`{label}`) RETURN COUNT(n) as count"
                    )
                    node_count = count_result.single()["count"]

                    # Get sample data
                    sample_result = session.run(f"MATCH (n:`{label}`) RETURN n LIMIT 3")
                    samples = []
                    for record in sample_result:
                        node = record["n"]
                        sample = dict(node)
                        # Convert values using the serialization function
                        sample = {
                            k: serialize_neo4j_value(v) for k, v in sample.items()
                        }
                        samples.append(sample)

                    node_schema[label] = {
                        "count": node_count,
                        "properties": properties,
                        "samples": samples,
                    }

        except Exception as e:
            self.console.print(
                f"[bold red]❌ Failed to extract node schema: {e}[/bold red]"
            )

        return node_schema

    def extract_relationship_types_and_properties(self) -> Dict[str, Dict]:
        """Extract relationship types and properties"""
        relationship_schema = {}

        try:
            with self.driver.session(database=self.database) as session:
                # Get all relationship types
                result = session.run("CALL db.relationshipTypes()").data()
                rel_types = [record["relationshipType"] for record in result]

                for rel_type in rel_types:
                    # Get relationship properties
                    properties = get_relation_properties(rel_type)

                    # Get relationship count
                    count_result = get_relation_count(rel_type)
                    rel_count = count_result

                    # Get source and target node types for relationships
                    pattern_result = get_relation_patterns(rel_type)

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
                    sample_result = get_sample_relationships(rel_type)
                    samples = []
                    for record in sample_result:
                        rel_data = dict(record["relationship"])
                        # Convert values using the serialization function
                        rel_data = {
                            k: serialize_neo4j_value(v) for k, v in rel_data.items()
                        }

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
            self.console.print(
                f"[bold red]❌ Failed to extract relationship schema: {e}[/bold red]"
            )

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
                        constraint_data = dict(record)
                        # Serialize constraint data
                        constraint_data = {
                            k: serialize_neo4j_value(v)
                            for k, v in constraint_data.items()
                        }
                        constraints_indexes["constraints"].append(constraint_data)
                except:
                    # Older Neo4j version
                    try:
                        result = session.run("CALL db.constraints()")
                        for record in result:
                            constraint_data = dict(record)
                            constraint_data = {
                                k: serialize_neo4j_value(v)
                                for k, v in constraint_data.items()
                            }
                            constraints_indexes["constraints"].append(constraint_data)
                    except:
                        pass

                # Get indexes
                try:
                    result = session.run("SHOW INDEXES")
                    for record in result:
                        index_data = dict(record)
                        # Serialize index data
                        index_data = {
                            k: serialize_neo4j_value(v) for k, v in index_data.items()
                        }
                        constraints_indexes["indexes"].append(index_data)
                except:
                    # Older Neo4j version
                    try:
                        result = session.run("CALL db.indexes()")
                        for record in result:
                            index_data = dict(record)
                            index_data = {
                                k: serialize_neo4j_value(v)
                                for k, v in index_data.items()
                            }
                            constraints_indexes["indexes"].append(index_data)
                    except:
                        pass

        except Exception as e:
            self.console.print(
                f"[bold yellow]⚠️ Failed to extract constraints and indexes: {e}[/bold yellow]"
            )

        return constraints_indexes

    def extract_full_schema(
        self, 
        output_file: str = None, 
        format: str = "json", 
        return_structured: bool = False,
        validate: bool = True
    ) -> Union[Dict, ExtractedGraphSchema, GraphSchema]:
        """
        Extract complete database schema
        
        Args:
            output_file: Path to save the schema file
            format: Output format ("json" or "yaml")
            return_structured: If True, return structured Pydantic models instead of raw dict
            validate: If True, validate the extraction result using Pydantic models
            
        Returns:
            Dict: Raw extraction result (default)
            ExtractedGraphSchema: Validated raw schema (if return_structured=True and validate=True)
            GraphSchema: Fully structured schema (if return_structured=True and validate=True)
        """
        self.console.print()
        self.console.rule("[bold green]🔍 Neo4j Schema Extraction", style="green")

        if not self.connect():
            return {} if not return_structured else None

        try:
            self.console.print("[bold cyan]Extracting node schema...[/bold cyan]")
            nodes_schema = self.extract_node_labels_and_properties()

            self.console.print(
                "[bold cyan]Extracting relationship schema...[/bold cyan]"
            )
            relationships_schema = self.extract_relationship_types_and_properties()

            self.console.print(
                "[bold cyan]Extracting constraints and indexes...[/bold cyan]"
            )
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

            # Validate extraction result if requested
            validated_schema = None
            structured_schema = None
            
            if validate:
                self.console.print("[bold cyan]Validating extraction result...[/bold cyan]")
                is_valid, validated_schema, error_msg = self.validate_extraction_result(full_schema)
                
                if not is_valid:
                    self.console.print(f"[bold red]❌ Schema validation failed: {error_msg}[/bold red]")
                    if return_structured:
                        return None
                elif validated_schema and return_structured:
                    # Convert to fully structured schema if requested
                    try:
                        structured_schema = validated_schema.to_structured_schema()
                        self.console.print("[green]✓ Schema converted to structured format[/green]")
                    except Exception as e:
                        self.console.print(f"[yellow]⚠️ Failed to convert to structured format: {e}[/yellow]")
                        # Fall back to validated raw schema
                        structured_schema = validated_schema

            # Save to file
            if output_file:
                output_path = Path(output_file)
                output_path.parent.mkdir(exist_ok=True)

                if format.lower() == "yaml":
                    # Convert to YAML format and save
                    yaml_schema = convert_schema_to_yaml_format(full_schema)
                    yaml_file = output_path.with_suffix(".yaml")
                    with open(yaml_file, "w", encoding="utf-8") as f:
                        yaml.dump(yaml_schema, f, default_flow_style=False, allow_unicode=True, indent=2, default_style=None)

                    self.console.print(
                        Panel(
                            f"[green]✓[/green] Schema extraction completed!\n"
                            f"[bold cyan]YAML file:[/bold cyan] {yaml_file}\n"
                            f"[bold cyan]Node types:[/bold cyan] {len(nodes_schema)}\n"
                            f"[bold cyan]Relationship types:[/bold cyan] {len(relationships_schema)}\n"
                            f"[bold cyan]Validation:[/bold cyan] {'✓ Passed' if validate and validated_schema else 'Skipped'}",
                            title="[bold green]Extraction Complete",
                            border_style="green",
                        )
                    )
                else:
                    # Save schema in JSON format (default)
                    json_file = output_path.with_suffix(".json")
                    with open(json_file, "w", encoding="utf-8") as f:
                        json.dump(full_schema, f, ensure_ascii=False, indent=2)

                    self.console.print(
                        Panel(
                            f"[green]✓[/green] Schema extraction completed!\n"
                            f"[bold cyan]JSON file:[/bold cyan] {json_file}\n"
                            f"[bold cyan]Node types:[/bold cyan] {len(nodes_schema)}\n"
                            f"[bold cyan]Relationship types:[/bold cyan] {len(relationships_schema)}\n"
                            f"[bold cyan]Validation:[/bold cyan] {'✓ Passed' if validate and validated_schema else 'Skipped'}",
                            title="[bold green]Extraction Complete",
                            border_style="green",
                        )
                    )

            # Return appropriate format based on parameters
            if return_structured and structured_schema:
                return structured_schema
            elif return_structured and validated_schema:
                return validated_schema
            else:
                return full_schema

        except Exception as e:
            error_msg = f"Schema extraction failed: {e}"
            self.console.print(f"[bold red]❌ {error_msg}[/bold red]")
            
            # Return appropriate error value based on return type
            if return_structured:
                return None
            else:
                return {}

        finally:
            self.close()

    def extract_structured_schema(self, output_file: str = None, format: str = "json") -> Optional[GraphSchema]:
        """
        Convenience method to extract and return a fully structured GraphSchema
        
        Args:
            output_file: Path to save the schema file
            format: Output format ("json" or "yaml")
            
        Returns:
            GraphSchema: Fully structured schema with Pydantic models, or None if extraction failed
        """
        result = self.extract_full_schema(
            output_file=output_file,
            format=format,
            return_structured=True,
            validate=True
        )
        
        if isinstance(result, GraphSchema):
            return result
        else:
            self.console.print("[bold red]❌ Failed to extract structured schema[/bold red]")
            return None
