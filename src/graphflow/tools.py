import os
import subprocess
from dotenv import load_dotenv
from typing import List
from neo4j import GraphDatabase
from src.utils import tools_to_openai_schema

load_dotenv()

def get_possible_nodes_type():
    """
    Get all the possible node types in graph database
    """
    with GraphDatabase.driver(
        uri=os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    ) as driver:
        with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
            result = session.run("CALL db.labels()")
            return [label["label"] for label in result.data()]

def get_node_schema(node_types: List[str]):
    """
    Get the valid schema of a given node type lists. Including: properties, relation patterns and sample data
    """
    with GraphDatabase.driver(
        uri=os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    ) as driver:
        node_schemas = {}
        with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
            for node_type in node_types:
                # Get properties
                properties = session.run(f"MATCH (n: `{node_type}`) UNWIND keys(n) AS properties RETURN DISTINCT properties").data()
                properties = [property["properties"] for property in properties]
                # Get one hop & two hop relation patterns
                one_hop_out_patterns = session.run(f"MATCH (n:`{node_type}`)-[r]->(m) RETURN head(labels(n)) as source,type(r) AS rel, head(labels(m)) AS target").data()
                one_hop_out_patterns = set([(pattern["source"], pattern["rel"], pattern["target"]) for pattern in one_hop_out_patterns])
                one_hop_in_patterns = session.run(f"MATCH (n: `{node_type}`)<-[r]-(m) RETURN head(labels(m)) as source,type(r) AS rel, head(labels(n)) AS target").data()
                one_hop_in_patterns = set([(pattern["source"], pattern["rel"], pattern["target"]) for pattern in one_hop_in_patterns])

                two_hop_out_patterns = session.run(f"MATCH (n:`{node_type}`)-[r1]->(m1)-[r2]->(m2) RETURN head(labels(n)) as source,type(r1) AS rel1, head(labels(m1)) as target1, type(r2) AS rel2, head(labels(m2)) as target2").data()
                two_hop_out_patterns = set([(pattern["source"], pattern["rel1"], pattern["target1"], pattern["rel2"], pattern["target2"]) for pattern in two_hop_out_patterns])
                two_hop_in_patterns = session.run(f"MATCH (n: `{node_type}`)<-[r1]-(m1)<-[r2]-(m2) RETURN head(labels(m2)) as source,type(r1) AS rel1, head(labels(m1)) as target1, type(r2) AS rel2, head(labels(n)) as target2").data()
                two_hop_in_patterns = set([(pattern["source"], pattern["rel1"], pattern["target1"], pattern["rel2"], pattern["target2"]) for pattern in two_hop_in_patterns])

                # Get sample data
                sample_data = session.run(f"MATCH (n:`{node_type}`) RETURN n LIMIT 1")
                sample_data = [data["n"] for data in sample_data.data()]



def run_python_code(code: str):
    """
    Run python code to compute, analyze numerical data for complex tasks
    """
    # bash activate current environment
    workspace = os.getenv("WORKSPACE")
    python_exec = os.path.join(workspace, ".venv", "bin", "python")
    # run python code
    try:
        result = subprocess.run(
            [python_exec, "-c", code],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    # Return error message if code execution fails
    except subprocess.CalledProcessError as e:
        return e.stderr.strip() or f"Python code execution failed: {e.returncode}"


if __name__ == "__main__":
    get_node_schema(["凭证分录", "员工"])