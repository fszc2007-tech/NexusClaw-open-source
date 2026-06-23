#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

resolve_snapshot_dir() {
  local model_root="$1"
  if [[ -z "${model_root}" ]]; then
    return 0
  fi
  if [[ -d "${model_root}/snapshots" ]]; then
    local latest_snapshot
    latest_snapshot="$(find "${model_root}/snapshots" -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1 || true)"
    if [[ -n "${latest_snapshot}" ]]; then
      printf '%s\n' "${latest_snapshot}"
      return 0
    fi
  fi
  if [[ -d "${model_root}" ]]; then
    printf '%s\n' "${model_root}"
  fi
}

detect_cached_model() {
  local candidate
  for candidate in "$@"; do
    if [[ -z "${candidate}" ]]; then
      continue
    fi
    local resolved
    resolved="$(resolve_snapshot_dir "${candidate}")"
    if [[ -n "${resolved}" ]]; then
      printf '%s\n' "${resolved}"
      return 0
    fi
  done
}

cd "${API_DIR}"

if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

EMBEDDING_CACHE_PATH="${HOME}/.cache/huggingface/hub/models--shibing624--text2vec-base-chinese"
RERANK_CACHE_PATH="${HOME}/.cache/huggingface/hub/models--BAAI--bge-reranker-base"

export LOCAL_RAG_HOST="${LOCAL_RAG_HOST:-127.0.0.1}"
export LOCAL_RAG_PORT="${LOCAL_RAG_PORT:-8101}"
export LOCAL_RAG_DB_PATH="${LOCAL_RAG_DB_PATH:-storage/local_rag/local_rag.sqlite3}"
export LOCAL_RAG_EMBEDDING_BATCH_SIZE="${LOCAL_RAG_EMBEDDING_BATCH_SIZE:-16}"
export LOCAL_RAG_RERANK_BATCH_SIZE="${LOCAL_RAG_RERANK_BATCH_SIZE:-4}"
export LOCAL_RAG_TORCH_NUM_THREADS="${LOCAL_RAG_TORCH_NUM_THREADS:-1}"
export LOCAL_RAG_ALLOW_DEGRADED_FALLBACK="${LOCAL_RAG_ALLOW_DEGRADED_FALLBACK:-true}"
export LOCAL_RAG_PRELOAD_MODELS="${LOCAL_RAG_PRELOAD_MODELS:-false}"
export LOCAL_RAG_RELOAD="${LOCAL_RAG_RELOAD:-false}"
export HF_HUB_DISABLE_XET="${HF_HUB_DISABLE_XET:-1}"

if [[ -z "${LOCAL_RAG_EMBEDDING_PROVIDER:-}" ]]; then
  export LOCAL_RAG_EMBEDDING_PROVIDER="sentence_transformers"
fi
if [[ "${LOCAL_RAG_EMBEDDING_PROVIDER}" == "sentence_transformers" && -z "${LOCAL_RAG_EMBEDDING_MODEL_PATH:-}" && -z "${LOCAL_RAG_EMBEDDING_MODEL:-}" ]]; then
  DETECTED_EMBEDDING_PATH="$(detect_cached_model "${EMBEDDING_CACHE_PATH}")"
  if [[ -n "${DETECTED_EMBEDDING_PATH:-}" ]]; then
    export LOCAL_RAG_EMBEDDING_MODEL_PATH="${DETECTED_EMBEDDING_PATH}"
  else
    export LOCAL_RAG_EMBEDDING_PROVIDER="hash"
  fi
fi
export LOCAL_RAG_EMBEDDING_DEVICE="${LOCAL_RAG_EMBEDDING_DEVICE:-cpu}"

if [[ -z "${LOCAL_RAG_RERANK_PROVIDER:-}" ]]; then
  export LOCAL_RAG_RERANK_PROVIDER="cross_encoder"
fi
if [[ "${LOCAL_RAG_RERANK_PROVIDER}" == "cross_encoder" && -z "${LOCAL_RAG_RERANK_MODEL_PATH:-}" && -z "${LOCAL_RAG_RERANK_MODEL:-}" ]]; then
  DETECTED_RERANK_PATH="$(detect_cached_model "${RERANK_CACHE_PATH}")"
  if [[ -n "${DETECTED_RERANK_PATH:-}" ]]; then
    export LOCAL_RAG_RERANK_MODEL_PATH="${DETECTED_RERANK_PATH}"
  else
    export LOCAL_RAG_RERANK_MODEL="BAAI/bge-reranker-base"
  fi
fi
export LOCAL_RAG_RERANK_DEVICE="${LOCAL_RAG_RERANK_DEVICE:-cpu}"

if [[ -z "${HF_ENDPOINT:-}" && ( "${LOCAL_RAG_EMBEDDING_PROVIDER}" == "sentence_transformers" || "${LOCAL_RAG_RERANK_PROVIDER}" == "cross_encoder" ) ]]; then
  export HF_ENDPOINT="https://hf-mirror.com"
fi

if [[ "${1:-}" == "--print-env" ]]; then
  cat <<EOF
LOCAL_RAG_HOST=${LOCAL_RAG_HOST}
LOCAL_RAG_PORT=${LOCAL_RAG_PORT}
LOCAL_RAG_DB_PATH=${LOCAL_RAG_DB_PATH}
LOCAL_RAG_EMBEDDING_PROVIDER=${LOCAL_RAG_EMBEDDING_PROVIDER}
LOCAL_RAG_EMBEDDING_MODEL=${LOCAL_RAG_EMBEDDING_MODEL:-}
LOCAL_RAG_EMBEDDING_MODEL_PATH=${LOCAL_RAG_EMBEDDING_MODEL_PATH:-}
LOCAL_RAG_EMBEDDING_DEVICE=${LOCAL_RAG_EMBEDDING_DEVICE}
LOCAL_RAG_RERANK_PROVIDER=${LOCAL_RAG_RERANK_PROVIDER}
LOCAL_RAG_RERANK_MODEL=${LOCAL_RAG_RERANK_MODEL:-}
LOCAL_RAG_RERANK_MODEL_PATH=${LOCAL_RAG_RERANK_MODEL_PATH:-}
LOCAL_RAG_RERANK_DEVICE=${LOCAL_RAG_RERANK_DEVICE}
LOCAL_RAG_RERANK_BATCH_SIZE=${LOCAL_RAG_RERANK_BATCH_SIZE}
LOCAL_RAG_TORCH_NUM_THREADS=${LOCAL_RAG_TORCH_NUM_THREADS}
LOCAL_RAG_ALLOW_DEGRADED_FALLBACK=${LOCAL_RAG_ALLOW_DEGRADED_FALLBACK}
LOCAL_RAG_PRELOAD_MODELS=${LOCAL_RAG_PRELOAD_MODELS}
LOCAL_RAG_RELOAD=${LOCAL_RAG_RELOAD}
HF_ENDPOINT=${HF_ENDPOINT:-}
HF_HUB_DISABLE_XET=${HF_HUB_DISABLE_XET}
EOF
  exit 0
fi

echo "[local-rag] host=${LOCAL_RAG_HOST} port=${LOCAL_RAG_PORT}"
echo "[local-rag] embedding=${LOCAL_RAG_EMBEDDING_PROVIDER} device=${LOCAL_RAG_EMBEDDING_DEVICE}"
echo "[local-rag] rerank=${LOCAL_RAG_RERANK_PROVIDER} device=${LOCAL_RAG_RERANK_DEVICE} batch=${LOCAL_RAG_RERANK_BATCH_SIZE}"
echo "[local-rag] torch_threads=${LOCAL_RAG_TORCH_NUM_THREADS} preload=${LOCAL_RAG_PRELOAD_MODELS} reload=${LOCAL_RAG_RELOAD} degraded_fallback=${LOCAL_RAG_ALLOW_DEGRADED_FALLBACK}"

UVICORN_ARGS=()
if [[ "${LOCAL_RAG_RELOAD}" == "true" ]]; then
  UVICORN_ARGS+=(--reload)
fi
UVICORN_ARGS+=("$@")

if (( ${#UVICORN_ARGS[@]} > 0 )); then
  exec uvicorn main_rag:app --host "${LOCAL_RAG_HOST}" --port "${LOCAL_RAG_PORT}" "${UVICORN_ARGS[@]}"
fi

exec uvicorn main_rag:app --host "${LOCAL_RAG_HOST}" --port "${LOCAL_RAG_PORT}"
