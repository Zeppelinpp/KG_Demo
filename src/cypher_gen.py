import os
from dotenv import load_dotenv
from openai import OpenAI
from prompts import CYPHER_GEN_PROMPT
from core import Neo4jSchemaExtractor

load_dotenv()

extractor = Neo4jSchemaExtractor(
    uri="bolt://localhost:7687",
    database="kggraph",
    username="neo4j",
    password="purui123",
)
schema = extractor.extract_full_schema()

client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
)


response = client.chat.completions.create(
    model="qwen-max-latest",
    messages=[
        {"role": "system", "content": CYPHER_GEN_PROMPT.format(schema=schema)},
        {"role": "user", "content": "江西银涛药业股份有限公司主账簿在2024年3期所有应付材料款发生额是多少"},
    ],
)

print(response.choices[0].message.content)
