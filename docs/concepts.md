# Key Concepts – Explained With This Project

## What is an LLM?

A **Large Language Model** is an AI model trained on huge amounts of text to predict the next words.
That lets it explain, summarize and answer questions. It only knows what it learned during training
and what you put in the prompt – it does not know your company's dbt project.
*Here:* Gemini 2.5 Flash writes the answers (`services/llm_provider.py → get_llm()`).

## What is RAG?

**Retrieval-Augmented Generation** = first *retrieve* relevant text from your documents, then let the
LLM *generate* an answer from that text. It reduces made-up answers ("hallucinations") and lets the
model use private, up-to-date documents without retraining.
*Here:* `rag/retriever.py` finds chunks, `agents/nodes.py → generate_answer` puts them in the prompt.

## What are embeddings?

An **embedding** is a list of numbers (a vector, e.g. 3072 numbers) representing the *meaning* of a
text. Similar meanings → vectors that point in similar directions. "CDC in Snowflake" and "streams
track table changes" get close vectors even with different words.
*Here:* `get_embeddings()` creates them; every chunk and every question is embedded.

## What is a vector database?

A database built to store vectors and quickly find the **nearest** ones to a query vector
("similarity search"). It also stores the original text and metadata.
*Here:* **ChromaDB** saves chunks in `backend/data/chroma/` with metadata
`document_id`, `document_name`, `page`, `chunk_index` (used for sources and deletes).

## What is chunking and why?

Documents are split into ~1000-character pieces with ~150 characters of overlap. Small chunks give
precise search results and fit in the prompt; overlap avoids cutting an idea in half.
*Here:* `rag/chunking.py` (RecursiveCharacterTextSplitter).

## What is LangChain?

A Python library of building blocks for LLM apps: model wrappers (`ChatGoogleGenerativeAI`),
document objects, text splitters, vector store integrations (`Chroma`). It lets us swap Gemini for
OpenAI by changing one setting.

## What is an AI agent? What is Agentic AI?

A plain LLM app makes one call: prompt in, text out. An **agent** runs a *process*: several steps,
shared memory (state), and **decisions** about what to do next. **Agentic AI** means building
systems this way.
*Here:* after answering, the agent *checks itself* and *decides* whether to finish or retry with a
better search – that decision is what makes it agentic.

## What is LangGraph?

A library for building agents as a **graph**:

- **State** – a shared dictionary (`agents/state.py`: question, chunks, answer, evaluation, attempt…).
- **Nodes** – Python functions that read the state and return updates (`agents/nodes.py`).
- **Edges** – arrows between nodes; **conditional edges** pick the next node at runtime
  (`route_after_evaluation` returns `"final"` or `"retry"`).

LangGraph makes loops, retries and branching explicit and testable.

## What is LLM evaluation?

Measuring answer quality in a repeatable way: a fixed set of questions with expected answers, plus
metrics (retrieval hit rate, groundedness, keyword coverage…). **LLM-as-a-judge** uses a second LLM
call to grade an answer. It is useful but imperfect – see the limitations in the README.
*Here:* live check per answer in `evaluate_answer`, offline suite in `app/evaluation/`.

## How does React talk to FastAPI?

React runs in the browser (`localhost:5173`), FastAPI runs in Python (`localhost:8000`). They talk
over **HTTP with JSON**:

1. You click *Send* → `ChatInput` calls `onSend` → `ChatPage.handleAsk`.
2. `services/api.js → askQuestion()` runs `fetch("http://localhost:8000/chat", {method: "POST", body: JSON})`.
3. FastAPI validates the body with `ChatRequest` (`api/schemas.py`), runs the agent, returns `ChatResponse` as JSON.
4. React stores it in state → `MessageBubble` and `SourceList` re-render.

Because the two run on different ports (different "origins"), the browser requires **CORS**
permission – configured in `main.py` with `CORSMiddleware`.
