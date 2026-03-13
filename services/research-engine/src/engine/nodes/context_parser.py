"""
Context Parser Node for Research Analysis.

Reads free-text research context, extracts topics/entities/keywords,
validates dates, and optionally uses LLM for semantic understanding.

Import fix: from utils.model_factory -> from ..utils.model_factory
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..utils.model_factory import ModelFactory

logger = logging.getLogger(__name__)

SEMANTIC_ANALYSIS_PROMPT = """Analyze the following research context and extract semantic understanding. This will guide downstream search and analysis.

## Research Context
{context}

## Date Range
{start_date} to {end_date}

## Instructions
Determine:
1. **query_intent** — What is the user trying to understand?
   - "event_explanation" — Asking what caused a specific metric change
   - "trend_analysis" — Asking about evolution over time
   - "general_research" — Broad research without a specific causal question
2. **metric_direction** — If a metric is mentioned, what direction did it move?
   - "decrease", "increase", "volatile", "stable", or "unknown"
3. **metric_magnitude** — Quantify the change if numbers are provided
4. **key_entities** — The main entities, protocols, or products mentioned (up to 5)
5. **suggested_event_types** — Based on the context, what types of events should be searched for? (up to 5)

Respond with ONLY valid JSON. No other text.
{{
  "query_intent": "event_explanation|trend_analysis|general_research",
  "metric_direction": "decrease|increase|volatile|stable|unknown",
  "metric_magnitude": "description or empty string",
  "key_entities": ["entity1", "entity2"],
  "suggested_event_types": ["type1", "type2"]
}}
"""


def _extract_topics_and_entities(text: str) -> Dict[str, List[str]]:
    phrases = re.split(r"[,;]+|\band\b", text)
    phrases = [p.strip() for p in phrases if p.strip()]

    entities = []
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text):
        entity = match.group(1)
        if len(entity) > 2 and entity not in entities:
            entities.append(entity)

    acronyms = list(set(re.findall(r"\b[A-Z]{2,}[a-z]*\b", text)))

    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "have", "been",
        "will", "about", "into", "over", "also", "than", "such", "most",
        "other", "some", "more", "their", "these", "those", "what", "which",
        "when", "where", "there", "here", "then", "them", "they", "each",
        "every", "both", "between", "through", "during", "before", "after",
        "growth", "trends", "analysis", "research",
    }
    words = re.findall(r"\b\w+\b", text.lower())
    keywords = list(dict.fromkeys(w for w in words if len(w) > 3 and w not in stopwords))

    return {
        "phrases": phrases[:10],
        "entities": entities[:10],
        "acronyms": acronyms[:5],
        "keywords": keywords[:20],
    }


def _validate_date_range(start_date: str, end_date: str) -> Dict[str, Any]:
    warnings: list[str] = []
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return {"valid": False, "error": f"Invalid start_date format: {start_date}"}

    try:
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        return {"valid": False, "error": f"Invalid end_date format: {end_date}"}

    if start >= end:
        return {"valid": False, "error": f"start_date ({start_date}) must be before end_date ({end_date})"}

    now = datetime.now()
    if end > now:
        warnings.append(f"end_date ({end_date}) is in the future, clamping to today")
        end = now
        end_date = end.strftime("%Y-%m-%d")

    days_span = (end - start).days
    if days_span > 365:
        warnings.append(f"Date range spans {days_span} days (>1 year)")

    return {"valid": True, "start_date": start_date, "end_date": end_date, "days_span": days_span, "warnings": warnings}


def _get_model_config(config: Dict[str, Any]) -> Dict[str, Any]:
    model_config = config.get("model_config", {})
    agent_models = model_config.get("agent_models", {})
    model = agent_models.get("research_analyzer", {}) or agent_models.get("query_generator_agent", {})
    return {
        "endpoint": model.get("endpoint", model_config.get("default_endpoint", "geia")),
        "model": model.get("model", "vertex_ai/gemini-2.5-flash"),
        "temperature": model.get("temperature", 0.1),
    }


def _run_semantic_analysis(config: Dict[str, Any], context_text: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
    model_cfg = _get_model_config(config)
    try:
        llm = ModelFactory.create_model(
            endpoint=model_cfg["endpoint"], model_name=model_cfg["model"], temperature=model_cfg["temperature"]
        )
        prompt = SEMANTIC_ANALYSIS_PROMPT.format(context=context_text, start_date=start_date, end_date=end_date)
        response = llm.invoke(prompt)
        content = response.content if hasattr(response, "content") else str(response)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]

        result = json.loads(content.strip())
        if isinstance(result, dict):
            return result
    except Exception as e:
        logger.warning(f"Semantic analysis failed (using regex fallback): {e}")
    return None


def parse_research_context_node(state: Dict[str, Any]) -> Dict[str, Any]:
    context_text = state.get("research_context", "")
    date_range = state.get("research_date_range", {})
    config = state.get("config", {})

    if not context_text:
        return {
            "research_parsed_context": None,
            "errors": [{"node_name": "parse_research_context", "error_type": "ValidationError", "error_message": "research_context is required"}],
        }

    start_date = date_range.get("start_date", "")
    end_date = date_range.get("end_date", "")

    if not start_date or not end_date:
        return {
            "research_parsed_context": None,
            "errors": [{"node_name": "parse_research_context", "error_type": "ValidationError", "error_message": "start_date and end_date are required"}],
        }

    date_validation = _validate_date_range(start_date, end_date)
    if not date_validation["valid"]:
        return {
            "research_parsed_context": None,
            "errors": [{"node_name": "parse_research_context", "error_type": "ValidationError", "error_message": date_validation["error"]}],
        }

    extracted = _extract_topics_and_entities(context_text)

    research_config = config.get("phase_configs", {}).get("research_analysis", {})
    include_terms = research_config.get("search_terms_include", [])
    exclude_terms = research_config.get("search_terms_exclude", [])

    if not include_terms:
        include_terms = extracted["entities"] + extracted["acronyms"]

    semantic_analysis = _run_semantic_analysis(config, context_text, date_validation["start_date"], date_validation["end_date"])

    parsed_context = {
        "original_context": context_text,
        "start_date": date_validation["start_date"],
        "end_date": date_validation["end_date"],
        "days_span": date_validation["days_span"],
        "phrases": extracted["phrases"],
        "entities": extracted["entities"],
        "acronyms": extracted["acronyms"],
        "keywords": extracted["keywords"],
        "include_terms": include_terms,
        "exclude_terms": exclude_terms,
        "semantic_analysis": semantic_analysis,
    }

    logger.info(
        f"Parsed research context: {len(extracted['phrases'])} phrases, "
        f"{len(extracted['entities'])} entities, "
        f"date range: {date_validation['start_date']} to {date_validation['end_date']}"
    )

    return {
        "research_parsed_context": parsed_context,
        "research_date_range": {"start_date": date_validation["start_date"], "end_date": date_validation["end_date"]},
        "errors": [],
    }
