"""
Date Range Searcher Node for Research Analysis.

Executes searches across the specified date range using UnifiedSearchEngine.

Import fix: from search.unified_search_engine -> from ..search.unified_search_engine
"""

import logging
from datetime import datetime
from typing import Any, Dict

from ..search.unified_search_engine import UnifiedSearchEngine

logger = logging.getLogger(__name__)


def search_date_range_node(state: Dict[str, Any]) -> Dict[str, Any]:
    config = state.get("config", {})
    research_config = config.get("phase_configs", {}).get("research_analysis", {})
    search_config = research_config.get("search_config", {})

    max_results_per_query = search_config.get("max_results_per_query", 5)
    batches = state.get("research_search_batches", [])

    if not batches:
        return {"research_search_results": [], "raw_articles": [], "errors": []}

    engine = UnifiedSearchEngine()
    provider_name = engine.get_provider_name()
    logger.info(f"Research search using {provider_name}")

    all_articles = []

    for batch in batches:
        queries = batch["queries"]
        start_date = batch["start_date"]
        end_date = batch["end_date"]

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            days_back = max((end - start).days, 1)
        except (ValueError, KeyError):
            days_back = 30

        logger.info(f"Searching ({start_date} to {end_date}): {len(queries)} queries, {max_results_per_query} results/query")

        try:
            articles = engine.search(
                queries=queries,
                days_back=days_back,
                max_results_per_query=max_results_per_query,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            articles = []

        for article in articles:
            article["research_window"] = "range"
            article["research_window_start"] = start_date
            article["research_window_end"] = end_date

        all_articles.extend(articles)
        logger.info(f"  Found {len(articles)} articles")

    logger.info(f"Research search complete: {len(all_articles)} total articles")

    return {
        "research_search_results": all_articles,
        "raw_articles": all_articles,
        "search_metadata": {"provider": provider_name},
        "errors": [],
    }
