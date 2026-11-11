"""
metrics.py - Simple, explainable evaluation metrics.

IMPORTANT LIMITATIONS (read before trusting the numbers):
  * keyword_coverage only checks that some expected words appear - an answer can
    contain them and still be wrong, or be right with different wording.
  * semantic_similarity compares embeddings - it measures "talks about the same
    thing", not "is factually correct".
  * groundedness comes from an LLM judge, which can itself make mistakes and
    tends to be lenient with its own model family.
  * A 10-question dataset is a smoke test, not a benchmark.
These checks are useful to catch regressions; they do NOT guarantee correctness.
"""
import math
import re


def retrieval_hit(retrieved_names: list[str], expected_source: str | None) -> bool | None:
    """Did the expected document appear among the retrieved chunks? (None if not applicable)"""
    if not expected_source:
        return None
    return expected_source in retrieved_names


def keyword_coverage(answer: str, expected_keywords: list[str]) -> float | None:
    """Fraction of expected keywords found in the answer (case-insensitive)."""
    if not expected_keywords:
        return None
    text = answer.lower()
    found = sum(1 for k in expected_keywords if re.search(re.escape(k.lower()), text))
    return round(found / len(expected_keywords), 2)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return round(dot / (na * nb), 3) if na and nb else 0.0


def case_passed(case: dict, result: dict) -> bool:
    """Pass rule for one test case.

    Answerable  -> not marked insufficient, right document retrieved,
                   answer judged grounded, and >= 50% keyword coverage.
    Unanswerable -> the agent must say there is not enough information.
    """
    if not case["answerable"]:
        return bool(result["insufficient_information"])
    return (
        not result["insufficient_information"]
        and bool(result["retrieval_hit"])
        and bool(result["grounded"])
        and (result["keyword_coverage"] or 0) >= 0.5
    )
