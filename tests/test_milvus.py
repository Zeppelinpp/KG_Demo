import ollama
from src.context.retriever import MappingRetriever
from src.model.mapping import Mapping
from config.constants import BUSSINESS_MAPPING

db = MappingRetriever("mapping")

test_data = [
    Mapping(
        term=term,
        term_embedding=ollama.embed(model="bge-m3", input=term).embeddings[0],
        attributes=[attributes] if isinstance(attributes, str) else attributes,
    )
    for term, attributes in BUSSINESS_MAPPING.items()
]


def test_insert():
    for data in test_data:
        db.insert(data)


def test_search():
    results = db.search(
        "江西银涛药业股份有限公司主账簿在2024年3期应付职工薪酬支出TOP10的部门"
    )
    print(results)


if __name__ == "__main__":
    test_insert()
    test_search()
