.PHONY: install build dev test lint clean demo-mock demo-agent-mock demo

install:
	pnpm install
	cd services/research-engine && uv sync --dev && uv pip install pytest pytest-asyncio ruff

build:
	pnpm -r build

dev:
	@echo "Starting all services..."
	@(cd services/research-engine && uv run uvicorn src.server:app --host 0.0.0.0 --port 8100 --reload) & \
	(pnpm --filter provider-gateway dev) & \
	wait

test:
	pnpm -r test
	cd services/research-engine && uv run python -m pytest

lint:
	pnpm -r lint
	cd services/research-engine && uv run ruff check src/ tests/

clean:
	rm -rf node_modules apps/*/node_modules apps/*/dist
	rm -rf services/research-engine/.venv

# Demo: direct purchase against mock gateway (no API keys needed)
demo-mock:
	./scripts/demo-mock.sh

# Demo: LLM agent against mock gateway (requires GEIA_API_KEY)
demo-agent-mock:
	./scripts/demo-agent-mock.sh

# Demo: full live mode (requires all API keys + funded wallet)
demo:
	$(MAKE) dev
