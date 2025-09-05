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

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--node_type", type=str, required=False)
    parser.add_argument("--query", type=str, required=False)
    parser.add_argument("--relation_type", type=str, required=False)
    args = parser.parse_args()
    if args.node_type:
        result = get_node_properties(args.node_type)
    elif args.query:
        result = execute_cypher(args.query)
    elif args.relation_type:
        result = get_relation_patterns(args.relation_type)
    else:
        raise ValueError("Either node_type or query must be provided")
    print(result)
