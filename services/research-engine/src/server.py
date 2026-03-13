"""FastAPI server wrapping the LangGraph research engine."""

import logging
import os
import time

from fastapi import FastAPI, HTTPException

from .schemas import ResearchRequest, ResearchResponse

logger = logging.getLogger(__name__)

MOCK_MODE = os.getenv("MOCK_MODE", "false").lower() == "true"

app = FastAPI(title="Research Engine", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "research-engine", "mock_mode": MOCK_MODE}


@app.post("/internal/run-research", response_model=ResearchResponse)
async def run_research(req: ResearchRequest):
    start = time.time()
    logger.info(f"Research request: {req.request_id} tier={req.tier} query={req.query[:80]}")

    try:
        if MOCK_MODE:
            from .mock_engine import run_mock_research

            result = run_mock_research(req)
        else:
            from .engine.runner import run_engine

            result = run_engine(req)

        elapsed = time.time() - start
        result.timings["total_seconds"] = round(elapsed, 2)
        return result
    except Exception as e:
        logger.error(f"Research failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
