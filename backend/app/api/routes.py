"""
routes.py - All HTTP endpoints. They stay thin: validate input, call a
service or the agent, and convert the result into a response schema.

    GET    /health                  -> is the backend up and configured?
    POST   /upload                  -> document_service.ingest_document()
    GET    /documents               -> document_registry.list_documents()
    DELETE /documents/{document_id} -> document_service.delete_document()
    POST   /chat                    -> agents.graph.run_agent()
"""
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.agents.graph import run_agent
from app.api.schemas import ChatRequest, ChatResponse, DocumentInfo, Source, UploadResponse
from app.config import settings
from app.rag.loaders import UnsupportedFileError
from app.services import document_registry, document_service
from app.services.llm_provider import ProviderNotConfiguredError

logger = logging.getLogger(__name__)
router = APIRouter()


def _llm_error(exc: Exception) -> HTTPException:
    """Turn provider errors (bad key, rate limit, network) into a readable 502."""
    logger.exception("LLM provider error")
    text = str(exc)
    if "429" in text or "quota" in text.lower() or "rate" in text.lower():
        hint = "The AI provider's rate limit was reached. Wait a minute and try again."
    else:
        hint = f"The AI provider returned an error: {text[:300]}"
    return HTTPException(status_code=502, detail=hint)


@router.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "llm_provider": settings.provider,
        "chat_model": settings.chat_model,
        "embedding_model": settings.embedding_model,
        "api_key_configured": settings.api_key_configured,
        "documents": len(document_registry.list_documents()),
    }


@router.post("/upload", response_model=UploadResponse, tags=["documents"])
async def upload(file: UploadFile = File(...)) -> UploadResponse:
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    try:
        # Embedding calls are slow, blocking work -> run them off the event loop.
        record = await run_in_threadpool(document_service.ingest_document, file.filename or "document", content)
    except (UnsupportedFileError, document_service.EmptyDocumentError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:  # provider / network problems while embedding
        raise _llm_error(exc)
    return UploadResponse(
        message=f"'{record['filename']}' processed into {record['num_chunks']} chunks.",
        document=DocumentInfo(**record),
    )


@router.get("/documents", response_model=list[DocumentInfo], tags=["documents"])
def list_documents() -> list[DocumentInfo]:
    return [DocumentInfo(**d) for d in document_registry.list_documents()]


@router.delete("/documents/{document_id}", tags=["documents"])
def delete_document(document_id: str) -> dict:
    if not document_service.delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": "Document deleted.", "document_id": document_id}


@router.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(request: ChatRequest) -> ChatResponse:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")
    try:
        state = await run_in_threadpool(run_agent, question, request.document_ids)
    except ProviderNotConfiguredError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        raise _llm_error(exc)

    sources = [
        Source(
            ref=i,
            document_id=c["document_id"],
            document_name=c["document_name"],
            page=c.get("page"),
            chunk_index=c["chunk_index"],
            relevance_score=c["score"],
            snippet=c["content"][:300] + ("..." if len(c["content"]) > 300 else ""),
        )
        for i, c in enumerate(state.get("retrieved", []), start=1)
    ]
    return ChatResponse(
        answer=state["final_answer"],
        sources=sources,
        insufficient_information=state.get("insufficient_information", False),
        attempts=state.get("attempt", 1),
        search_query=state.get("search_query", question),
        evaluation=state.get("evaluation"),
    )
