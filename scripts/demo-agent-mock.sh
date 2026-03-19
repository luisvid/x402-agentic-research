#!/usr/bin/env bash
# demo-agent-mock.sh — Run the LLM agent demo in mock mode
#
# Requires GEIA_API_KEY to be set.
# The gateway and engine run in mock mode (no wallet/payments needed).

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export MOCK_MODE=true
export LOG_LEVEL=info

if [ -z "${GEIA_API_KEY:-}" ]; then
  echo "ERROR: GEIA_API_KEY is required for agent mode."
  echo "       Set it in your environment or .env file."
  exit 1
fi

echo "============================================================"
echo "  x402 Agentic Research — Agent Demo (Mock)"
echo "============================================================"
echo ""
echo "  Mode:     MOCK gateway + LLM agent"
echo "  Model:    ${BUYER_LLM_MODEL:-vertex_ai/gemini-2.5-pro}"
echo "  Engine:   http://localhost:8100"
echo "  Gateway:  http://localhost:8200"
echo ""

cleanup() {
  echo ""
  echo "Shutting down services..."
  kill "$ENGINE_PID" "$GATEWAY_PID" 2>/dev/null || true
  wait "$ENGINE_PID" "$GATEWAY_PID" 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT

echo "[1/3] Starting research engine (mock mode)..."
cd services/research-engine
MOCK_MODE=true uv run uvicorn src.server:app --host 0.0.0.0 --port 8100 --log-level warning &
ENGINE_PID=$!
cd "$ROOT_DIR"

echo "[2/3] Starting provider gateway (mock mode)..."
MOCK_MODE=true pnpm --filter provider-gateway dev 2>&1 | grep -v "^$" &
GATEWAY_PID=$!

echo "     Waiting for services..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8100/health > /dev/null 2>&1 && \
     curl -sf http://localhost:8200/health > /dev/null 2>&1; then
    echo "     Services ready."
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "     ERROR: Services did not start in time."
    exit 1
  fi
  sleep 1
done

GOAL="${1:-Investigate why Ethena USDe TVL dropped significantly in Q4 2025 and find potential recovery signals}"

echo ""
echo "[3/3] Running buyer agent with goal:"
echo "      \"$GOAL\""
echo ""

pnpm --filter buyer-agent buyer agent "$GOAL"

echo ""
echo "============================================================"
echo "  Agent demo complete!"
echo "============================================================"
