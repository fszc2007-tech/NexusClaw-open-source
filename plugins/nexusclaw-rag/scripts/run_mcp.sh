#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PLUGIN_DIR}"

if [ ! -d node_modules ]; then
  npm install --silent --no-fund --no-audit
fi

exec node ./scripts/gzt-rag-mcp.mjs
