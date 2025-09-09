import os
import ollama
from dotenv import load_dotenv
from neo4j import GraphDatabase
from pymilvus import MilvusClient, FieldSchema, DataType, CollectionSchema
from pymilvus.milvus_client.index import IndexParams
from src.model.schema import NodeSchema, Pattern

load_dotenv()


GET_NODES = """
CALL db.schema.nodeTypeProperties() YIELD nodeType, propertyName
WITH nodeType, collect(propertyName) AS properties
RETURN nodeType, properties
"""

GET_OUT_RELATED_RELATIONS = """
MATCH (n: `{node_type}`)-[r]->(m)
RETURN DISTINCT type(r) AS relationType
LIMIT 20;
"""

GET_IN_RELATED_RELATIONS = """
MATCH (n)-[r]->(m: `{node_type}`)
RETURN DISTINCT type(r) AS relationType
LIMIT 20;
"""

GET_OUT_PATTERNS = """
MATCH (s: `{node_type}`)-[:{relation_type}]->(t) RETURN DISTINCT labels(t) as targetType
"""

GET_IN_PATTERNS = """
MATCH (s)-[:{relation_type}]->(t: `{node_type}`) RETURN DISTINCT labels(s) as sourceType
"""


def get_node_schema():
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )

    node_schemas = []
    with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
        nodes = session.run(GET_NODES).data()
        for node in nodes:
            node_type = node["nodeType"].split(":")[-1].strip("`")
            properties = node["properties"]

            # Extract out and in relations
            out_relations = session.run(
                GET_OUT_RELATED_RELATIONS.format(node_type=node_type)
            ).data()
            out_relations = [relation["relationType"] for relation in out_relations]
            in_relations = session.run(
                GET_IN_RELATED_RELATIONS.format(node_type=node_type)
            ).data()
            in_relations = [relation["relationType"] for relation in in_relations]

            # Extract patterns
            patterns = []
            for relation in out_relations:
                out_patterns = session.run(
                    GET_OUT_PATTERNS.format(node_type=node_type, relation_type=relation)
                ).data()
                for pattern in out_patterns:
                    patterns.append(
                        Pattern(
                            source=node_type,
                            target=pattern["targetType"][0],
                            relation=relation,
                        )
                    )
            for relation in in_relations:
                in_patterns = session.run(
                    GET_IN_PATTERNS.format(node_type=node_type, relation_type=relation)
                ).data()
                for pattern in in_patterns:
                    patterns.append(
                        Pattern(
                            source=pattern["sourceType"][0],
                            target=node_type,
                            relation=relation,
                        )
                    )

            # Gen embedding with node + rel + pattern
            doc = [
                f"节点标签：{node_type}",
                f"节点属性：{properties}",
                f"出边关系：{out_relations}",
                f"入边关系：{in_relations}",
            ]
            doc_str = "\n".join(doc)
            doc_embedding = ollama.embed(model="bge-m3", input=doc_str).embeddings[0]

            node_schema = NodeSchema(
                node_type=node_type,
                properties=properties,
                out_relations=out_relations,
                in_relations=in_relations,
                patterns=patterns,
                embeddings=doc_embedding,
            )
            node_schemas.append(node_schema)

    return node_schemas


# Create collection and store in Milvus
def create_collection_and_store_in_milvus():
    node_schemas = get_node_schema()
    milvus_client = MilvusClient("milvus.db")
    if milvus_client.has_collection("node_schema"):
        milvus_client.drop_collection("node_schema")
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
    milvus_client.create_collection(
        collection_name="node_schema",
        schema=schema,
        index_params=index_params,
        using="default",
        consistency_level="Strong",
    )

    data = [node_schema.model_dump(mode="json") for node_schema in node_schemas]
    milvus_client.insert(
        collection_name="node_schema",
        data=data,
    )


if __name__ == "__main__":
    create_collection_and_store_in_milvus()