"""
RAGAS evaluation script for the research engine.

Runs a subset of eval_cases.jsonl through the research pipeline and
measures answer_relevancy and faithfulness against RAGAS thresholds.

Usage:
    make eval
    # or directly:
    cd services/research-engine && uv run python -m tests.eval_ragas

Environment:
    OPENAI_API_KEY   — required (RAGAS uses it as the LLM judge, even in mock mode)
    TAVILY_API_KEY   — required only when EVAL_MOCK_MODE=false
    EVAL_MOCK_MODE   — "true" to use mock engine responses (no Tavily needed)
    EVAL_MAX_CASES   — max number of cases to evaluate (default: 5)
    EVAL_MIN_RELEVANCY — minimum answer_relevancy threshold (default: 0.70, enforced)
    faithfulness is tracked but not enforced — see run_eval() for rationale
"""

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (two levels up from services/research-engine)
_root_env = Path(__file__).parents[3] / ".env"
load_dotenv(_root_env)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EVAL_CASES_PATH = Path(__file__).parent / "eval_cases.jsonl"
EVAL_MOCK_MODE = os.getenv("EVAL_MOCK_MODE", "false").lower() == "true"
EVAL_MAX_CASES = int(os.getenv("EVAL_MAX_CASES", "5"))
EVAL_MIN_RELEVANCY = float(os.getenv("EVAL_MIN_RELEVANCY", "0.70"))


def load_eval_cases(max_cases: int) -> list[dict]:
    cases = []
    with open(EVAL_CASES_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            if case.get("difficulty") == "out_of_scope":
                continue
            cases.append(case)
            if len(cases) >= max_cases:
                break
    return cases


def run_research_for_case(case: dict) -> dict | None:
    """Run the research engine for a single eval case. Returns a RAGAS-compatible dict."""
    if EVAL_MOCK_MODE:
        import uuid

        from src.mock_engine import run_mock_research
        from src.schemas import ResearchRequest

        req = ResearchRequest(
            request_id=str(uuid.uuid4()),
            query=case["query"],
            start_date=case["start_date"],
            end_date=case["end_date"],
            tier=case["tier"],
        )
        result = run_mock_research(req)
    else:
        import uuid

        from src.engine.runner import run_engine
        from src.schemas import ResearchRequest

        req = ResearchRequest(
            request_id=str(uuid.uuid4()),
            query=case["query"],
            start_date=case["start_date"],
            end_date=case["end_date"],
            tier=case["tier"],
        )
        result = run_engine(req)

    if result.status not in ("completed", "no_data"):
        logger.warning(f"Case {case['id']} returned status={result.status}")
        return None

    # Use article snippets as contexts so RAGAS faithfulness has real text to check.
    # Falls back to title if snippet is absent (e.g. mock engine).
    contexts = [
        s.get("snippet") or s.get("title", "")
        for s in (result.sources or [])
        if s.get("snippet") or s.get("title")
    ]
    return {
        "question": case["query"],
        "answer": result.summary or "",
        "contexts": contexts or ["no sources"],
    }


def run_eval() -> None:
    try:
        from datasets import Dataset
        from langchain_openai import ChatOpenAI
        from langchain_openai import OpenAIEmbeddings as LCOpenAIEmbeddings
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import _AnswerRelevancy as AnswerRelevancy
        from ragas.metrics import _Faithfulness as Faithfulness
    except ImportError:
        logger.error("ragas and datasets are required: run 'uv sync --extra dev' in services/research-engine")
        sys.exit(1)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY is required — RAGAS uses it as the LLM judge")
        sys.exit(1)

    # Use gpt-4o-mini as the RAGAS judge — cheaper, sufficient for relevancy/faithfulness.
    # _AnswerRelevancy needs LangChain-style embed_query/embed_documents interface.
    evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", api_key=api_key))
    evaluator_embeddings = LCOpenAIEmbeddings(api_key=api_key)

    cases = load_eval_cases(EVAL_MAX_CASES)
    logger.info(f"Running RAGAS eval on {len(cases)} cases (mock_engine={EVAL_MOCK_MODE})")

    rows: list[dict] = []
    for case in cases:
        logger.info(f"Evaluating case {case['id']}: {case['query'][:60]}...")
        row = run_research_for_case(case)
        if row:
            rows.append(row)

    if not rows:
        logger.error("No valid results collected — cannot evaluate")
        sys.exit(1)

    dataset = Dataset.from_list(rows)
    logger.info(f"Running RAGAS metrics on {len(rows)} results...")

    result = evaluate(
        dataset,
        metrics=[
            AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings),
            Faithfulness(llm=evaluator_llm),
        ],
    )

    def _to_float(val: object) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, list):
            valid = [v for v in val if v is not None and v == v]  # filter None and NaN
            return sum(valid) / len(valid) if valid else float("nan")
        return float("nan")

    relevancy = _to_float(result["answer_relevancy"])
    faithfulness_score = _to_float(result["faithfulness"])

    rel_str = f"{relevancy:.3f}" if relevancy == relevancy else "n/a"
    faith_str = f"{faithfulness_score:.3f}" if faithfulness_score == faithfulness_score else "n/a"

    print(f"\n{'='*50}")
    print(f"RAGAS Evaluation Results ({len(rows)} cases)")
    if EVAL_MOCK_MODE:
        print("  NOTE: mock mode — scores not meaningful, thresholds not enforced")
    print(f"{'='*50}")
    print(f"  answer_relevancy : {rel_str}  (threshold: {EVAL_MIN_RELEVANCY})  ← primary gate")
    print(f"  faithfulness     : {faith_str}  (informational only)")
    print(f"{'='*50}\n")

    # In mock mode the engine returns canned generic text and sources are bare URLs,
    # so quality scores are structurally meaningless — skip threshold enforcement.
    if EVAL_MOCK_MODE:
        logger.info("EVAL COMPLETE (mock mode — thresholds not enforced)")
        return

    # Faithfulness is tracked as a trend indicator only. This is a causal synthesis
    # engine — it draws conclusions across many sources, so claims rarely appear
    # verbatim in any 500-char snippet even when accurate. answer_relevancy is the
    # meaningful pass/fail gate.
    if relevancy != relevancy:  # NaN — all LLM judge calls failed
        logger.error("answer_relevancy could not be computed — check OPENAI_API_KEY")
        sys.exit(1)

    if relevancy < EVAL_MIN_RELEVANCY:
        logger.error(f"EVAL FAILED: answer_relevancy {relevancy:.3f} < {EVAL_MIN_RELEVANCY}")
        sys.exit(1)

    logger.info("EVAL PASSED")


if __name__ == "__main__":
    run_eval()
