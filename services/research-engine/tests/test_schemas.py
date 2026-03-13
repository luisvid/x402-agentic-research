"""Tests for research engine schemas."""

import pytest
from pydantic import ValidationError

from src.schemas import ResearchRequest, ResearchResponse


def test_research_request_defaults():
    req = ResearchRequest(query="Test query", start_date="2025-01-01", end_date="2025-06-01")
    assert req.tier == "pro"
    assert req.format == "both"
    assert req.request_id  # auto-generated


def test_research_request_valid_tiers():
    for tier in ("basic", "pro", "deep"):
        req = ResearchRequest(query="Test", start_date="2025-01-01", end_date="2025-06-01", tier=tier)
        assert req.tier == tier


def test_research_request_invalid_tier():
    with pytest.raises(ValidationError):
        ResearchRequest(query="Test", start_date="2025-01-01", end_date="2025-06-01", tier="premium")


def test_research_response_minimal():
    resp = ResearchResponse(
        request_id="test-123",
        status="completed",
        tier="pro",
        sources=[],
    )
    assert resp.status == "completed"
    assert resp.summary is None
    assert resp.timings == {}


def test_research_response_full():
    resp = ResearchResponse(
        request_id="test-456",
        status="completed",
        tier="deep",
        summary="Test summary",
        key_findings=[{"finding": "Test"}],
        causal_chain={"trigger": "Test event"},
        sources=[{"title": "Source", "url": "https://example.com"}],
        confidence=0.85,
        report_markdown="# Report",
        timings={"total_seconds": 5.2},
        metadata={"engine": "mock"},
    )
    assert resp.confidence == 0.85
    assert len(resp.sources) == 1
