"""
graph.py - Wires the nodes together into a LangGraph workflow.

A StateGraph has:
  * nodes  - the steps (functions from nodes.py)
  * edges  - fixed arrows "after A, run B"
  * conditional edges - arrows chosen at runtime by a function
    (here: route_after_evaluation decides "final" or "retry")

`run_agent()` is the single function the API calls.
"""
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from app.agents import nodes
from app.agents.state import AgentState
from app.services import document_registry


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("understand_query", nodes.understand_query)
    graph.add_node("retrieve_documents", nodes.retrieve_documents)
    graph.add_node("generate_answer", nodes.generate_answer)
    graph.add_node("evaluate_answer", nodes.evaluate_answer)
    graph.add_node("refine_query", nodes.refine_query)
    graph.add_node("final_response", nodes.final_response)

    graph.add_edge(START, "understand_query")
    graph.add_edge("understand_query", "retrieve_documents")
    graph.add_edge("retrieve_documents", "generate_answer")
    graph.add_edge("generate_answer", "evaluate_answer")
    graph.add_conditional_edges(
        "evaluate_answer",
        nodes.route_after_evaluation,
        {"final": "final_response", "retry": "refine_query"},
    )
    graph.add_edge("refine_query", "retrieve_documents")  # the retry loop
    graph.add_edge("final_response", END)

    return graph.compile()


@lru_cache
def get_graph():
    """Compile the graph once and reuse it."""
    return build_graph()


def run_agent(question: str, document_ids: list[str] | None = None) -> dict:
    """Run the full workflow for one question and return the final state."""
    if not document_registry.list_documents():
        return {
            "final_answer": nodes.NO_DOCUMENTS_MESSAGE,
            "insufficient_information": True,
            "retrieved": [],
            "attempt": 0,
            "search_query": question,
            "evaluation": None,
        }
    initial_state: AgentState = {"question": question, "document_ids": document_ids or None, "attempt": 1}
    return get_graph().invoke(initial_state)
