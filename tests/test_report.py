import os
from dotenv import load_dotenv
from openai import OpenAI
from src.tools import query_neo4j

load_dotenv()

llm = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_BASE_URL"),
)
prompt = """
你是一个专业的ERP财务分析专家，请根据提供的Cypher语句和对应到的查询结果，详细回答用户的问题并提供洞察
"""

user_prompt = """
问题: {query}
Cypher: {cypher}
查询结果: {result}
"""

cypher = """
// 参数定义
WITH '2024年11期' AS currentPeriod,
     '2024年10期' AS lastPeriod,
     '2023年11期' AS lastYearSamePeriod,
     '2024年' AS currentYearPrefix,
     '2023年' AS lastYearPrefix

// 1. 获取销售费用和销售收入各期间金额
MATCH (k:科目余额)
WHERE (k.科目名称 CONTAINS '销售费用' OR k.科目名称 CONTAINS '销售收入')
  AND (k.期间 IN [currentPeriod, lastPeriod, lastYearSamePeriod] OR k.期间 STARTS WITH currentYearPrefix OR k.期间 STARTS WITH lastYearPrefix)
WITH 
  SUM(CASE WHEN k.科目名称 CONTAINS '销售费用' AND k.期间 = currentPeriod THEN k.`本期发生_本位币_借` ELSE 0 END) AS 销售费用本月,
  SUM(CASE WHEN k.科目名称 CONTAINS '销售收入' AND k.期间 = currentPeriod THEN k.`本期发生_本位币_贷` ELSE 0 END) AS 销售收入本月,
  SUM(CASE WHEN k.科目名称 CONTAINS '销售费用' AND k.期间 = lastPeriod THEN k.`本期发生_本位币_借` ELSE 0 END) AS 销售费用上月,
  SUM(CASE WHEN k.科目名称 CONTAINS '销售收入' AND k.期间 = lastPeriod THEN k.`本期发生_本位币_贷` ELSE 0 END) AS 销售收入上月,
  SUM(CASE WHEN k.科目名称 CONTAINS '销售费用' AND k.期间 = lastYearSamePeriod THEN k.`本期发生_本位币_借` ELSE 0 END) AS 销售费用去年同期,
  SUM(CASE WHEN k.科目名称 CONTAINS '销售收入' AND k.期间 = lastYearSamePeriod THEN k.`本期发生_本位币_贷` ELSE 0 END) AS 销售收入去年同期,
  SUM(CASE WHEN k.科目名称 CONTAINS '销售费用' AND k.期间 STARTS WITH currentYearPrefix THEN k.`本年累计_本位币_借` ELSE 0 END) AS 销售费用本年累计,
  SUM(CASE WHEN k.科目名称 CONTAINS '销售收入' AND k.期间 STARTS WITH currentYearPrefix THEN k.`本年累计_本位币_贷` ELSE 0 END) AS 销售收入本年累计,
  SUM(CASE WHEN k.科目名称 CONTAINS '销售费用' AND k.期间 STARTS WITH lastYearPrefix THEN k.`本年累计_本位币_借` ELSE 0 END) AS 销售费用去年累计,
  SUM(CASE WHEN k.科目名称 CONTAINS '销售收入' AND k.期间 STARTS WITH lastYearPrefix THEN k.`本年累计_本位币_贷` ELSE 0 END) AS 销售收入去年累计

// 2. 计算环比、同比、累计同比
WITH *,
  (销售费用本月 - 销售费用上月)/CASE WHEN 销售费用上月=0 THEN 1 ELSE 销售费用上月 END AS 销售费用环比,
  (销售收入本月 - 销售收入上月)/CASE WHEN 销售收入上月=0 THEN 1 ELSE 销售收入上月 END AS 销售收入环比,
  (销售费用本月 - 销售费用去年同期)/CASE WHEN 销售费用去年同期=0 THEN 1 ELSE 销售费用去年同期 END AS 销售费用同比,
  (销售收入本月 - 销售收入去年同期)/CASE WHEN 销售收入去年同期=0 THEN 1 ELSE 销售收入去年同期 END AS 销售收入同比,
  (销售费用本年累计 - 销售费用去年累计)/CASE WHEN 销售费用去年累计=0 THEN 1 ELSE 销售费用去年累计 END AS 销售费用累计同比,
  (销售收入本年累计 - 销售收入去年累计)/CASE WHEN 销售收入去年累计=0 THEN 1 ELSE 销售收入去年累计 END AS 销售收入累计同比

// 3. 比较增长率匹配情况
WITH *,
  CASE 
    WHEN (销售费用环比 * 销售收入环比 > 0) AND (销售费用同比 * 销售收入同比 > 0) THEN '匹配'
    ELSE '不匹配'
  END AS 增长率匹配情况

// 4. 输出结果
RETURN 销售费用本月, 销售收入本月,
       销售费用环比, 销售收入环比,
       销售费用同比, 销售收入同比,
       销售费用本年累计, 销售收入本年累计,
       销售费用累计同比, 销售收入累计同比,
       增长率匹配情况;
"""

result = query_neo4j(cypher)
print(result)
print("\n\n---------------------------------\n")
user_prompt = user_prompt.format(query="本月销售费用是增还是降，是否和收入匹配？", cypher=cypher, result=result)
response = llm.chat.completions.create(
    model="qwen-max-latest",
    messages=[
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_prompt},
    ],
    stream=True,
    temperature=0.7
)
for chunk in response:
    print(chunk.choices[0].delta.content, end="")
