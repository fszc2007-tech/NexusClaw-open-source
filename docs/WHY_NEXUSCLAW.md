# Why NexusClaw

NexusClaw is designed for teams that need to operate knowledge assistants, not only prototype them.

Generic RAG demos are useful for proving that retrieval can answer a question. Production knowledge assistants need more surrounding machinery: source management, project configuration, prompt control, file parsing, logs, evaluation, governance, and workflow handling.

## Positioning

NexusClaw sits between low-level LLM frameworks and fully hosted no-code tools.

- Compared with a LangChain or LlamaIndex starter, NexusClaw includes application surfaces: admin console, portal, project settings, logs, evaluation, and governance.
- Compared with general chatbot UIs, NexusClaw focuses on managed knowledge bases, source-aware answers, and operational review workflows.
- Compared with no-code platforms, NexusClaw is code-first and easier to customize deeply inside your own stack.

## What Makes It Different

### Knowledge Operations, Not Just Chat

NexusClaw treats knowledge as an asset that changes over time. The codebase includes flows for files, chunks, freshness, conflicts, deduplication, governance tasks, and answer review.

### Source-Aware Retrieval

The retrieval layer supports keyword retrieval, vector retrieval, reranking, chunk retrieval, and fallback paths. The answer layer is designed to preserve source context and avoid unsupported answers.

### Admin And Portal Together

The repository includes both sides of the product:

- an admin console for maintainers and operators
- a portal experience for end users

This makes it easier to build a complete internal or public-facing knowledge product instead of wiring separate demos together.

### Document-First Workflows

The backend supports parsing and processing PDFs, Word documents, spreadsheets, presentations, HTML, Markdown, images, and text files. It also includes table-aware ingestion and formatting paths for structured content.

### Evaluation And Logs

NexusClaw includes evaluation datasets, testing tasks, and chat log inspection so teams can improve quality over time instead of relying only on manual spot checks.

### Scene Runtime

Some workflows need structured fields, confirmation steps, generated PDFs, or action previews. NexusClaw includes scene workflow primitives and an OpenClaw-compatible plugin bundle for these cases.

## When To Use It

Use NexusClaw if you want:

- a code-first grounded assistant framework
- a real admin console and portal, not only an API endpoint
- managed knowledge ingestion and governance
- source-aware answers and logs
- local-first development with optional model-backed retrieval
- workflows that combine chat with structured data collection

If you only need a quick chatbot demo over a few documents, a smaller RAG template may be enough. If you need an extensible product foundation for knowledge operations, NexusClaw is a better starting point.
