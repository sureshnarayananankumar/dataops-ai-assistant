"""
schemas.py - The "shape" of data going in and out of the API.

Pydantic models validate incoming JSON (e.g. a chat question must be a
non-empty string) and document the responses on the /docs page.
React reads exactly these field names.
"""
from pydantic import BaseModel, Field


class DocumentInfo(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int
    num_chunks: int
    uploaded_at: str


class UploadResponse(BaseModel):
    message: str
    document: DocumentInfo


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, examples=["What is a DBT incremental model?"])
    # Optional: only search these documents. Empty/None = search all documents.
    document_ids: list[str] | None = None


class Source(BaseModel):
    ref: int                        # matches the [1], [2] citation numbers in the answer
    document_id: str
    document_name: str
    page: int | None = None
    chunk_index: int
    relevance_score: float
    snippet: str


class EvaluationResult(BaseModel):
    retrieval_relevance: float      # 0-1, how similar retrieved chunks are to the question
    answer_relevant: bool           # does the answer address the question? (LLM judge)
    grounded: bool                  # is the answer supported by the chunks? (LLM judge)
    groundedness_score: float       # 0-1 (LLM judge)
    passed: bool
    reason: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    insufficient_information: bool
    attempts: int                   # 1 = first try worked, 2 = a retry was needed
    search_query: str               # the query the agent actually searched with
    evaluation: EvaluationResult | None = None
