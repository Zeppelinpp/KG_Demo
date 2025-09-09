import os
import re
from neo4j import GraphDatabase
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

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
        r"(?<!`)(\b[^`\s\(\):]+\.csv\b)(?!`)",  # matches xxx.csv not surrounded by `
        wrap_csv_with_backticks,
        cypher_query,
    )

    # Wrap property names with backticks using split approach
    # First, temporarily replace already wrapped properties to protect them
    protected_patterns = []
    placeholder_pattern = "___PROTECTED_PROP_{}___"

    # Find and protect already wrapped properties
    def protect_wrapped(match):
        index = len(protected_patterns)
        protected_patterns.append(match.group(0))
        return placeholder_pattern.format(index)

    cypher_query = re.sub(r"\b[a-zA-Z_]\w*\.`[^`]+`", protect_wrapped, cypher_query)

    # Now process unprotected properties using split approach
    def wrap_property_with_split(match):
        full_match = match.group(0)
        # Split by dot
        parts = full_match.split(".")
        if len(parts) >= 2:
            # First part is variable name, rest are property parts
            variable = parts[0]
            property_parts = parts[1:]
            # Join property parts with dots and wrap with backticks
            property_name = ".".join(property_parts)
            return f"{variable}.`{property_name}`"
        return full_match

    # Match variable.property patterns (including multi-level properties)
    cypher_query = re.sub(
        r"\b[a-zA-Z_]\w*(?:\.[^`\s\(\)\[\],;=<>!]+)+",  # matches var.prop1.prop2...
        wrap_property_with_split,
        cypher_query,
    )

    # Restore protected patterns
    for i, pattern in enumerate(protected_patterns):
        cypher_query = cypher_query.replace(placeholder_pattern.format(i), pattern)
    print(cypher_query)
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


def execute_cypher(cypher: str):
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
    cypher = f"""
    MATCH (n:`{node_type}`)-[r]-(m)
    WITH type(r) AS relType
    RETURN DISTINCT relType
    ORDER BY relType
    """
    result = execute_cypher(cypher.format(node_type=node_type))
    return [relType["relType"] for relType in result]


def get_node_properties(node_type: str):
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


def get_schema_info(node_types: List[str]):
    """
    获取节点的属性字段信息已经与其连接的边的信息作为图谱的schema信息
    Args:
        node_types: 节点类型列表
    Returns:
        schema_info: 图谱的schema信息
    """
    schema = {}
    for node_type in node_types:
        schema[node_type] = {
            "properties": get_node_properties(node_type),
            "relationships": get_relation(node_type),
        }
    # Convert to markdown
    schema_markdown = ""
    for node_type, info in schema.items():
        schema_markdown += f"## {node_type}\n"
        schema_markdown += f"### 属性\n"
        schema_markdown += f"{info['properties']}\n"
        schema_markdown += f"### 关系边\n"
        schema_markdown += f"{info['relationships']}\n"
    return schema_markdown


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--node_type", type=str, required=False)
    parser.add_argument("--query", type=str, required=False)
    parser.add_argument("--relation_type", type=str, required=False)
    args = parser.parse_args()
    if args.node_type:
        result = get_relation(args.node_type)
    elif args.query:
        result = execute_cypher(args.query)
    elif args.relation_type:
        result = get_relation_patterns(args.relation_type)
    else:
        raise ValueError("Either node_type or query must be provided")
    print(result)
