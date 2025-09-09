import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

with open("config/graph_schema.md", "r") as f:
    schema = f.read()

client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
)

prompt = f"""
这是一些常见查询问句：
query_samples = [
    "xx账簿在xx期所有的应付账款发生额",
    "xx账簿在xx期应付职工薪酬支出TOP10的部门",
    "xx账簿在xx期间和xx客户的所有往来",
    "科目不包含银行存款且客户包含/不包含xx的所有完整凭证",
    "找出xx账簿xx期间所有的数外凭证",
    "xx账簿近一年/半年的银行存款支出变化",
    "xx账簿xx期间有发生额的所有明细科目余额",
    "xx账簿近一年/半年存款余额变化",
    "近一年/半年存款余额环比变化超过10%的账簿",
    "xx账簿和xx账簿在xx期间不包含xx科目的所有明细账",
    "xx账簿和xx账簿在xx期间不包含客户维度的按期间列示/按期间融合的明细账",
    "xx账簿和xx账簿在xx期间不包含xx科目，按第一维度编码排序并小计的明细账"
]

<图谱schema>
{schema}
</图谱schema>
"""
response = client.chat.completions.create(
    model="qwen-max-latest",
    messages=[
        {
            "role": "system",
            "content": f"""
你是一个ERP和财务系统专家，你可以准确分析用户的业务问题并根据图谱schema找到用户问题和schema中字段的对应关系
请严格按照以下步骤：
1. 分析图谱schema，理解图谱中节点和属性的含义
2. 分析常见问句，理解常见问句中业务词汇的含义
3. 生成一个常见问句中一些业务词汇与图谱中节点和属性名称的对应关系

以json格式输出
比如:
{{
    "账簿": ["账簿.名称"],
    "期间": ["期间.名称", "期间.年份", "期间.期数"],
    ...
}}
            """,
        },
        {"role": "user", "content": prompt},
    ],
    response_format={"type": "json_object"},
)

result = response.choices[0].message.content
print(result)
