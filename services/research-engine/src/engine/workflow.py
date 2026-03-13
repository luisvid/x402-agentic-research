"""
Research Analysis Workflow — 7-node LangGraph pipeline.

Pipeline:
  parse_research_context → generate_research_queries → search_date_range
  → correlate_research → score_articles → llm_analyze_research → generate_research_report → END
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from .nodes.article_scorer import score_articles_node
from .nodes.context_parser import parse_research_context_node
from .nodes.date_range_searcher import search_date_range_node
from .nodes.query_generator import generate_research_queries_node
from .nodes.report_generator import generate_research_report_node
from .nodes.research_analyzer import llm_analyze_research_node
from .nodes.research_correlator import correlate_research_node
from .state import GraphState


def build_research_workflow():
    """Build and compile the research analysis workflow."""
    workflow = StateGraph(GraphState)

    workflow.add_node("parse_research_context", parse_research_context_node)
    workflow.add_node("generate_research_queries", generate_research_queries_node)
    workflow.add_node("search_date_range", search_date_range_node)
    workflow.add_node("correlate_research", correlate_research_node)
    workflow.add_node("score_articles", score_articles_node)
    workflow.add_node("llm_analyze_research", llm_analyze_research_node)
    workflow.add_node("generate_research_report", generate_research_report_node)

    workflow.add_edge("parse_research_context", "generate_research_queries")
    workflow.add_edge("generate_research_queries", "search_date_range")
    workflow.add_edge("search_date_range", "correlate_research")

    workflow.add_conditional_edges(
        "correlate_research",
        lambda state: "score" if state.get("research_search_results") else "end",
        {"score": "score_articles", "end": END},
    )

    workflow.add_edge("score_articles", "llm_analyze_research")
    workflow.add_edge("llm_analyze_research", "generate_research_report")
    workflow.add_edge("generate_research_report", END)

    workflow.set_entry_point("parse_research_context")

    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
