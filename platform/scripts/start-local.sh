#!/usr/bin/env bash
# Start the normal RAG Evaluation Platform API and its WebUI.
#
# Adapter Workers remain run-scoped: the Platform starts them when an
# evaluation is queued and persists the resulting run in the standard Runs
# store. This launcher does not start a second, detached LightRAG service.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MONOREPO_ROOT="$(cd "$PLATFORM_ROOT/.." && pwd)"
WORKSPACE_ROOT="$(cd "$MONOREPO_ROOT/.." && pwd)"

WEBUI_ROOT="${RAG_EVAL_WEBUI_DIR:-$MONOREPO_ROOT/webui}"
PLATFORM_HOME="${RAG_EVAL_HOME:-$WORKSPACE_ROOT/data/evaluation-system/platform-home}"
API_PORT="${RAG_EVAL_API_PORT:-8765}"
WEBUI_PORT="${RAG_EVAL_WEBUI_PORT:-4178}"
API_URL="http://127.0.0.1:${API_PORT}/api/v1"

api_ready() {
  curl --noproxy '*' --fail --silent --max-time 1 "$API_URL/health" >/dev/null
}

valid_port() {
  [[ "$1" =~ ^[1-9][0-9]{0,4}$ ]] && (( 10#$1 <= 65535 ))
}

port_in_use() {
  command -v nc >/dev/null 2>&1 && nc -z -w 1 127.0.0.1 "$1" >/dev/null 2>&1
}

if ! valid_port "$API_PORT" || ! valid_port "$WEBUI_PORT"; then
  echo "RAG_EVAL_API_PORT and RAG_EVAL_WEBUI_PORT must be valid TCP ports." >&2
  exit 2
fi
if [[ "$API_PORT" == "$WEBUI_PORT" ]]; then
  echo "RAG_EVAL_API_PORT and RAG_EVAL_WEBUI_PORT must be different." >&2
  exit 2
fi

# Keep one obvious Platform/WebUI pair per launcher invocation.  Silently
# moving the defaults when an older instance is still running makes the user
# open the wrong tab and then see misleading "Failed to fetch" errors.  Stop
# the existing launcher (or explicitly choose a different pair) instead.
occupied_ports=()
port_in_use "$API_PORT" && occupied_ports+=("API $API_PORT")
port_in_use "$WEBUI_PORT" && occupied_ports+=("WebUI $WEBUI_PORT")
if (( ${#occupied_ports[@]} )); then
  echo "Required Platform port(s) are already in use: ${occupied_ports[*]}." >&2
  echo "Stop the existing start-local.sh process, or set both RAG_EVAL_API_PORT and RAG_EVAL_WEBUI_PORT to a free pair." >&2
  exit 2
fi
API_URL="http://127.0.0.1:${API_PORT}/api/v1"
if [[ ! -f "$WEBUI_ROOT/package.json" ]]; then
  echo "WebUI checkout not found: $WEBUI_ROOT" >&2
  echo "Set RAG_EVAL_WEBUI_DIR to the evaluation-system WebUI directory." >&2
  exit 2
fi
if [[ ! -x "$WEBUI_ROOT/node_modules/.bin/vite" ]]; then
  echo "WebUI dependencies are missing: $WEBUI_ROOT/node_modules/.bin/vite" >&2
  echo "Run 'npm ci' in $WEBUI_ROOT, then run this script again." >&2
  exit 2
fi

if command -v node >/dev/null 2>&1; then
  NODE_COMMAND="$(command -v node)"
else
  # A desktop shell may not source nvm even though the checked-out WebUI has
  # its dependencies installed.  Use an installed nvm Node as a narrow local
  # fallback; do not download or install anything from this launcher.
  shopt -s nullglob
  NODE_CANDIDATES=("$HOME"/.nvm/versions/node/*/bin/node)
  shopt -u nullglob
  if (( ${#NODE_CANDIDATES[@]} )); then
    NODE_COMMAND="${NODE_CANDIDATES[${#NODE_CANDIDATES[@]} - 1]}"
  else
    echo "Node.js is not available in PATH and no local nvm runtime was found." >&2
    exit 2
  fi
fi

if [[ -x "$PLATFORM_ROOT/.venv/bin/rag-eval" ]]; then
  RAG_EVAL_COMMAND=("$PLATFORM_ROOT/.venv/bin/rag-eval")
elif command -v rag-eval >/dev/null 2>&1; then
  RAG_EVAL_COMMAND=("$(command -v rag-eval)")
else
  echo "rag-eval is not installed for this checkout." >&2
  echo "Create the Platform environment, then install this repository before retrying." >&2
  exit 2
fi

API_PID=""
WEBUI_PID=""

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  for pid in "$WEBUI_PID" "$API_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for pid in "$WEBUI_PID" "$API_PID"; do
    if [[ -n "$pid" ]]; then
      wait "$pid" 2>/dev/null || true
    fi
  done
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

echo "Starting RAG Evaluation Platform"
echo "  API:    $API_URL"
echo "  WebUI:  http://127.0.0.1:${WEBUI_PORT}"
echo "  Home:   $PLATFORM_HOME"

"${RAG_EVAL_COMMAND[@]}" --home "$PLATFORM_HOME" serve --host 127.0.0.1 --port "$API_PORT" &
API_PID=$!

for _attempt in $(seq 1 50); do
  if api_ready; then
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null; then
    wait "$API_PID"
    exit $?
  fi
  sleep 0.2
done

if ! curl --noproxy '*' --fail --silent --show-error --max-time 1 "$API_URL/health" >/dev/null; then
  echo "Platform API did not become ready at $API_URL/health." >&2
  exit 1
fi

(
  cd "$WEBUI_ROOT"
  # Replace this subshell with Vite.  The cleanup trap can then terminate the
  # exact WebUI process it started, rather than leaving an orphaned Node
  # process occupying the port after the API is stopped or restarted.
  exec env VITE_RAG_EVAL_API="$API_URL" "$NODE_COMMAND" node_modules/vite/bin/vite.js --host 127.0.0.1 --port "$WEBUI_PORT" --strictPort
) &
WEBUI_PID=$!

while true; do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    wait "$API_PID"
    exit $?
  fi
  if ! kill -0 "$WEBUI_PID" 2>/dev/null; then
    wait "$WEBUI_PID"
    exit $?
  fi
  sleep 1
done
