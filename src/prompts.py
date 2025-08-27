CYPHER_GEN_PROMPT="""
请根据提供的图数据库Schema和用户的问题, 生成一个可以解决用户问题的合法的Cypher查询语句.

<KG Schema>
{schema}
</KG Schema>

请严格按照以下步骤：
1. 分析用户问题，理解查询需求
2. 根据schema生成准确的Cypher查询语句

请只输出Cypher查询语句,不要输出任何其他内容.
"""

KG_AGENT_PROMPT="""
请根据提供的知识图谱schema,分析用户问题,生成可以解决用户问题的cypher查询语句,并使用工具调用查询语句并返回结果.

<KG Schema>
{schema}
</KG Schema>

请严格按照以下步骤：
1. 分析用户问题，理解查询需求
2. 根据schema生成准确的Cypher查询语句
3. 使用query_neo4j工具执行查询
4. 基于查询结果回答用户问题
"""