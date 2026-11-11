"""
chunking.py - Step 2 of ingestion: split long text into small chunks.

Why chunk? An LLM prompt has limited space, and a search works better on
small focused pieces than on a 50-page document. Each chunk is ~1000
characters, overlapping the previous one by ~150 characters so a sentence
cut at a boundary still appears whole in one of the chunks.
"""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings


def split_documents(docs: list[Document], document_id: str, document_name: str) -> list[Document]:
    """Split documents into chunks and tag every chunk with where it came from."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        # Try to split on paragraphs first, then lines, then sentences, then words.
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)

    for index, chunk in enumerate(chunks):
        # This metadata is what lets us show "Source: dbt_guide.md, page 2" in the UI
        # and delete all chunks of one document later.
        chunk.metadata.update(
            {
                "document_id": document_id,
                "document_name": document_name,
                "chunk_index": index,
            }
        )
    return chunks
