"""Integration test: FastAPI server in mock mode."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["MOCK_MODE"] = "true"

from src.server import app


@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mock_mode"] is True


@pytest.mark.asyncio
async def test_run_research_mock():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/internal/run-research",
            json={
                "query": "Why did Ethena TVL drop from $15B to $5B?",
                "start_date": "2025-10-01",
                "end_date": "2026-03-01",
                "tier": "pro",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["tier"] == "pro"
    assert data["summary"] is not None
    assert data["report_markdown"] is not None
    assert len(data["sources"]) > 0


@pytest.mark.asyncio
async def test_run_research_basic_tier_no_report():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/internal/run-research",
            json={
                "query": "Simple DeFi market research query",
                "start_date": "2025-01-01",
                "end_date": "2025-06-01",
                "tier": "basic",
            },
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["report_markdown"] is None
    assert data["causal_chain"] is None
