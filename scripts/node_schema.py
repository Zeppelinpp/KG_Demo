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

GET_CONNECTED_NODES = """
MATCH (n)-[r]-()
WITH DISTINCT labels(n) AS nodeLabels
UNWIND nodeLabels AS nodeLabel
RETURN DISTINCT nodeLabel
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

GET_SAMPLE_DATA = """
MATCH (n:`{node_type}`) RETURN n as sample LIMIT {limit}
"""


def get_node_schema():
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )

    node_schemas = []
    with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
        # First get all connected node labels
        connected_nodes = session.run(GET_CONNECTED_NODES).data()
        connected_node_labels = {node["nodeLabel"] for node in connected_nodes}
        
        # Then get all nodes with properties
        nodes = session.run(GET_NODES).data()
        for node in nodes:
            node_type = node["nodeType"].split(":")[-1].strip("`")
            
            # Skip nodes that don't have any relationships
            if node_type not in connected_node_labels:
                continue
                
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

            # Get sample data
            sample_data = session.run(
                GET_SAMPLE_DATA.format(node_type=node_type, limit=1)
            ).data()
            sample_data = [str(record["sample"]) for record in sample_data]

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
                samples=sample_data,
                embeddings=doc_embedding,
            )
            node_schemas.append(node_schema)

    return node_schemas


def get_connected_node_labels():
    """Get only node labels that have relationships"""
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD")),
    )
    
    with driver.session(database=os.getenv("NEO4J_DATABASE")) as session:
        connected_nodes = session.run(GET_CONNECTED_NODES).data()
        connected_node_labels = [node["nodeLabel"] for node in connected_nodes]
        
    driver.close()
    return connected_node_labels


def write_node_schema_to_md():
    """Write node schema information to graph_schema.md"""
    node_schemas = get_node_schema()
    
    # Generate markdown content
    md_content = ["# Graph Schema", "## Node Details"]
    
    for node_schema in node_schemas:
        # Node header with type and sample count
        sample_count = len(node_schema.samples) if node_schema.samples else 0
        md_content.append(f"- `{node_schema.node_type}` has properties: {node_schema.properties}")
        
        # Add sample data if available
        if node_schema.samples:
            md_content.append(f"  - Sample data: {node_schema.samples[0]}")
        
        # Add relationship information
        if node_schema.out_relations:
            md_content.append(f"  - Outgoing relations: {node_schema.out_relations}")
        if node_schema.in_relations:
            md_content.append(f"  - Incoming relations: {node_schema.in_relations}")
        
        # Add patterns if available
        if node_schema.patterns:
            md_content.append(f"  - Relationship patterns:")
            for pattern in node_schema.patterns[:5]:  # Limit to first 5 patterns
                md_content.append(f"    - ({pattern.source})-[{pattern.relation}]->({pattern.target})")
        
        md_content.append("")  # Empty line for separation
    
    # Write to file
    md_file_path = "/Users/ruipu/projects/KG_Demo/config/graph_schema.md"
    with open(md_file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(md_content))
    
    print(f"Node schema information written to {md_file_path}")
    print(f"Total nodes processed: {len(node_schemas)}")


# Create collection and store in Milvus
def sync_node_schema_to_milvus():
    """Sync node schema data to Milvus database"""
    node_schemas = get_node_schema()
    milvus_client = MilvusClient("milvus.db")
    
    # Initialize collection if needed
    from scripts.init_milvus import init_node_schema_collection
    init_node_schema_collection()

    data = []
    for node_schema in node_schemas:
        node_schema_dict = node_schema.model_dump(mode="json")
        data.append(node_schema_dict)
    milvus_client.insert(
        collection_name="node_schema",
        data=data,
    )
    print(f"Synced {len(data)} node schemas to Milvus")


if __name__ == "__main__":
    # Test: Get only connected node labels
    connected_labels = get_connected_node_labels()
    print("存在关系边连接的节点标签:")
    for label in connected_labels:
        print(f"  - {label}")
    print(f"\n总共找到 {len(connected_labels)} 个有关系连接的节点标签")

    # Write node schema to markdown file
    print("\n正在写入节点模式信息到 graph_schema.md...")
    write_node_schema_to_md()
    
    # Sync to Milvus (optional)
    sync_node_schema_to_milvus()