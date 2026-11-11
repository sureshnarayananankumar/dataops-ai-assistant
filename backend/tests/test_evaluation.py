"""Tests for the evaluation metrics and an end-to-end evaluation run with fake models."""
import json

from app.evaluation import metrics, run_evaluation


def test_keyword_coverage():
    assert metrics.keyword_coverage("Tasks are created suspended; run RESUME.", ["suspended", "resume"]) == 1.0
    assert metrics.keyword_coverage("No idea.", ["suspended", "resume"]) == 0.0
    assert metrics.keyword_coverage("anything", []) is None


def test_retrieval_hit():
    assert metrics.retrieval_hit(["a.md", "b.md"], "b.md") is True
    assert metrics.retrieval_hit(["a.md"], "b.md") is False
    assert metrics.retrieval_hit(["a.md"], None) is None


def test_cosine_similarity():
    assert metrics.cosine_similarity([1, 0], [1, 0]) == 1.0
    assert metrics.cosine_similarity([1, 0], [0, 1]) == 0.0


def test_case_passed_rules():
    unanswerable = {"answerable": False}
    assert metrics.case_passed(unanswerable, {"insufficient_information": True})
    assert not metrics.case_passed(unanswerable, {"insufficient_information": False})

    answerable = {"answerable": True}
    good = {"insufficient_information": False, "retrieval_hit": True, "grounded": True, "keyword_coverage": 0.6}
    assert metrics.case_passed(answerable, good)
    assert not metrics.case_passed(answerable, {**good, "grounded": False})


def test_full_evaluation_run_writes_report(tmp_path, monkeypatch):
    monkeypatch.setattr(run_evaluation, "REPORT_DIR", tmp_path / "reports")
    run_evaluation._use_eval_storage()
    run_evaluation._ingest_samples()
    results = run_evaluation.evaluate(delay=0)
    report = run_evaluation.write_report(results)

    assert len(results) == len(json.loads(run_evaluation.DATASET.read_text()))
    assert report.exists() and "Limitations" in report.read_text(encoding="utf-8")
    # Off-topic question (no matching words in the samples) -> "insufficient information".
    revenue = next(r for r in results if r["id"] == "q10")
    assert revenue["insufficient_information"] and revenue["passed"]
    # The expected document is retrieved for an answerable question.
    assert next(r for r in results if r["id"] == "q04")["retrieval_hit"] is True
