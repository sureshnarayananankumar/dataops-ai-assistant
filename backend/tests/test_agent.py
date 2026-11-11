"""Tests for the LangGraph agent and the /chat endpoint (with the fake LLM)."""
from app.agents import nodes
from app.agents.graph import run_agent

from tests.conftest import DBT_TEXT, SNOWFLAKE_TEXT


def _upload(client, name, text):
    return client.post("/upload", files={"file": (name, text.encode(), "text/plain")}).json()["document"]


def test_chat_without_documents(client):
    r = client.post("/chat", json={"question": "What is dbt?"})
    assert r.status_code == 200
    body = r.json()
    assert body["insufficient_information"] is True
    assert "No documents" in body["answer"]


def test_grounded_answer_on_first_attempt(client):
    _upload(client, "dbt.md", DBT_TEXT)
    _upload(client, "snowflake.txt", SNOWFLAKE_TEXT)
    body = client.post("/chat", json={"question": "What is a DBT incremental model?"}).json()

    assert body["insufficient_information"] is False
    assert body["attempts"] == 1
    assert body["evaluation"]["passed"] is True
    assert body["sources"][0]["document_name"] == "dbt.md"
    assert body["sources"][0]["ref"] == 1


def test_unanswerable_question_retries_once_then_reports_insufficient(client, fake_llm):
    _upload(client, "dbt.md", DBT_TEXT)
    body = client.post("/chat", json={"question": "How does Kubernetes autoscaling work?"}).json()

    assert body["insufficient_information"] is True
    assert body["attempts"] == 2                       # first try + one retry
    assert body["answer"] == nodes.INSUFFICIENT_MESSAGE
    assert any("did not find enough evidence" in c for c in fake_llm.calls)  # refine_query ran


def test_ungrounded_answer_is_rejected(client, fake_llm):
    _upload(client, "dbt.md", DBT_TEXT)
    fake_llm.judge_grounded = False                    # judge says "not supported"
    state = run_agent("What is a DBT incremental model?")
    assert state["attempt"] == 2
    assert state["insufficient_information"] is True
    assert state["evaluation"]["grounded"] is False


def test_summary_intent_uses_document_chunks(client):
    doc = _upload(client, "snowflake.txt", SNOWFLAKE_TEXT)
    state = run_agent("Summarize the uploaded document", document_ids=[doc["id"]])
    assert state["intent"] == "summary"
    assert state["retrieved"] and all(c["document_id"] == doc["id"] for c in state["retrieved"])


def test_document_filter_limits_search(client):
    dbt = _upload(client, "dbt.md", DBT_TEXT)
    _upload(client, "snowflake.txt", SNOWFLAKE_TEXT)
    state = run_agent("Explain Snowflake streams", document_ids=[dbt["id"]])
    assert {c["document_name"] for c in state["retrieved"]} == {"dbt.md"}


def test_parse_json_handles_code_fences():
    assert nodes._parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert nodes._parse_json("no json here") is None


def test_empty_question_is_rejected(client):
    assert client.post("/chat", json={"question": ""}).status_code == 422
