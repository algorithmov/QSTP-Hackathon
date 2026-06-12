#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

MODEL_DIR="$REPO_ROOT/model_service"
BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"

MODEL_VENV="$MODEL_DIR/.venv/bin/uvicorn"
BACKEND_VENV="$BACKEND_DIR/.venv/bin/uvicorn"

# ── environment checks & auto-setup ─────────────────────────────────────────

need_node() {
  command -v node >/dev/null 2>&1 || { echo "ERROR: node not found. Install Node.js 18+ first."; exit 1; }
  command -v npm  >/dev/null 2>&1 || { echo "ERROR: npm not found. Install Node.js 18+ first."; exit 1; }
}

need_python() {
  command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found."; exit 1; }
}

setup_python_venv() {
  local dir="$1"
  local name="$2"
  local requirements="$dir/requirements.txt"
  if [[ ! -f "$requirements" && -f "$dir/requirements.mac.txt" ]]; then
    requirements="$dir/requirements.mac.txt"
  fi
  if [[ ! -f "$requirements" && -f "$dir/requirements.lock.txt" ]]; then
    requirements="$dir/requirements.lock.txt"
  fi
  if [[ ! -f "$requirements" ]]; then
    echo "ERROR: no requirements file found for $name in $dir." >&2
    exit 1
  fi

  if [[ ! -f "$dir/.venv/bin/python" ]]; then
    echo "Setting up Python environment for $name..."
    need_python
    python3 -m venv "$dir/.venv"
  fi

  local stamp="$dir/.venv/.masar_requirements_installed"
  if [[ ! -f "$dir/.venv/bin/uvicorn" || ! -f "$stamp" || "$requirements" -nt "$stamp" ]]; then
    echo "Installing Python dependencies for $name from $(basename "$requirements")..."
    "$dir/.venv/bin/pip" install -q --upgrade pip
    "$dir/.venv/bin/pip" install -q -r "$requirements"
    date > "$stamp"
    echo "$name environment ready."
  fi
}

setup_frontend() {
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "Installing frontend dependencies..."
    need_node
    cd "$FRONTEND_DIR"
    npm install --silent
    echo "Frontend dependencies ready."
  fi
}

echo "Checking environments..."
setup_python_venv "$MODEL_DIR"   "model_service"
setup_python_venv "$BACKEND_DIR" "backend"
setup_frontend

# ── backend .env guard ───────────────────────────────────────────────────────

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo ""
  echo "WARNING: $BACKEND_DIR/.env not found."
  echo "Creating a local .env that uses the local model service and rule-based LLM fallback."
  cat > "$BACKEND_DIR/.env" <<'ENVEOF'
MODEL_SERVICE_URL=http://localhost:9000
MOCK_MODE=false
ENABLE_DIALECT_REWRITE=false
LLM_PROVIDER=rule_based
GEMINI_MODEL=gemini-2.5-flash
LLM_TIMEOUT=8
ENVEOF
  echo "Created $BACKEND_DIR/.env — add GEMINI_API_KEY and FANAR_API_KEY for live LLM output."
fi

if [[ ! -f "$FRONTEND_DIR/.env.local" ]]; then
  cat > "$FRONTEND_DIR/.env.local" <<'ENVEOF'
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCKS=false
ENVEOF
  echo "Created $FRONTEND_DIR/.env.local for live local backend calls."
fi

# ── kill any stale processes on our ports ────────────────────────────────────

for port in 9000 8000 3000; do
  existing=$(lsof -ti ":$port" 2>/dev/null || true)
  if [[ -n "$existing" ]]; then
    echo "Killing stale process on port $port (PID $existing)..."
    kill -9 $existing 2>/dev/null || true
    sleep 0.5
  fi
done

# ── start services ───────────────────────────────────────────────────────────

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

echo ""
echo "Starting model service on port 9000..."
(
  cd "$MODEL_DIR"
  OMP_NUM_THREADS=1 TRANSFORMERS_OFFLINE=1 PYTHONUNBUFFERED=1 \
    "$MODEL_VENV" app.main:app --host 0.0.0.0 --port 9000 \
    --log-level warning
) > "$REPO_ROOT/scripts/model_service.log" 2>&1 &
PIDS+=($!)
MODEL_PID=$!

echo "Waiting for model service (CLIP + EasyOCR load ~60 s on first run)..."
until curl -sf http://localhost:9000/health > /dev/null 2>&1; do
  if ! kill -0 "$MODEL_PID" 2>/dev/null; then
    echo "ERROR: model service died. See scripts/model_service.log" >&2
    exit 1
  fi
  printf "."
  sleep 3
done
echo ""
echo "Model service ready."

echo "Starting backend on port 8000..."
(
  cd "$BACKEND_DIR"
  "$BACKEND_VENV" app.main:app --host 0.0.0.0 --port 8000 \
    --log-level warning
) > "$REPO_ROOT/scripts/backend.log" 2>&1 &
PIDS+=($!)
sleep 2

echo "Starting frontend on port 3000..."
cd "$FRONTEND_DIR"
npm run dev > "$REPO_ROOT/scripts/frontend.log" 2>&1 &
PIDS+=($!)

echo ""
echo "All three services are running."
echo ""
echo "  Model service : http://localhost:9000/health"
echo "  Backend API   : http://localhost:8000/health"
echo "  Frontend      : http://localhost:3000"
echo ""
echo "Logs:"
echo "  scripts/model_service.log"
echo "  scripts/backend.log"
echo "  scripts/frontend.log"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

wait
