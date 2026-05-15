# Testing Guide

## Quick Reference

```bash
make test       # Run everything (recommended)
make lint       # Lint everything
make eval       # RAGAS eval — mock engine, CI-safe, thresholds not enforced
make eval-live  # RAGAS eval — real engine, real scores, thresholds enforced
make build      # TypeScript type-check
```

## Test Suites

The project has **41 functional tests** across three services. All tests run without API keys or network access.

### 1. Research Engine (Python) — 16 tests

```bash
cd services/research-engine && uv run python -m pytest
```

| File | Tests | What it covers |
|------|-------|----------------|
| `tests/test_config.py` | 4 | Tier configuration matrix (basic/pro/deep query counts, features) |
| `tests/test_mock_engine.py` | 4 | Mock engine returns correct structure, tier-aware responses |
| `tests/test_schemas.py` | 5 | ResearchRequest/ResearchResponse Pydantic validation |
| `tests/test_server_mock.py` | 3 | FastAPI /health endpoint, POST /internal/run-research in mock mode |

**Run a single file:**
```bash
cd services/research-engine && uv run python -m pytest tests/test_schemas.py -v
```

### 2. Provider Gateway (TypeScript/vitest) — 11 tests

```bash
pnpm --filter provider-gateway test
```

| File | Tests | What it covers |
|------|-------|----------------|
| `src/__tests__/health.test.ts` | 3 | Config defaults, tier schema validation, request schema validation |
| `src/__tests__/x402.test.ts` | 4 | Payment middleware: mock mode skip, registration, route config, scheme setup |
| `src/__tests__/audit-store.test.ts` | 4 | SQLite audit: insert/retrieve, complete with latency, list order, missing record |

**Run a single file:**
```bash
pnpm --filter provider-gateway exec vitest run src/__tests__/x402.test.ts
```

### 3. Buyer Agent (TypeScript/vitest) — 14 tests

```bash
pnpm --filter buyer-agent test
```

| File | Tests | What it covers |
|------|-------|----------------|
| `src/__tests__/config.test.ts` | 1 | Config loads with correct defaults (GATEWAY_URL, DAILY_BUDGET_USD, MOCK_MODE) |
| `src/__tests__/budget.test.ts` | 6 | Budget tracker: allow/reject by limit, daily exhaustion, spend tracking, tier prices |
| `src/__tests__/tools.test.ts` | 4 | Agent tool execution: list_tiers, check_budget, budget rejection, unknown tool |
| `src/__tests__/prompts.test.ts` | 3 | System prompt mentions all tools, tool definitions structure, required fields |

**Run a single file:**
```bash
pnpm --filter buyer-agent exec vitest run src/__tests__/budget.test.ts
```

## RAGAS Quality Eval

Functional tests verify that the code runs correctly. The RAGAS eval measures whether the LLM pipeline produces good outputs. These are separate concerns — all functional tests can pass while output quality is poor.

There are two targets:

```bash
make eval       # mock engine — verifies the script runs, no API costs, CI-safe
make eval-live  # real engine — actual quality scores that mean something
```

### `make eval` (mock mode)

Runs `tests/eval_ragas.py` against the mock engine. Uses 5 of the 25 golden cases from `tests/eval_cases.jsonl`. Completes in ~3 minutes and costs only the RAGAS judge calls (gpt-4o-mini). **Thresholds are not enforced** — mock responses are canned generic text, so quality scores are structurally low and meaningless. This target exists to confirm the eval pipeline works end-to-end.

Requires: `OPENAI_API_KEY` (RAGAS uses it as the LLM judge even in mock mode).

### `make eval-live` (live mode)

Runs against the real research engine: real Tavily searches, real LLM calls, real outputs. Thresholds are enforced — exits non-zero if `answer_relevancy < 0.70` or `faithfulness < 0.65`.

Requires: `OPENAI_API_KEY` + `TAVILY_API_KEY` (both already in `.env`).

**Run more cases or adjust thresholds:**

```bash
# 10 cases with stricter relevancy threshold
cd services/research-engine && EVAL_MAX_CASES=10 EVAL_MIN_RELEVANCY=0.75 uv run python -m tests.eval_ragas

# All 24 non-out-of-scope cases (slow, costs more)
cd services/research-engine && EVAL_MAX_CASES=24 uv run python -m tests.eval_ragas
```

**Environment variables:**

| Variable | Default | Description |
|---|---|---|
| `EVAL_MOCK_MODE` | `false` | `true` = mock engine, `false` = real engine |
| `EVAL_MAX_CASES` | `5` | Number of golden cases to evaluate |
| `EVAL_MIN_RELEVANCY` | `0.70` | Minimum `answer_relevancy` threshold (live mode only) |

**On faithfulness scores:** Faithfulness is printed but **not enforced** as a pass/fail gate. This is a causal synthesis engine — it draws conclusions across 15–25 articles that won't appear verbatim in any 500-char snippet, even when accurate. A Q&A bot that copies sentences from sources scores 0.9+; a system that reasons across sources typically lands in the 0.30–0.45 range. Track it as a trend over time (a sudden drop signals the model may be hallucinating), but don't use it as a hard gate. `answer_relevancy` is the primary quality signal.

**When to run `make eval-live`:**
- Before and after any prompt change in the research engine
- Before any model upgrade or swap (`PROVIDER_LLM_MODEL`, `PROVIDER_LLM_MODEL_FAST`)
- After significant changes to the LangGraph pipeline nodes

## Recommended Test Order

When developing or verifying changes, run tests in dependency order:

```bash
# 1. Research engine first (no dependencies)
cd services/research-engine && uv run python -m pytest -v

# 2. Provider gateway (depends on engine contract)
pnpm --filter provider-gateway test

# 3. Buyer agent (depends on gateway contract)
pnpm --filter buyer-agent test
```

Or just run everything at once:

```bash
make test
```

## Linting

```bash
# Everything
make lint

# Individual services
pnpm --filter provider-gateway lint    # ESLint for TypeScript
pnpm --filter buyer-agent lint         # ESLint for TypeScript
cd services/research-engine && uv run ruff check src/ tests/   # Ruff for Python
```

## TypeScript Build Verification

```bash
# Build all TypeScript packages
make build

# Individual
pnpm --filter provider-gateway build
pnpm --filter buyer-agent build
```

Build errors indicate type mismatches — fix these before running tests. vitest uses esbuild transforms and is more permissive than `tsc`, so tests can pass while the build fails.

## End-to-End Smoke Test

The fastest way to verify the full system works:

```bash
make demo-mock
```

This starts all services in mock mode, runs a direct research purchase, and shuts down. If it exits cleanly with a research result displayed, the full stack is working.

**LLM agent smoke test** (requires `OPENAI_API_KEY`):

```bash
make demo-agent-mock
```

Starts gateway + engine in mock mode, then runs the buyer agent's tool-calling loop for real.

## CI

GitHub Actions runs on every push and pull request to `main`. See `.github/workflows/ci.yml`.

| Job | Trigger | What it runs |
|---|---|---|
| `test-node` | push, PR | `pnpm -r lint` + `pnpm -r test` |
| `test-python` | push, PR | `ruff check` + `pytest` |
| `eval` | push to `main` only | RAGAS eval in mock mode |

The `eval` job only runs on `main` pushes (not PRs) because it requires `OPENAI_API_KEY` to be set as a repository secret.

## Test Architecture Notes

- **Config defaults:** `LLM_PROVIDER=openai`, `BUYER_LLM_MODEL=gpt-4o`, `BUYER_LLM_MODEL_FAST=gpt-4o-mini`. Tests that construct a config object manually (e.g. `budget.test.ts`, `tools.test.ts`) use these values — update them if the schema changes.
- **Mocking strategy:** Tests mock the `../index.js` logger export to prevent Commander.js from parsing `process.argv` during test imports. If you add a new test file that imports from modules using `logger`, add `vi.mock("../index.js", ...)` before your imports.
- **SQLite tests:** The audit store tests create a `data/test-audit.db` file that is cleaned up in `afterEach`. If tests fail mid-run, you may need to manually delete this file.
- **No network:** All functional tests run offline. The x402 middleware tests mock `@x402/express`, `@x402/core/server`, and `@x402/evm/exact/server`. The buyer agent tests mock the logger and don't instantiate real HTTP clients.
- **Eval dataset:** `tests/eval_cases.jsonl` is the golden set for RAGAS. Add new cases as JSONL lines; cases with `"difficulty": "out_of_scope"` are skipped by the eval script.
