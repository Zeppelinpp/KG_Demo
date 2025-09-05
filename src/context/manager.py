import os
from typing import Optional
from dotenv import load_dotenv
from config.constants import BUSSINESS_MAPPING
from src.core import Neo4jSchemaExtractor
from src.pipeline import extractor

load_dotenv()

class ContextManager:
    def __init__(self, persistent_path: str, schema_path: Optional[str] = None):
        self.persistent_path = persistent_path
        self.bussiness_mapping = BUSSINESS_MAPPING
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                # Load md file of graph schema
                self.graph_schema = f.read()
        else:
            extractor = Neo4jSchemaExtractor(
                uri=os.getenv("NEO4J_URI"),
                database=os.getenv("NEO4J_DATABASE"),
                username=os.getenv("NEO4J_USER"),
                password=os.getenv("NEO4J_PASSWORD"),
            )
            self.graph_schema = extractor.extract_full_schema(schema_path)


    def load_context(self, query):
        pass