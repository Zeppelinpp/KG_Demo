import os
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Literal, Optional, List, Dict, Any
from dotenv import load_dotenv
from openai import OpenAI
from config.constants import BUSSINESS_MAPPING, MAX_CONTEXT_WINDOW
from src.core import Neo4jSchemaExtractor
from src.storage.milvus_db import MilvusDB
from src.prompts import KG_AGENT_PROMPT, COMPRESS_PROMPT
from src.logger import kg_logger

load_dotenv()

PREFIX = {
    "mapping": "这次查询涉及的业务用词与知识图谱中可能相关的字段名称对应如下:\n",
}


class ContextManager:
    def __init__(
        self,
        resources: List[str],
        schema: Optional[str] = None,
        llm_client: Optional[OpenAI] = None,
    ):
        self.bussiness_mapping = BUSSINESS_MAPPING
        self.resources = resources
        self.prefix = {}
        for resource in resources:
            self.prefix[resource] = PREFIX[resource]
        
        # Use provided schema or load from Neo4j
        if schema:
            self.graph_schema = schema
        else:
            extractor = Neo4jSchemaExtractor(
                uri=os.getenv("NEO4J_URI"),
                database=os.getenv("NEO4J_DATABASE"),
                username=os.getenv("NEO4J_USER"),
                password=os.getenv("NEO4J_PASSWORD"),
            )
            self.graph_schema = extractor.extract_full_schema(return_structured=True).to_md()

        # Use provided LLM client or create new one
        self.llm = llm_client or OpenAI(
            base_url=os.getenv("OPENAI_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

        # Initialize collections with proper error handling
        self.collections = {}
        for collection_name in self.resources:
            try:
                self.collections[collection_name] = MilvusDB(
                    collection_name=collection_name
                )
            except Exception as e:
                print(f"Warning: Failed to initialize collection {collection_name}: {e}")

    def _parse(
        self, result: Dict[str, Any], role: Literal["user", "assistant"], resource: str
    ):
        """
        Parse result to Human message and Assistant message
        """
        message = {"role": role, "content": f"{self.prefix[resource]}{result}"}
        return message

    def add_context_to_history(self, history: List[Dict[str, Any]], context_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Add context messages to history and manage context window
        """
        new_history = history + context_messages
        
        # Check context window and compress if needed
        if len(new_history) > MAX_CONTEXT_WINDOW:
            new_history = self._compress(new_history)
        
        return new_history

    def _compress(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compress context window, summarize essential facts and remain core information in history
        """
        # Keep system prompt
        system_message = history[0]
        context = history[1:]

        try:
            response = self.llm.chat.completions.create(
                model="qwen-max-latest",
                messages=[
                    {"role": "user", "content": COMPRESS_PROMPT.format(history=json.dumps(context, ensure_ascii=False))},
                ],
                response_format={"type": "json_object"},
            )
            compressed_history = json.loads(response.choices[0].message.content)

            # Validate the compressed history
            if not isinstance(compressed_history, list):
                raise ValueError("Compressed history is not a list")
            
            for message in compressed_history:
                if not isinstance(message, dict) or "role" not in message or "content" not in message:
                    raise ValueError("Invalid message format")
                if message["role"] not in ["user", "assistant"]:
                    raise ValueError("Invalid role in message")

            return [system_message] + compressed_history
        
        except Exception as e:
            print(f"Warning: Context compression failed: {e}")
            # Return original history if compression fails
            return history

    def load_context(self, query: str, from_resources: List[str]) -> List[Dict[str, Any]]:
        """
        Load context from specified resources and return context messages
        """
        if not from_resources or not any(res in self.collections for res in from_resources):
            kg_logger.log_context_loading(query, from_resources, {})
            return []
        
        # Load extra information from available collections
        available_collections = [
            (name, self.collections[name]) for name in from_resources 
            if name in self.collections
        ]
        
        if not available_collections:
            kg_logger.log_context_loading(query, from_resources, {})
            return []
        
        try:
            with ThreadPoolExecutor(max_workers=len(available_collections)) as pool:
                search_args = {"query": query, "top_k": 5}
                futures = [
                    (name, pool.submit(db.search, **search_args)) 
                    for name, db in available_collections
                ]
                results = [(name, future.result()) for name, future in futures]

            # Combine results from all collections
            combined_results = {}
            for name, result in results:
                if result and len(result) > 0:
                    for hit in result[0]:
                        if "entity" in hit and "term" in hit["entity"]:
                            # Convert attributes from RepeatedScalarContainer to list
                            attributes = hit["entity"].get("attributes", [])
                            if hasattr(attributes, '__iter__') and not isinstance(attributes, (str, dict)):
                                # Convert to list if it's a RepeatedScalarContainer or similar
                                attributes = list(attributes)
                            combined_results[hit["entity"]["term"]] = attributes

            # Log context loading information
            kg_logger.log_context_loading(query, from_resources, combined_results)

            # Generate context messages
            context_messages = []
            for resource in from_resources:
                if combined_results:
                    context_messages.append(self._parse(combined_results, "user", resource))
            
            return context_messages
            
        except Exception as e:
            error_msg = f"Failed to load context from resources {from_resources}: {e}"
            kg_logger.log_error(error_msg, {"query": query, "resources": from_resources})
            print(f"Warning: {error_msg}")
            return []


    def cleanup(self):
        """
        Clean up resources
        """
        pass


if __name__ == "__main__":
    context_manager = ContextManager(
        resources=["mapping"],
    )
    result = context_manager.load_context(
        "江西银涛药业股份有限公司主账簿账簿在2024年3期期所有的应付账款发生额",
        from_resources=["mapping"],
    )
    print(f"Context messages: {result}")
    context_manager.cleanup()
