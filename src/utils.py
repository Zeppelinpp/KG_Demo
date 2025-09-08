import inspect
from typing import List, Dict, Any, Callable, Union
from neo4j.time import DateTime, Date, Time, Duration


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
