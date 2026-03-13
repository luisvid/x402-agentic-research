"""
Research Analyzer Node for Research Analysis.

Multi-step reasoning pipeline:
  Step 1: Event Extraction & Classification (Flash)
  Step 2: Causal Ranking (Flash)
  Step 3: Synthesis & Report (Pro)

Import fix: from utils.model_factory -> from ..utils.model_factory
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..utils.model_factory import ModelFactory

logger = logging.getLogger(__name__)

EVENT_EXTRACTION_PROMPT = """You are a research analyst. Extract distinct events from the articles below and classify each using the causal taxonomy.

## Research Topic
{context}

## Date Range
{start_date} to {end_date}

{semantic_context_section}

## Articles ({article_count} total)

{articles_text}

## Causal Taxonomy — classify each event as exactly ONE of:
- **trigger** — A discrete event that initiated or accelerated the metric change
- **precondition** — A trend already underway BEFORE the timeframe, creating vulnerability
- **consequence** — A downstream outcome CAUSED BY the trigger
- **contextual** — Background conditions that influenced magnitude but didn't initiate the change

## Output
Respond with ONLY a valid JSON array. No other text.
[{{"event": "Brief description", "event_type": "trigger|precondition|consequence|contextual", "approximate_date": "YYYY-MM-DD or range", "evidence_articles": [1, 5], "magnitude": "Quantitative impact", "causal_role": "How this connects to the metric change"}}]
"""

CAUSAL_RANKING_PROMPT = """You are a causal reasoning specialist. Rank the extracted events by explanatory power.

## Research Topic
{context}

## Date Range
{start_date} to {end_date}

## Extracted Events
{events_json}

## Ranking Priority: Triggers first, then consequences, preconditions, contextual.

## Output
Respond with ONLY valid JSON.
{{"ranked_events": [{{"rank": 1, "event": "...", "event_type": "trigger", "temporal_match": "strong|moderate|weak", "ranking_justification": "..."}}], "causal_chain": {{"preconditions": ["..."], "trigger": "The pivotal event", "cascading_effects": ["..."], "contextual_factors": ["..."]}}, "ranking_rationale": "..."}}
"""

SYNTHESIS_PROMPT = """You are a senior research analyst writing the final report. PRESERVE the ranking order exactly as provided.

## Research Topic
{context}

## Date Range
{start_date} to {end_date}

## Pre-Computed Causal Analysis
{ranking_json}

## Articles ({article_count} total)
{articles_text}

## Output
Respond with ONLY valid JSON.
{{"executive_summary": "2-3 sentences", "key_findings": [{{"finding": "...", "event_type": "trigger|precondition|consequence|contextual", "temporal_match": "strong|moderate|weak", "approximate_date": "...", "confidence": "high|medium|low", "evidence": ["..."], "causal_role": "..."}}], "causal_chain": {{"preconditions": [], "trigger": "...", "cascading_effects": [], "contextual_factors": []}}, "timeline": {{"early_period": "...", "mid_period": "...", "recent_period": "..."}}, "implications": "...", "additional_context": "..."}}
"""


def _format_articles_for_prompt(articles: List[Dict], max_chars: int = 800) -> str:
    if not articles:
        return "*No articles found.*"
    lines = []
    for i, article in enumerate(articles[:30], 1):
        title = article.get("title", "Untitled")
        content = article.get("content", "")[:max_chars]
        url = article.get("url", "")
        date = article.get("published_date", "")
        lines.append(f"{i}. **{title}**\n   {content}\n   Source: {url} ({date})")
    return "\n\n".join(lines)


def _get_model_config(config: Dict[str, Any], step: str = "pro") -> Dict[str, Any]:
    model_config = config.get("model_config", {})
    agent_models = model_config.get("agent_models", {})
    model = agent_models.get("research_analyzer", {}) or agent_models.get("tvl_analyzer", {})

    if step == "flash":
        return {
            "endpoint": model.get("endpoint", model_config.get("default_endpoint", "geia")),
            "model": model.get("model", "vertex_ai/gemini-2.5-flash"),
            "temperature": model.get("temperature", 0.1),
        }
    else:
        return {
            "endpoint": model.get("endpoint", model_config.get("default_endpoint", "geia")),
            "model": model.get("model", "vertex_ai/gemini-2.5-pro"),
            "temperature": model.get("temperature", 0.2),
        }


def _parse_json_response(content: str) -> Any:
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0]
    elif "```" in content:
        content = content.split("```")[1].split("```")[0]
    return json.loads(content.strip())


def _build_semantic_context_section(parsed_context: Dict[str, Any]) -> str:
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


def _step1_extract_events(llm, articles_text, context_text, start_date, end_date, article_count, parsed_context) -> Optional[List[Dict]]:
    semantic_section = _build_semantic_context_section(parsed_context)
    prompt = EVENT_EXTRACTION_PROMPT.format(
        context=context_text, start_date=start_date, end_date=end_date,
        semantic_context_section=semantic_section, article_count=article_count, articles_text=articles_text,
    )
    logger.info("Step 1/3: Extracting and classifying events...")
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    events = _parse_json_response(content)
    if not isinstance(events, list):
        events = [events] if events else []
    logger.info(f"Step 1 complete: extracted {len(events)} events")
    return events


def _step2_rank_events(llm, events, context_text, start_date, end_date) -> Optional[Dict]:
    prompt = CAUSAL_RANKING_PROMPT.format(
        context=context_text, start_date=start_date, end_date=end_date, events_json=json.dumps(events, indent=2),
    )
    logger.info("Step 2/3: Ranking events by causal explanatory power...")
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    ranking = _parse_json_response(content)
    if not isinstance(ranking, dict):
        return None
    logger.info(f"Step 2 complete: ranked {len(ranking.get('ranked_events', []))} events")
    return ranking


def _step3_synthesize(llm, ranking, articles_text, context_text, start_date, end_date, article_count) -> Optional[Dict]:
    prompt = SYNTHESIS_PROMPT.format(
        context=context_text, start_date=start_date, end_date=end_date,
        ranking_json=json.dumps(ranking, indent=2), article_count=article_count, articles_text=articles_text,
    )
    logger.info("Step 3/3: Synthesizing final analysis report...")
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    analysis = _parse_json_response(content)
    if not isinstance(analysis, dict):
        return None
    logger.info(f"Step 3 complete: {len(analysis.get('key_findings', []))} findings synthesized")
    return analysis


def _fallback_single_prompt(llm, articles_text, context_text, start_date, end_date, article_count) -> Optional[Dict]:
    prompt = f"""Analyze these articles about the research topic and provide structured analysis.

## Research Topic
{context_text}

## Date Range
{start_date} to {end_date}

## Articles ({article_count} total)
{articles_text}

Respond in valid JSON: {{"executive_summary": "...", "key_findings": [{{"finding": "...", "event_type": "...", "temporal_match": "...", "approximate_date": "", "confidence": "...", "evidence": ["..."], "causal_role": "..."}}], "causal_chain": {{"preconditions": [], "trigger": "...", "cascading_effects": [], "contextual_factors": []}}, "timeline": {{"early_period": "", "mid_period": "", "recent_period": ""}}, "implications": "", "additional_context": ""}}
"""
    logger.info("Running fallback single-prompt analysis...")
    response = llm.invoke(prompt)
    content = response.content if hasattr(response, "content") else str(response)
    return _parse_json_response(content)


def llm_analyze_research_node(state: Dict[str, Any]) -> Dict[str, Any]:
    config = state.get("config", {})
    research_config = config.get("phase_configs", {}).get("research_analysis", {})
    analysis_config = research_config.get("analysis_config", {})
    min_articles = analysis_config.get("min_articles_for_analysis", 3)

    articles = state.get("research_search_results", [])
    parsed_context = state.get("research_parsed_context", {})

    if not parsed_context:
        return {"research_analysis_result": None, "errors": []}

    context_text = parsed_context.get("original_context", "")
    start_date = parsed_context.get("start_date", "")
    end_date = parsed_context.get("end_date", "")
    total_articles = len(articles)

    if total_articles < min_articles:
        return {
            "research_analysis_result": {"status": "insufficient_data", "total_articles": total_articles, "context": context_text, "analysis": None},
            "errors": [],
        }

    flash_cfg = _get_model_config(config, step="flash")
    pro_cfg = _get_model_config(config, step="pro")

    try:
        flash_llm = ModelFactory.create_model(endpoint=flash_cfg["endpoint"], model_name=flash_cfg["model"], temperature=flash_cfg["temperature"])
        pro_llm = ModelFactory.create_model(endpoint=pro_cfg["endpoint"], model_name=pro_cfg["model"], temperature=pro_cfg["temperature"])
    except Exception as e:
        logger.error(f"Failed to create LLM: {e}")
        return {"research_analysis_result": None, "errors": [{"node_name": "llm_analyze_research", "error_type": "ModelError", "error_message": str(e)}]}

    articles_text = _format_articles_for_prompt(articles)
    analysis_data = None
    intermediate_data: dict[str, Any] = {}

    try:
        events = _step1_extract_events(flash_llm, articles_text, context_text, start_date, end_date, total_articles, parsed_context)
        intermediate_data["step1_events"] = events
        if not events:
            raise ValueError("Step 1 produced no events")

        ranking = _step2_rank_events(flash_llm, events, context_text, start_date, end_date)
        intermediate_data["step2_ranking"] = ranking
        if not ranking or not ranking.get("ranked_events"):
            raise ValueError("Step 2 produced no ranking")

        analysis_data = _step3_synthesize(pro_llm, ranking, articles_text, context_text, start_date, end_date, total_articles)
        intermediate_data["step3_synthesis"] = analysis_data
        if not analysis_data:
            raise ValueError("Step 3 produced no analysis")

        if "causal_chain" not in analysis_data and "causal_chain" in ranking:
            analysis_data["causal_chain"] = ranking["causal_chain"]

    except Exception as e:
        logger.warning(f"Multi-step pipeline failed: {e}")
        try:
            analysis_data = _fallback_single_prompt(pro_llm, articles_text, context_text, start_date, end_date, total_articles)
        except Exception as fallback_err:
            logger.error(f"Fallback also failed: {fallback_err}")

    if not analysis_data:
        return {
            "research_analysis_result": {"status": "error", "total_articles": total_articles, "context": context_text, "analysis": None, "error": "All analysis attempts failed"},
            "errors": [{"node_name": "llm_analyze_research", "error_type": "LLMError", "error_message": "All analysis failed"}],
        }

    if not isinstance(analysis_data, dict):
        analysis_data = {"executive_summary": str(analysis_data)[:500], "key_findings": [], "causal_chain": {"preconditions": [], "trigger": "", "cascading_effects": [], "contextual_factors": []}, "timeline": {"early_period": "", "mid_period": "", "recent_period": ""}, "implications": "", "additional_context": ""}

    result = {
        "status": "analyzed",
        "total_articles": total_articles,
        "context": context_text,
        "start_date": start_date,
        "end_date": end_date,
        "analysis": analysis_data,
        "intermediate_data": intermediate_data,
    }

    return {"research_analysis_result": result, "errors": []}
