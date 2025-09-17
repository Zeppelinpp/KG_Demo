from concurrent.futures import ThreadPoolExecutor
import os
from typing import List, Dict, Any, Optional
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
import asyncio

load_dotenv()
console = Console()
CURRENT_TIME = "2024-12-30 10:00:00"


class AnalyzeResult(BaseModel):
    main_query: str
    insights_queries: List[str]


class AnalyzeResultEvent(Event):
    """Event to signal analysis completion"""

    result: AnalyzeResult
    session_id: Optional[str] = None  # Add session identifier


class GraphKnowledgeEvent(Event):
    """Event containing graph knowledge results"""

    graph_knowledge: Dict[str, Any]
    session_id: Optional[str] = None  # Add session identifier


class StreamMessageEvent(Event):
    """Event for streaming messages to UI"""

    message: str
    metadata: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None  # Add session identifier


class ToolCallEvent(Event):
    """Event for tool call information"""

    tool_name: str
    tool_args: Dict[str, Any]
    tool_result: Any = None
    session_id: Optional[str] = None  # Add session identifier


class ReportChunkEvent(Event):
    """Event for streaming report chunks"""

    chunk: str
    session_id: Optional[str] = None  # Add session identifier


async def execute_query_async(
    query: str,
    prompt: str,
    agent: FunctionCallingAgent,
    ctx: Context = None,
    agent_name: str = None,
    session_id: str = None,  # Add session_id parameter
) -> str:
    """
    Async function for executing queries with event handling
    """

    # Create event callback for this agent
    async def agent_event_callback(event_type: str, data: Dict[str, Any]):
        if ctx and event_type == "tool_call_complete":
            ctx.write_event_to_stream(
                ToolCallEvent(
                    tool_name=data["tool_name"],
                    tool_args=data["tool_args"],
                    tool_result=data["tool_result"],
                    session_id=session_id,  # Include session_id
                )
            )

    # Temporarily set the event callback
    original_callback = agent.event_callback
    agent.event_callback = agent_event_callback

    try:
        result = ""
        async for chunk in agent.run_query_stream(query, prompt):
            result += chunk
        return result
    finally:
        # Restore original callback
        agent.event_callback = original_callback


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
            tool_usage=True,
            event_callback=None,  # Will be set per query
        )

        # Initialize knowledge retriever
        Settings.embed_model = OllamaEmbedding(model_name="bge-m3")
        documents = SimpleDirectoryReader(
            "/Users/ruipu/projects/KG_Demo/knowledge"
        ).load_data()
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
    async def analyze(self, ctx: Context, ev: StartEvent) -> AnalyzeResultEvent:
        """
        Analyze the user query to generate a query plan
        """
        # Get session_id from StartEvent if available
        session_id = getattr(ev, "session_id", None)

        # Store session_id in context for use in other steps
        await ctx.store.set("session_id", session_id)
        await ctx.store.set("original_query", ev.query)
        # Stream analysis start message
        ctx.write_event_to_stream(
            StreamMessageEvent(
                message="🔍 Analyzing your query...",
                metadata={"status": "pending", "step": "analysis"},
                session_id=session_id,
            )
        )

        # Retrieve knowledge
        knowledge = self.context_manager.load_mapping_knowledge(ev.query)

        prompt = ANALYZE_PROMPT.format(
            business_knowledge=knowledge,
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

        # Stream analysis complete with details
        ctx.write_event_to_stream(
            StreamMessageEvent(
                message="✅ Analysis complete",
                metadata={
                    "status": "done",
                    "step": "analysis",
                    "main_query": result.main_query,
                    "insights_queries": result.insights_queries,
                    "queries_count": len(result.insights_queries) + 1,
                },
                session_id=session_id,
            )
        )

        await ctx.store.set("analyze_result", result)
        return AnalyzeResultEvent(result=result, session_id=session_id)

    @step
    async def execute_queries(
        self, ctx: Context, ev: AnalyzeResultEvent
    ) -> GraphKnowledgeEvent:
        """
        Execute the queries using multiprocessing and collect results
        """
        plan = ev.result

        # Retrieve session_id from context
        session_id = await ctx.store.get("session_id")

        # Stream execution start
        ctx.write_event_to_stream(
            StreamMessageEvent(
                message=f"📊 Executing {len(plan.insights_queries) + 1} queries in parallel...",
                metadata={
                    "status": "pending",
                    "step": "execution",
                    "queries_count": len(plan.insights_queries) + 1,
                },
                session_id=session_id,
            )
        )

        results = {}
        if (
            plan.main_query
        ):  # Changed: Only check for main_query, insights_queries can be empty
            # Prepare all queries with their contexts
            all_queries = []

            # Main query
            main_context = self.context_manager.load_mapping_knowledge(plan.main_query)
            all_queries.append(
                {
                    "type": "main",
                    "query": plan.main_query,
                    "prompt": GRAPH_QUERY_RPOMPT.format(
                        schema=self.schema,
                        related_knowledge=main_context,
                        current_time=CURRENT_TIME,
                    ),
                }
            )

            # Insights queries (if any)
            if plan.insights_queries:
                for idx, query in enumerate(plan.insights_queries):
                    context = self.context_manager.load_mapping_knowledge(query)
                    all_queries.append(
                        {
                            "type": f"insight_{idx}",
                            "query": query,
                            "prompt": GRAPH_QUERY_RPOMPT.format(
                                schema=self.schema,
                                related_knowledge=context,
                                current_time=CURRENT_TIME,
                            ),
                        }
                    )

            # Execute all queries in parallel using asyncio
            tasks = []
            for q in all_queries:
                agent_name = (
                    "Main Query Agent"
                    if q["type"] == "main"
                    else f"Insight Agent {q['type'].split('_')[1]}"
                )
                task = asyncio.create_task(
                    execute_query_async(
                        q["query"],
                        q["prompt"],
                        self.graph_agent,
                        ctx,
                        agent_name,
                        session_id,
                    )
                )
                tasks.append((q["type"], q["query"], task))

            # Wait for all tasks to complete
            for query_type, query_text, task in tasks:
                try:
                    result = await task
                    results[query_type] = {"query": query_text, "result": result}

                    # Stream individual query completion
                    ctx.write_event_to_stream(
                        StreamMessageEvent(
                            message=f"✓ Query completed: {query_text[:50]}...",
                            metadata={
                                "query_type": query_type,
                                "query": query_text,
                                "result_preview": result[:200] + "..."
                                if len(result) > 200
                                else result,
                            },
                            session_id=session_id,
                        )
                    )
                except Exception as e:
                    kg_logger.log_error(f"Error executing query {query_type}: {e}")
                    results[query_type] = {
                        "query": query_text,
                        "result": f"Error: {str(e)}",
                    }

        # Stream execution complete
        ctx.write_event_to_stream(
            StreamMessageEvent(
                message="✅ All queries executed successfully",
                metadata={
                    "status": "done",
                    "step": "execution",
                    "total_results": len(results),
                    "queries_count": len(results),  # Add queries_count for consistency
                },
                session_id=session_id,
            )
        )

        # Log before returning
        kg_logger.logger.info(
            f"[EXECUTE] Completed execute_queries, returning GraphKnowledgeEvent with {len(results)} results"
        )
        print(
            f"[EXECUTE] Returning GraphKnowledgeEvent with {len(results)} results: {results}, session_id: {session_id}"
        )

        return GraphKnowledgeEvent(graph_knowledge=results, session_id=session_id)

    @step
    async def report(self, ctx: Context, ev: GraphKnowledgeEvent) -> StopEvent:
        """
        Generate final report with streaming
        """
        # Log report step entry
        kg_logger.logger.info(
            f"[REPORT] Entering report step with {len(ev.graph_knowledge)} results"
        )
        print(
            f"[REPORT] Entering report step with graph_knowledge: {len(ev.graph_knowledge)} results"
        )

        # Retrieve session_id from context
        session_id = await ctx.store.get("session_id")
        print(f"[REPORT] Session ID: {session_id}")

        # Stream report generation start
        ctx.write_event_to_stream(
            StreamMessageEvent(
                message="📝 Generating comprehensive report...",
                metadata={"status": "pending", "step": "report"},
                session_id=session_id,
            )
        )

        # Format knowledge for report
        formatted_knowledge = ""
        for key, value in ev.graph_knowledge.items():
            formatted_knowledge += f"\n### {value['query']}\n{value['result']}\n"

        print(f"[REPORT] Calling LLM for report generation...")
        original_query = await ctx.store.get("original_query")
        response = await self.llm.chat.completions.create(
            model="qwen-max-latest",
            messages=[
                {
                    "role": "system",
                    "content": REPORT_PROMPT.format(
                        graph_knowledge=formatted_knowledge, current_time=CURRENT_TIME
                    ),
                },
                {
                    "role": "user",
                    "content": original_query,
                },
            ],
            stream=True,
        )
        print(f"[REPORT] LLM response received, starting to stream...")

        # Stream the report chunks
        full_report = ""
        chunk_count = 0
        async for chunk in response:
            if chunk.choices[0].delta.content:
                chunk_text = chunk.choices[0].delta.content
                full_report += chunk_text
                chunk_count += 1
                if chunk_count == 1:
                    print(f"[REPORT] First chunk received: {chunk_text[:50]}...")
                ctx.write_event_to_stream(
                    ReportChunkEvent(chunk=chunk_text, session_id=session_id)
                )

        print(
            f"[REPORT] Report generation completed. Total chunks: {chunk_count}, Report length: {len(full_report)}"
        )
        kg_logger.logger.info(
            f"[REPORT] Report completed with {chunk_count} chunks, {len(full_report)} characters"
        )

        return StopEvent(result=full_report)


async def main(query: str):
    """Test the workflow"""
    wf = KGWorkflow(timeout=1000, verbose=True)
    handler = await wf.run(query=query)

    # Stream events
    async for event in handler.stream_events():
        if isinstance(event, StreamMessageEvent):
            print(f"\n{event.message}")
            if event.metadata:
                print(f"Metadata: {event.metadata}")
        elif isinstance(event, ReportChunkEvent):
            print(event.chunk, end="", flush=True)

    # Get final result
    result = await handler
    print(f"\n\nFinal result: {result}")


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, required=True)
    args = parser.parse_args()
    asyncio.run(main(query=args.query))
