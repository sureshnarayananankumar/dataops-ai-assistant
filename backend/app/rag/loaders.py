"""
loaders.py - Step 1 of ingestion: turn a file into plain text.

Each file becomes a list of LangChain `Document` objects. A Document is just
`page_content` (the text) + `metadata` (a dict, e.g. {"page": 3}).
PDFs give one Document per page so we can cite page numbers later.
"""
from pathlib import Path

from langchain_core.documents import Document
from pypdf import PdfReader

# .sql files are plain text too - useful for dbt models and queries.
SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".sql"}


class UnsupportedFileError(ValueError):
    pass


def load_document(path: Path) -> list[Document]:
    """Read a file and return its text as LangChain Documents."""
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if ext == ".pdf":
        return _load_pdf(path)
    return _load_text(path)


def _load_pdf(path: Path) -> list[Document]:
    reader = PdfReader(str(path))
    docs = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:  # skip empty pages (e.g. scanned images without text)
            docs.append(Document(page_content=text, metadata={"page": page_number}))
    return docs


def _load_text(path: Path) -> list[Document]:
    # utf-8 first; fall back to latin-1 so odd characters never crash the upload
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
    text = text.strip()
    return [Document(page_content=text, metadata={})] if text else []
