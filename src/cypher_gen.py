import os
from dotenv import load_dotenv
from openai import OpenAI
from prompts import CYPHER_GEN_PROMPT
from core import Neo4jSchemaExtractor

load_dotenv()

extractor = Neo4jSchemaExtractor(
    uri=os.getenv("NEO4J_URI"),
    database=os.getenv("NEO4J_DATABASE"),
    username=os.getenv("NEO4J_USER"),
    password=os.getenv("NEO4J_PASSWORD"),
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
    ],
)

print(response.choices[0].message.content)
