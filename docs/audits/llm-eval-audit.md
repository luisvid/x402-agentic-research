# Evaluation & Observability Audit — x402-agentic-research

> Audited: 2026-05-13

## System type & stack

This is a **multi-service agentic workflow**: a TypeScript tool-calling buyer agent (custom loop, 10 turns max) that purchases results from a Python LangGraph pipeline (7-node: context parsing → query generation → Tavily search → correlation → LLM scoring → analysis → report). The LLM layer uses GEIA (OpenAI-compatible proxy at `api.saia.ai/v1`) via the OpenAI SDK in Node and `langchain-openai` in Python. No vector database; search is Tavily API. No eval tooling of any kind is installed.

## Maturity level

**Level 1 — Ad-hoc**

The project has 41 functional tests (vitest + pytest) covering schema validation, budget math, SQLite CRUD, and HTTP routing — but none of them measure LLM output quality. There is no tracing, no golden dataset, no eval framework, and no CI. Quality assessment today is: "run `make demo-mock` and eyeball it."

---

## Dimension scores

| Dimension | Score | Status |
|---|---|---|
| Tracing & Observability | 0/3 | ❌ No tracing. LLM calls are invisible beyond stdout |
| Offline Evaluation | 0/3 | ❌ No eval metrics anywhere in the codebase |
| Regression Testing | 1/3 | ⚠️ Functional tests exist; zero quality gates |
| Dataset Quality | 0/3 | ❌ No eval dataset; test data is all hardcoded |
| Human Review | 0/3 | ❌ No feedback mechanism of any kind |

---

## Gap findings

| Severity | Dimension | Finding | Recommended fix |
|---|---|---|---|
| **High** | Tracing | No LLM call is traced — latency, token cost, tool calls, and LangGraph node outputs are all invisible | Add LangSmith to Python engine (env var only for LangGraph); add OpenAI SDK wrapper in buyer agent |
| **High** | Offline Eval | `article_scorer.py` is the quality bottleneck but has zero automated evaluation — bad prompts ship silently | Add RAGAS `answer_relevancy` + `faithfulness` against a golden set |
| **High** | Regression | No CI pipeline exists; `make test` is manual and checks no quality signal | Add GitHub Actions workflow that runs tests + fail-fast eval threshold |
| **High** | Dataset | All test data is inline in 11 test files; no shareable, rerunnable eval corpus | Create `tests/eval_cases.jsonl` with 25–50 annotated examples |
| **Medium** | Offline Eval | The agent loop (`research-agent.ts`) has no test measuring whether it picks the right tier or stays in budget across varied inputs | Add 5–10 scenario-based agent evals with expected tool call sequences |
| **Medium** | Tracing | LangGraph node outputs are merged in `runner.py` but intermediate state is never captured | Instrument individual nodes with LangSmith child spans |
| **Medium** | Dataset | `article_scorer.py` uses LLM-as-judge (relevance 1–5) but the judge has never been calibrated against human labels | Create 20 hand-labeled article–query pairs; measure judge accuracy |
| **Low** | Dataset | Prompts are hardcoded inline across 7 node files — silent prompt regressions possible | Pin prompts in a versioned config file; track changes in git history with explicit version bumps |
| **Low** | Human Review | No mechanism to flag bad research outputs for review; the audit store (`audit.db`) records requests but no quality signal | Add a `quality_flag` column to audit store; surface a `/admin/flag/:id` endpoint |

---

## Detailed recommendations

### 1. Add LangSmith tracing (estimated effort: 3–4 hours)

**Current state:** `services/research-engine/src/engine/workflow.py` compiles the LangGraph graph at line 44 with no tracing hooks. The 7 nodes each call GEIA with no span attribution. In `apps/buyer-agent/src/agent/research-agent.ts`, the OpenAI SDK tool-calling loop runs completely opaque.

**Why it matters:** You cannot debug cost overruns, latency spikes, or wrong outputs without traces. LangGraph nodes merge state — without per-node spans you can't tell if a bad report came from `query_generator`, `article_scorer`, or `research_analyzer`.

**Implementation:**

```bash
# Python
cd services/research-engine && uv add langsmith
```

Add to root `.env`:
```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__...
LANGCHAIN_PROJECT=x402-research-engine
```

That's it for LangGraph — it auto-instruments because `langchain-openai` is already in use. No code changes needed.

For the buyer agent, add a thin wrapper around the OpenAI client in `apps/buyer-agent/src/agent/research-agent.ts` using `langsmith/wrappers` (the `wrapOpenAI` helper):

```typescript
// research-agent.ts top
import { wrapOpenAI } from 'langsmith/wrappers'
const client = wrapOpenAI(new OpenAI({ ... }))
```

---

### 2. Create a golden eval dataset (estimated effort: 4–5 hours)

**Current state:** Not found in codebase. All test assertions are structural (schema shape, HTTP status codes). There is no file matching `*.jsonl` or `golden*.json`.

**Why it matters:** Without a fixed dataset, you cannot tell if a code change improved or degraded research quality. Every prompt edit is a leap of faith.

**Implementation:** Create `services/research-engine/tests/eval_cases.jsonl`. Each line:

```json
{
  "id": "ev-001",
  "query": "Why did Ethena USDe TVL drop in Q4 2025?",
  "tier": "pro",
  "start_date": "2025-10-01",
  "end_date": "2025-12-31",
  "expected_topics": ["collateral", "redemption", "yield compression"],
  "expected_min_sources": 8,
  "expected_causal_chain": true,
  "difficulty": "medium",
  "added": "2026-05-13"
}
```

Start with 20–25 cases covering: easy factual queries, hard causal queries, out-of-scope queries, queries with ambiguous date ranges, and queries where the answer is "no signal found." This becomes the regression anchor for all future changes.

---

### 3. Add a RAGAS eval script (estimated effort: 4–6 hours, after dataset exists)

**Current state:** No eval framework installed. `article_scorer.py:18` has `SCORING_PROMPT` that runs LLM-as-judge for relevance (1–5 scale) but this is part of the production pipeline — it evaluates articles, not the pipeline's own output quality.

**Why it matters:** The LLM scoring node is the highest-risk component. A prompt drift there silently degrades every research report.

**Implementation:**

```bash
cd services/research-engine && uv add ragas datasets
```

Create `services/research-engine/tests/eval_ragas.py`:

```python
from ragas import evaluate
from ragas.metrics import answer_relevancy, faithfulness, context_recall
from datasets import Dataset

# Load golden cases from eval_cases.jsonl
# Run research engine for each → collect (question, answer, contexts)
# Then:
result = evaluate(
    dataset,
    metrics=[answer_relevancy, faithfulness, context_recall],
)
print(result)
assert result["answer_relevancy"] >= 0.75, "Relevancy regression detected"
```

Run this as `make eval` before any prompt change ships.

---

### 4. Add a GitHub Actions CI workflow (estimated effort: 2–3 hours)

**Current state:** No `.github/workflows/` directory found. `make test` exists but is run manually.

**Why it matters:** Without CI, every developer's "it works on my machine" is the only gate.

**Implementation:** Create `.github/workflows/ci.yml`:

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v3
      - run: make install
      - run: make test
      - run: make lint
```

Add the RAGAS eval as a separate `eval` job gated on `main` only (it needs API keys and takes longer).

---

## What's already in place

- **41 functional tests** across 11 files with good coverage of budget logic, x402 payment flow, SQLite audit store, schema validation, and HTTP routing. These are clean and well-structured.
- **`make test` wires both runtimes** — `pnpm -r test` + `uv run pytest` in one command.
- **Mock mode** (`MOCK_MODE=true`) means eval can run without API keys or a funded wallet — a major enabler for CI.
- **LangGraph node isolation** — the 7-node architecture in `workflow.py` is already structured for per-node evals. Nodes take typed state in, return typed state out.
- **SQLite audit trail** — `data/audit.db` with `GET /admin/records` gives a corpus of real requests to mine for golden cases.

---

## Recommended tool stack

| Concern | Tool | Justification |
|---|---|---|
| Tracing | **LangSmith** | Zero-config for LangGraph (env var only); also works with the OpenAI SDK via `wrapOpenAI`; free tier covers this usage |
| Offline eval | **RAGAS** | Purpose-built for the retrieve → score → generate pattern this engine uses; `answer_relevancy` + `faithfulness` match the pipeline's output contract |
| CI regression | **pytest + assert thresholds** | Already using pytest; no new tool needed — just add an `eval_ragas.py` with `assert score >= threshold` |
| Dataset | **JSONL in Git** | Lightweight, code-reviewable, works with RAGAS `Dataset.from_json()`; no platform lock-in at this scale |
| Human review | **LangSmith annotation queues** (later) | Once tracing is live, low-scoring traces can be auto-queued for review without a separate tool |

Do not add Braintrust or DeepEval — LangSmith + RAGAS is sufficient and avoids platform sprawl.

---

## Prioritised roadmap

### Week 1 (quick wins, no new platforms)

1. Add `LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY` to `.env` → instant LangGraph observability (30 min)
2. Add `wrapOpenAI` in `research-agent.ts` → buyer agent traces appear in same project (1 hour)
3. Mine `audit.db` for real queries → seed first 10 `eval_cases.jsonl` entries (2 hours)
4. Add `.github/workflows/ci.yml` running `make test` (1 hour)

### Month 1

5. Expand golden dataset to 25–30 cases (difficulty-balanced)
6. Write `eval_ragas.py` with `answer_relevancy` + `faithfulness` thresholds
7. Add `make eval` target; wire it to CI on `main` branch pushes
8. Add quality calibration: hand-label 20 article–query pairs; compare to `article_scorer.py` output; adjust scoring prompt if agreement < 80%

### Quarter 1

9. Add LangSmith annotation queue for low-scored traces (< 0.6 answer_relevancy)
10. Implement `context_recall` metric once golden contexts are established
11. Add agent-level evals: scenario tests verifying the buyer agent picks the correct tier given different query types
12. Pin prompt versions in a `prompts/` directory with changelog; add prompt diff check to CI
