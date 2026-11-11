"""
document_registry.py - Keeps a list of uploaded documents in a small JSON file.

ChromaDB stores the *chunks*; this registry stores one record per *document*
(name, size, number of chunks, upload time) so the sidebar can list them
quickly. A real product would use a database table; a JSON file keeps this
project simple.
"""
import json
import threading
from pathlib import Path

from app.config import settings

_lock = threading.Lock()  # stops two requests writing the file at the same time


def _registry_file() -> Path:
    return settings.data_path / "documents.json"


def _read() -> dict[str, dict]:
    path = _registry_file()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write(data: dict[str, dict]) -> None:
    path = _registry_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def list_documents() -> list[dict]:
    """All documents, newest first."""
    with _lock:
        docs = list(_read().values())
    return sorted(docs, key=lambda d: d["uploaded_at"], reverse=True)


def get_document(document_id: str) -> dict | None:
    with _lock:
        return _read().get(document_id)


def add_document(record: dict) -> None:
    with _lock:
        data = _read()
        data[record["id"]] = record
        _write(data)


def remove_document(document_id: str) -> dict | None:
    with _lock:
        data = _read()
        record = data.pop(document_id, None)
        _write(data)
    return record
