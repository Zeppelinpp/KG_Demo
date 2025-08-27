import os
import inspect
import re
from neo4j import GraphDatabase
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional, Callable, Union

load_dotenv()


def query_neo4j(
    cypher_query: str, parameters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Execute Cypher query and return results

    Args:
        cypher_query: Cypher query
        parameters: Query parameters (optional)

    Returns:
        Query results list
    """
    driver = None
    # cypher preprocess

    # Wrap xxx.csv with backticks if not already wrapped
    def wrap_csv_with_backticks(match):
        csv_name = match.group(1)
        return f"`{csv_name}`"

    # Only wrap xxx.csv that are not already wrapped in backticks
    cypher_query = re.sub(
        r'(?<!`)(\b[^`\s\(\):]+\.csv\b)(?!`)',  # matches xxx.csv not surrounded by `
        wrap_csv_with_backticks,
        cypher_query
    )
    # print(cypher_query)
    try:
        # Connect to Neo4j database
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI"),
            auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
        )

        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            result = session.run(cypher_query, parameters or {})
            records = []
            for record in result:
                records.append(dict(record))

            return records
    except Exception as e:
        return [{"error": f"Query failed: {str(e)}"}]

    finally:
        if driver:
            driver.close()


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


if __name__ == "__main__":
    query = """
MATCH (v:凭证记录表.csv)
WHERE v.科目全名 = '其他应付款_员工往来' 
RETURN v.`部门.名称` AS department, SUM(toFloat(replace(v.借方, ",", ""))) AS total_expense
ORDER BY total_expense DESC
LIMIT 3
    """
    query_neo4j(query)