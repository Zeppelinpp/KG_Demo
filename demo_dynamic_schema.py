#!/usr/bin/env python3
"""
动态Schema抽取功能演示脚本
"""

import os
import asyncio
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from src.dynamic_schema import DynamicSchemaExtractor

load_dotenv()
console = Console()


async def demo_dynamic_schema():
    """演示动态schema抽取功能"""
    
    console.rule("[bold green]🚀 动态Schema抽取功能演示", style="green")
    console.print()
    
    # 创建动态schema抽取器
    extractor = DynamicSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD"),
        console=console
    )
    
    # 演示查询列表
    demo_queries = [
        {
            "query": "查询张三的凭证信息",
            "description": "查询特定人员的凭证记录"
        },
        {
            "query": "显示应付账款科目的余额",
            "description": "查询科目余额信息"
        },
        {
            "query": "找出所有供应商相关的费用记录",
            "description": "查询供应商费用关联"
        },
        {
            "query": "统计各部门的人员数量",
            "description": "部门人员统计查询"
        },
        {
            "query": "查看银行账户的交易记录",
            "description": "银行交易记录查询"
        }
    ]
    
    console.print(
        Panel(
            "[bold cyan]功能特点:[/bold cyan]\n\n"
            "• 🎯 [green]智能术语识别[/green] - 从查询中自动提取关键业务术语\n"
            "• 🔍 [green]动态schema抽取[/green] - 只提取查询相关的节点和关系类型\n"
            "• ⚡ [green]缓存优化[/green] - 避免重复查询，提高响应速度\n"
            "• 🤖 [green]LLM增强[/green] - 结合LLM进行更精确的术语识别\n"
            "• 📊 [green]示例数据[/green] - 提供实际的节点和关系示例",
            title="[bold blue]动态Schema抽取器",
            border_style="blue",
        )
    )
    console.print()
    
    for i, demo in enumerate(demo_queries, 1):
        console.print(f"[bold yellow]演示 {i}: {demo['description']}[/bold yellow]")
        console.print(f"[dim]查询: {demo['query']}[/dim]")
        console.print()
        
        # 提取动态schema
        result = await extractor.extract_dynamic_schema(demo['query'])
        
        # 显示提取结果摘要
        console.print(
            Panel(
                f"[green]✓ 提取完成[/green]\n\n"
                f"[bold cyan]提取时间:[/bold cyan] {result.extraction_time:.3f}秒\n"
                f"[bold cyan]识别术语:[/bold cyan] {', '.join(result.query_terms.all_terms())}\n"
                f"[bold cyan]节点类型:[/bold cyan] {len(result.nodes)} 个\n"
                f"[bold cyan]关系类型:[/bold cyan] {len(result.relationships)} 个",
                title=f"[bold green]提取结果 - 演示 {i}",
                border_style="green",
            )
        )
        
        # 显示详细的schema信息（前几个）
        if result.nodes:
            console.print("\n[bold blue]节点类型详情:[/bold blue]")
            for j, (node_label, node_info) in enumerate(list(result.nodes.items())[:2]):
                count = node_info.get('count', 0)
                properties = [prop['name'] if isinstance(prop, dict) else prop 
                            for prop in node_info.get('properties', [])]
                
                console.print(f"  [cyan]• {node_label}[/cyan] ({count} 个节点)")
                if properties:
                    console.print(f"    属性: {properties[:5]}")  # 只显示前5个属性
                    if len(properties) > 5:
                        console.print(f"    ... 还有 {len(properties) - 5} 个属性")
        
        if result.relationships:
            console.print("\n[bold blue]关系类型详情:[/bold blue]")
            for j, (rel_type, rel_info) in enumerate(list(result.relationships.items())[:2]):
                count = rel_info.get('count', 0)
                patterns = rel_info.get('patterns', [])
                
                console.print(f"  [cyan]• {rel_type}[/cyan] ({count} 个关系)")
                if patterns:
                    pattern = patterns[0]
                    console.print(f"    模式: {pattern['source_labels']} -> {pattern['target_labels']}")
        
        console.print()
        console.rule(style="dim")
        console.print()
    
    # 展示完整的schema输出示例
    console.print("[bold yellow]完整Schema输出示例:[/bold yellow]")
    console.print()
    
    example_result = await extractor.extract_dynamic_schema("查询凭证和科目的关联信息")
    
    # 使用语法高亮显示markdown输出
    md_output = example_result.to_md()
    syntax = Syntax(md_output, "markdown", theme="monokai", line_numbers=True)
    console.print(
        Panel(
            syntax,
            title="[bold green]动态Schema Markdown输出",
            border_style="green",
        )
    )
    
    console.print()
    console.print(
        Panel(
            "[bold green]✅ 演示完成![/bold green]\n\n"
            "[yellow]优势总结:[/yellow]\n"
            "• 相比静态schema，动态抽取只返回查询相关的信息\n"
            "• 减少了LLM prompt的长度，提高了响应效率\n"
            "• 自动适应不同类型的查询需求\n"
            "• 包含实际的示例数据，帮助LLM更好地理解schema",
            title="[bold blue]演示总结",
            border_style="blue",
        )
    )


if __name__ == "__main__":
    asyncio.run(demo_dynamic_schema())
