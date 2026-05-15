"""
Config builder: maps tier → engine configuration dict.

Tier matrix:
  basic: 8 queries, 20 results, fast model only, no report/causal chain
  pro:   15 queries, 40 results, fast+strong models, full report
  deep:  25 queries, 60 results, fast+strong models, full report

Model selection is driven by environment variables:
  PROVIDER_LLM_MODEL      — "strong" model for synthesis/analysis (default: gpt-4o)
  PROVIDER_LLM_MODEL_FAST — "fast" model for extraction/scoring  (default: gpt-4o-mini)
  LLM_PROVIDER            — provider backend: openai | anthropic (default: openai)
"""

import os
from typing import Any, Dict, Literal

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
PROVIDER_LLM_MODEL = os.getenv("PROVIDER_LLM_MODEL", "gpt-4o")
PROVIDER_LLM_MODEL_FAST = os.getenv("PROVIDER_LLM_MODEL_FAST", "gpt-4o-mini")

TIER_CONFIGS: Dict[str, Dict[str, Any]] = {
    "basic": {
        "max_queries": 8,
        "phase_configs": {
            "research_analysis": {
                "search_config": {"max_results_per_query": 3},
                "analysis_config": {"min_articles_for_analysis": 2, "skip_pro_synthesis": True},
            }
        },
        "model_config": {
            "default_endpoint": LLM_PROVIDER,
            "agent_models": {
                "research_analyzer": {"endpoint": LLM_PROVIDER, "model": PROVIDER_LLM_MODEL_FAST, "temperature": 0.1},
                "query_generator_agent": {"endpoint": LLM_PROVIDER, "model": PROVIDER_LLM_MODEL_FAST, "temperature": 0.7},
            },
        },
        "include_report": False,
        "include_causal_chain": False,
    },
    "pro": {
        "max_queries": 15,
        "phase_configs": {
            "research_analysis": {
                "search_config": {"max_results_per_query": 5},
                "analysis_config": {"min_articles_for_analysis": 3, "skip_pro_synthesis": False},
            }
        },
        "model_config": {
            "default_endpoint": LLM_PROVIDER,
            "agent_models": {
                "research_analyzer": {"endpoint": LLM_PROVIDER, "model": PROVIDER_LLM_MODEL, "temperature": 0.1},
                "query_generator_agent": {"endpoint": LLM_PROVIDER, "model": PROVIDER_LLM_MODEL_FAST, "temperature": 0.7},
            },
        },
        "include_report": True,
        "include_causal_chain": True,
    },
    "deep": {
        "max_queries": 25,
        "phase_configs": {
            "research_analysis": {
                "search_config": {"max_results_per_query": 5},
                "analysis_config": {"min_articles_for_analysis": 3, "skip_pro_synthesis": False},
            }
        },
        "model_config": {
            "default_endpoint": LLM_PROVIDER,
            "agent_models": {
                "research_analyzer": {"endpoint": LLM_PROVIDER, "model": PROVIDER_LLM_MODEL, "temperature": 0.1},
                "query_generator_agent": {"endpoint": LLM_PROVIDER, "model": PROVIDER_LLM_MODEL_FAST, "temperature": 0.7},
            },
        },
        "include_report": True,
        "include_causal_chain": True,
    },
}


def build_engine_config(tier: Literal["basic", "pro", "deep"]) -> Dict[str, Any]:
    """Build engine configuration for a given tier."""
    if tier not in TIER_CONFIGS:
        raise ValueError(f"Invalid tier: {tier}. Must be basic, pro, or deep")
    return TIER_CONFIGS[tier].copy()
