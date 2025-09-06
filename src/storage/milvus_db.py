import os
import numpy as np
import ollama
from pymilvus import MilvusClient, CollectionSchema, FieldSchema, DataType, Collection
from pymilvus.milvus_client.index import IndexParams
from typing import Dict, Any, List
from src.model.mapping import Mapping


def init_collection(collection_name: str):
    client = MilvusClient("milvus.db")

    fields = [
        FieldSchema(
            name="term", dtype=DataType.VARCHAR, max_length=200, is_primary=True
        ),
        FieldSchema(name="term_embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
        FieldSchema(
            name="attributes",
            dtype=DataType.ARRAY,
            element_type=DataType.VARCHAR,
            max_length=200,
            max_capacity=10,
        ),
    ]

    schema = CollectionSchema(fields, description="Contextual Knowledge Base")
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)

    index_params = IndexParams()
    index_params.add_index(
        field_name="term_embedding",
        index_type="FLAT",
        index_name="term_embedding",
        metric_type="COSINE",
    )
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
        using="default",
        consistency_level="Strong",
    )


class MilvusDB:
    def __init__(self, collection_name: str):
        self.client = MilvusClient("milvus.db")
        self.collection_name = collection_name
        if self.client.has_collection(collection_name):
            self.client.load_collection(collection_name)
        else:
            raise ValueError(f"Collection {collection_name} not found")
        self.embed_model = ollama.Client(host=os.getenv("OLLAMA_HOST"))

    def insert(self, data: Mapping):
        self.client.insert(collection_name=self.collection_name, data=[data.model_dump()])

    def search(self, query: str, top_k: int = 5):
        query_embedding = self.embed_model.embed(model="bge-m3", input=query).embeddings
        results = self.client.search(
            collection_name=self.collection_name,
            data=query_embedding,
            anns_field="term_embedding",
            limit=top_k,
            output_fields=["term", "attributes"],
        )
        return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--collection_name", type=str, required=True)
    args = parser.parse_args()
    init_collection(args.collection_name)
