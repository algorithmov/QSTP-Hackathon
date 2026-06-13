#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

BACKEND_DIR="$REPO_ROOT/backend"
FRONTEND_DIR="$REPO_ROOT/frontend"
BACKEND_VENV="$BACKEND_DIR/.venv/bin/uvicorn"

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

  if [[ ! -f "$requirements" ]]; then
    echo "ERROR: $requirements not found for $name." >&2
    exit 1
  fi

  if [[ ! -f "$dir/.venv/bin/python" ]]; then
    echo "Setting up Python environment for $name..."
    need_python
    python3 -m venv "$dir/.venv"
  fi

  local stamp="$dir/.venv/.masar_installed"
  if [[ ! -f "$dir/.venv/bin/uvicorn" || ! -f "$stamp" || "$requirements" -nt "$stamp" ]]; then
    echo "Installing Python dependencies for $name..."
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
setup_python_venv "$BACKEND_DIR" "backend"
setup_frontend

if [[ ! -f "$BACKEND_DIR/.env" ]]; then
  echo ""
  echo "WARNING: $BACKEND_DIR/.env not found. Creating minimal .env with MOCK_MODE=true."
  cat > "$BACKEND_DIR/.env" <<'ENVEOF'
MOCK_MODE=true
LLM_PROVIDER_ORDER=gemini,groq
GEMINI_API_KEYS=
GEMINI_MODEL=gemini-2.5-flash
GROQ_API_KEY=
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODEL=llama-3.1-8b-instant
TAVILY_API_KEY=
SERPER_API_KEY=
EVIDENCE_CACHE_TTL_HOURS=24
ALLOWED_ORIGINS=http://localhost:3000
ENVEOF
  echo "Created $BACKEND_DIR/.env — add GEMINI_API_KEYS or GROQ_API_KEY plus search keys to enable live calls."
fi

if [[ ! -f "$FRONTEND_DIR/.env.local" ]]; then
  cat > "$FRONTEND_DIR/.env.local" <<'ENVEOF'
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOCKS=true
ENVEOF
  echo "Created $FRONTEND_DIR/.env.local"
fi

for port in 8000 3000; do
  existing=$(lsof -ti ":$port" 2>/dev/null || true)
  if [[ -n "$existing" ]]; then
    echo "Killing stale process on port $port (PID $existing)..."
    kill -9 $existing 2>/dev/null || true
    sleep 0.5
  fi
done

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
echo "Starting backend on port 8000..."
(
  cd "$BACKEND_DIR"
  "$BACKEND_VENV" app.main:app --host 0.0.0.0 --port 8000 --log-level warning
) > "$REPO_ROOT/scripts/backend.log" 2>&1 &
PIDS+=($!)

echo "Waiting for backend..."
until curl -sf http://localhost:8000/health > /dev/null 2>&1; do
  printf "."
  sleep 1
done
echo ""
echo "Backend ready."

echo "Starting frontend on port 3000..."
cd "$FRONTEND_DIR"
npm run dev > "$REPO_ROOT/scripts/frontend.log" 2>&1 &
PIDS+=($!)

echo ""
echo "All services running."
echo ""
echo "  Backend API : http://localhost:8000/health"
echo "  Frontend    : http://localhost:3000"
echo ""
echo "Logs:"
echo "  scripts/backend.log"
echo "  scripts/frontend.log"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

wait
