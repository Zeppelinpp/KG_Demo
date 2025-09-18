from pymilvus import MilvusClient

client = MilvusClient("http://172.20.236.27:19530")

print(client.has_collection("mapping"))