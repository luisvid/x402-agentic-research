"""
Trimmed GraphState for Research Analysis only.

Keeps only the ~15 fields needed for the 7-node research pipeline.
Stripped: weekly/monthly/quarterly, TVL, social media, GCS, email, HITL fields.
"""

import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict


class GraphState(TypedDict):
    """State for the research analysis pipeline."""

    # Input configuration
    config: Optional[Dict[str, Any]]

    # Pipeline tracking
    execution_id: str
    phase: Optional[str]
    errors: Annotated[List[Dict[str, Any]], operator.add]

    # Search
    search_queries: List[str]
    raw_articles: Annotated[List[Dict[str, Any]], operator.add]
    search_metadata: Optional[Dict[str, Any]]

    # Research Analysis fields
    research_context: Optional[str]
    research_date_range: Optional[Dict[str, str]]
    research_parsed_context: Optional[Dict[str, Any]]
    research_search_batches: Optional[List[Dict[str, Any]]]
    research_search_results: Optional[List[Dict[str, Any]]]
    research_article_scores: Optional[List[Dict[str, Any]]]
    research_analysis_result: Optional[Dict[str, Any]]

    # Clustering (used by correlator)
    clustered_events: List[Dict[str, Any]]

    # Final output
    final_report: Optional[str]
