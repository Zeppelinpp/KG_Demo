import json
import ollama
from config.constants import CYPHER_MAPPING

kv_embedding_mapping = {}
for query, cypher in CYPHER_MAPPING.items():
    query_embedding = ollama.embed(model="bge-m3", input=query).embeddings[0]
    kv_embedding_mapping[query] = {
        "query_embedding": query_embedding,
        "cypher": cypher
    }

json.dump(kv_embedding_mapping, ensure_ascii=False, indent=4, fp=open("config/kv_embedding_mapping.json", "w"))