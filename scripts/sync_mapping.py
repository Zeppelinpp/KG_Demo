import ollama
from src.context.retriever import MappingRetriever
from src.model.mapping import Mapping
from config.constants import BUSSINESS_MAPPING

db = MappingRetriever("mapping")

datas = [
    Mapping(
        term=term,
        term_embedding=ollama.embed(model="bge-m3", input=term).embeddings[0],
        description=[description] if isinstance(description, str) else description,
    )
    for term, description in BUSSINESS_MAPPING.items()
]


def insert():
    for data in datas:
        db.insert(data)


def search():
    results = db.search(
        "从2025年8期往回近一年存款期末余额环比变化"
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
