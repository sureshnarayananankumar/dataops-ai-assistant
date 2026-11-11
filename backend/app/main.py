"""
main.py - Entry point of the FastAPI backend.

Run from the backend/ folder:
    uvicorn app.main:app --reload --port 8000

It creates the FastAPI `app`, enables CORS so the React frontend
(a different origin: localhost:5173) may call it, makes sure the data
folders exist, and registers the API routes from app/api/routes.py.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup (before `yield`) and once at shutdown (after)."""
    settings.uploads_path.mkdir(parents=True, exist_ok=True)
    settings.chroma_path.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="DataOps AI Assistant",
    description="Agentic RAG assistant for DataOps documentation (FastAPI + LangChain + LangGraph).",
    version="1.0.0",
)

# CORS: browsers block calls to a different origin unless the server allows it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All endpoints (/health, /upload, /documents, /chat) live in the router.
app.include_router(router)
