#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"

install_missing_runtime_macos() {
  local missing=("$@")
  if [[ "${#missing[@]}" -eq 0 ]]; then
    return
  fi

  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "ERROR: missing required runtime(s): ${missing[*]}" >&2
    echo "Install Python 3 and Node.js 18+ first, then rerun ./setup.sh." >&2
    exit 1
  fi

  if ! command -v brew >/dev/null 2>&1; then
    echo "ERROR: missing required runtime(s): ${missing[*]}" >&2
    echo "Homebrew is not installed, so setup.sh will not install system packages automatically." >&2
    echo "Install Python 3 and Node.js 18+ first, then rerun ./setup.sh." >&2
    exit 1
  fi

  echo "Installing missing runtime(s) with Homebrew: ${missing[*]}"
  for runtime in "${missing[@]}"; do
    case "$runtime" in
      python3) brew install python ;;
      node|npm) brew install node ;;
    esac
  done
}

missing=()
command -v python3 >/dev/null 2>&1 || missing+=("python3")
command -v node >/dev/null 2>&1 || missing+=("node")
command -v npm >/dev/null 2>&1 || missing+=("npm")

if [[ "${#missing[@]}" -gt 0 ]]; then
  install_missing_runtime_macos "${missing[@]}"
fi

echo "Masar local setup"
echo "Repository: $REPO_ROOT"
echo ""
echo "This will start:"
echo "  model service : http://localhost:9000"
echo "  backend API   : http://localhost:8000"
echo "  frontend      : http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop all services."
echo ""

exec "$REPO_ROOT/scripts/run_local.sh"
