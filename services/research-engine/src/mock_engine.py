"""Deterministic mock engine for testing without API keys."""

from .schemas import ResearchRequest, ResearchResponse


def run_mock_research(req: ResearchRequest) -> ResearchResponse:
    """Return canned research response for testing."""
    summary = (
        f"Mock analysis of '{req.query}' from {req.start_date} to {req.end_date}. "
        f"Tier: {req.tier}. This is a deterministic mock response for testing."
    )

    key_findings = [
        {
            "finding": "Mock finding 1: Significant market event detected",
            "event_type": "trigger",
            "confidence": "high",
            "evidence": ["Mock source article 1", "Mock source article 2"],
            "causal_role": "Primary driver of observed metric change",
        },
        {
            "finding": "Mock finding 2: Structural precondition identified",
            "event_type": "precondition",
            "confidence": "medium",
            "evidence": ["Mock source article 3"],
            "causal_role": "Created vulnerability exploited by trigger event",
        },
    ]

    causal_chain = {
        "preconditions": ["Pre-existing structural weakness (mock)"],
        "trigger": "Specific catalytic event (mock)",
        "cascading_effects": ["Downstream consequence 1 (mock)"],
        "contextual_factors": ["Broader market condition (mock)"],
    }

    sources = [
        {"title": "Mock Article 1", "url": "https://example.com/article-1", "published_date": req.start_date},
        {"title": "Mock Article 2", "url": "https://example.com/article-2", "published_date": req.end_date},
    ]

    report_md = f"""# Research Analysis Report

**Topic:** {req.query}
**Date Range:** {req.start_date} to {req.end_date}

## Executive Summary
{summary}

## Key Findings
1. **Mock finding 1** [TRIGGER] (Confidence: high)
2. **Mock finding 2** [PRECONDITION] (Confidence: medium)

## Causal Model
**Trigger:** Specific catalytic event (mock)
**Preconditions:** Pre-existing structural weakness (mock)

---
*Mock report generated for testing*
"""

    include_report = req.tier in ("pro", "deep")
    include_causal = req.tier in ("pro", "deep")

    return ResearchResponse(
        request_id=req.request_id,
        status="completed",
        tier=req.tier,
        summary=summary,
        key_findings=key_findings,
        causal_chain=causal_chain if include_causal else None,
        sources=sources,
        confidence=0.82,
        report_markdown=report_md if include_report else None,
        timings={"mock": True},
        metadata={"engine": "mock", "tier": req.tier},
    )
