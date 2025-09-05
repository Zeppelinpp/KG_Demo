#!/usr/bin/env python3
"""
Example script showing how to extract Neo4j schema in YAML format
"""

import os
from dotenv import load_dotenv
from src.core import Neo4jSchemaExtractor
from src.model.graph import ExtractedGraphSchema, GraphSchema

load_dotenv()


def extract_schema_as_yaml():
    """Extract Neo4j schema and save as YAML file"""

    # Create schema extractor
    extractor = Neo4jSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD"),
    )

    # Extract schema in YAML format
    print("Extracting schema in YAML format...")
    schema = extractor.extract_full_schema("config/schema", format="yaml")

    return GraphSchema.from_extracted_schema(
        ExtractedGraphSchema.from_extraction_result(schema)
    )


if __name__ == "__main__":
    schema = extract_schema_as_yaml()
    schema.to_md()
