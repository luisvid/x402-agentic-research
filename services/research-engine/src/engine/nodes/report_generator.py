"""
Report Generator Node for Research Analysis.

Renders the research analysis into a Jinja2 template.
STRIPPED: GCS upload, email send, Slack send, report_storage dependency.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "../../templates")


def _load_template():
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), trim_blocks=True, lstrip_blocks=True)
    return env.get_template("research_analysis.md")


def _extract_sources(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen_urls: set[str] = set()
    sources = []
    for article in articles:
        url = article.get("url", "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        sources.append({"title": article.get("title", "Untitled"), "url": url, "published_date": article.get("published_date") or ""})
    sources.sort(key=lambda s: s.get("published_date") or "")
    return sources


def generate_research_report_node(state: Dict[str, Any]) -> Dict[str, Any]:
    analysis = state.get("research_analysis_result")
    parsed_context = state.get("research_parsed_context", {})
    articles = state.get("research_search_results", [])

    if not analysis:
        logger.warning("No analysis to report")
        return {"final_report": None, "errors": []}

    context_text = parsed_context.get("original_context", "Research Analysis")
    start_date = parsed_context.get("start_date", "")
    end_date = parsed_context.get("end_date", "")

    sources = _extract_sources(articles)
    article_scores = state.get("research_article_scores", [])

    template_data = {
        "topic": context_text,
        "start_date": start_date,
        "end_date": end_date,
        "analysis": analysis,
        "sources": sources,
        "total_articles": analysis.get("total_articles", len(articles)),
        "search_provider": state.get("search_metadata", {}).get("provider", "Unknown"),
        "generated_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "article_scores": article_scores,
    }

    try:
        template = _load_template()
        report_content = template.render(**template_data)
    except Exception as e:
        logger.error(f"Template rendering failed: {e}")
        return {"final_report": None, "errors": [{"node_name": "generate_research_report", "error_type": "TemplateError", "error_message": str(e)}]}

    logger.info("Research analysis report generated")

    return {"final_report": report_content, "errors": []}
