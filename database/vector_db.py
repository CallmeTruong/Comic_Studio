import os
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

# Tắt Telemetry của ChromaDB để tránh log rác
os.environ["CHROMA_TELEMETRY_IMPL"] = "chromadb.telemetry.dummy.DummyTelemetry"
os.environ["ANONYMIZED_TELEMETRY"] = "False"

DB_DIR = "data/chroma_db"

def get_vector_store():
    embeddings = OpenAIEmbeddings()
    vector_store = Chroma(
        collection_name="story_memory",
        embedding_function=embeddings,
        persist_directory=DB_DIR
    )
    return vector_store

def add_story_event(chapter: int, page: int, summary: str):
    store = get_vector_store()
    metadata = {"chapter": chapter, "page": page}
    store.add_texts(texts=[summary], metadatas=[metadata])

def search_past_events(query: str, k: int = 3):
    store = get_vector_store()
    results = store.similarity_search(query, k=k)
    return [{"text": doc.page_content, "metadata": doc.metadata} for doc in results]
