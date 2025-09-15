from llama_index.core import Settings
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import SimpleDirectoryReader
from llama_index.core import VectorStoreIndex
from llama_index.vector_stores.milvus import MilvusVectorStore
from llama_index.core import StorageContext


Settings.embed_model = OllamaEmbedding(model_name="bge-m3")
documents = SimpleDirectoryReader("/Users/ruipu/projects/KG_Demo/knowledge").load_data()
vector_store = MilvusVectorStore(
    uri="/Users/ruipu/projects/KG_Demo/milvus.db", dim=1024, overwrite=True
)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_documents(
    documents, storage_context=storage_context, show_progress=True
)
index.storage_context.persist(persist_dir="knowledge")
retriever = index.as_retriever(similarity_top_k=20)
docs = retriever.retrieve("销售费用整体分析")
for doc in docs:
    print(doc.text)