import os
import asyncio
import ollama
from dotenv import load_dotenv
from openai import OpenAI
from pymilvus import MilvusClient
from src.core import FunctionCallingAgent
from src.tools import query_neo4j
from rich.console import Console


load_dotenv()

db_client = MilvusClient("milvus.db")
llm_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)

knowledge = db_client.search(
    collection_name="mapping",
    data=ollama.embed(model="bge-m3", input="本月销售费用主要花在哪里，是否合理？").embeddings,
    anns_field="term_embedding",
    limit=2,
    output_fields=["term", "description"],
)[0]

knowledge = "\n".join(
    [
        f"问题:{result['entity']['term']}\n思路:{result['entity']['description'][0]}"
        for result in knowledge
    ]
)
# print(knowledge)
with open("config/graph_schema.md", "r") as f:
    schema = f.read()

gen_subqueries_prompt = """
根据与用户问题可能相关的问题的解决思路，把当前的提问拆分成多个子查询任务，并调用 `query_neo4j` 工具执行相关查询

<与当前问提可能相关的问题和对应的思路>
{related_knowledge}
</与当前问提可能相关的问题和对应的思路>

<图谱Schema>
{schema}
</图谱Schema>

<输出>
使用Markdown将查到数据展示出来, 不要修改任何数据，必修严格遵循输出工具调用的结果进行输出
</输出>
"""
gen_subqueries_prompt = gen_subqueries_prompt.format(related_knowledge=knowledge, schema=schema)

console = Console()
agent = FunctionCallingAgent(
    model="qwen-max-latest",
    tools=[query_neo4j],
    console=console,
)

async def main():
    response = agent.run_query_stream(user_query="本月销售费用主要花在哪里，是否合理？", system_prompt=gen_subqueries_prompt)
    async for chunk in response:
        console.print(chunk, end="")

if __name__ == "__main__":
    asyncio.run(main())