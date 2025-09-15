from concurrent.futures import ThreadPoolExecutor
import os
from typing import List
from pydantic import BaseModel
from dotenv import load_dotenv
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.core import Settings
from llama_index.core import SimpleDirectoryReader
from llama_index.core.workflow import (
    StartEvent,
    Workflow,
    Context,
    step,
    Event,
    StopEvent,
)
from openai import AsyncOpenAI
from src.context.manager import ContextManager
from rich.console import Console
from src.core import FunctionCallingAgent
from src.tools import query_neo4j
from src.prompts import (
    GRAPH_QUERY_RPOMPT,
    KG_AGENT_PROMPT,
    DYNAMIC_KG_AGENT_PROMPT,
    ANALYZE_PROMPT,
    REPORT_PROMPT,
)
from src.logger import kg_logger

load_dotenv()
console = Console()
CURRENT_TIME = "2024-06-30 10:00:00"

class AnalyzeResult(BaseModel):
    main_query: str
    insights_queries: List[str]


class AnalyzeResultEvent(Event):
    result: AnalyzeResult


class GraphKnowledgeEvent(Event):
    graph_knowledge: str


class KGWorkflow(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.llm = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL")
        )
        with open("config/graph_schema.md", "r") as f:
            schema = f.read()
        self.schema = schema
        self.context_manager = ContextManager(
            resources=["mapping"],
            schema=schema,
            llm_client=self.llm,
            schema_mode="static",
        )
        self.graph_agent = FunctionCallingAgent(
            model="qwen-max-latest",
            tools=[query_neo4j],
            console=console,
            tool_usage=True
        )
        
        # init knowldege retriever
        Settings.embed_model = OllamaEmbedding(model_name="bge-m3")
        documents = SimpleDirectoryReader("/Users/ruipu/projects/KG_Demo/knowledge").load_data()
        vector_store = MilvusVectorStore(
            uri="/Users/ruipu/projects/KG_Demo/milvus.db", dim=1024, overwrite=True
        )
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(
            documents, storage_context=storage_context, show_progress=True
        )
        index.storage_context.persist(persist_dir="knowledge")
        self.knowledge_retriever = index.as_retriever(similarity_top_k=20)

    @step
    async def analyze(self, ev: StartEvent, ctx: Context) -> AnalyzeResultEvent:
        """
        Analyze the user query to generate a query plan
        """
        knowlege_node = self.knowledge_retriever.retrieve(ev.query)
        knowlege = "\n".join([node.text for node in knowlege_node])
        console.print(f"Current time: {CURRENT_TIME}")
        prompt = ANALYZE_PROMPT.format(
            business_knowledge=knowlege,
            schema=self.schema,
            current_time=CURRENT_TIME,
        )
        response = await self.llm.chat.completions.create(
            model="qwen-max-latest",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": ev.query},
            ],
            response_format={"type": "json_object"},
        )

        result = AnalyzeResult.model_validate_json(response.choices[0].message.content)
        console.print(result)
        await ctx.store.set("analyze_result", result)
        return AnalyzeResultEvent(result=result)

    @step
    async def execute_queries(
        self, ev: AnalyzeResultEvent, ctx: Context
    ) -> GraphKnowledgeEvent:
        """
        Execute the queries and get the graph knowledge
        """
        plan = ev.result
        if plan.main_query and plan.insights_queries:
            with ThreadPoolExecutor(max_workers=len(plan.insights_queries) + 1) as pool:
                main_quer_context = await self.context_manager.load_context(
                    plan.main_query, ["mapping"]
                )
                main_query_future = pool.submit(
                    self.graph_agent.run_query_stream,
                    plan.main_query,
                    GRAPH_QUERY_RPOMPT.format(
                        schema=self.schema, related_knowledge=main_quer_context, current_time=CURRENT_TIME
                    ),
                )

                insights_queries_contexts = [
                    await self.context_manager.load_context(query, ["mapping"])
                    for query in plan.insights_queries
                ]
                insights_queries_futures = [
                    pool.submit(
                        self.graph_agent.run_query_stream,
                        query,
                        GRAPH_QUERY_RPOMPT.format(
                            schema=self.schema, related_knowledge=context, current_time=CURRENT_TIME
                        ),
                    )
                    for query, context in zip(
                        plan.insights_queries, insights_queries_contexts
                    )
                ]

                main_query_result_str = ""
                main_query_result = main_query_future.result()
                async for chunk in main_query_result:
                    main_query_result_str += chunk
                    print(chunk, end="")
                insights_queries_results = [
                    future.result() for future in insights_queries_futures
                ]
                insights_queries_results_str = ""
                for result in insights_queries_results:
                    async for chunk in result:
                        insights_queries_results_str += chunk
                        print(chunk, end="")

        knowledge = {
            "main_query": main_query_result_str,
            "insights_queries": insights_queries_results_str,
        }
        return GraphKnowledgeEvent(graph_knowledge=str(knowledge))

    @step
    async def report(self, ev: GraphKnowledgeEvent, ctx: Context) -> StopEvent:
        """
        Final Report
        """
        response = await self.llm.chat.completions.create(
            model="qwen-max-latest",
            messages=[
                {
                    "role": "system",
                    "content": REPORT_PROMPT.format(graph_knowledge=ev.graph_knowledge, current_time=CURRENT_TIME),
                },
            ],
            stream=True,
        )

        async for chunk in response:
            print(chunk.choices[0].delta.content, end="")
        return StopEvent()

async def main(query: str):
    wf = KGWorkflow(timeout=1000, verbose=True)
    handler = await wf.run(query=query)


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, required=True)
    args = parser.parse_args()
    asyncio.run(main(query=args.query))
