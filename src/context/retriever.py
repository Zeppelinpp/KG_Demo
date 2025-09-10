import os
import json
import ollama
from openai import AsyncOpenAI
from pymilvus import MilvusClient
from typing import Dict, Any, List, Union
from src.model.mapping import Mapping


class MappingRetriever:
    """Retriever for business term mappings"""

    def __init__(self, collection_name: str = "mapping"):
        self.client = MilvusClient("milvus.db")
        self.collection_name = collection_name
        if self.client.has_collection(collection_name):
            self.client.load_collection(collection_name)
        else:
            raise ValueError(f"Collection {collection_name} not found")
        self.embed_model = ollama.Client(host=os.getenv("OLLAMA_HOST"))

    def insert(self, data: Mapping):
        """Insert mapping data into collection"""
        self.client.insert(
            collection_name=self.collection_name, data=[data.model_dump()]
        )

    def search(self, query: str, top_k: int = 5):
        """Search for similar mappings"""
        query_embedding = self.embed_model.embed(model="bge-m3", input=query).embeddings
        results = self.client.search(
            collection_name=self.collection_name,
            data=query_embedding,
            anns_field="term_embedding",
            limit=top_k,
            output_fields=["term", "description"],
        )
        return results


class SchemaRetriever:
    """Retriever for graph schema information"""

    def __init__(self, collection_name: str = "node_schema"):
        self.milvus_client = MilvusClient("milvus.db")
        self.collection_name = collection_name
        self.llm = AsyncOpenAI(
            base_url=os.getenv("OPENAI_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )

    async def _extract_keywords(self, query: str, mapping: Union[Mapping, str]):
        """Extract keywords from query for schema retrieval"""
        if isinstance(mapping, Mapping):
            mapping = mapping.model_dump_json()
        response = await self.llm.chat.completions.create(
            model="qwen-max",
            messages=[
                {
                    "role": "system",
                    "content": f"""
                你是一个ERP和财务系统专家, 根据提供的业务可能相关的业务词汇和知识图谱中可能相关的字段名称的对应关系, 
                从用户的问题中提取可以用于召回相关schema的关键词, 以JSON格式返回,结果是一个关键词列表, 不要输出任何其他内容
                """,
                },
                {
                    "role": "user",
                    "content": f"业务词汇和知识图谱中可能相关的字段名称的对应关系:\n{mapping}\n用户的问题:\n{query}",
                },
            ],
            response_format={"type": "json_object"},
        )
        response_content = response.choices[0].message.content
        print(response_content)
        return json.loads(response.choices[0].message.content)

    async def retrieve(self, query: str, mapping: Union[Mapping, str]):
        """Retrieve relevant schema based on query and mapping"""
        keywords = await self._extract_keywords(query, mapping)
        results = self.milvus_client.search(
            collection_name=self.collection_name,
            data=ollama.embed(model="bge-m3", input=keywords).embeddings,
            anns_field="embeddings",
            limit=5,
            output_fields=["node_type", "properties", "patterns"],
        )
        doc = []
        for keyword_result in results:
            for result in keyword_result:
                doc.append(
                    f"## 节点标签:{result['entity']['node_type']}\n- 属性:{result['entity']['properties']}\n- Pattern:{result['entity']['patterns']}\n"
                )
        return "\n".join(doc)
