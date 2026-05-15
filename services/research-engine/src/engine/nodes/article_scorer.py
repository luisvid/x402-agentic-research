"""
Article Scorer Node — ranks articles by semantic relevance to the research context.

Uses local sentence-transformer embeddings (cosine similarity) instead of LLM calls.
The all-MiniLM-L6-v2 model is already loaded as a singleton in model_manager.
"""

import logging
from typing import Any, Dict, List

from sklearn.metrics.pairwise import cosine_similarity

from ..utils.model_manager import model_manager

logger = logging.getLogger(__name__)


def score_articles_node(state: Dict[str, Any]) -> Dict[str, Any]:
    articles: List[Dict] = state.get("research_search_results", [])
    parsed_context: Dict = state.get("research_parsed_context", {})

    if not articles or not parsed_context:
        return {"research_search_results": articles, "research_article_scores": [], "errors": []}

    context_text = parsed_context.get("original_context", "")
    if not context_text:
        return {"research_search_results": articles, "research_article_scores": [], "errors": []}

    logger.info(f"Scoring {len(articles)} articles with local embeddings...")

    model = model_manager.get_sentence_transformer()

    query_emb = model.encode([context_text])
    article_texts = [
        (a.get("title", "") + " " + a.get("content", ""))[:512]
        for a in articles
    ]
    article_embs = model.encode(article_texts)
    scores = cosine_similarity(query_emb, article_embs)[0]

    for article, score in zip(articles, scores):
        article["_relevance_score"] = max(1, min(5, round(float(score) * 5)))
        article["_article_type"] = "unknown"

    articles.sort(key=lambda a: a.get("_relevance_score", 0), reverse=True)

    logger.info(f"Article scoring complete: {len(articles)} articles ranked")
    return {"research_search_results": articles, "research_article_scores": [], "errors": []}
