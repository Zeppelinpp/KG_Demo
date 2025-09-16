#!/usr/bin/env python
"""
测试Web应用的事件流
"""

import asyncio
from src.workflow_v2 import KGWorkflow, StreamMessageEvent, AnalyzeResultEvent

async def test_events():
    """测试工作流事件"""
    workflow = KGWorkflow(timeout=1000, verbose=False)
    
    # 测试查询
    query = "分析苹果公司的财务状况"
    
    # 启动工作流
    handler = workflow.run(query=query)
    
    print("=== 开始监听事件 ===\n")
    
    # 监听事件
    async for event in handler.stream_events():
        if isinstance(event, StreamMessageEvent):
            if event.metadata:
                step = event.metadata.get('step', '')
                status = event.metadata.get('status', '')
                
                if step == 'analysis' and status == 'done':
                    print(f"✅ 分析完成事件:")
                    print(f"   主查询: {event.metadata.get('main_query', 'N/A')}")
                    print(f"   洞察查询: {event.metadata.get('insights_queries', [])}")
                    print()
                elif step == 'analysis':
                    print(f"📊 分析状态: {event.message}")
                    
        elif isinstance(event, AnalyzeResultEvent):
            print(f"🔍 AnalyzeResultEvent 接收到:")
            print(f"   主查询: {event.result.main_query}")
            print(f"   洞察查询: {event.result.insights_queries}")
            print()
    
    # 获取最终结果
    result = await handler
    print(f"\n=== 工作流完成 ===")
    print(f"最终结果长度: {len(result)} 字符")

if __name__ == "__main__":
    asyncio.run(test_events())
