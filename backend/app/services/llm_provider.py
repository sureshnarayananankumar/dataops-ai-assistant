"""
llm_provider.py - Creates the chat model (LLM) and the embedding model.

The rest of the app calls get_llm() / get_embeddings() and never needs to know
WHICH provider is behind them. Switching from Gemini to OpenAI is just a change
of LLM_PROVIDER in .env - this is called the "factory" pattern.
"""
from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import settings


class ProviderNotConfiguredError(RuntimeError):
    """Raised when the API key for the selected provider is missing."""


def _check_key() -> None:
    if not settings.api_key_configured:
        name = "GOOGLE_API_KEY" if settings.provider == "gemini" else "OPENAI_API_KEY"
        raise ProviderNotConfiguredError(
            f"{name} is not set in .env (LLM_PROVIDER={settings.provider})."
        )


@lru_cache
def get_llm() -> BaseChatModel:
    """Return the chat model. temperature=0 -> focused, repeatable answers."""
    _check_key()
    if settings.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.gemini_chat_model,
            google_api_key=settings.google_api_key,
            temperature=0,
        )
    if settings.provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.openai_chat_model,
            api_key=settings.openai_api_key,
            temperature=0,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.provider!r} (use 'gemini' or 'openai')")


@lru_cache
def get_embeddings() -> Embeddings:
    """Return the embedding model that turns text into vectors."""
    _check_key()
    if settings.provider == "gemini":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        return GoogleGenerativeAIEmbeddings(
            model=settings.gemini_embedding_model,
            google_api_key=settings.google_api_key,
        )
    if settings.provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=settings.openai_api_key,
        )
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.provider!r} (use 'gemini' or 'openai')")
