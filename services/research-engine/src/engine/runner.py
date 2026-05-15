"""
Engine runner: builds initial state, calls workflow, extracts ResearchResponse.
"""

import hashlib
import logging
import os
import time
from uuid import uuid4

from langchain_core.tracers.context import collect_runs

from ..config import build_engine_config
from ..schemas import ResearchRequest, ResearchResponse
from .workflow import build_research_workflow

logger = logging.getLogger(__name__)

# In-memory result cache keyed on (query, start_date, end_date, tier)
_result_cache: dict = {}

# Build workflow once at module level
_workflow = None


def _get_workflow():
    global _workflow
    if _workflow is None:
        _workflow = build_research_workflow()
    return _workflow


def _cache_key(query: str, start_date: str, end_date: str, tier: str) -> str:
    raw = f"{query}|{start_date}|{end_date}|{tier}"
    return hashlib.md5(raw.encode()).hexdigest()


def _log_feedback(run_id: str, response: ResearchResponse) -> None:
    """Attach run metadata to the LangSmith trace. No-op when tracing is off."""
    if os.getenv("LANGCHAIN_TRACING_V2", "").lower() != "true":
        return
    try:
        from langsmith import Client

        client = Client()
        scores: list[tuple[str, float | None, str | None]] = [
            ("tier", None, response.tier),
            ("status", None, response.status),
            ("source_count", float(len(response.sources)), None),
            ("pipeline_seconds", response.timings.get("pipeline_seconds"), None),
            ("mock_mode", 0.0, None),
        ]
        if response.confidence is not None:
            scores.append(("confidence", response.confidence, None))
        for key, score, value in scores:
            client.create_feedback(run_id=run_id, key=key, score=score, value=value)
        logger.debug(f"LangSmith feedback logged for run {run_id}")
    except Exception:
        logger.debug("LangSmith feedback logging failed", exc_info=True)


def run_engine(req: ResearchRequest) -> ResearchResponse:
    """Run the LangGraph research pipeline and return a ResearchResponse."""
    cache_key = _cache_key(req.query, req.start_date, req.end_date, req.tier)
    if cache_key in _result_cache:
        logger.info(f"Cache hit for request (tier={req.tier}), returning cached result")
        return _result_cache[cache_key]

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

    # Run the workflow — stream yields {node_name: state_update} for each node
    # Merge ALL node outputs, not just the last one
    merged = dict(initial_state)
    with collect_runs() as cb:
        for state in workflow.stream(initial_state, config={"configurable": {"thread_id": thread_id}}):
            if isinstance(state, dict):
                for node_name, node_output in state.items():
                    if isinstance(node_output, dict):
                        logger.debug(f"Node '{node_name}' returned keys: {list(node_output.keys())}")
                        merged.update(node_output)
    _langsmith_run_id = str(cb.traced_runs[-1].id) if cb.traced_runs else None

    elapsed = time.time() - start
    logger.info(f"Pipeline complete in {elapsed:.1f}s")

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
            sources.append({
                "title": article.get("title", ""),
                "url": url,
                "published_date": article.get("published_date"),
                "snippet": article.get("content", "")[:500],
            })

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

    response = ResearchResponse(
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

    if status == "completed":
        _result_cache[cache_key] = response

    if _langsmith_run_id:
        _log_feedback(_langsmith_run_id, response)

    return response
