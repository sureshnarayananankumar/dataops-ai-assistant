// demoBackend.js - an in-browser stand-in for the FastAPI backend, used by the
// live demo on GitHub Pages (no server, no API key).
//
// It mirrors the real LangGraph workflow step by step:
//   understand_query -> retrieve_documents -> generate_answer -> evaluate_answer
//          ^                                                        |
//          |------------- refine_query (1 retry) <-------------------|
//                                                                    v
//                                                             final_response
//
// What is different from the real backend (and why):
//   * Embeddings  -> TF-IDF cosine similarity (no embedding API in the browser)
//   * Generation  -> extractive: the best-matching sentences, each cited [n]
//   * LLM judge   -> a deterministic check of how much of the question the
//                    cited sentences cover
// The response JSON has exactly the same shape as the real /chat endpoint.
import { SAMPLE_DOCUMENTS } from "./sampleDocuments.js";

const CHUNK_SIZE = 1000;
const CHUNK_OVERLAP = 150;
const TOP_K = 4;
const MAX_ATTEMPTS = 2;
const MIN_COVERAGE = 0.5;

const INSUFFICIENT_MESSAGE =
  "The uploaded documents do not contain enough information to answer this question. " +
  "Try rephrasing it, or upload a document that covers this topic.";
const NO_DOCUMENTS_MESSAGE = "No documents have been uploaded yet. Upload a PDF, TXT, Markdown or SQL file first.";

const STOP = new Set(
  ("a an the is are was were be been of to in on for and or with by as at from it this that these those what which who how why " +
    "when where do does did can could should would will i you we they my your our their me us explain tell describe about " +
    "please give show list there use used using into than then also any some more most such its it's not no yes")
    .split(" ")
);

// Small domain synonym map used by the retry step to broaden the search.
const SYNONYMS = {
  fail: ["error", "failure", "troubleshoot", "debug"],
  failed: ["error", "failure", "troubleshoot"],
  troubleshoot: ["error", "debug", "failure", "fix"],
  broken: ["error", "failure"],
  slow: ["performance", "warehouse", "timeout"],
  incremental: ["is_incremental", "merge", "unique_key"],
  staging: ["stg", "layer", "raw", "clean"],
  layer: ["staging", "marts", "intermediate"],
  stream: ["streams", "change", "cdc"],
  task: ["tasks", "schedule"],
  quality: ["test", "tests", "checklist", "null", "unique"],
  test: ["tests", "unique", "not_null", "accepted_values"],
  freshness: ["warn_after", "error_after", "source"],
  duplicate: ["unique", "primary", "key"],
};

const tokenize = (text) =>
  (text.toLowerCase().match(/[a-z0-9_]+/g) || [])
    .map((w) => (w.length > 4 && w.endsWith("s") && !w.endsWith("ss") ? w.slice(0, -1) : w))
    .filter((w) => w.length > 1 && !STOP.has(w));

// ------------------------------------------------------------------ store
let documents = [];   // DocumentInfo-shaped records
let chunks = [];      // { content, document_id, document_name, page, chunk_index, tokens }
let idf = new Map();
let seeded = false;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function splitText(text) {
  // Simplified RecursiveCharacterTextSplitter: paragraphs first, then hard split.
  const parts = [];
  let current = "";
  for (const para of text.split(/\n{2,}/)) {
    if ((current + "\n\n" + para).length <= CHUNK_SIZE) {
      current = current ? `${current}\n\n${para}` : para;
    } else {
      if (current) parts.push(current);
      if (para.length <= CHUNK_SIZE) current = para;
      else {
        for (let i = 0; i < para.length; i += CHUNK_SIZE - CHUNK_OVERLAP) parts.push(para.slice(i, i + CHUNK_SIZE));
        current = "";
      }
    }
  }
  if (current) parts.push(current);
  // carry a small overlap between neighbouring chunks
  // Carry a small overlap between neighbouring chunks, starting at a line or sentence boundary.
  const overlapOf = (prev) => {
    const tail = prev.slice(-CHUNK_OVERLAP);
    const cut = tail.search(/(?<=[.!?])\s|\n/);
    return cut >= 0 ? tail.slice(cut).trim() : "";
  };
  return parts.map((p, i) => (i > 0 && overlapOf(parts[i - 1]) ? overlapOf(parts[i - 1]) + "\n\n" + p : p)).filter((p) => p.trim());
}

function rebuildIndex() {
  const df = new Map();
  for (const c of chunks) for (const t of new Set(c.tokens)) df.set(t, (df.get(t) || 0) + 1);
  idf = new Map([...df].map(([t, n]) => [t, Math.log(1 + chunks.length / n)]));
}

function vector(tokens) {
  const tf = new Map();
  for (const t of tokens) tf.set(t, (tf.get(t) || 0) + 1);
  const v = new Map();
  let norm = 0;
  for (const [t, n] of tf) {
    const w = (1 + Math.log(n)) * (idf.get(t) || 0);
    if (w) { v.set(t, w); norm += w * w; }
  }
  return { v, norm: Math.sqrt(norm) || 1 };
}

function cosine(a, b) {
  let dot = 0;
  for (const [t, w] of a.v) if (b.v.has(t)) dot += w * b.v.get(t);
  return dot / (a.norm * b.norm);
}

function ingest(filename, pages, sizeBytes) {
  const id = `demo-${Math.random().toString(36).slice(2, 10)}`;
  let index = 0;
  for (const { page, text } of pages) {
    for (const content of splitText(text)) {
      chunks.push({ content, document_id: id, document_name: filename, page, chunk_index: index++, tokens: tokenize(content) });
    }
  }
  const record = {
    id,
    filename,
    file_type: filename.split(".").pop().toLowerCase(),
    size_bytes: sizeBytes,
    num_chunks: index,
    uploaded_at: new Date().toISOString(),
  };
  documents.push(record);
  rebuildIndex();
  return record;
}

function seed() {
  if (seeded) return;
  seeded = true;
  for (const d of SAMPLE_DOCUMENTS) ingest(d.filename, d.pages, d.size_bytes);
}

// ------------------------------------------------------------------ agent nodes
function understandQuery(question) {
  const intent = /\b(summar|overview)/i.test(question) ? "summary" : "question";
  return { intent, search_query: tokenize(question).join(" ") || question };
}

function retrieve(state) {
  const k = TOP_K * state.attempt;
  const pool = chunks.filter((c) => !state.document_ids || state.document_ids.includes(c.document_id));
  if (state.intent === "summary") {
    return pool.filter((c) => c.chunk_index === 0).slice(0, TOP_K * 2).map((c) => ({ ...c, score: 1 }));
  }
  const q = vector(tokenize(state.search_query));
  return pool
    .map((c) => ({ ...c, score: Math.round(cosine(q, vector(c.tokens)) * 1000) / 1000 }))
    .filter((c) => c.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, k);
}

function sentencesOf(text) {
  // Re-join hard-wrapped lines, keep list items / headings as their own units,
  // then split into sentences. Headings and titles are not used as answers.
  const units = [];
  for (const para of text.replace(/```[\s\S]*?```/g, " ").split(/\n\s*\n/)) {
    let buf = "";
    for (const raw of para.split("\n")) {
      const line = raw.trim();
      if (!line) continue;
      if (/^#/.test(line)) { if (buf) units.push(buf); buf = ""; continue; } // heading
      if (/^([-*]|\d+[.)])\s+/.test(line)) { if (buf) units.push(buf); buf = line.replace(/^([-*]|\d+[.)])\s+/, ""); continue; }
      buf = buf ? `${buf} ${line}` : line;
    }
    if (buf) units.push(buf);
  }
  return units
    .flatMap((u) => u.split(/(?<=[.!?])\s+(?=[A-Z`*"(])/))
    .map((s) => s.trim().replace(/^[A-Z0-9 \-–:]{8,}\s(?=[A-Z][a-z])/, ""))
    .map((s) => ((s.match(/\*\*/g) || []).length % 2 ? s.replace(/\*\*/g, "") : s))
    .filter((s) => s.length > 30 && /[a-z]/.test(s) && (/[.!?:)]$/.test(s) || s.length > 80) && s !== s.toUpperCase());
}

function generate(state, retrieved) {
  if (!retrieved.length) return { answer: null, used: [] };
  const qTerms = new Set(tokenize(state.question).concat(tokenize(state.search_query)));
  const scored = [];
  retrieved.forEach((c, i) => {
    for (const s of sentencesOf(c.content)) {
      const hits = tokenize(s).filter((t) => qTerms.has(t));
      if (state.intent === "summary" || hits.length) scored.push({ s, ref: i + 1, hits: new Set(hits), score: hits.length + c.score });
    }
  });
  scored.sort((a, b) => b.score - a.score);
  const picked = [];
  const seen = new Set();
  for (const x of scored) {
    if (seen.has(x.s)) continue;
    seen.add(x.s);
    picked.push(x);
    if (picked.length >= (state.intent === "summary" ? 5 : 4)) break;
  }
  if (!picked.length) return { answer: null, used: [] };
  const lines = picked.map((x) => `- ${x.s} [${x.ref}]`);
  const lead = state.intent === "summary" ? "Here is a summary of the documents:" : "Based on the documents:";
  return { answer: `${lead}\n${lines.join("\n")}`, used: picked };
}

function evaluate(state, retrieved, gen) {
  const retrieval_relevance = retrieved.length
    ? Math.round((retrieved.reduce((s, c) => s + c.score, 0) / retrieved.length) * 1000) / 1000
    : 0;
  if (!gen.answer) {
    return { retrieval_relevance, answer_relevant: false, grounded: false, groundedness_score: 0, passed: false,
      reason: retrieved.length ? "No sentence in the retrieved chunks addresses the question." : "No relevant chunks found." };
  }
  const q = new Set(tokenize(state.question));
  const covered = new Set();
  gen.used.forEach((u) => u.hits.forEach((t) => q.has(t) && covered.add(t)));
  const coverage = state.intent === "summary" ? 1 : q.size ? covered.size / q.size : 0;
  const passed = coverage >= MIN_COVERAGE;
  return {
    retrieval_relevance,
    answer_relevant: passed,
    grounded: true, // every sentence is quoted from a retrieved chunk
    groundedness_score: Math.round(Math.min(1, 0.55 + coverage * 0.45) * 100) / 100,
    passed,
    reason: passed
      ? `Every sentence is quoted from a cited chunk; the answer covers ${Math.round(coverage * 100)}% of the question's key terms.`
      : `The cited sentences cover only ${Math.round(coverage * 100)}% of the question's key terms.`,
  };
}

function refine(state) {
  const extra = tokenize(state.question).flatMap((t) => SYNONYMS[t] || []);
  return { ...state, attempt: state.attempt + 1, intent: "question", search_query: [state.search_query, ...extra].join(" ") };
}

// ------------------------------------------------------------------ API (same shapes as FastAPI)
export async function getHealth() {
  seed();
  return { status: "ok", llm_provider: "demo", chat_model: "in-browser extractive RAG", embedding_model: "TF-IDF",
    api_key_configured: true, documents: documents.length, demo: true };
}

export async function listDocuments() {
  seed();
  return documents.map(({ ...d }) => d);
}

export async function uploadDocument(file) {
  seed();
  await sleep(500);
  const ext = file.name.split(".").pop().toLowerCase();
  if (ext === "pdf") throw new Error("PDF upload needs the full backend. In the live demo, upload a .md, .txt or .sql file.");
  if (!["md", "txt", "sql"].includes(ext)) throw new Error(`Unsupported file type '.${ext}'. Use PDF, TXT, Markdown or SQL.`);
  if (file.size > 2 * 1024 * 1024) throw new Error("The live demo accepts files up to 2 MB.");
  const text = await file.text();
  if (!text.trim()) throw new Error("The uploaded file is empty.");
  const record = ingest(file.name, [{ page: null, text }], file.size);
  return { message: `'${record.filename}' processed into ${record.num_chunks} chunks.`, document: record };
}

export async function deleteDocument(documentId) {
  seed();
  const before = documents.length;
  documents = documents.filter((d) => d.id !== documentId);
  chunks = chunks.filter((c) => c.document_id !== documentId);
  rebuildIndex();
  if (documents.length === before) throw new Error("Document not found.");
  return { message: "Document deleted.", document_id: documentId };
}

export async function askQuestion(question, documentIds = []) {
  seed();
  await sleep(700); // feel like a real round trip
  question = question.trim();
  if (!question) throw new Error("Question must not be empty.");
  if (!documents.length) {
    return { answer: NO_DOCUMENTS_MESSAGE, sources: [], insufficient_information: true, attempts: 0, search_query: question, evaluation: null };
  }

  let state = { question, document_ids: documentIds.length ? documentIds : null, attempt: 1, ...understandQuery(question) };
  let retrieved, gen, evaluation;
  for (;;) {
    retrieved = retrieve(state);
    gen = generate(state, retrieved);
    evaluation = evaluate(state, retrieved, gen);
    if (evaluation.passed || state.attempt >= MAX_ATTEMPTS || !retrieved.length) break;
    state = refine(state);
  }

  const sources = retrieved.map((c, i) => ({
    ref: i + 1,
    document_id: c.document_id,
    document_name: c.document_name,
    page: c.page,
    chunk_index: c.chunk_index,
    relevance_score: c.score,
    snippet: c.content.slice(0, 300) + (c.content.length > 300 ? "..." : ""),
  }));
  return {
    answer: evaluation.passed ? gen.answer : INSUFFICIENT_MESSAGE,
    sources,
    insufficient_information: !evaluation.passed,
    attempts: state.attempt,
    search_query: state.search_query,
    evaluation,
  };
}

/** Test helper: start again from the sample documents. */
export function _resetDemo() {
  documents = []; chunks = []; idf = new Map(); seeded = false;
}
