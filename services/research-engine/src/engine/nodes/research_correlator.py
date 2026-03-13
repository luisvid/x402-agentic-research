"""
Correlator Node for Research Analysis.

Clusters articles, deduplicates, and filters using
inclusion/exclusion terms and desired/non-desired information lists.

Import fix: from nodes.clustering_node -> from ..clustering.clustering_node
"""

import logging
import re
from typing import Any, Dict, List
from urllib.parse import urlparse

from ..clustering.clustering_node import ClusteringNode

logger = logging.getLogger(__name__)


def _validate_urls(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    NON_ARTICLE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".mp4", ".mp3", ".zip", ".exe"}
    valid = []
    for article in articles:
        url = article.get("url", "")
        if not url:
            continue
        try:
            parsed = urlparse(url)
        except Exception:
            continue
        if not parsed.scheme or not parsed.netloc:
            continue
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in NON_ARTICLE_EXTENSIONS):
            continue
        valid.append(article)
    filtered_count = len(articles) - len(valid)
    if filtered_count:
        logger.info(f"URL validation filtered {filtered_count} articles")
    return valid


def _penalize_generic_content(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    LISTICLE_PATTERNS = [
        r"^top\s+\d+\s+", r"^best\s+.+\s+20\d{2}", r"^\d+\s+(?:best|top|ways)",
        r"complete\s+guide\s+to", r"beginner.?s?\s+guide", r"everything\s+you\s+need\s+to\s+know",
        r"what\s+is\s+.+\?\s*$", r"^how\s+to\s+(?:buy|invest|stake|earn)",
    ]
    compiled = [re.compile(p, re.IGNORECASE) for p in LISTICLE_PATTERNS]

    for article in articles:
        title = article.get("title", "")
        for pattern in compiled:
            if pattern.search(title):
                existing = article.get("_relevance_score", 0)
                article["_relevance_score"] = existing - 2
                break
    return articles


def _filter_by_terms(articles: List[Dict[str, Any]], include_terms: List[str], exclude_terms: List[str]) -> List[Dict[str, Any]]:
    if not include_terms and not exclude_terms:
        return articles
    filtered = []
    for article in articles:
        text = (article.get("title", "") + " " + article.get("content", "")).lower()
        if any(term.lower() in text for term in exclude_terms):
            continue
        if include_terms and not any(term.lower() in text for term in include_terms):
            continue
        filtered.append(article)
    return filtered


def _filter_by_desired_info(articles: List[Dict[str, Any]], desired: List[str], non_desired: List[str]) -> List[Dict[str, Any]]:
    if not desired and not non_desired:
        return articles
    for article in articles:
        text = (article.get("title", "") + " " + article.get("content", "")).lower()
        score = 0
        for info in desired:
            if any(kw in text for kw in info.lower().split() if len(kw) > 3):
                score += 1
        for info in non_desired:
            if any(kw in text for kw in info.lower().split() if len(kw) > 3):
                score -= 1
        article["_relevance_score"] = score
    return [a for a in articles if a.get("_relevance_score", 0) >= 0]


def correlate_research_node(state: Dict[str, Any]) -> Dict[str, Any]:
    config = state.get("config", {})
    research_config = config.get("phase_configs", {}).get("research_analysis", {})
    articles = state.get("research_search_results", [])
    parsed_context = state.get("research_parsed_context", {})

    desired_info = research_config.get("desired_information", [])
    non_desired_info = research_config.get("non_desired_information", [])

    if not articles:
        return {"research_search_results": [], "clustered_events": [], "errors": []}

    logger.info(f"Correlating {len(articles)} research articles")

    include_terms = parsed_context.get("include_terms", [])
    exclude_terms = parsed_context.get("exclude_terms", [])

    articles = _validate_urls(articles)
    articles = _filter_by_terms(articles, include_terms, exclude_terms)
    articles = _penalize_generic_content(articles)
    articles = _filter_by_desired_info(articles, desired_info, non_desired_info)

    if not articles:
        return {"research_search_results": [], "clustered_events": [], "errors": []}

    clusterer = ClusteringNode(similarity_threshold=0.70)
    try:
        clusters = clusterer.cluster_articles(articles, min_cluster_size=1, max_cluster_size=10)
    except Exception as e:
        logger.error(f"Clustering failed: {e}")
        clusters = [{"cluster_id": "research_all", "articles": articles, "cluster_size": len(articles), "representative_title": articles[0].get("title", ""), "urls": [a.get("url", "") for a in articles], "buzz_score": len(articles)}]

    for cluster in clusters:
        cluster["research_topic"] = parsed_context.get("original_context", "")[:100]

    deduped_articles = []
    seen_urls: set[str] = set()
    for cluster in clusters:
        for article in cluster.get("articles", []):
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                deduped_articles.append(article)

    logger.info(f"Correlation complete: {len(clusters)} clusters, {len(deduped_articles)} unique articles")

    return {"research_search_results": deduped_articles, "clustered_events": clusters, "errors": []}
