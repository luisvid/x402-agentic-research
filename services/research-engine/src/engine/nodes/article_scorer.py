"""
Article Scorer Node for Research Analysis.

LLM-based article triage that evaluates articles against the research context.

Import fix: from utils.model_factory -> from ..utils.model_factory
"""

import json
import logging
import os
from typing import Any, Dict, List

from ..utils.model_factory import ModelFactory

logger = logging.getLogger(__name__)

SCORING_PROMPT = """You are a research article relevance scorer. Your ONLY task is to evaluate how relevant each article is to the given research topic.

## Research Topic
{context}

## Date Range
{start_date} to {end_date}

{semantic_context_section}

## Articles to Score

{articles_text}

## Scoring Instructions

For each article, provide:
1. **relevance_score** (1-5): 5=directly causal, 4=related causal, 3=context, 2=tangential, 1=not relevant
2. **article_type**: breaking_news, analysis, data_report, trend_report, opinion, generic

## Output
Respond with ONLY a valid JSON array. No other text.
[{{"article_index": 1, "relevance_score": 5, "article_type": "breaking_news", "brief_reason": "..."}}]
"""


def _format_articles_for_scoring(articles: List[Dict], batch_start: int = 0) -> str:
    lines = []
    for i, article in enumerate(articles, batch_start + 1):
        title = article.get("title", "Untitled")
        content = article.get("content", "")[:400]
        date = article.get("published_date", "")
        lines.append(f"{i}. **{title}** ({date})\n   {content}")
    return "\n\n".join(lines)


def _build_semantic_section(parsed_context: Dict[str, Any]) -> str:
    semantic = parsed_context.get("semantic_analysis")
    if not semantic:
        return ""
    parts = ["## Semantic Context"]
    if semantic.get("query_intent"):
        parts.append(f"- **Query intent:** {semantic['query_intent']}")
    if semantic.get("metric_direction"):
        parts.append(f"- **Metric direction:** {semantic['metric_direction']}")
    if semantic.get("key_entities"):
        parts.append(f"- **Key entities:** {', '.join(semantic['key_entities'])}")
    return "\n".join(parts)


def _get_model_config(config: Dict[str, Any]) -> Dict[str, Any]:
    model_config = config.get("model_config", {})
    agent_models = model_config.get("agent_models", {})
    model = agent_models.get("research_analyzer", {}) or agent_models.get("query_generator_agent", {})
    return {
        "endpoint": model.get("endpoint", model_config.get("default_endpoint", "geia")),
        "model": model.get("model", os.environ.get("PROVIDER_LLM_MODEL_FAST", "vertex_ai/gemini-2.5-flash")),
        "temperature": model.get("temperature", 0.1),
    }


def _score_batch(llm, articles, context_text, start_date, end_date, parsed_context, batch_start) -> List[Dict]:
    articles_text = _format_articles_for_scoring(articles, batch_start)
    semantic_section = _build_semantic_section(parsed_context)

    prompt = SCORING_PROMPT.format(
        context=context_text, start_date=start_date, end_date=end_date,
        semantic_context_section=semantic_section, articles_text=articles_text,
    )

    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)

    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]

    scores = json.loads(content.strip())
    return scores if isinstance(scores, list) else []


def score_articles_node(state: Dict[str, Any]) -> Dict[str, Any]:
    config = state.get("config", {})
    articles = state.get("research_search_results", [])
    parsed_context = state.get("research_parsed_context", {})

    if not articles or not parsed_context:
        return {"research_search_results": articles, "research_article_scores": [], "errors": []}

    context_text = parsed_context.get("original_context", "")
    start_date = parsed_context.get("start_date", "")
    end_date = parsed_context.get("end_date", "")

    if len(articles) <= 15:
        logger.info(f"Only {len(articles)} articles — skipping LLM scoring")
        return {"research_search_results": articles, "research_article_scores": [], "errors": []}

    model_cfg = _get_model_config(config)

    try:
        llm = ModelFactory.create_model(
            endpoint=model_cfg["endpoint"], model_name=model_cfg["model"], temperature=model_cfg["temperature"]
        )
    except Exception as e:
        logger.error(f"Failed to create scoring model: {e}")
        return {"research_search_results": articles, "research_article_scores": [], "errors": [{"node_name": "score_articles", "error_type": "ModelError", "error_message": str(e)}]}

    batch_size = 15
    all_scores: list[dict] = []

    logger.info(f"Scoring {len(articles)} articles for causal relevance...")

    for batch_start in range(0, len(articles), batch_size):
        batch = articles[batch_start:batch_start + batch_size]
        try:
            scores = _score_batch(llm, batch, context_text, start_date, end_date, parsed_context, batch_start)
            all_scores.extend(scores)
        except Exception as e:
            logger.warning(f"Batch scoring failed at offset {batch_start}: {e}")
            for i in range(len(batch)):
                all_scores.append({"article_index": batch_start + i + 1, "relevance_score": 3, "article_type": "unknown", "brief_reason": "Scoring failed"})

    score_map = {s.get("article_index", 0): s for s in all_scores if s.get("article_index", 0) >= 1}

    for i, article in enumerate(articles, 1):
        score_data = score_map.get(i, {})
        article["_relevance_score"] = score_data.get("relevance_score", 3)
        article["_article_type"] = score_data.get("article_type", "unknown")

    articles.sort(key=lambda a: a.get("_relevance_score", 0), reverse=True)

    logger.info(f"Article scoring complete: {len(all_scores)} scores")

    return {"research_search_results": articles, "research_article_scores": all_scores, "errors": []}
