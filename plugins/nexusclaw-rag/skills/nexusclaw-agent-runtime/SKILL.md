---
name: nexusclaw-agent-runtime
description: Run NexusClaw workflow cases as a stable agent runtime with explicit scene status, field collection, confirmation gates, PDF generation, and mail actions.
---

# NexusClaw Agent Runtime

Use this skill whenever the user is trying to complete a government workflow, not just ask a policy question.

## Operating mode

1. Prefer workflow mode over pure Q&A when the user says things like "帮我办理", "生成 PDF", "确认资料", "预览邮件", or "发送邮件".
2. For natural-language continuation or resume, prefer `scene-continue` first because it returns a unified `scene_runtime` envelope with `scene`, `field_status`, `next_actions`, `intent_mode`, `classification_reason`, and optional `hybrid_context`.
3. If the user already has an active `case_id` and asks to inspect or act on the case directly, call `gzt_scene_status` first to recover current progress before asking anything else.
4. If there is no active case and the user is clearly entering a workflow, call `gzt_scene_start` and enter an explicit case lifecycle.
5. Ask only the single highest-priority missing field each turn. Do not dump the entire form unless the user asks.
6. After each field update, re-check `gzt_scene_get_fields` or `gzt_scene_get_next_actions` before deciding the next step.
7. Read `planner` first when it is present. Use `planner.mode`, `planner.next_step`, and `planner.communication` as the primary runtime strategy instead of re-deriving the next step yourself.
8. If `planner.mode` is `collect_bundle`, ask for the bundled fields together and preserve the grouped wording from `next_question` instead of splitting them back into separate turns.
9. If the runtime reports `last_error_code`, `retry_allowed`, or `requires_status_refresh`, prefer `gzt_scene_recover` before improvising your own retry logic.
10. For gated actions, read `confirmation_requirements` from scene status or next actions and pass the matching `confirmation_token`.
11. Treat `gzt_rag_ask` and `gzt_rag_search` as supporting tools for policy explanation, not as the main workflow engine.
12. If `intent_mode` is `hybrid_request`, keep the user inside workflow mode and use `hybrid_context` only as supporting explanation or source evidence.
13. If `field_status.address_analysis` is present, summarize the parsed address structure in user terms. If confidence is low or the structure is incomplete, ask the user to confirm or correct the parsed address before proceeding.

## Confirmation gates

Always ask for explicit user confirmation before calling:

- `gzt_scene_confirm_payload`
- `gzt_scene_confirm_signature`
- `gzt_scene_send_mail`

If the user has not clearly confirmed, summarize the current state and wait. When the user does confirm, fetch the latest `confirmation_token` and include it in the action call.

## Preferred tool order

1. `scene-continue`
2. `gzt_scene_status`
3. `gzt_scene_start`
4. `gzt_scene_get_fields`
5. `gzt_scene_collect_info` or `gzt_scene_update_field`
6. `gzt_scene_get_next_actions`
7. Consume `planner`
8. `gzt_scene_recover`
9. `gzt_scene_confirm_payload`
10. `gzt_scene_generate_pdf`
11. `gzt_scene_confirm_signature`
12. `gzt_scene_preview_mail`
13. `gzt_scene_send_mail`
14. `gzt_scene_get_artifact`

## Response style

- Always show the current scene, case state, missing fields count, and the next available action.
- When `planner` exists, phrase the reply around `planner.communication.status_headline` and `planner.communication.status_detail`.
- If `intent_mode` is `hybrid_request`, keep the main answer focused on workflow progress, then append a short policy explanation with sources from `hybrid_context`.
- When blocked, explain exactly what is missing or which confirmation is required.
- When recovery is available, explicitly say whether the runtime only refreshed status or already auto-retried a safe action.
- When a field is invalid, explain the field name and why it failed.
- When artifacts exist, mention whether preview PDF, final PDF, and mail preview are available.
- For parsed addresses, explicitly mention the normalized structure you are using, such as district, street, building, floor, block, and room, so the user can quickly spot mistakes.

## Fallback when MCP tools are unavailable

Use the bundled CLI:

```bash
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-start --scene-key hk_tax_address_change --initial-query "我要改收税单地址"
```

```bash
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-collect --case-id case_xxx --payload '{"full_name":"CHAN TAI MAN"}'
```

```bash
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-action --case-id case_xxx --action-name generate_pdf
```
