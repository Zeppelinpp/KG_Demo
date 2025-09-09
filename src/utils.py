import os
import re
import inspect
from neo4j import GraphDatabase
from dotenv import load_dotenv
from typing import List, Dict, Any, Callable, Union, Optional

load_dotenv()


def tools_to_openai_schema(tools: List[Callable]) -> List[Dict[str, Any]]:
    """
    Convert callable functions to OpenAI function call format

    Args:
        tools: List of callable functions to convert to OpenAI schema

    Returns:
        Tool list in OpenAI function call format
    """
    openai_functions = []

    for tool in tools:
        if not callable(tool):
            continue

        # Get function signature
        sig = inspect.signature(tool)

        # Get function name and docstring
        func_name = tool.__name__
        func_doc = inspect.getdoc(tool) or f"Function {func_name}"

        # Build parameters schema
        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            # Skip *args and **kwargs
            if param.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue

            # Determine parameter type from annotation
            param_type = "string"  # default type
            param_description = f"Parameter {param_name}"

            if param.annotation != inspect.Parameter.empty:
                annotation = param.annotation

                # Handle typing annotations
                if hasattr(annotation, "__origin__"):
                    origin = annotation.__origin__
                    if origin is Union:
                        # Handle Optional types (Union[T, None])
                        args = annotation.__args__
                        if len(args) == 2 and type(None) in args:
                            # This is Optional[T]
                            non_none_type = next(
                                arg for arg in args if arg is not type(None)
                            )
                            param_type = _get_json_type(non_none_type)
                        else:
                            param_type = "string"  # fallback for complex unions
                    elif origin is list:
                        param_type = "array"
                    elif origin is dict:
                        param_type = "object"
                    else:
                        param_type = _get_json_type(annotation)
                else:
                    param_type = _get_json_type(annotation)

            properties[param_name] = {
                "type": param_type,
                "description": param_description,
            }

            # Add to required if no default value
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        function_def = {
            "type": "function",
            "function": {
                "name": func_name,
                "description": func_doc,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
        openai_functions.append(function_def)

    return openai_functions


def _get_json_type(python_type) -> str:
    """
    Convert Python type to JSON schema type

    Args:
        python_type: Python type annotation

    Returns:
        JSON schema type string
    """
    type_mapping = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }

    return type_mapping.get(python_type, "string")


def execute_cypher(cypher: str):
    """Execute Cypher query and return results"""
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )
    with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
        try:
            result = session.run(cypher).data()
        except Exception as e:
            return f"Failed to execute cypher: {str(e)}"

        return result


def get_schema():
    """
    Get schema of Knowledge Graph
    """
    # Import here to avoid circular import
    from src.core import Neo4jSchemaExtractor

    extractor = Neo4jSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD"),
    )
    schema = extractor.extract_full_schema()
    return schema


def get_relation_properties(relation_type: str):
    """Get properties of a specific relation type"""
    cypher = """
    MATCH (n)-[r:`{relation_type}`]-(m)
    UNWIND keys(r) AS prop
    RETURN DISTINCT prop
    """
    result = execute_cypher(cypher.format(relation_type=relation_type))

    if result:
        return [prop["prop"] for prop in result]
    else:
        return []


def get_relation_count(relation_type: str):
    """Get count of relationships for a specific relation type"""
    cypher = """
    MATCH ()-[r:`{relation_type}`]-()
    RETURN COUNT(r) as count
    """
    result = execute_cypher(cypher.format(relation_type=relation_type))

    if result:
        return result[0]["count"]
    else:
        return []


def get_relation(node_type: str):
    """Get all relations for a specific node type"""
    cypher = f"""
    MATCH (n:`{node_type}`)-[r]-(m)
    WITH type(r) AS relType
    RETURN DISTINCT relType
    ORDER BY relType
    """
    result = execute_cypher(cypher.format(node_type=node_type))
    return [relType["relType"] for relType in result]


def get_node_properties(node_type: str):
    """Get properties of a specific node type"""
    cypher = """
    MATCH (n:`{node_type}`)
    UNWIND keys(n) AS prop
    RETURN DISTINCT prop
    """
    result = execute_cypher(cypher.format(node_type=node_type))

    if result:
        return [prop["prop"] for prop in result]
    else:
        return []


def get_relation_patterns(relation_type: str):
    """Get patterns for a specific relation type"""
    cypher = """
    MATCH (source)-[r:`{relation_type}`]->(target)
    RETURN DISTINCT labels(source) as source_labels, labels(target) as target_labels, COUNT(*) as frequency
    ORDER BY frequency DESC
    LIMIT 10
    """
    result = execute_cypher(cypher.format(relation_type=relation_type))

    if result:
        return result
    else:
        return []


def get_sample_relationships(relation_type: str):
    """Get sample relationships for a specific relation type"""
    cypher = """
    MATCH (source)-[r:`{relation_type}`]-(target)
    RETURN labels(source) as source_labels, labels(target) as target_labels, r as relationship
    LIMIT 2
    """
    result = execute_cypher(cypher.format(relation_type=relation_type))
    if result:
        return result
    else:
        return []
