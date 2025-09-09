import ollama
from src.storage.milvus_db import MilvusDB
from src.model.mapping import Mapping
from config.constants import BUSSINESS_MAPPING

db = MilvusDB("mapping")

datas = [
    Mapping(
        term=term,
        term_embedding=ollama.embed(model="bge-m3", input=term).embeddings[0],
        attributes=[attributes] if isinstance(attributes, str) else attributes,
    )
    for term, attributes in BUSSINESS_MAPPING.items()
]

def insert():
    for data in datas:
        db.insert(data)

def search():
    results = db.search("江西银涛药业股份有限公司主账簿在2024年3期应付职工薪酬支出TOP10的部门")
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