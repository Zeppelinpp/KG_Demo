import ollama

result = ollama.embed(
    model="bge-m3",
    input="江西银涛药业股份有限公司主账簿账簿在2024年3期期所有的应付账款发生额",
)
print(result)
