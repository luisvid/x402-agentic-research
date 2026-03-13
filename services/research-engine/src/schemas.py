"""Pydantic schemas for the research engine API."""

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class ResearchRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    start_date: str  # YYYY-MM-DD
    end_date: str
    tier: Literal["basic", "pro", "deep"] = "pro"
    format: Literal["json", "markdown", "both"] = "both"


class ResearchResponse(BaseModel):
    request_id: str
    status: Literal["completed", "failed", "no_data"]
    tier: str
    summary: str | None = None
    key_findings: list[dict] | None = None
    causal_chain: dict | None = None
    sources: list[dict] = Field(default_factory=list)
    confidence: float | None = None
    report_markdown: str | None = None
    timings: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
