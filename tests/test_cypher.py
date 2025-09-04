import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
)


cypher = """
CALL apoc.meta.relTypeProperties()
YIELD relType, sourceNodeLabels, targetNodeLabels, propertyName, propertyTypes
RETURN relType, sourceNodeLabels, targetNodeLabels, propertyName, propertyTypes
ORDER BY relType
"""
with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
    result = session.run(cypher)
    print(result.data())