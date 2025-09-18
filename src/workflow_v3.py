import os
import json
from dotenv import load_dotenv
from llama_index.core.workflow import Workflow, StartEvent, StopEvent, Context, step, Event
import ollama
from openai import AsyncOpenAI
import numpy as np
from src.core import FunctionCallingAgent
from src.tools import query_neo4j
from config.constants import CYPHER_MAPPING
from rich.console import Console
from typing import List

load_dotenv()

console = Console()


def similarity(query_embedding: List[float], target_embedding: List[float]) -> float:
    # cosine similarity
    score = np.dot(query_embedding, target_embedding) / (np.linalg.norm(query_embedding) * np.linalg.norm(target_embedding))
    # return top 1
    return score
class CypherEvent(Event):
    cypher: str

class MatchingCompletedEvent(Event):
    """Event when query matching is completed"""
    matched_query: str
    similarity_score: float
    cypher: str

class ReportChunkEvent(Event):
    """Event for streaming report chunks"""
    chunk: str

class QueryExecutingEvent(Event):
    """Event when starting to execute a query"""
    cypher: str
    index: int

class QueryExecutedEvent(Event):
    """Event for each executed query"""
    cypher: str
    result: str
    index: int

class KGWorkflow(Workflow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.llm = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL")
        )
        with open("config/kv_embedding_mapping.json", "r") as f:
            self.kv_embedding_mapping = json.load(f)
    
    @step
    async def match_mapping(self, ev: StartEvent, ctx: Context) -> CypherEvent:
        query = ev.query
        await ctx.store.set("original_query", query)
        query_embedding = ollama.embed(model="bge-m3", input=query).embeddings[0]

        match_query = ""
        max_score = 0
        for kv_query, data in self.kv_embedding_mapping.items():
            current_score = similarity(query_embedding, data["query_embedding"])
            if current_score > max_score:
                match_query = kv_query
                max_score = current_score
        
        # Get the matched cypher
        matched_cypher = self.kv_embedding_mapping[match_query]["cypher"]
        
        # Log the match result
        console.print(f"[green]Matched query: {match_query}")
        console.print(f"[green]Similarity score: {max_score:.4f}")
        console.print(f"[cyan]Cypher: {matched_cypher}")
        
        # Send matching completed event to frontend
        ctx.write_event_to_stream(MatchingCompletedEvent(
            matched_query=match_query,
            similarity_score=max_score,
            cypher=matched_cypher
        ))
        
        return CypherEvent(cypher=matched_cypher)
    
    @step
    async def report(self, ev: CypherEvent, ctx: Context) -> StopEvent:
        cyphers = ev.cypher.split(";")
        valid_cyphers = []
        for cypher in cyphers:
            if len(cypher.strip()) == 0:
                continue
            valid_cyphers.append(cypher.strip())
        
        # Execute queries and emit events for each
        results = {}
        for idx, cypher in enumerate(valid_cyphers):
            # Emit event when starting to execute
            ctx.write_event_to_stream(QueryExecutingEvent(
                cypher=cypher,
                index=idx
            ))
            
            # Execute the query
            result = query_neo4j(cypher)
            results[cypher] = result
            
            # Emit event after execution completes
            # Format result as JSON string for better display
            import json
            try:
                # Try to convert to JSON for pretty display
                if isinstance(result, (list, dict)):
                    result_str = json.dumps(result, ensure_ascii=False, indent=2)
                else:
                    result_str = str(result)
            except:
                result_str = str(result)
            
            # Truncate if too long
            if len(result_str) > 1000:
                result_str = result_str[:1000] + "..."
                
            ctx.write_event_to_stream(QueryExecutedEvent(
                cypher=cypher,
                result=result_str,
                index=idx
            ))

        prompt = """
你是一个ERP系统和财务领域专家，请根据知识图谱的查询语句以及查询结果，生成与问题相关的分析报告与相关洞察

<财务知识>
1. 借方为负数的原因
当 “本币_借” 为负数时，本质是通过 “借方红字”（负数）替代 “贷方蓝字”，代表对已入账的销售费用进行冲减、更正或转回，即费用金额减少。
常见业务场景举例：
费用退款 / 返还：已支付的销售费用因业务取消或协商退款，冲减原入账费用。
例：此前支付的展会费 10000 元，因展会取消收到主办方退款 5000 元，需冲减广告费，此时 “本币_借：销售费用 - 展会费 -5000”（替代贷方 5000）
</财务知识>

<回复风格>
严谨，自信的根据财务知识，分析查询结果，生成与问题相关的分析报告与相关洞察 如有数据异常请给出相关分析
不需要说根据哪些知识分析的，只需要说明根据什么数据进行分析的
</回复风格>
        """

        user_prompt = """
问题: {query}
Cypher & Result: {results}
        """
        original_query = await ctx.store.get("original_query")
        user_prompt = user_prompt.format(query=original_query, results=results)
        response = await self.llm.chat.completions.create(
            model="qwen-max-latest",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
        )
        
        # Collect the full report for return
        full_report = ""
        async for chunk in response:
            if chunk.choices[0].delta.content:
                chunk_text = chunk.choices[0].delta.content
                full_report += chunk_text
                # Write each chunk to the event stream
                ctx.write_event_to_stream(ReportChunkEvent(chunk=chunk_text))
        
        return StopEvent(result=full_report)


async def main():
    """Test the workflow with streaming"""
    import sys
    query = sys.argv[1] if len(sys.argv) > 1 else "本月销售费用主要花在哪里，是否合理？"
    
    workflow = KGWorkflow(timeout=1000, verbose=False)
    handler = workflow.run(query=query)
    
    console.print(f"[bold green]Processing query: {query}")
    console.print("-" * 50)
    
    # Stream events
    async for event in handler.stream_events():
        if isinstance(event, CypherEvent):
            console.print(f"[yellow]Matched Cypher: {event.cypher[:100]}...")
        elif isinstance(event, ReportChunkEvent):
            # Print report chunks without newline for streaming effect
            print(event.chunk, end="", flush=True)
    
    # Get final result
    result = await handler
    console.print("\n" + "-" * 50)
    console.print("[bold green]Analysis complete!")
    
    return result


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())