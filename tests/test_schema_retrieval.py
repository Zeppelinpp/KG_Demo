import ollama
from pymilvus import MilvusClient

client = MilvusClient("milvus.db")

client.load_collection("node_schema")

accountbook_results = client.search(
    collection_name="node_schema",
    data=ollama.embed(
        model="bge-m3", input="金蝶国际主账簿在2024年3期应付职工薪酬支出TOP10的部门"
    ).embeddings,
    anns_field="embeddings",
    limit=5,
    output_fields=["node_type", "properties", "patterns"],
)[0]

accountbook_results = "\n".join(
    [
        f"节点:{result['entity']['node_type']}\n节点属性:{result['entity']['properties']}\n节点模式:{result['entity']['patterns']}"
        for result in accountbook_results
    ]
)
print(accountbook_results)
