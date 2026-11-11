"""
conftest.py - Shared pytest setup.

Tests must be fast, free and repeatable, so they NEVER call a real AI provider.
Instead we plug in:
  * FakeEmbeddings - a tiny bag-of-words embedding (texts sharing words are "similar")
  * RuleBasedFakeLLM - returns predictable replies depending on which prompt it gets
and point all data (uploads, Chroma, registry) at a temporary folder.
"""
import hashlib
import math
import re

import pytest
from fastapi.testclient import TestClient
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.agents.prompts import INSUFFICIENT_MARKER
from app.config import settings
from app.rag import vector_store
from app.services import llm_provider

DIM = 256
STOPWORDS = {"what", "is", "a", "the", "how", "can", "i", "of", "and", "to", "in", "does", "do", "are", "explain"}


def _words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in STOPWORDS]


class FakeEmbeddings(Embeddings):
    """Hash each word into one of 256 buckets -> normalized count vector."""

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for w in _words(text):
            vec[int(hashlib.md5(w.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts):
        return [self._embed(t) for t in texts]

    def embed_query(self, text):
        return self._embed(text)


class RuleBasedFakeLLM(BaseChatModel):
    """Answers by looking at which of our prompts it received."""

    judge_grounded: bool = True  # tests can flip this to simulate an unsupported answer
    calls: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "rule-based-fake"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        prompt = messages[-1].content
        self.calls.append(prompt)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self._reply(prompt)))])

    def _reply(self, prompt: str) -> str:
        if "Analyse the user's question" in prompt:
            question = prompt.split("User question:")[-1].strip()
            intent = "summary" if "summar" in question.lower() else "question"
            return f'```json\n{{"intent": "{intent}", "search_query": "{question}"}}\n```'
        if "strict reviewer" in prompt:
            g = "true" if self.judge_grounded else "false"
            score = 0.95 if self.judge_grounded else 0.2
            return f'{{"answer_relevant": true, "grounded": {g}, "groundedness_score": {score}, "reason": "fake judge"}}'
        if "did not find enough evidence" in prompt:
            return "improved search query"
        if "The user wants a summary" in prompt:
            return "The document covers Snowflake streams and tasks [1]."
        # Answer prompt: answer only if a question keyword appears in the context.
        question = re.search(r"Question: (.*)\n\nAnswer:", prompt, re.DOTALL).group(1)
        context = prompt.split("Context:")[-1].split("Question:")[0].lower()
        keywords = [w for w in _words(question) if len(w) > 4]
        if any(k in context for k in keywords):
            return "Based on the documents, here is the answer [1]."
        return INSUFFICIENT_MARKER


@pytest.fixture
def fake_llm():
    return RuleBasedFakeLLM(calls=[])


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch, fake_llm):
    """Every test gets an empty data folder and the fake models."""
    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "chroma_collection", f"test_{tmp_path.name}"[:60])
    monkeypatch.setattr(settings, "chunk_size", 300)
    monkeypatch.setattr(settings, "chunk_overlap", 30)
    monkeypatch.setattr(llm_provider, "get_llm", lambda: fake_llm)
    monkeypatch.setattr(llm_provider, "get_embeddings", lambda: FakeEmbeddings())
    vector_store.reset_vector_store()
    yield
    vector_store.reset_vector_store()


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


DBT_TEXT = """# dbt incremental models

An incremental model in dbt only processes new or changed rows since the last run,
instead of rebuilding the whole table. Use the is_incremental() macro to filter rows.
Configure it with materialized='incremental' and a unique_key for merges.
"""

SNOWFLAKE_TEXT = """Snowflake streams record change data capture (CDC) information:
inserts, updates and deletes made to a table. Snowflake tasks run SQL on a schedule.
Combine streams and tasks to build continuous ELT pipelines.
"""
