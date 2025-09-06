import concurrent
from concurrent.futures import ThreadPoolExecutor
import os
import ollama
from typing import Optional, List
from dotenv import load_dotenv
from openai import OpenAI
from config.constants import BUSSINESS_MAPPING
from src.core import Neo4jSchemaExtractor
from src.storage.milvus_db import MilvusDB

load_dotenv()


class ContextManager:
    def __init__(
        self,
        # persistent_path: str,
        resources: List[str],
        schema_path: Optional[str] = None,
    ):
        # self.persistent_path = persistent_path
        self.bussiness_mapping = BUSSINESS_MAPPING
        self.resources = resources
        try:
            with open(schema_path, "r") as f:
                # Load md file of graph schema
                self.graph_schema = f.read()
        except Exception as e:
            print(f"Error loading schema from {schema_path}: {e}")
            extractor = Neo4jSchemaExtractor(
                uri=os.getenv("NEO4J_URI"),
                database=os.getenv("NEO4J_DATABASE"),
                username=os.getenv("NEO4J_USER"),
                password=os.getenv("NEO4J_PASSWORD"),
            )
            self.graph_schema = extractor.extract_full_schema(schema_path)
        self.llm = OpenAI(
            base_url=os.getenv("OPENAI_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        self.collections = {}
        for collection_name in self.resources:
            self.collections[collection_name] = MilvusDB(
                collection_name=collection_name
            )

    def load_context(self, query, from_resources: List[str]):
        collections = [
            self.collections[collection_name] for collection_name in from_resources
        ]
        with ThreadPoolExecutor(max_workers=len(collections)) as pool:
            search_args = {"query": query, "top_k": 5}
            futures = [
                pool.submit(
                    db.search,
                    **search_args
                )
                for db in collections
            ]
            results = [future.result() for future in futures]
        
        combined_results = {}
        for result in results:
            for hit in result[0]:
                combined_results[hit["entity"]["term"]] = hit["entity"]["attributes"]
        
        return combined_results


if __name__ == "__main__":
    context_manager = ContextManager(
        #persistent_path="persistent",
        resources=["mapping"],
        schema_path="/Users/ruipu/projects/KG_Demo/config/graph_schema.md",
    )
    result = context_manager.load_context("江西银涛药业股份有限公司主账簿账簿在2024年3期期所有的应付账款发生额", from_resources=["mapping"])
    print(result)

