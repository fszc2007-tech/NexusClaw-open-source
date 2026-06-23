#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLUGIN_SOURCE="${REPO_ROOT}/plugins/nexusclaw-rag"
OPENCLAW_HOME="${HOME}/.openclaw"
WORKSPACE_DIR="${OPENCLAW_HOME}/workspace"
PLUGIN_TARGET_DIR="${WORKSPACE_DIR}/plugins/nexusclaw-rag"
OPENCLAW_VERSION="${OPENCLAW_VERSION:-2026.4.2}"

if ! command -v openclaw >/dev/null 2>&1; then
  npm install -g "openclaw@${OPENCLAW_VERSION}"
fi

mkdir -p "${WORKSPACE_DIR}/plugins"
rsync -a --delete "${PLUGIN_SOURCE}/" "${PLUGIN_TARGET_DIR}/"

chmod +x "${PLUGIN_TARGET_DIR}/scripts/run_mcp.sh"
chmod +x "${PLUGIN_TARGET_DIR}/scripts/gzt-rag-cli.mjs"
chmod +x "${PLUGIN_TARGET_DIR}/scripts/gzt-rag-mcp.mjs"

(
  cd "${PLUGIN_TARGET_DIR}"
  npm install --silent --no-fund --no-audit
)

cat <<EOF
NexusClaw bundle synced to:
  ${PLUGIN_TARGET_DIR}

Bundle config:
  ${PLUGIN_TARGET_DIR}/config.json

Next steps:
1. Start the NexusClaw backend:
   cd ${REPO_ROOT}/backend/api-server && uvicorn main:app --reload --port 8000
2. Start the local RAG service:
   cd ${REPO_ROOT}/backend/api-server && ./scripts/run_local_rag.sh
3. Launch OpenClaw:
   openclaw

If you need to migrate existing cloud state first, run:
  ${REPO_ROOT}/scripts/openclaw_migrate_from_gcp.sh <instance-name> <zone>
EOF
