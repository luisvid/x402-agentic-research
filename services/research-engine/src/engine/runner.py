"""
Engine runner: builds initial state, calls workflow, extracts ResearchResponse.
"""

import logging
import time
from uuid import uuid4

from ..config import build_engine_config
from ..schemas import ResearchRequest, ResearchResponse
from .workflow import build_research_workflow

logger = logging.getLogger(__name__)

# Build workflow once at module level
_workflow = None


def _get_workflow():
    global _workflow
    if _workflow is None:
        _workflow = build_research_workflow()
    return _workflow


def run_engine(req: ResearchRequest) -> ResearchResponse:
    """Run the LangGraph research pipeline and return a ResearchResponse."""
    tier_config = build_engine_config(req.tier)
    max_queries = tier_config.get("max_queries", 15)

    initial_state = {
        "config": tier_config,
        "execution_id": f"research-{req.request_id}",
        "phase": "research-analysis",
        "errors": [],
        "search_queries": [],
        "raw_articles": [],
        "search_metadata": None,
        "research_context": req.query,
        "research_date_range": {"start_date": req.start_date, "end_date": req.end_date},
        "research_parsed_context": None,
        "research_search_batches": None,
        "research_search_results": None,
        "research_article_scores": None,
        "research_analysis_result": None,
        "clustered_events": [],
        "final_report": None,
    }

    workflow = _get_workflow()
    thread_id = str(uuid4())

    logger.info(f"Running research pipeline: tier={req.tier}, max_queries={max_queries}")
    start = time.time()

    # Run the workflow
    final_state = None
    for state in workflow.stream(initial_state, config={"configurable": {"thread_id": thread_id}}):
        final_state = state

    elapsed = time.time() - start
    logger.info(f"Pipeline complete in {elapsed:.1f}s")

    # Extract the last state values (stream yields {node_name: state_update})
    # Merge all updates into a single dict
    merged = dict(initial_state)
    if final_state:
        for node_name, node_output in (final_state.items() if isinstance(final_state, dict) else []):
            if isinstance(node_output, dict):
                merged.update(node_output)

    # Build response
    analysis = merged.get("research_analysis_result")
    report = merged.get("final_report")
    articles = merged.get("research_search_results", []) or merged.get("raw_articles", [])

    # Extract key findings and summary from analysis
    summary = None
    key_findings = None
    causal_chain = None
    confidence = None

    if analysis and isinstance(analysis, dict):
        analysis_data = analysis.get("analysis")
        if analysis_data and isinstance(analysis_data, dict):
            summary = analysis_data.get("executive_summary")
            key_findings = analysis_data.get("key_findings")
            causal_chain = analysis_data.get("causal_chain")

        # Compute average confidence from findings
        if key_findings:
            conf_map = {"high": 0.9, "medium": 0.7, "low": 0.4}
            scores = [conf_map.get(f.get("confidence", "medium"), 0.5) for f in key_findings]
            confidence = round(sum(scores) / len(scores), 2) if scores else None

    # Build sources list
    sources = []
    seen_urls: set[str] = set()
    for article in (articles or []):
        url = article.get("url", "")
        if url and url not in seen_urls:
            seen_urls.add(url)
            sources.append({"title": article.get("title", ""), "url": url, "published_date": article.get("published_date")})

    # Determine status
    status = "completed"
    if analysis and analysis.get("status") == "insufficient_data":
        status = "no_data"
    elif analysis and analysis.get("status") == "error":
        status = "failed"
    elif not analysis:
        status = "failed"

    # Apply tier restrictions
    include_report = tier_config.get("include_report", True)
    include_causal = tier_config.get("include_causal_chain", True)

    return ResearchResponse(
        request_id=req.request_id,
        status=status,
        tier=req.tier,
        summary=summary,
        key_findings=key_findings,
        causal_chain=causal_chain if include_causal else None,
        sources=sources,
        confidence=confidence,
        report_markdown=report if include_report else None,
        timings={"pipeline_seconds": round(elapsed, 2)},
        metadata={
            "engine": "langgraph",
            "tier": req.tier,
            "total_articles": len(articles or []),
            "total_sources": len(sources),
        },
    )
