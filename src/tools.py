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
            result = session.run(cypher)
        except Exception as e:
            return f"Failed to execute cypher: {str(e)}"

        properties = []
        for property in result:
            properties.append(property["prop"])
        return properties


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


def get_relation(entites: List[str], hops: int = 2):
    # TODO Implement utility: Get relations of certain entities within certain hops
    pass


def get_node_properties(node_type: str):
    cypher = """
    MATCH (n:`{node_type}`)
    UNWIND keys(n) AS prop
    RETURN DISTINCT prop
    """
    result = execute_cypher(cypher.format(node_type=node_type))
    return result


if __name__ == "__main__":
    result = get_node_properties("Entry")
    print(result)
