import os
from dotenv import load_dotenv
from openai import OpenAI
from src.prompts import CYPHER_GEN_PROMPT
from src.core import Neo4jSchemaExtractor

load_dotenv()

extractor = Neo4jSchemaExtractor(
    uri=os.getenv("NEO4J_URI"),
    database=os.getenv("NEO4J_DATABASE"),
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),
)
schema = extractor.extract_full_schema("config/schema.json")

client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
)


response = client.chat.completions.create(
    model="qwen-max-latest",
    messages=[
        {"role": "system", "content": CYPHER_GEN_PROMPT.format(schema=schema)},
        {"role": "user", "content": "修改提问"},
    ],
)

print(response.choices[0].message.content)
