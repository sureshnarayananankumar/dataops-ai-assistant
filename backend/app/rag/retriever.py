"""
retriever.py - The "R" in RAG: find the chunks most relevant to a question.

Two strategies:
  * similarity search  - normal questions ("What is a stream?")
  * first chunks of a document - for "summarize the document", where
    similarity search would only find chunks that contain the word "summary".
"""
from langchain_core.documents import Document

from app.rag.vector_store import get_vector_store


def _where(document_ids: list[str] | None) -> dict | None:
    """Build a Chroma metadata filter limiting the search to some documents."""
    if not document_ids:
        return None
    if len(document_ids) == 1:
        return {"document_id": document_ids[0]}
    return {"document_id": {"$in": document_ids}}


def search(query: str, k: int, document_ids: list[str] | None = None) -> list[tuple[Document, float]]:
    """Return up to k (chunk, relevance_score) pairs, best first. Score is ~0..1."""
    results = get_vector_store().similarity_search_with_relevance_scores(
        query, k=k, filter=_where(document_ids)
    )
    # Clamp to 0..1 so the numbers are easy to read in the UI and reports.
    return [(doc, max(0.0, min(1.0, float(score)))) for doc, score in results]


def first_chunks(document_ids: list[str] | None, limit: int) -> list[tuple[Document, float]]:
    """Return the opening chunks of the selected documents (used for summaries)."""
    data = get_vector_store().get(where=_where(document_ids), include=["documents", "metadatas"])
    docs = [
        Document(page_content=text, metadata=meta)
        for text, meta in zip(data["documents"], data["metadatas"])
    ]
    docs.sort(key=lambda d: (d.metadata.get("document_name", ""), d.metadata.get("chunk_index", 0)))
    # Spread the limit across documents so every selected document is represented.
    by_doc: dict[str, list[Document]] = {}
    for d in docs:
        by_doc.setdefault(d.metadata["document_id"], []).append(d)
    per_doc = max(1, limit // max(1, len(by_doc)))
    picked = [d for chunks in by_doc.values() for d in chunks[:per_doc]]
    # Score 1.0: these chunks were chosen on purpose, not by similarity.
    return [(d, 1.0) for d in picked[:limit]]
