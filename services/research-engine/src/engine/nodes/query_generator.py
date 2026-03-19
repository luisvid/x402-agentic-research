"""
Query Generator Node for Research Analysis.

Uses LLM to generate diverse search queries from the research context,
with pattern-based fallback if LLM fails.

Import fix: from utils.model_factory -> from ..utils.model_factory
"""

import json
import logging
import os
from typing import Any, Dict, List

from ..utils.model_factory import ModelFactory

logger = logging.getLogger(__name__)

QUERY_GENERATION_PROMPT = """You are a research analyst generating search queries to find relevant news and articles.

Given the following research topic/context, generate 15-25 diverse search queries that would find relevant articles, news, and analysis.

## Research Context
{context}

## Date Range
{start_date} to {end_date}

## Instructions
Generate queries that cover multiple angles:
- Direct topic news and announcements
- Partnerships and collaborations
- Product launches and updates
- Regulatory developments
- Competitive landscape
- Market trends and analysis
- Crisis events, incidents, failures, exploits, or depegs
- Market reaction, price impact, and liquidation data
- On-chain metrics, data dashboards, and forensic analysis
- Capital flow patterns, withdrawal or inflow surges

Each query should be 3-8 words, suitable for a news search engine.
Avoid overly generic queries — be specific to the research topic.

Respond with a JSON array of strings:
["query 1", "query 2", ...]
"""


def _generate_fallback_queries(parsed_context: Dict[str, Any]) -> List[str]:
    queries = []
    phrases = parsed_context.get("phrases", [])
    entities = parsed_context.get("entities", [])
    keywords = parsed_context.get("keywords", [])

    topics = phrases[:5] if phrases else entities[:5]
    if not topics:
        topics = [" ".join(keywords[:3])] if keywords else ["blockchain news"]

    patterns = [
        "{topic} news", "{topic} announcement", "{topic} launch",
        "{topic} partnership", "{topic} regulatory", "{topic} market analysis",
        "{topic} incident", "{topic} crisis", "{topic} decline", "{topic} impact",
    ]

    for topic in topics[:4]:
        for pattern in patterns:
            queries.append(pattern.format(topic=topic.strip()))

    for entity in entities[:3]:
        queries.append(f"{entity} news update")

    return queries[:25]


def _get_model_config(config: Dict[str, Any]) -> Dict[str, Any]:
    model_config = config.get("model_config", {})
    agent_models = model_config.get("agent_models", {})
    model = agent_models.get("query_generator_agent", {}) or agent_models.get("research_analyzer", {})
    return {
        "endpoint": model.get("endpoint", model_config.get("default_endpoint", "geia")),
        "model": model.get("model", os.environ.get("PROVIDER_LLM_MODEL_FAST", "vertex_ai/gemini-2.5-flash")),
        "temperature": model.get("temperature", 0.7),
    }


def generate_research_queries_node(state: Dict[str, Any]) -> Dict[str, Any]:
    parsed_context = state.get("research_parsed_context")
    config = state.get("config", {})

    if not parsed_context:
        return {"search_queries": [], "research_search_batches": [], "errors": []}

    context_text = parsed_context["original_context"]
    start_date = parsed_context["start_date"]
    end_date = parsed_context["end_date"]

    queries: list[str] = []
    model_cfg = _get_model_config(config)

    try:
        llm = ModelFactory.create_model(
            endpoint=model_cfg["endpoint"], model_name=model_cfg["model"], temperature=model_cfg["temperature"]
        )
        prompt = QUERY_GENERATION_PROMPT.format(context=context_text, start_date=start_date, end_date=end_date)
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        parsed = json.loads(content.strip())
        if isinstance(parsed, list):
            queries = [q for q in parsed if isinstance(q, str) and q.strip()]
            logger.info(f"LLM generated {len(queries)} search queries")
    except Exception as e:
        logger.warning(f"LLM query generation failed: {e}, using fallback")

    if not queries:
        queries = _generate_fallback_queries(parsed_context)
        logger.info(f"Using {len(queries)} fallback queries")

    search_batch = {
        "context": context_text,
        "start_date": start_date,
        "end_date": end_date,
        "queries": queries,
        "search_terms_exclude": parsed_context.get("exclude_terms", []),
    }

    return {"search_queries": queries, "research_search_batches": [search_batch], "errors": []}
