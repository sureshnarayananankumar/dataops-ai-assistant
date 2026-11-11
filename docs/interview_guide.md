# Interview Guide – DataOps AI Assistant

## 30-second pitch

"I built a DataOps AI Assistant: users upload technical docs – dbt guides, Snowflake notes, SQL,
runbooks – and ask questions. It uses RAG with ChromaDB to find the relevant passages and a
LangGraph agent that understands the query, retrieves, answers, and then **evaluates its own answer
for groundedness**. If the answer isn't supported, it retries once with a refined query; if evidence
is still missing, it tells the user honestly instead of hallucinating. Every answer shows its
sources. Backend is FastAPI, frontend is React, and I added a test suite plus an evaluation report."

## 2-minute walkthrough

1. **Ingestion** – upload → text extraction (pypdf for PDFs, page numbers kept) → recursive chunking
   (1000 chars, 150 overlap) → embeddings → ChromaDB with metadata (document id/name, page, chunk index).
2. **Agent (LangGraph)** – typed state flowing through nodes:
   Query Understanding (intent + rewritten search query) → Retrieval (top-k cosine similarity, or
   first chunks for summaries) → Generation (context-only prompt with numbered citations and an
   explicit "insufficient context" escape) → Evaluation (LLM judge: relevance, groundedness score)
   → conditional edge: final, or Refine Query → retrieve again with 2× k and a stricter prompt.
3. **API** – FastAPI endpoints `/upload`, `/documents`, `/documents/{id}`, `/chat`, `/health`;
   Pydantic schemas; slow LLM work runs in a thread pool; provider errors become readable 502s.
4. **Frontend** – React + Vite; one `api.js` service layer; sidebar to upload/select/delete docs;
   chat with citations, evaluation badge and collapsible sources.
5. **Quality** – pytest suite with fake LLM/embeddings (deterministic, free, no network) and an
   offline evaluation over a labelled dataset including unanswerable questions.

## Design decisions you can defend

| Decision | Why |
|---|---|
| LangGraph instead of a single chain | Retry loop and branching are explicit, inspectable and unit-testable. |
| Self-evaluation + one retry | Catches unsupported answers; capped at one retry to control latency and cost. |
| Explicit "insufficient information" path | In DataOps, a confident wrong answer about a pipeline is worse than "I don't know". |
| Metadata on every chunk | Enables citations, per-document filtering and clean deletes. |
| Provider factory (`llm_provider.py`) | Swap Gemini/OpenAI via `.env`; tests inject fakes in one place. |
| Cosine distance in Chroma | Gives an interpretable 0–1 relevance score for UI and evaluation. |
| Separate eval storage | Evaluation never touches the user's documents. |
| JSON registry instead of SQL DB | Keeps the project small; easy to swap for SQLite/Postgres later. |

## Likely questions and good answers

- **How do you reduce hallucinations?** Context-only prompt, required citations, an explicit
  "insufficient context" output, an LLM-judge groundedness check, a retry, and an honest fallback.
- **How do you know it works?** Automated tests for the logic, plus an evaluation report:
  retrieval hit rate, groundedness, keyword coverage, similarity to reference answers, and whether
  unanswerable questions are refused. I'm clear these are signals, not guarantees – the judge can be
  wrong, so I'd add human review and a larger dataset.
- **What are the weaknesses?** LLM judge reliability; pure vector search misses exact identifiers
  (hybrid BM25 would help); no conversation memory; free-tier rate limits; single-user local storage.
- **How would you scale it?** Server-hosted vector DB, background ingestion queue, streaming
  responses, caching of embeddings, auth, tracing (LangSmith), and CI running tests + evals.
- **Why chunk overlap?** So a fact split across a boundary is still complete in at least one chunk.
- **What happens if you change the embedding model?** Old vectors become incompatible; re-index.
