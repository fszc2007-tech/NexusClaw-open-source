# NexusClaw

NexusClaw is an open-source knowledge Q&A platform for building grounded, configurable assistants over domain-specific documents and workflows.

It includes a FastAPI backend, an admin console, a user-facing portal, local RAG utilities, and scene workflow helpers for structured information collection and document-oriented service flows.

## Why NexusClaw

- Built for operational knowledge systems, not only one-off chatbot demos
- Keeps project configuration, knowledge management, retrieval, answer generation, logs, and evaluation in one codebase
- Supports both admin/operator workflows and end-user portal experiences
- Designed for evidence-aware answers, source inspection, and governance loops
- Can run with lightweight local retrieval first, then be extended to model-backed embedding and reranking
- Provides scene workflow primitives for tasks that need structured fields, confirmations, generated artifacts, or action previews

## Technical Highlights

- FastAPI service layer with SQLAlchemy models and Alembic migrations
- Configurable retrieval pipeline with keyword, vector, rerank, chunk retrieval, and fallback paths
- Table-aware ingestion and answer formatting for structured document content
- Multi-turn chat orchestration with session-scoped context controls
- Knowledge compilation and governance modules for maintaining long-lived knowledge assets
- Document parsing support for PDFs, Word, Excel, PowerPoint, HTML, Markdown, images, and text files
- Admin console built with React, Umi Max, and Ant Design
- Portal web app with project selection, upload flow, chat memory indicators, and retrieval mode controls
- OpenClaw-compatible plugin bundle exposing RAG and scene runtime tools through MCP/CLI helpers
- Secret-safe development setup with example env files and a checked-in `detect-secrets` baseline

## Features

- Project-level assistant configuration, prompts, opening messages, and recommended questions
- Knowledge base and file management
- Retrieval-augmented chat with source-aware answer generation
- Multi-turn session context and memory controls
- Knowledge deduplication, replacement, freshness, and governance workflows
- Document parsing, preview, chunking, and document Q&A
- Evaluation datasets, test tasks, and chat log inspection
- Admin web console for operators and maintainers
- Portal web experience for end users
- Local RAG service and OpenClaw-compatible runtime helpers

## Architecture

```text
backend/
  api-server/        FastAPI application, migrations, services, local RAG

frontend/
  admin-web/         Admin console
  portal-web/        User-facing portal

plugins/
  nexusclaw-rag/     OpenClaw-compatible RAG and scene runtime bundle

docs/
  api/               API reference
  db/                Schema notes
  prd/               Product and IA notes
  tech-design/       Technical design docs

scripts/             Local helper scripts
```

## Quick Start

Start MySQL and Redis:

```bash
docker compose up -d
```

Start the backend:

```bash
cd backend/api-server
cp .env.example .env
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Start the admin console:

```bash
cd frontend/admin-web
pnpm install
pnpm dev
```

Start the portal:

```bash
cd frontend/portal-web
pnpm install
pnpm dev
```

For local RAG setup and optional model-backed retrieval, see `docs/LOCAL_DEV.md`.

## Configuration

Configuration is environment-driven. Use the checked-in example files as templates:

- `backend/api-server/.env.example`
- `backend/api-server/.env.local-rag.example`
- `frontend/admin-web/.env.example`
- `frontend/portal-web/.env.example`

Do not commit real `.env` files, credentials, uploaded documents, generated storage files, or database dumps.

## Documentation

- `docs/LOCAL_DEV.md`
- `docs/api/API_SPEC.md`
- `docs/db/SCHEMA.md`
- `docs/tech-design/TECH_DESIGN.md`
- `docs/tech-design/RAG_CAPABILITY_AUDIT.md`
- `docs/tech-design/CHAT_MEMORY_DESIGN.md`
- `docs/openclaw/NEXUSCLAW_LOCAL_DEPLOY.md`

## Development

Useful checks:

```bash
cd backend/api-server
python -m compileall app migrations
```

```bash
cd frontend/admin-web
pnpm build
```

```bash
cd frontend/portal-web
pnpm build
```

## Security

Please report vulnerabilities privately. See `SECURITY.md`.

## Contributing

Contributions are welcome. See `CONTRIBUTING.md`.

## License

NexusClaw is licensed under the Apache License, Version 2.0. See `LICENSE` and `NOTICE`.
