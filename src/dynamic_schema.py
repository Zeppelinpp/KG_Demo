#!/usr/bin/env python3
"""
动态Schema抽取器
根据用户查询动态提取相关的图数据库schema信息，而不是加载整个schema
"""

import os
import re
import json
import time
from typing import List, Dict, Set, Optional, Tuple, Any
from dataclasses import dataclass, field
from neo4j import GraphDatabase
from openai import AsyncOpenAI
from rich.console import Console
from src.logger import kg_logger
from src.utils import serialize_neo4j_value


@dataclass
class QueryTerms:
    """查询术语提取结果"""
    entities: Set[str] = field(default_factory=set)  # 实体词
    attributes: Set[str] = field(default_factory=set)  # 属性词
    actions: Set[str] = field(default_factory=set)  # 动作词
    
    def all_terms(self) -> Set[str]:
        """获取所有术语"""
        return self.entities | self.attributes | self.actions


@dataclass
class CandidateSchema:
    """候选schema信息"""
    node_labels: Set[str] = field(default_factory=set)
    relationship_types: Set[str] = field(default_factory=set)
    
    def is_empty(self) -> bool:
        """检查是否为空"""
        return len(self.node_labels) == 0 and len(self.relationship_types) == 0


@dataclass
class DynamicSchemaResult:
    """动态schema抽取结果"""
    nodes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    relationships: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    query_terms: QueryTerms = field(default_factory=QueryTerms)
    candidate_schema: CandidateSchema = field(default_factory=CandidateSchema)
    extraction_time: float = 0.0
    
    def to_md(self) -> str:
        """转换为markdown格式"""
        md = []
        
        # 基本信息
        md.append("# 动态Schema信息\n")
        md.append(f"**提取时间**: {self.extraction_time:.3f}秒\n")
        md.append(f"**查询术语**: {', '.join(self.query_terms.all_terms())}\n\n")
        
        # 节点信息
        if self.nodes:
            md.append("## 节点类型\n")
            for node_label, node_info in self.nodes.items():
                properties = node_info.get('properties', [])
                count = node_info.get('count', 0)
                md.append(f"- `{node_label}` ({count} 个节点)\n")
                
                # 属性信息
                if properties:
                    prop_names = [prop['name'] if isinstance(prop, dict) else prop for prop in properties]
                    md.append(f"  - 属性: {prop_names}\n")
                
                # 示例数据
                if 'samples' in node_info and node_info['samples']:
                    sample = node_info['samples'][0]
                    md.append(f"  - 示例: {sample}\n")
                
                md.append("\n")
        
        # 关系信息
        if self.relationships:
            md.append("## 关系类型\n")
            for rel_type, rel_info in self.relationships.items():
                properties = rel_info.get('properties', [])
                count = rel_info.get('count', 0)
                md.append(f"- `{rel_type}` ({count} 个关系)\n")
                
                # 属性信息
                if properties:
                    prop_names = [prop['name'] if isinstance(prop, dict) else prop for prop in properties]
                    md.append(f"  - 属性: {prop_names}\n")
                
                # 模式信息
                if 'patterns' in rel_info and rel_info['patterns']:
                    md.append(f"  - 常见模式:\n")
                    for pattern in rel_info['patterns'][:3]:  # 显示前3个模式
                        md.append(f"    - {pattern['source_labels']} -> {pattern['target_labels']} (频次: {pattern['frequency']})\n")
                
                md.append("\n")
        
        return "".join(md)


class DynamicSchemaExtractor:
    """动态Schema抽取器"""
    
    def __init__(
        self,
        uri: str,
        database: str,
        username: str = "neo4j",
        password: str = "password",
        console: Console = None,
        cache_ttl: int = 300  # 缓存时间5分钟
    ):
        self.uri = uri
        self.database = database
        self.username = username
        self.password = password
        self.console = console or Console()
        self.driver = None
        
        # 缓存机制
        self.cache_ttl = cache_ttl
        self._schema_cache: Dict[str, Tuple[DynamicSchemaResult, float]] = {}
        
        # 业务术语映射表（可扩展）
        self.term_mappings = {
            # 凭证相关
            "凭证": ["凭证"],
            "voucher": ["凭证"],
            "单据": ["凭证"],
            
            # 科目相关
            "科目": ["科目"],
            "account": ["科目"],
            "会计科目": ["科目"],
            
            # 客户相关
            "客户": ["客户"],
            "customer": ["客户"],
            
            # 供应商相关
            "供应商": ["供应商"],
            "supplier": ["供应商"],
            "vendor": ["供应商"],
            
            # 余额相关
            "余额": ["余额"],
            "balance": ["余额"],
            
            # 人员相关
            "人员": ["人员"],
            "员工": ["人员"],
            "staff": ["人员"],
            "employee": ["人员"],
            
            # 费用相关
            "费用": ["费用"],
            "expense": ["费用"],
            "成本": ["费用"],
            
            # 银行相关
            "银行": ["银行账户", "银行类别"],
            "bank": ["银行账户", "银行类别"],
            "账户": ["银行账户"],
            
            # 仓库相关
            "仓库": ["仓库"],
            "warehouse": ["仓库"],
            
            # 部门相关
            "部门": ["部门"],
            "department": ["部门"],
            
            # 项目相关
            "项目": ["项目"],
            "project": ["项目"],
            
            # 业务单元相关
            "业务单元": ["业务单元"],
            "business_unit": ["业务单元"],
            
            # 产品线相关
            "产品线": ["产品线"],
            "product_line": ["产品线"],
        }
        
        # 关系类型映射
        self.relation_mappings = {
            "制单": ["由...制单", "凭证由人员制单"],
            "审核": ["由...审核", "凭证由人员审核"],
            "使用": ["凭证使用科目"],
            "涉及": ["涉及客户", "涉及供应商", "涉及费用", "涉及仓库", "涉及人员", "涉及银行"],
            "对应": ["余额对应科目", "余额对应客户", "余额对应供应商", "余额对应银行", "余额对应人员", "余额对应仓库", "余额对应费用"],
            "属于": ["属于客户"],
        }
        
        # LLM客户端用于术语提取
        self.llm_client = AsyncOpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL")
        )
    
    def connect(self) -> bool:
        """连接到Neo4j数据库"""
        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.username, self.password)
            )
            
            # 测试连接
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            
            return True
        except Exception as e:
            kg_logger.log_error(f"Failed to connect to Neo4j: {e}")
            return False
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
    
    async def extract_query_terms(self, user_query: str) -> QueryTerms:
        """从用户查询中提取关键术语"""
        
        # 1. 基于规则的术语提取
        terms = QueryTerms()
        
        # 简单的分词和术语识别
        query_lower = user_query.lower()
        
        # 提取已知的业务术语
        for term, labels in self.term_mappings.items():
            if term in query_lower:
                terms.entities.update(labels)
                kg_logger.log_info(f"Found term '{term}' in query, adding labels: {labels}")
        
        # 提取关系相关术语
        for action, relations in self.relation_mappings.items():
            if action in query_lower:
                terms.actions.add(action)
                kg_logger.log_info(f"Found action '{action}' in query")
        
        # 如果基于规则没有找到任何术语，尝试包含查询
        if len(terms.entities) == 0 and len(terms.actions) == 0:
            # 尝试更宽松的匹配
            for term, labels in self.term_mappings.items():
                if any(word in query_lower for word in term.split()):
                    terms.entities.update(labels)
                    kg_logger.log_info(f"Found partial match for term '{term}', adding labels: {labels}")
        
        # 2. 使用LLM进行更精确的术语提取
        try:
            llm_terms = await self._extract_terms_with_llm(user_query)
            if llm_terms:
                terms.entities.update(llm_terms.entities)
                terms.attributes.update(llm_terms.attributes)
                terms.actions.update(llm_terms.actions)
                kg_logger.log_info(f"LLM extracted terms - entities: {llm_terms.entities}, actions: {llm_terms.actions}")
        except Exception as e:
            kg_logger.log_error(f"LLM term extraction failed: {e}")
        
        kg_logger.log_info(f"Final extracted terms for '{user_query}': entities={terms.entities}, actions={terms.actions}")
        
        return terms
    
    async def _extract_terms_with_llm(self, user_query: str) -> Optional[QueryTerms]:
        """使用LLM提取术语"""
        
        prompt = f"""
        请从以下用户查询中提取关键术语，并分类为实体词、属性词和动作词。
        
        用户查询: {user_query}
        
        已知的业务实体类型: {list(self.term_mappings.keys())}
        
        请以JSON格式返回结果:
        {{
            "entities": ["实体词1", "实体词2"],
            "attributes": ["属性词1", "属性词2"],
            "actions": ["动作词1", "动作词2"]
        }}
        
        只返回JSON，不要其他内容。
        """
        
        try:
            response = await self.llm_client.chat.completions.create(
                model="qwen-max",
                messages=[
                    {"role": "system", "content": "你是一个专业的术语提取专家，专门从ERP业务查询中提取关键术语。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # 尝试解析JSON
            result_json = json.loads(result_text)
            
            return QueryTerms(
                entities=set(result_json.get("entities", [])),
                attributes=set(result_json.get("attributes", [])),
                actions=set(result_json.get("actions", []))
            )
            
        except Exception as e:
            kg_logger.log_error(f"LLM term extraction error: {e}")
            return None
    
    def generate_candidate_schema(self, terms: QueryTerms) -> CandidateSchema:
        """根据术语生成候选schema"""
        
        candidate = CandidateSchema()
        
        # 基于实体术语映射到节点标签
        for entity in terms.entities:
            if entity in self.term_mappings:
                candidate.node_labels.update(self.term_mappings[entity])
            else:
                # 直接添加实体词作为候选标签
                candidate.node_labels.add(entity)
        
        # 基于动作词映射到关系类型
        for action in terms.actions:
            if action in self.relation_mappings:
                candidate.relationship_types.update(self.relation_mappings[action])
        
        # 如果没有明确的关系类型，添加常用的关系
        if not candidate.relationship_types and candidate.node_labels:
            # 如果涉及凭证，添加常用的凭证关系
            if "凭证" in candidate.node_labels:
                candidate.relationship_types.update([
                    "凭证使用科目", "凭证涉及客户", "凭证涉及供应商", 
                    "凭证由人员制单", "凭证由人员审核"
                ])
            
            # 如果涉及余额，添加余额相关关系
            if "余额" in candidate.node_labels:
                candidate.relationship_types.update([
                    "余额对应科目", "余额对应客户", "余额对应供应商"
                ])
        
        return candidate
    
    def extract_node_sample_data(self, node_label: str, limit: int = 3) -> Dict[str, Any]:
        """提取节点的示例数据和属性信息"""
        
        if not self.driver:
            return {}
        
        try:
            with self.driver.session(database=self.database) as session:
                # 获取节点数量
                count_result = session.run(
                    f"MATCH (n:`{node_label}`) RETURN COUNT(n) as count"
                )
                node_count = count_result.single()["count"]
                
                # 获取节点属性
                props_result = session.run(
                    f"""
                    MATCH (n:`{node_label}`) 
                    WITH n LIMIT {limit}
                    RETURN DISTINCT keys(n) as props
                    """
                )
                
                all_props = set()
                for record in props_result:
                    all_props.update(record["props"])
                
                properties = [{"name": prop} for prop in sorted(all_props)]
                
                # 获取示例数据
                sample_result = session.run(
                    f"MATCH (n:`{node_label}`) RETURN n LIMIT {limit}"
                )
                
                samples = []
                for record in sample_result:
                    node = record["n"]
                    sample = dict(node)
                    # 序列化Neo4j值
                    sample = {k: serialize_neo4j_value(v) for k, v in sample.items()}
                    samples.append(sample)
                
                return {
                    "count": node_count,
                    "properties": properties,
                    "samples": samples
                }
                
        except Exception as e:
            kg_logger.log_error(f"Failed to extract node data for {node_label}: {e}")
            return {}
    
    def extract_relationship_sample_data(self, rel_type: str, limit: int = 3) -> Dict[str, Any]:
        """提取关系的示例数据和模式信息"""
        
        if not self.driver:
            return {}
        
        try:
            with self.driver.session(database=self.database) as session:
                # 获取关系数量
                count_result = session.run(
                    f"MATCH ()-[r:`{rel_type}`]->() RETURN COUNT(r) as count"
                )
                rel_count = count_result.single()["count"]
                
                # 获取关系属性
                props_result = session.run(
                    f"""
                    MATCH ()-[r:`{rel_type}`]->() 
                    WITH r LIMIT {limit}
                    RETURN DISTINCT keys(r) as props
                    """
                )
                
                all_props = set()
                for record in props_result:
                    all_props.update(record["props"])
                
                properties = [{"name": prop} for prop in sorted(all_props)]
                
                # 获取关系模式
                pattern_result = session.run(
                    f"""
                    MATCH (source)-[r:`{rel_type}`]->(target)
                    RETURN labels(source) as source_labels, 
                           labels(target) as target_labels,
                           COUNT(*) as frequency
                    ORDER BY frequency DESC
                    LIMIT {limit}
                    """
                )
                
                patterns = []
                for record in pattern_result:
                    patterns.append({
                        "source_labels": record["source_labels"],
                        "target_labels": record["target_labels"],
                        "frequency": record["frequency"]
                    })
                
                # 获取示例关系
                sample_result = session.run(
                    f"""
                    MATCH (source)-[r:`{rel_type}`]->(target)
                    RETURN labels(source) as source_labels,
                           labels(target) as target_labels,
                           [type(r), properties(r)] as relationship
                    LIMIT {limit}
                    """
                )
                
                samples = []
                for record in sample_result:
                    samples.append({
                        "source_labels": record["source_labels"],
                        "target_labels": record["target_labels"],
                        "relationship": record["relationship"]
                    })
                
                return {
                    "count": rel_count,
                    "properties": properties,
                    "patterns": patterns,
                    "samples": samples
                }
                
        except Exception as e:
            kg_logger.log_error(f"Failed to extract relationship data for {rel_type}: {e}")
            return {}
    
    def _get_cache_key(self, user_query: str) -> str:
        """生成缓存键"""
        return f"dynamic_schema_{hash(user_query.lower().strip())}"
    
    def _is_cache_valid(self, cache_time: float) -> bool:
        """检查缓存是否有效"""
        return time.time() - cache_time < self.cache_ttl
    
    async def extract_dynamic_schema(
        self, 
        user_query: str, 
        use_cache: bool = True,
        max_samples: int = 3
    ) -> DynamicSchemaResult:
        """
        根据用户查询动态提取相关的schema信息
        
        Args:
            user_query: 用户查询
            use_cache: 是否使用缓存
            max_samples: 最大示例数量
            
        Returns:
            DynamicSchemaResult: 动态schema抽取结果
        """
        
        start_time = time.time()
        
        # 检查缓存
        cache_key = self._get_cache_key(user_query)
        if use_cache and cache_key in self._schema_cache:
            cached_result, cache_time = self._schema_cache[cache_key]
            if self._is_cache_valid(cache_time):
                kg_logger.log_info(f"Using cached dynamic schema for query: {user_query[:50]}...")
                return cached_result
        
        # 连接数据库
        if not self.connect():
            return DynamicSchemaResult()
        
        try:
            # 1. 提取查询术语
            kg_logger.log_info(f"Extracting terms from query: {user_query}")
            query_terms = await self.extract_query_terms(user_query)
            
            # 2. 生成候选schema
            candidate_schema = self.generate_candidate_schema(query_terms)
            
            if candidate_schema.is_empty():
                kg_logger.log_warning("No candidate schema found, falling back to common entities")
                # 回退策略：使用常见的实体类型
                candidate_schema.node_labels.update(["凭证", "科目", "客户", "供应商", "余额"])
                candidate_schema.relationship_types.update(["凭证使用科目", "余额对应科目"])
            
            # 3. 提取候选节点的详细信息
            result = DynamicSchemaResult(
                query_terms=query_terms,
                candidate_schema=candidate_schema
            )
            
            # 提取节点信息
            for node_label in candidate_schema.node_labels:
                kg_logger.log_info(f"Extracting node data for: {node_label}")
                node_data = self.extract_node_sample_data(node_label, max_samples)
                if node_data:
                    result.nodes[node_label] = node_data
            
            # 提取关系信息
            for rel_type in candidate_schema.relationship_types:
                kg_logger.log_info(f"Extracting relationship data for: {rel_type}")
                rel_data = self.extract_relationship_sample_data(rel_type, max_samples)
                if rel_data:
                    result.relationships[rel_type] = rel_data
            
            # 4. 计算提取时间
            result.extraction_time = time.time() - start_time
            
            # 5. 缓存结果
            if use_cache:
                self._schema_cache[cache_key] = (result, time.time())
            
            kg_logger.log_info(
                f"Dynamic schema extraction completed in {result.extraction_time:.3f}s. "
                f"Found {len(result.nodes)} node types and {len(result.relationships)} relationship types."
            )
            
            return result
            
        except Exception as e:
            kg_logger.log_error(f"Dynamic schema extraction failed: {e}")
            return DynamicSchemaResult(extraction_time=time.time() - start_time)
        
        finally:
            self.close()
    
    def clear_cache(self):
        """清空缓存"""
        self._schema_cache.clear()
        kg_logger.log_info("Dynamic schema cache cleared")


# 便利函数
async def extract_dynamic_schema_for_query(
    user_query: str,
    uri: str = None,
    database: str = None,
    username: str = None,
    password: str = None
) -> DynamicSchemaResult:
    """
    便利函数：为查询提取动态schema
    """
    
    # 使用环境变量作为默认值
    uri = uri or os.getenv("NEO4J_URI")
    database = database or os.getenv("NEO4J_DATABASE")
    username = username or os.getenv("NEO4J_USER", "neo4j")
    password = password or os.getenv("NEO4J_PASSWORD", "password")
    
    extractor = DynamicSchemaExtractor(
        uri=uri,
        database=database,
        username=username,
        password=password
    )
    
    return await extractor.extract_dynamic_schema(user_query)


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    
    load_dotenv()
    
    async def test_dynamic_extraction():
        """测试动态抽取功能"""
        
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
        
        for query in test_queries:
            print(f"\n{'='*50}")
            print(f"查询: {query}")
            print(f"{'='*50}")
            
            result = await extractor.extract_dynamic_schema(query)
            print(result.to_md())
    
    asyncio.run(test_dynamic_extraction())
