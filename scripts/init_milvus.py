import os
import ollama
from dotenv import load_dotenv
from pymilvus import MilvusClient, FieldSchema, DataType, CollectionSchema
from pymilvus.milvus_client.index import IndexParams

load_dotenv()


def init_mapping_collection():
    """Initialize mapping collection for business term mappings"""
    client = MilvusClient("milvus.db")
    collection_name = "mapping"

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
    print(f"Collection '{collection_name}' initialized successfully")


def init_node_schema_collection():
    """Initialize node schema collection for graph schema storage"""
    client = MilvusClient("milvus.db")
    collection_name = "node_schema"
    
    if client.has_collection(collection_name):
        client.drop_collection(collection_name)
        
    fields = [
        FieldSchema(name="node_type", dtype=DataType.VARCHAR, max_length=200, is_primary=True),
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


def init_all_collections():
    """Initialize all Milvus collections"""
    print("Initializing Milvus collections...")
    init_mapping_collection()
    init_node_schema_collection()
    print("All collections initialized successfully")


if __name__ == "__main__":
    init_all_collections()
