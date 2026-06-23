# Contributing to NexusClaw

Thanks for your interest in NexusClaw.

## Project Scope

NexusClaw is an open-core government-domain knowledge Q&A platform. The public
repository focuses on the reusable application framework:

- FastAPI backend for project configuration, knowledge management, retrieval,
  chat orchestration, logs, and evaluation scaffolding
- admin web console
- citizen-facing portal web experience
- local RAG and scene-agent helpers

Private deployments, customer-specific knowledge bases, quotations, credentials,
production data, and advanced hosted-operation assets should stay outside this
repository.

## Development Workflow

1. Create a topic branch from the default branch.
2. Keep changes focused and avoid unrelated refactors.
3. Add or update tests for behavior changes.
4. Run the relevant build or test command before opening a pull request.
5. Do not commit generated artifacts, local uploads, database files, or secrets.

## Local Setup

See `docs/LOCAL_DEV.md` for the local development flow.

## Pull Requests

Please include:

- what changed
- why it changed
- how it was verified
- any migration or configuration impact

By contributing, you agree that your contribution is submitted under the Apache
License, Version 2.0.
