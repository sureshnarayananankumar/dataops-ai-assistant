"""
prompts.py - All instructions we send to the LLM, kept in one place.

Keeping prompts separate from code makes them easy to read, compare and
improve - "prompt engineering" is a big part of building LLM apps.
"""

INSUFFICIENT_MARKER = "INSUFFICIENT_CONTEXT"

QUERY_UNDERSTANDING_PROMPT = """You help search technical DataOps documentation \
(dbt, Snowflake, SQL, data pipelines).

Analyse the user's question and reply with ONLY a JSON object, no other text:
{{"intent": "summary" or "question",
  "search_query": "a short, keyword-rich search query for a vector database"}}

Use intent "summary" only when the user asks to summarize / give an overview of the
uploaded document(s). Otherwise use "question".
Expand abbreviations and add useful synonyms to the search query
(e.g. "CDC" -> "change data capture streams").

User question: {question}"""

ANSWER_PROMPT = """You are a DataOps assistant. Answer the question using ONLY the
context below, which comes from the user's uploaded documents.

Rules:
- Use only facts found in the context. Do not use outside knowledge.
- Cite the context blocks you used with their numbers, e.g. [1] or [2][3].
- Be clear and concise. Use short paragraphs or bullet points.
- If the context does not contain enough information to answer, reply with
  exactly: {marker}
{extra_instructions}
Context:
{context}

Question: {question}

Answer:"""

SUMMARY_INSTRUCTIONS = """- The user wants a summary: describe the main topics and key points of the
  document(s) in the context, citing the blocks."""

RETRY_INSTRUCTIONS = """- IMPORTANT: a previous answer was rejected by a reviewer for this reason:
  "{reason}". Be stricter: only state what the context explicitly supports."""

EVALUATION_PROMPT = """You are a strict reviewer checking an AI answer against its source context.

Context:
{context}

Question: {question}

Answer to review:
{answer}

Fields:
- answer_relevant: true if the answer addresses the question.
- grounded: true if every factual claim in the answer is supported by the context.
- groundedness_score: number from 0.0 to 1.0, the fraction of claims supported by the context.
- reason: one short sentence explaining your verdict.

Reply with ONLY a JSON object, no other text, for example:
{{"answer_relevant": true, "grounded": true, "groundedness_score": 0.9, "reason": "..."}}"""

REFINE_QUERY_PROMPT = """A search of technical documentation did not find enough evidence
to answer a question. Write ONE better search query: use different wording, synonyms
and the key technical terms. Reply with ONLY the query text.

Question: {question}
Previous search query: {previous_query}
Reviewer feedback: {reason}"""
