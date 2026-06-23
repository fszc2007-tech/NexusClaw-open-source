#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
API_DIR="${REPO_ROOT}/backend/api-server"
API_LOG="/tmp/nexusclaw-api.log"
RAG_LOG="/tmp/nexusclaw-rag.log"

is_listening() {
  local port="$1"
  lsof -nP -iTCP:"${port}" -sTCP:LISTEN >/dev/null 2>&1
}

wait_for_http() {
  local url="$1"
  local name="$2"
  local retries="${3:-20}"
  local i
  for ((i = 1; i <= retries; i++)); do
    if curl -sS --max-time 2 "${url}" >/dev/null 2>&1; then
      echo "[ok] ${name}: ${url}"
      return 0
    fi
    sleep 1
  done
  echo "[warn] ${name} did not become ready in time: ${url}"
  return 1
}

start_api() {
  if is_listening 8000; then
    echo "[skip] API already listening on 127.0.0.1:8000"
    return 0
  fi

  nohup bash -lc "
    cd '${API_DIR}'
    source .venv/bin/activate
    exec uvicorn main:app --host 127.0.0.1 --port 8000
  " >'${API_LOG}' 2>&1 &

  echo "[start] API -> ${API_LOG}"
}

start_rag() {
  if is_listening 8101; then
    echo "[skip] Local RAG already listening on 127.0.0.1:8101"
    return 0
  fi

  nohup bash -lc "
    cd '${API_DIR}'
    exec ./scripts/run_local_rag.sh
  " >'${RAG_LOG}' 2>&1 &

  echo "[start] Local RAG -> ${RAG_LOG}"
}

stop_stack() {
  pkill -f "uvicorn main:app --host 127.0.0.1 --port 8000" >/dev/null 2>&1 || true
  pkill -f "uvicorn main_rag:app --host 127.0.0.1 --port 8101" >/dev/null 2>&1 || true
  echo "[stop] requested API and local RAG shutdown"
}

status_stack() {
  echo "[status] listeners"
  lsof -nP -iTCP:8000 -sTCP:LISTEN || true
  lsof -nP -iTCP:8101 -sTCP:LISTEN || true
  echo
  echo "[status] health"
  curl -sS --max-time 3 http://127.0.0.1:8000/health || true
  echo
  curl -sS --max-time 3 http://127.0.0.1:8101/health || true
  echo
}

case "${1:-start}" in
  start)
    start_api
    start_rag
    wait_for_http "http://127.0.0.1:8000/health" "API"
    wait_for_http "http://127.0.0.1:8101/health" "Local RAG"
    status_stack
    ;;
  restart)
    stop_stack
    sleep 1
    start_api
    start_rag
    wait_for_http "http://127.0.0.1:8000/health" "API"
    wait_for_http "http://127.0.0.1:8101/health" "Local RAG"
    status_stack
    ;;
  stop)
    stop_stack
    ;;
  status)
    status_stack
    ;;
  *)
    echo "usage: $0 {start|restart|stop|status}"
    exit 1
    ;;
esac
