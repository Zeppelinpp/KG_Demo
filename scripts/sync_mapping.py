import ollama
import os
from dotenv import load_dotenv
from src.context.retriever import MappingRetriever
from src.model.mapping import Mapping
from config.constants import BUSSINESS_MAPPING

load_dotenv()

db = MappingRetriever("mapping")

datas = [
    Mapping(
        term=term,
        term_embedding=ollama.embed(model=os.getenv("EMBED_MODEL"), input=term).embeddings[0],
        description=[description] if isinstance(description, str) else description,
    )
    for term, description in BUSSINESS_MAPPING.items()
]


def insert():
    for data in datas:
        db.insert(data)


def search():
    results = db.search(
        "按客户分析2025年3月末应收账款分布（金额及占比），结果按金额降序。"
    )
    print(results)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--insert", default=False, required=False)
    parser.add_argument("--search", default=False, required=False)
    args = parser.parse_args()

    if args.insert:
        insert()
    if args.search:
        search()
