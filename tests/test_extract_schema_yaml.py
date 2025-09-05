#!/usr/bin/env python3
"""
Example script showing how to extract Neo4j schema in YAML format
"""
import os
from dotenv import load_dotenv
from src.core import Neo4jSchemaExtractor

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
    
    return schema

if __name__ == "__main__":
    extract_schema_as_yaml()
