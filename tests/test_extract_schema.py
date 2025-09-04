import os
from src.core import Neo4jSchemaExtractor
from dotenv import load_dotenv
load_dotenv()

extractor = Neo4jSchemaExtractor(
    uri=os.getenv("NEO4J_URI"),
    database=os.getenv("NEO4J_DATABASE"),
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),
)

extractor.extract_full_schema("tests/schema.json")