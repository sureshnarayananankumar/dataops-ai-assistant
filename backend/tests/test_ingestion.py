"""Tests for loading, chunking, uploading, listing and deleting documents."""
from pathlib import Path

import pytest

from app.rag.chunking import split_documents
from app.rag.loaders import UnsupportedFileError, load_document
from app.rag.retriever import search

from tests.conftest import DBT_TEXT, SNOWFLAKE_TEXT


def test_load_markdown_file(tmp_path: Path):
    f = tmp_path / "guide.md"
    f.write_text(DBT_TEXT, encoding="utf-8")
    docs = load_document(f)
    assert len(docs) == 1
    assert "incremental" in docs[0].page_content


def test_unsupported_extension_is_rejected(tmp_path: Path):
    f = tmp_path / "image.png"
    f.write_bytes(b"\x89PNG")
    with pytest.raises(UnsupportedFileError):
        load_document(f)


def test_chunks_carry_source_metadata(tmp_path: Path):
    f = tmp_path / "long.txt"
    f.write_text(DBT_TEXT * 5, encoding="utf-8")
    chunks = split_documents(load_document(f), document_id="abc", document_name="long.txt")
    assert len(chunks) > 1
    assert all(c.metadata["document_id"] == "abc" for c in chunks)
    assert [c.metadata["chunk_index"] for c in chunks] == list(range(len(chunks)))


def test_upload_list_and_delete(client):
    r = client.post("/upload", files={"file": ("dbt.md", DBT_TEXT.encode(), "text/markdown")})
    assert r.status_code == 200, r.text
    doc = r.json()["document"]
    assert doc["filename"] == "dbt.md" and doc["num_chunks"] >= 1

    listed = client.get("/documents").json()
    assert [d["id"] for d in listed] == [doc["id"]]

    assert client.delete(f"/documents/{doc['id']}").status_code == 200
    assert client.get("/documents").json() == []
    assert client.delete(f"/documents/{doc['id']}").status_code == 404


def test_upload_rejects_bad_type_and_empty_file(client):
    assert client.post("/upload", files={"file": ("x.exe", b"abc", "application/octet-stream")}).status_code == 400
    assert client.post("/upload", files={"file": ("empty.txt", b"", "text/plain")}).status_code == 400


def test_retrieval_finds_the_right_document(client):
    client.post("/upload", files={"file": ("dbt.md", DBT_TEXT.encode(), "text/markdown")})
    client.post("/upload", files={"file": ("snowflake.txt", SNOWFLAKE_TEXT.encode(), "text/plain")})
    results = search("snowflake streams tasks", k=1)
    assert results[0][0].metadata["document_name"] == "snowflake.txt"


def test_deleted_document_is_not_retrieved(client):
    r = client.post("/upload", files={"file": ("snowflake.txt", SNOWFLAKE_TEXT.encode(), "text/plain")})
    client.delete(f"/documents/{r.json()['document']['id']}")
    client.post("/upload", files={"file": ("dbt.md", DBT_TEXT.encode(), "text/markdown")})
    names = {d.metadata["document_name"] for d, _ in search("snowflake streams", k=5)}
    assert names == {"dbt.md"}
