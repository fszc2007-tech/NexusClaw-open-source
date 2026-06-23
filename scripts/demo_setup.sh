#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

copy_if_missing() {
  local source_file="$1"
  local target_file="$2"
  if [[ ! -f "$target_file" ]]; then
    cp "$source_file" "$target_file"
    echo "[created] ${target_file#$ROOT_DIR/}"
  else
    echo "[skip] ${target_file#$ROOT_DIR/} already exists"
  fi
}

copy_if_missing "$ROOT_DIR/backend/api-server/.env.example" "$ROOT_DIR/backend/api-server/.env"
copy_if_missing "$ROOT_DIR/frontend/admin-web/.env.example" "$ROOT_DIR/frontend/admin-web/.env"
copy_if_missing "$ROOT_DIR/frontend/portal-web/.env.example" "$ROOT_DIR/frontend/portal-web/.env"

echo
echo "Next steps:"
echo "  docker compose up -d"
echo "  cd backend/api-server && python3.13 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && alembic upgrade head && uvicorn main:app --reload --port 8000"
echo "  cd frontend/admin-web && pnpm install && pnpm dev"
echo "  cd frontend/portal-web && pnpm install && pnpm dev"
echo
echo "Demo documents:"
echo "  examples/demo-project/docs"
