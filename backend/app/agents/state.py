"""
state.py - The shared "memory" that flows through the LangGraph workflow.

Every node receives the current state and returns a dict with the fields it
wants to update. LangGraph merges that dict into the state and passes it to
the next node. Think of it as a form that each step fills in.
"""
from typing import TypedDict


class RetrievedChunk(TypedDict):
    content: str
    document_id: str
    document_name: str
    page: int | None
    chunk_index: int
    score: float


class Evaluation(TypedDict):
    retrieval_relevance: float
    answer_relevant: bool
    grounded: bool
    groundedness_score: float
    passed: bool
    reason: str


class AgentState(TypedDict, total=False):
    # --- input ---
    question: str
    document_ids: list[str] | None
    # --- filled by Query Understanding ---
    intent: str                       # "question" or "summary"
    search_query: str
    # --- filled by Document Retrieval ---
    retrieved: list[RetrievedChunk]
    # --- filled by Answer Generation ---
    answer: str
    # --- filled by Answer Evaluation ---
    evaluation: Evaluation
    # --- control flow ---
    attempt: int                      # 1 on the first pass, 2 on the retry
    # --- filled by Final Response ---
    final_answer: str
    insufficient_information: bool
