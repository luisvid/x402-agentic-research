# Testing Guide

## Quick Reference

```bash
make test    # Run everything (recommended)
make lint    # Lint everything
```

## Test Suites

The project has **41 tests** across three services. All tests run without API keys or network access.

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
| `src/__tests__/config.test.ts` | 1 | Config loads with correct defaults |
| `src/__tests__/budget.test.ts` | 6 | Budget tracker: allow/reject by limit, daily exhaustion, spend tracking, tier prices |
| `src/__tests__/tools.test.ts` | 4 | Agent tool execution: list_tiers, check_budget, budget rejection, unknown tool |
| `src/__tests__/prompts.test.ts` | 3 | System prompt mentions all tools, tool definitions structure, required fields |

**Run a single file:**
```bash
pnpm --filter buyer-agent exec vitest run src/__tests__/budget.test.ts
```

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

Build errors indicate type mismatches — fix these before running tests.

## End-to-End Smoke Test

The fastest way to verify the full system works:

```bash
make demo-mock
```

This starts all services in mock mode, runs a buyer agent purchase, and shuts down. If it exits cleanly with a research result displayed, the full stack is working.

## Test Architecture Notes

- **Mocking strategy:** Tests mock the `../index.js` logger export to prevent Commander.js from parsing `process.argv` during test imports. If you add a new test file that imports from modules using `logger`, add `vi.mock("../index.js", ...)` before your imports.
- **SQLite tests:** The audit store tests create a `data/test-audit.db` file that is cleaned up in `afterEach`. If tests fail mid-run, you may need to manually delete this file.
- **No network:** All tests run offline. The x402 middleware tests mock `@x402/express`, `@x402/core/server`, and `@x402/evm/exact/server`. The buyer agent tests mock the logger and don't instantiate real HTTP clients.
