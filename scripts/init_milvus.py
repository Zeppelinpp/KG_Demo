import os
import ollama
from dotenv import load_dotenv
from pymilvus import MilvusClient, FieldSchema, DataType, CollectionSchema
from pymilvus.milvus_client.index import IndexParams

load_dotenv()

client = MilvusClient("http://172.20.236.27:19530")
def init_mapping_collection():
    """Initialize mapping collection for business term mappings"""
    collection_name = "mapping"

    fields = [
        FieldSchema(
            name="term", dtype=DataType.VARCHAR, max_length=200, is_primary=True
        ),
        FieldSchema(name="term_embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
        FieldSchema(
            name="description",
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
    print(f"Collection '{collection_name}' initialized successfully")


def init_node_schema_collection():
    """Initialize node schema collection for graph schema storage"""
    
    collection_name = "node_schema"

    if client.has_collection(collection_name):
        client.drop_collection(collection_name)

    fields = [
        FieldSchema(
            name="node_type", dtype=DataType.VARCHAR, max_length=200, is_primary=True
        ),
        FieldSchema(
            name="properties",
            dtype=DataType.ARRAY,
            element_type=DataType.VARCHAR,
            max_length=200,
        ),
        FieldSchema(
            name="out_relations",
            dtype=DataType.ARRAY,
            element_type=DataType.VARCHAR,
            max_length=200,
        ),
        FieldSchema(
            name="in_relations",
            dtype=DataType.ARRAY,
            element_type=DataType.VARCHAR,
            max_length=200,
        ),
        FieldSchema(
            name="patterns",
            dtype=DataType.ARRAY,
            element_type=DataType.VARCHAR,
            max_length=200,
        ),
        FieldSchema(
            name="samples",
            dtype=DataType.ARRAY,
            element_type=DataType.VARCHAR,
            max_length=200,
        ),
        FieldSchema(name="embeddings", dtype=DataType.FLOAT_VECTOR, dim=1024),
    ]

    schema = CollectionSchema(fields, description="Node Schema")
    index_params = IndexParams()
    index_params.add_index(
        field_name="embeddings",
        index_type="FLAT",
        index_name="embeddings",
        metric_type="COSINE",
    )
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
        using="default",
        consistency_level="Strong",
    )
    print(f"Collection '{collection_name}' initialized successfully")


def init_all_collections(collection: str = None):
    """Initialize all Milvus collections"""
    print("Initializing Milvus collections...")
    if collection == "mapping":
        init_mapping_collection()
    elif collection == "node_schema":
        init_node_schema_collection()
    else:
        init_mapping_collection()
        init_node_schema_collection()
    print("All collections initialized successfully")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", type=str, required=False)
    args = parser.parse_args()
    if args.collection:
        init_all_collections(args.collection)
    else:
        init_all_collections()
