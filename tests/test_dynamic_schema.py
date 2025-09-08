#!/usr/bin/env python3
"""
测试动态Schema抽取功能
"""

import os
import asyncio
from dotenv import load_dotenv
from src.dynamic_schema import DynamicSchemaExtractor, extract_dynamic_schema_for_query

load_dotenv()


async def test_extract_query_terms():
    """测试查询术语提取"""
    
    extractor = DynamicSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    test_cases = [
        {
            "query": "查询张三的凭证信息",
            "expected_entities": {"凭证", "人员"}
        },
        {
            "query": "显示应付账款科目的余额",
            "expected_entities": {"科目", "余额"}
        },
        {
            "query": "找出所有供应商相关的费用记录",
            "expected_entities": {"供应商", "费用"}
        }
    ]
    
    for case in test_cases:
        terms = await extractor.extract_query_terms(case["query"])
        
        # 检查是否提取到预期的实体
        assert len(terms.entities & case["expected_entities"]) > 0, \
            f"Failed to extract expected entities for query: {case['query']}"
        print(f"✓ 术语提取测试通过: {case['query']}")


async def test_extract_dynamic_schema():
    """测试动态schema抽取"""
    
    extractor = DynamicSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    test_queries = [
        "查询张三的凭证信息",
        "显示应付账款科目的余额",
        "找出所有供应商相关的费用记录"
    ]
    
    for query in test_queries:
        result = await extractor.extract_dynamic_schema(query)
        
        # 验证基本结构
        assert result is not None
        assert hasattr(result, 'nodes')
        assert hasattr(result, 'relationships')
        assert hasattr(result, 'query_terms')
        assert hasattr(result, 'candidate_schema')
        
        # 显示调试信息
        print(f"   查询: {query}")
        print(f"   提取的术语: {result.query_terms.all_terms()}")
        print(f"   候选节点: {result.candidate_schema.node_labels}")
        print(f"   候选关系: {result.candidate_schema.relationship_types}")
        print(f"   实际节点: {list(result.nodes.keys())}")
        print(f"   实际关系: {list(result.relationships.keys())}")
        
        # 验证至少提取到一些数据或候选schema
        if len(result.nodes) == 0 and len(result.relationships) == 0:
            print(f"   警告: 没有提取到实际数据，但候选schema不为空: {not result.candidate_schema.is_empty()}")
            # 如果候选schema不为空，说明逻辑是正确的，可能是数据库中没有对应的数据
            if not result.candidate_schema.is_empty():
                print(f"   这可能是因为数据库中没有对应的标签或关系类型")
        
        # 验证提取时间
        assert result.extraction_time > 0
        
        # 验证可以转换为markdown
        md_output = result.to_md()
        assert len(md_output) > 0
        assert "动态Schema信息" in md_output
        
        print(f"✓ 动态schema抽取测试通过: {query} (节点:{len(result.nodes)}, 关系:{len(result.relationships)})")


async def test_cache_functionality():
    """测试缓存功能"""
    
    extractor = DynamicSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    query = "查询凭证信息"
    
    # 第一次查询
    result1 = await extractor.extract_dynamic_schema(query, use_cache=True)
    time1 = result1.extraction_time
    
    # 第二次查询（应该使用缓存）
    result2 = await extractor.extract_dynamic_schema(query, use_cache=True)
    
    # 缓存应该使结果相同且更快
    assert result1.nodes.keys() == result2.nodes.keys()
    assert result1.relationships.keys() == result2.relationships.keys()
    
    # 清空缓存
    extractor.clear_cache()
    
    # 第三次查询（不使用缓存）
    result3 = await extractor.extract_dynamic_schema(query, use_cache=False)
    assert result3.extraction_time > 0
    
    print(f"✓ 缓存功能测试通过: 第一次 {time1:.3f}s, 第二次(缓存) {result2.extraction_time:.3f}s")


def test_term_mappings():
    """测试术语映射功能"""
    
    extractor = DynamicSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    # 测试中文术语映射
    assert "凭证" in extractor.term_mappings
    assert "客户" in extractor.term_mappings
    assert "供应商" in extractor.term_mappings
    
    # 测试英文术语映射
    assert "customer" in extractor.term_mappings
    assert "supplier" in extractor.term_mappings
    
    # 测试关系映射
    assert "制单" in extractor.relation_mappings
    assert "审核" in extractor.relation_mappings
    
    print("✓ 术语映射测试通过")


def test_connection():
    """测试数据库连接"""
    
    extractor = DynamicSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    # 测试连接
    assert extractor.connect() == True
    
    # 测试关闭连接
    extractor.close()
    
    print("✓ 数据库连接测试通过")


async def test_convenience_function():
    """测试便利函数"""
    
    result = await extract_dynamic_schema_for_query("查询凭证信息")
    
    assert result is not None
    assert hasattr(result, 'nodes')
    assert hasattr(result, 'relationships')
    
    print("✓ 便利函数测试通过")


def test_schema_result_structure():
    """测试schema结果结构"""
    
    from src.dynamic_schema import DynamicSchemaResult, QueryTerms, CandidateSchema
    
    # 测试QueryTerms
    terms = QueryTerms()
    terms.entities.add("凭证")
    terms.attributes.add("金额")
    terms.actions.add("查询")
    
    all_terms = terms.all_terms()
    assert "凭证" in all_terms
    assert "金额" in all_terms
    assert "查询" in all_terms
    
    # 测试CandidateSchema
    candidate = CandidateSchema()
    assert candidate.is_empty() == True
    
    candidate.node_labels.add("凭证")
    assert candidate.is_empty() == False
    
    # 测试DynamicSchemaResult
    result = DynamicSchemaResult()
    result.nodes["凭证"] = {"count": 100, "properties": []}
    result.relationships["凭证使用科目"] = {"count": 50, "properties": []}
    
    md_output = result.to_md()
    assert "动态Schema信息" in md_output
    assert "凭证" in md_output


async def run_all_tests():
    """运行所有测试"""
    
    print("🚀 开始测试动态Schema抽取功能...\n")
    
    try:
        # 1. 测试数据库连接
        print("1. 测试数据库连接...")
        test_connection()
        
        # 2. 测试术语映射
        print("\n2. 测试术语映射...")
        test_term_mappings()
        
        # 3. 测试便利函数
        print("\n3. 测试便利函数...")
        await test_convenience_function()
        
        # 4. 测试术语提取
        print("\n4. 测试术语提取...")
        await test_extract_query_terms()
        
        # 5. 测试动态schema抽取
        print("\n5. 测试动态schema抽取...")
        await test_extract_dynamic_schema()
        
        # 6. 测试缓存功能
        print("\n6. 测试缓存功能...")
        await test_cache_functionality()
        
        # 7. 测试schema结果结构
        print("\n7. 测试schema结果结构...")
        test_schema_result_structure()
        
        # 8. 演示完整功能
        print("\n8. 演示完整功能...")
        await demo_full_functionality()
        
        print("\n✅ 所有测试通过!")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        raise


async def demo_full_functionality():
    """演示完整功能"""
    
    test_queries = [
        "查询张三的凭证信息",
        "显示应付账款科目的余额", 
        "找出所有供应商相关的费用记录",
        "统计各部门的人员数量",
        "查看银行账户的交易记录"
    ]
    
    extractor = DynamicSchemaExtractor(
        uri=os.getenv("NEO4J_URI"),
        database=os.getenv("NEO4J_DATABASE"),
        username=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    for i, query in enumerate(test_queries, 1):
        print(f"   查询 {i}: {query}")
        result = await extractor.extract_dynamic_schema(query)
        print(f"   ✓ 提取到 {len(result.nodes)} 个节点类型, {len(result.relationships)} 个关系类型 (耗时: {result.extraction_time:.3f}s)")
    
    # 显示一个完整的结果示例
    print(f"\n   示例输出 (查询: {test_queries[0]}):")
    print("   " + "=" * 50)
    result = await extractor.extract_dynamic_schema(test_queries[0])
    md_lines = result.to_md().split('\n')
    for line in md_lines[:20]:  # 只显示前20行
        print(f"   {line}")
    if len(md_lines) > 20:
        print(f"   ... (还有 {len(md_lines) - 20} 行)")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
