"""
document_service.py - The full ingestion pipeline, used by POST /upload.

    save file -> load text (loaders.py) -> split into chunks (chunking.py)
    -> embed + store in Chroma (vector_store.py) -> record in registry

and the reverse for DELETE /documents/{id}.
"""
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.rag.chunking import split_documents
from app.rag.loaders import SUPPORTED_EXTENSIONS, UnsupportedFileError, load_document
from app.rag.vector_store import add_chunks, delete_document_chunks
from app.services import document_registry

MAX_FILE_SIZE_MB = 20


class EmptyDocumentError(ValueError):
    pass


def _safe_filename(name: str) -> str:
    """Keep only safe characters so a filename can't escape the uploads folder."""
    name = Path(name).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name) or "document"


def ingest_document(filename: str, content: bytes) -> dict:
    """Save, process and index an uploaded file. Returns the registry record."""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(
            f"Unsupported file type '{ext or 'none'}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if len(content) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise ValueError(f"File is larger than {MAX_FILE_SIZE_MB} MB.")

    document_id = uuid.uuid4().hex[:12]
    display_name = Path(filename).name
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    stored_path = settings.uploads_path / f"{document_id}_{_safe_filename(display_name)}"
    stored_path.write_bytes(content)

    try:
        pages = load_document(stored_path)
        chunks = split_documents(pages, document_id=document_id, document_name=display_name)
        if not chunks:
            raise EmptyDocumentError(
                "No text could be extracted from this file (scanned PDFs without a text layer are not supported)."
            )
        add_chunks(chunks)
    except Exception:
        stored_path.unlink(missing_ok=True)  # don't leave half-processed files behind
        raise

    record = {
        "id": document_id,
        "filename": display_name,
        "file_type": ext.lstrip("."),
        "size_bytes": len(content),
        "num_chunks": len(chunks),
        "uploaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stored_path": stored_path.name,
    }
    document_registry.add_document(record)
    return record


def delete_document(document_id: str) -> bool:
    """Delete a document's chunks, file and registry entry. False if not found."""
    record = document_registry.get_document(document_id)
    if record is None:
        return False
    delete_document_chunks(document_id)
    (settings.uploads_path / record["stored_path"]).unlink(missing_ok=True)
    document_registry.remove_document(document_id)
    return True
