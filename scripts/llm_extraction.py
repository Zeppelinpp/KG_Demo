import asyncio
from src.tools import query_neo4j
from src.core import FunctionCallingAgent
from rich.console import Console

agent = FunctionCallingAgent(
    model="qwen-max",
    tools=[query_neo4j],
    console=Console(),
)

agent.set_history([
    {"role": "system", "content": """
    你是一个ERP和财务系统专家并且精通Neo4j数据库的使用, 请使用query_neo4j工具自行探索知识图谱的结构，并生成自然语言的查询指南
    查询所有节点的语句:
    call db.labels()

    查询节点的属性的语句:
    match (n: node_type) unwind keys(n) as prop return distinct prop

    查询与节点相关边的语句:
    match (n: node_type)-[r]-(m) return distinct type(r) as relation_type
    """}
])

async def main():

    response = agent.run_query_stream("请说明图数据库中有哪些节点且包含哪些属性，结构化的描述其含义，并总结一个查询指南，比如什么样的query需要使用如何的cypher来查询")
    async for chunk in response:
        print(chunk, end="")

if __name__ == "__main__":
    asyncio.run(main())