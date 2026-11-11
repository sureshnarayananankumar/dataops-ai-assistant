"""
check_llm.py - Quick check that your API key, chat model and embedding model work.

Run from the backend/ folder (with the virtual environment active):
    python -m scripts.check_llm
"""
from app.config import settings
from app.services.llm_provider import get_embeddings, get_llm

print(f"Provider: {settings.provider} | chat: {settings.chat_model} | embeddings: {settings.embedding_model}")

reply = get_llm().invoke("In one short sentence, what is a data pipeline?")
print("Chat model reply:", reply.content)

vector = get_embeddings().embed_query("What is a DBT incremental model?")
print(f"Embedding OK: got a vector of {len(vector)} numbers, first 3 = {vector[:3]}")
