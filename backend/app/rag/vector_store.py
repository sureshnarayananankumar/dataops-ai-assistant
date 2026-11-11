"""
vector_store.py - Step 3 of ingestion: store chunks + embeddings in ChromaDB.

When we add a chunk, LangChain calls the embedding model to turn its text
into a vector, then Chroma saves (vector, text, metadata) on disk in
backend/data/chroma/. Later, a question is embedded the same way and Chroma
returns the chunks whose vectors are closest to it.
"""
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.config import settings
from app.services import llm_provider

_store: Chroma | None = None


def get_vector_store() -> Chroma:
    """Create the Chroma store once and reuse it."""
    global _store
    if _store is None:
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        _store = Chroma(
            collection_name=settings.chroma_collection,
            embedding_function=llm_provider.get_embeddings(),
            persist_directory=str(settings.chroma_path),
            # cosine distance -> relevance score = 1 - distance (roughly 0..1, higher = better)
            collection_metadata={"hnsw:space": "cosine"},
        )
    return _store


def reset_vector_store() -> None:
    """Forget the cached store (used by tests and when settings change)."""
    global _store
    _store = None


def add_chunks(chunks: list[Document]) -> None:
    if not chunks:
        return
    ids = [f"{c.metadata['document_id']}_{c.metadata['chunk_index']}" for c in chunks]
    # Small batches are gentler on free-tier embedding rate limits.
    batch = 50
    for start in range(0, len(chunks), batch):
        get_vector_store().add_documents(chunks[start : start + batch], ids=ids[start : start + batch])


def delete_document_chunks(document_id: str) -> None:
    """Remove every chunk that belongs to one document."""
    get_vector_store().delete(where={"document_id": document_id})
