#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

MODEL_DIR="$REPO_ROOT/model_service"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

MODEL_VENV="$MODEL_DIR/.venv/bin/uvicorn"
BACKEND_VENV="$BACKEND_DIR/.venv/bin/uvicorn"

for bin in "$MODEL_VENV" "$BACKEND_VENV"; do
  if [[ ! -x "$bin" ]]; then
    echo "ERROR: $bin not found. Run the setup steps for that service first." >&2
    exit 1
  fi
done

if [[ ! -f "$FRONTEND_DIR/package.json" ]]; then
  echo "ERROR: $FRONTEND_DIR/package.json not found." >&2
  exit 1
fi

PIDS=()

cleanup() {
  echo ""
  echo "Stopping all services..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "All services stopped."
  exit 0
}

trap cleanup INT TERM

echo "Starting model service on port 9000..."
OMP_NUM_THREADS=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1 \
  "$MODEL_VENV" app.main:app --host 0.0.0.0 --port 9000 \
  --log-level warning \
  > "$REPO_ROOT/scripts/model_service.log" 2>&1 &
PIDS+=($!)
MODEL_PID=$!

echo "Waiting for model service to be ready (this takes ~60s on first load)..."
until curl -sf http://localhost:9000/health > /dev/null 2>&1; do
  if ! kill -0 "$MODEL_PID" 2>/dev/null; then
    echo "ERROR: model service process died. Check scripts/model_service.log" >&2
    exit 1
  fi
  printf "."
  sleep 3
done
echo ""
echo "Model service is ready."

echo "Starting backend on port 8000..."
"$BACKEND_VENV" app.main:app --host 0.0.0.0 --port 8000 \
  --log-level warning \
  > "$REPO_ROOT/scripts/backend.log" 2>&1 &
PIDS+=($!)

sleep 2

echo "Starting frontend on port 3000..."
cd "$FRONTEND_DIR"
npm run dev > "$REPO_ROOT/scripts/frontend.log" 2>&1 &
PIDS+=($!)

echo ""
echo "All three services are running."
echo ""
echo "  Model service health : http://localhost:9000/health"
echo "  Backend API          : http://localhost:8000"
echo "  Frontend             : http://localhost:3000"
echo ""
echo "Logs: scripts/model_service.log  scripts/backend.log  scripts/frontend.log"
echo "Press Ctrl+C to stop all services."
echo ""

wait
