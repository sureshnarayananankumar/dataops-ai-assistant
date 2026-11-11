"""
nodes.py - The steps (nodes) of the LangGraph agent.

Each node is a plain Python function:  state in  ->  dict of updates out.

    understand_query -> retrieve_documents -> generate_answer -> evaluate_answer
                              ^                                       |
                              |---- refine_query  <---- (not good enough, 1 retry)
                                                                      |
                                                              final_response
"""
import json
import re

from app.agents.prompts import (
    ANSWER_PROMPT,
    EVALUATION_PROMPT,
    INSUFFICIENT_MARKER,
    QUERY_UNDERSTANDING_PROMPT,
    REFINE_QUERY_PROMPT,
    RETRY_INSTRUCTIONS,
    SUMMARY_INSTRUCTIONS,
)
from app.agents.state import AgentState, Evaluation, RetrievedChunk
from app.config import settings
from app.rag import retriever
from app.services import llm_provider

MAX_ATTEMPTS = 2            # first try + one retry
GROUNDEDNESS_THRESHOLD = 0.7

INSUFFICIENT_MESSAGE = (
    "The uploaded documents do not contain enough information to answer this question. "
    "Try rephrasing it, or upload a document that covers this topic."
)
NO_DOCUMENTS_MESSAGE = "No documents have been uploaded yet. Upload a PDF, TXT, Markdown or SQL file first."


# ----------------------------------------------------------------- helpers
def _llm_text(prompt: str) -> str:
    """Call the LLM and return its reply as plain text."""
    message = llm_provider.get_llm().invoke(prompt)
    content = message.content
    if isinstance(content, list):  # some providers return a list of content parts
        content = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content).strip()


def _parse_json(text: str) -> dict | None:
    """LLMs sometimes wrap JSON in ```json fences or add text - extract the {...} part."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _format_context(chunks: list[RetrievedChunk]) -> str:
    """Number each chunk so the LLM can cite it as [1], [2], ..."""
    blocks = []
    for i, c in enumerate(chunks, start=1):
        where = c["document_name"] + (f", page {c['page']}" if c.get("page") else "")
        blocks.append(f"[{i}] (source: {where})\n{c['content']}")
    return "\n\n".join(blocks)


def _to_chunk(doc, score: float) -> RetrievedChunk:
    m = doc.metadata
    return {
        "content": doc.page_content,
        "document_id": m.get("document_id", ""),
        "document_name": m.get("document_name", "unknown"),
        "page": m.get("page"),
        "chunk_index": int(m.get("chunk_index", 0)),
        "score": round(score, 3),
    }


# ------------------------------------------------------------------- nodes
def understand_query(state: AgentState) -> dict:
    """Node 1 - Query Understanding: detect intent and build a better search query."""
    question = state["question"]
    intent, search_query = "question", question
    parsed = _parse_json(_llm_text(QUERY_UNDERSTANDING_PROMPT.format(question=question)))
    if parsed:
        intent = "summary" if parsed.get("intent") == "summary" else "question"
        search_query = str(parsed.get("search_query") or question).strip()
    elif re.search(r"\b(summar|overview)", question, re.IGNORECASE):
        intent = "summary"
    return {"intent": intent, "search_query": search_query, "attempt": state.get("attempt", 1)}


def retrieve_documents(state: AgentState) -> dict:
    """Node 2 - Document Retrieval (RAG): fetch the most relevant chunks from ChromaDB."""
    doc_ids = state.get("document_ids")
    attempt = state.get("attempt", 1)
    k = settings.top_k * attempt  # the retry looks at more chunks

    if state.get("intent") == "summary":
        results = retriever.first_chunks(doc_ids, limit=settings.top_k * 2)
    else:
        results = retriever.search(state["search_query"], k=k, document_ids=doc_ids)
        if attempt > 1:
            # On retry, also search with the user's original wording and merge.
            results += retriever.search(state["question"], k=k, document_ids=doc_ids)

    # Remove duplicates (same chunk found twice), keep the best score, best first.
    best: dict[str, RetrievedChunk] = {}
    for doc, score in results:
        chunk = _to_chunk(doc, score)
        key = f"{chunk['document_id']}_{chunk['chunk_index']}"
        if key not in best or chunk["score"] > best[key]["score"]:
            best[key] = chunk
    chunks = sorted(best.values(), key=lambda c: c["score"], reverse=True)[:k]
    return {"retrieved": chunks}


def generate_answer(state: AgentState) -> dict:
    """Node 3 - Answer Generation: ask the LLM to answer using only the retrieved chunks."""
    chunks = state.get("retrieved", [])
    if not chunks:
        return {"answer": INSUFFICIENT_MARKER}

    extra = []
    if state.get("intent") == "summary":
        extra.append(SUMMARY_INSTRUCTIONS)
    if state.get("attempt", 1) > 1 and state.get("evaluation"):
        extra.append(RETRY_INSTRUCTIONS.format(reason=state["evaluation"]["reason"]))

    prompt = ANSWER_PROMPT.format(
        marker=INSUFFICIENT_MARKER,
        extra_instructions="\n".join(extra),
        context=_format_context(chunks),
        question=state["question"],
    )
    return {"answer": _llm_text(prompt)}


def evaluate_answer(state: AgentState) -> dict:
    """Node 4 - Answer Evaluation: is the answer relevant and supported by the chunks?"""
    chunks = state.get("retrieved", [])
    answer = state.get("answer", "")
    retrieval_relevance = round(sum(c["score"] for c in chunks) / len(chunks), 3) if chunks else 0.0

    if not chunks or INSUFFICIENT_MARKER in answer:
        evaluation: Evaluation = {
            "retrieval_relevance": retrieval_relevance,
            "answer_relevant": False,
            "grounded": False,
            "groundedness_score": 0.0,
            "passed": False,
            "reason": "No relevant chunks found." if not chunks
            else "The model said the context does not contain the answer.",
        }
        return {"evaluation": evaluation}

    # "LLM-as-a-judge": a second LLM call reviews the first one's answer.
    verdict = _parse_json(
        _llm_text(
            EVALUATION_PROMPT.format(
                context=_format_context(chunks), question=state["question"], answer=answer
            )
        )
    )
    if verdict is None:
        # If the judge's reply can't be read we don't block the user, but we say so.
        evaluation = {
            "retrieval_relevance": retrieval_relevance,
            "answer_relevant": True,
            "grounded": True,
            "groundedness_score": 0.0,
            "passed": True,
            "reason": "Automatic evaluation unavailable - answer was not verified.",
        }
        return {"evaluation": evaluation}

    relevant = bool(verdict.get("answer_relevant", False))
    grounded = bool(verdict.get("grounded", False))
    try:
        score = max(0.0, min(1.0, float(verdict.get("groundedness_score", 0.0))))
    except (TypeError, ValueError):
        score = 0.0
    evaluation = {
        "retrieval_relevance": retrieval_relevance,
        "answer_relevant": relevant,
        "grounded": grounded,
        "groundedness_score": round(score, 2),
        "passed": relevant and grounded and score >= GROUNDEDNESS_THRESHOLD,
        "reason": str(verdict.get("reason", "")),
    }
    return {"evaluation": evaluation}


def refine_query(state: AgentState) -> dict:
    """Retry step: write an improved search query and increase the attempt counter."""
    reason = state.get("evaluation", {}).get("reason", "")
    new_query = _llm_text(
        REFINE_QUERY_PROMPT.format(
            question=state["question"], previous_query=state.get("search_query", ""), reason=reason
        )
    ).strip().strip('"')
    return {
        "search_query": new_query or state["question"],
        "attempt": state.get("attempt", 1) + 1,
        # a summary that failed is retried as a normal similarity search
        "intent": "question",
    }


def final_response(state: AgentState) -> dict:
    """Node 5 - Final Response: return the answer, or say clearly that evidence is missing."""
    evaluation = state.get("evaluation", {})
    if evaluation.get("passed"):
        return {"final_answer": state["answer"], "insufficient_information": False}
    return {"final_answer": INSUFFICIENT_MESSAGE, "insufficient_information": True}


# ------------------------------------------------------------ routing
def route_after_evaluation(state: AgentState) -> str:
    """Conditional edge: decide where to go after evaluation."""
    if state["evaluation"]["passed"]:
        return "final"
    if state.get("attempt", 1) < MAX_ATTEMPTS and state.get("retrieved"):
        return "retry"
    return "final"
