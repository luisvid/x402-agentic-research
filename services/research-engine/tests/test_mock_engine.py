"""Tests for mock engine."""

from src.mock_engine import run_mock_research
from src.schemas import ResearchRequest


def test_mock_returns_completed():
    req = ResearchRequest(query="Test query about DeFi", start_date="2025-01-01", end_date="2025-06-01", tier="pro")
    resp = run_mock_research(req)
    assert resp.status == "completed"
    assert resp.tier == "pro"
    assert resp.summary is not None
    assert resp.confidence is not None
    assert len(resp.sources) > 0
    assert len(resp.key_findings) > 0


def test_mock_basic_tier_no_report():
    req = ResearchRequest(query="Simple query test here", start_date="2025-01-01", end_date="2025-06-01", tier="basic")
    resp = run_mock_research(req)
    assert resp.status == "completed"
    assert resp.report_markdown is None
    assert resp.causal_chain is None


def test_mock_deep_tier_has_report():
    req = ResearchRequest(query="Deep analysis query test", start_date="2025-01-01", end_date="2025-06-01", tier="deep")
    resp = run_mock_research(req)
    assert resp.report_markdown is not None
    assert resp.causal_chain is not None


def test_mock_preserves_request_id():
    req = ResearchRequest(
        request_id="custom-id-123", query="Custom ID test query", start_date="2025-01-01", end_date="2025-06-01"
    )
    resp = run_mock_research(req)
    assert resp.request_id == "custom-id-123"
