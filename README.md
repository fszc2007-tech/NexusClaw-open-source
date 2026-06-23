# NexusClaw

NexusClaw is an open-source knowledge operations platform for building grounded assistants over domain documents, workflows, citations, evaluation, and governance.

It is not just a RAG chatbot template. NexusClaw combines document ingestion, project configuration, retrieval, answer generation, source inspection, logs, evaluation, knowledge governance, and structured scene workflows in one developer-friendly stack.

## Current Status

NexusClaw is in an early open-source release.

Good for:

- local development and architecture exploration
- RAG pipeline experimentation
- document Q&A prototypes
- admin and portal workflow exploration
- knowledge governance and evaluation flow review
- OpenClaw plugin integration experiments

Not yet production-ready for:

- public multi-tenant SaaS without additional hardening
- strict RBAC or regulated enterprise environments
- unattended production deployment
- external connector ecosystems without custom integration work

## Why NexusClaw

- Built for operational knowledge systems, not only one-off chatbot demos
- Keeps project configuration, knowledge management, retrieval, answer generation, logs, and evaluation in one codebase
- Supports both admin/operator workflows and end-user portal experiences
- Designed for evidence-aware answers, source inspection, and governance loops
- Can run with lightweight local retrieval first, then be extended to model-backed embedding and reranking
- Provides scene workflow primitives for tasks that need structured fields, confirmations, generated artifacts, or action previews

## Good Fit

NexusClaw is useful when you need more than a prompt wrapper:

- internal knowledge assistants with managed source documents
- public-service or enterprise support portals
- policy, SOP, FAQ, or handbook Q&A with traceable answers
- document-heavy workflows that need file parsing, chunking, and review
- evaluation loops for testing answer quality over time
- workflows that combine chat with structured fields and generated artifacts

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

## Demo Project

A lightweight demo dataset is included in `examples/demo-project`.

It contains sample HR policy, insurance FAQ, government service guide, and medical billing explanation documents. Use it to test the basic flow:

```text
create knowledge base -> upload sample document -> ask a question -> inspect source-aware answer
```

Example questions:

- What documents are required for remote work approval?
- When should an employee submit an expense reimbursement?
- What is the difference between a deductible and coinsurance?
- What should a resident prepare before booking a service appointment?

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

Clone and prepare local configuration:

```bash
git clone https://github.com/fszc2007-tech/NexusClaw-open-source.git
cd NexusClaw-open-source
./scripts/demo_setup.sh
```

Start MySQL and Redis:

```bash
docker compose up -d
```

Start the backend:

```bash
cd backend/api-server
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
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

## How It Differs From Generic RAG Starters

Many RAG starters focus on a single chat endpoint. NexusClaw includes the surrounding product and operations surface:

- admin UI for projects, knowledge, files, prompts, logs, and tests
- portal UI for end users
- source-aware answer generation and retrieval controls
- document parsing and table-aware ingestion
- governance workflows for stale, duplicated, or conflicting knowledge
- evaluation datasets and task tracking
- scene runtime helpers for structured workflows beyond free-form chat

See `docs/WHY_NEXUSCLAW.md` for a longer comparison.

## Configuration

Configuration is environment-driven. Use the checked-in example files as templates:

- `backend/api-server/.env.example`
- `backend/api-server/.env.local-rag.example`
- `frontend/admin-web/.env.example`
- `frontend/portal-web/.env.example`

Do not commit real `.env` files, credentials, uploaded documents, generated storage files, or database dumps.

## Documentation

- `ROADMAP.md`
- `docs/LOCAL_DEV.md`
- `docs/WHY_NEXUSCLAW.md`
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
