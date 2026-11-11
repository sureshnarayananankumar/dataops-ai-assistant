"""
run_evaluation.py - Run the agent on a small test dataset and write a report.

Run from the backend/ folder (virtual environment active, API key in .env):
    python -m app.evaluation.run_evaluation
    python -m app.evaluation.run_evaluation --delay 5   # slower, kinder to free-tier limits

What it does:
  1. Uses a SEPARATE data folder (data/eval) so your own uploads are untouched.
  2. Ingests every file in sample_documents/ (only the first time).
  3. Asks every question in dataset.json through the real LangGraph agent.
  4. Scores each answer (metrics.py) and writes:
        app/evaluation/reports/eval_report.md   (human-readable)
        app/evaluation/reports/eval_report.json (machine-readable)
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from app.config import PROJECT_ROOT, settings
from app.evaluation import metrics

HERE = Path(__file__).parent
DATASET = HERE / "dataset.json"
REPORT_DIR = HERE / "reports"
SAMPLE_DIR = PROJECT_ROOT / "sample_documents"


def _use_eval_storage() -> None:
    """Point all storage at data/eval BEFORE anything touches Chroma."""
    from app.rag.vector_store import reset_vector_store

    settings.data_dir = str(settings.data_path / "eval")
    settings.chroma_collection = "eval_docs"
    reset_vector_store()


def _ingest_samples() -> None:
    from app.services import document_registry, document_service

    existing = {d["filename"] for d in document_registry.list_documents()}
    for path in sorted(SAMPLE_DIR.iterdir()):
        if path.name.startswith(".") or path.name in existing:
            continue
        print(f"  ingesting {path.name} ...")
        document_service.ingest_document(path.name, path.read_bytes())


def evaluate(delay: float) -> list[dict]:
    from app.agents.graph import run_agent
    from app.services.llm_provider import get_embeddings

    cases = json.loads(DATASET.read_text(encoding="utf-8"))
    embeddings = get_embeddings()
    results = []
    for i, case in enumerate(cases, start=1):
        print(f"[{i}/{len(cases)}] {case['question']}")
        started = time.perf_counter()
        try:
            state = run_agent(case["question"])
            error = None
        except Exception as exc:  # e.g. rate limit - record it and keep going
            state, error = {"final_answer": "", "retrieved": [], "insufficient_information": False}, str(exc)[:200]
        seconds = round(time.perf_counter() - started, 1)

        answer = state.get("final_answer", "")
        evaluation = state.get("evaluation") or {}
        names = [c["document_name"] for c in state.get("retrieved", [])]

        similarity = None
        if case["answerable"] and answer and not state.get("insufficient_information"):
            similarity = metrics.cosine_similarity(
                embeddings.embed_query(answer), embeddings.embed_query(case["expected_answer"])
            )

        result = {
            "id": case["id"],
            "question": case["question"],
            "answerable": case["answerable"],
            "answer": answer,
            "error": error,
            "attempts": state.get("attempt"),
            "insufficient_information": bool(state.get("insufficient_information")),
            "retrieved_documents": sorted(set(names)),
            "retrieval_hit": metrics.retrieval_hit(names, case.get("expected_source")),
            "retrieval_relevance": evaluation.get("retrieval_relevance"),
            "answer_relevant": evaluation.get("answer_relevant"),
            "grounded": evaluation.get("grounded"),
            "groundedness_score": evaluation.get("groundedness_score"),
            "keyword_coverage": metrics.keyword_coverage(answer, case["expected_keywords"]),
            "semantic_similarity": similarity,
            "seconds": seconds,
        }
        result["passed"] = error is None and metrics.case_passed(case, result)
        print(f"    -> {'PASS' if result['passed'] else 'FAIL'} ({seconds}s)")
        results.append(result)
        time.sleep(delay)
    return results


def _avg(values) -> str:
    values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    return f"{sum(values) / len(values):.2f}" if values else "n/a"


def _rate(values) -> str:
    values = [v for v in values if v is not None]
    return f"{sum(1 for v in values if v)}/{len(values)}" if values else "n/a"


def write_report(results: list[dict]) -> Path:
    REPORT_DIR.mkdir(exist_ok=True)
    answerable = [r for r in results if r["answerable"]]
    unanswerable = [r for r in results if not r["answerable"]]
    lines = [
        "# Evaluation Report – DataOps AI Assistant",
        "",
        f"- Date: {datetime.now():%Y-%m-%d %H:%M}",
        f"- Provider / chat model: {settings.provider} / {settings.chat_model}",
        f"- Embedding model: {settings.embedding_model}",
        f"- Test cases: {len(results)} ({len(answerable)} answerable, {len(unanswerable)} unanswerable)",
        "",
        "## Summary",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| Overall pass rate | {_rate([r['passed'] for r in results])} |",
        f"| Retrieval hit rate (expected doc retrieved) | {_rate([r['retrieval_hit'] for r in answerable])} |",
        f"| Avg retrieval relevance score | {_avg([r['retrieval_relevance'] for r in answerable])} |",
        f"| Answer relevant (LLM judge) | {_rate([r['answer_relevant'] for r in answerable])} |",
        f"| Grounded (LLM judge) | {_rate([r['grounded'] for r in answerable])} |",
        f"| Avg groundedness score | {_avg([r['groundedness_score'] for r in answerable])} |",
        f"| Avg keyword coverage | {_avg([r['keyword_coverage'] for r in answerable])} |",
        f"| Avg semantic similarity to expected answer | {_avg([r['semantic_similarity'] for r in answerable])} |",
        f"| Insufficient-info handled correctly | {_rate([r['insufficient_information'] for r in unanswerable])} |",
        "",
        "## Per-question results",
        "",
        "| ID | Question | Pass | Attempts | Retrieval hit | Grounded | Keywords | Similarity |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['question']} | {'✅' if r['passed'] else '❌'} | {r['attempts']} | "
            f"{r['retrieval_hit']} | {r['grounded']} | {r['keyword_coverage']} | {r['semantic_similarity']} |"
        )
    errors = [r for r in results if r["error"]]
    if errors:
        lines += ["", "## Errors", ""] + [f"- {r['id']}: {r['error']}" for r in errors]
    lines += [
        "",
        "## Limitations",
        "",
        "- These are automated *signals*, not proof of correctness.",
        "- Keyword coverage can pass a wrong answer that happens to contain the words, and fail a correct paraphrase.",
        "- Semantic similarity measures topical closeness, not factual accuracy.",
        "- Groundedness and relevance are judged by an LLM, which can be wrong or lenient.",
        "- 10 questions over 5 short documents is a smoke test; results vary between runs and models.",
        "- Human review of a sample of answers is still needed before trusting the system.",
    ]
    md = REPORT_DIR / "eval_report.md"
    md.write_text("\n".join(lines), encoding="utf-8")
    (REPORT_DIR / "eval_report.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return md


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the DataOps AI Assistant.")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds to wait between questions")
    args = parser.parse_args()

    _use_eval_storage()
    print("Ingesting sample documents ...")
    _ingest_samples()
    print("Running questions ...")
    results = evaluate(args.delay)
    path = write_report(results)
    passed = sum(r["passed"] for r in results)
    print(f"\nDone: {passed}/{len(results)} passed. Report: {path}")


if __name__ == "__main__":
    main()
