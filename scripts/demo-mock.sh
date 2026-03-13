#!/usr/bin/env bash
# demo-mock.sh — Run a full mock demo (no API keys, no wallet, no real payments)
#
# Starts the research engine + provider gateway in mock mode, then runs
# a buyer agent direct purchase against the mock gateway.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export MOCK_MODE=true
export LOG_LEVEL=info

echo "============================================================"
echo "  x402 Agentic Research — Mock Demo"
echo "============================================================"
echo ""
echo "  Mode:     MOCK (no real payments, no external APIs)"
echo "  Engine:   http://localhost:8100"
echo "  Gateway:  http://localhost:8200"
echo ""

# Cleanup function
cleanup() {
  echo ""
  echo "Shutting down services..."
  kill "$ENGINE_PID" "$GATEWAY_PID" 2>/dev/null || true
  wait "$ENGINE_PID" "$GATEWAY_PID" 2>/dev/null || true
  echo "Done."
}
trap cleanup EXIT

# Start research engine
echo "[1/3] Starting research engine (mock mode)..."
cd services/research-engine
MOCK_MODE=true uv run uvicorn src.server:app --host 0.0.0.0 --port 8100 --log-level warning &
ENGINE_PID=$!
cd "$ROOT_DIR"

# Start provider gateway
echo "[2/3] Starting provider gateway (mock mode)..."
MOCK_MODE=true pnpm --filter provider-gateway dev 2>&1 | grep -v "^$" &
GATEWAY_PID=$!

# Wait for services to be ready
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

echo ""
echo "[3/3] Running buyer agent — direct purchase (pro tier)..."
echo ""

# Run the buyer agent direct command
pnpm --filter buyer-agent buyer direct \
  --query "Compare yield-bearing stablecoins on Cardano vs Ethereum L2s" \
  --start-date "2025-10-01" \
  --end-date "2026-03-01" \
  --tier pro

echo ""
echo "============================================================"
echo "  Mock demo complete!"
echo "============================================================"
