# NexusClaw Agent Runtime Bundle

This bundle lets a local OpenClaw deployment call the NexusClaw backend and local RAG service through:

- MCP tools for RAG and workflow runtime:
  - `gzt_rag_search`, `gzt_rag_ask`, `gzt_rag_health`
  - `gzt_scene_continue`, `gzt_scene_start`, `gzt_scene_status`
  - `gzt_scene_get_fields`, `gzt_scene_get_next_actions`
  - `gzt_scene_collect_info`, `gzt_scene_update_field`
  - `gzt_scene_confirm_payload`, `gzt_scene_generate_pdf`
  - `gzt_scene_confirm_signature`, `gzt_scene_preview_mail`, `gzt_scene_send_mail`
  - `gzt_scene_get_artifact`
- bundled skills:
  - `nexusclaw-rag`
  - `nexusclaw-agent-runtime`
- an `exec` fallback CLI for backends that do not expose MCP tools

Install and sync it into the OpenClaw workspace with:

```bash
cd /path/to/NexusClaw
./scripts/openclaw_install_local.sh
```

After the workspace bundle is synced, OpenClaw can discover:

- skills from `./skills/`
- MCP config from `./.mcp.json`

The bundle assumes the local backend API is available at `http://127.0.0.1:8000` and the local RAG health endpoint is available at `http://127.0.0.1:8101/health`.
The runtime reads local settings from `config.json`. If your local project ID or ports differ, edit that file before installing or after syncing into `~/.openclaw/workspace/plugins/nexusclaw-rag/config.json`.
For scene/agent flows, `sceneRequestTimeoutMs` is intentionally longer than the generic RAG timeout so hybrid orchestration does not get cut off while the backend is still retrieving and composing the scene response.
The scene runtime also exposes a recovery control plane. When the backend returns `last_error_code`, the plugin can call `gzt_scene_recover` to refresh confirmation requirements or safely retry non-destructive actions such as `generate_pdf` or `preview_mail`.

`scene-continue` now returns the same workflow runtime control surface as the explicit scene APIs, including `intent_mode`, `field_status`, `next_actions`, and `scene_runtime`.

For environments without MCP, the fallback CLI now exposes the same scene control surface:

```bash
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-start --scene-key hk_tax_address_change --initial-query "我要改收税单地址"
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-collect --case-id case_xxx --payload '{"full_name":"CHAN TAI MAN"}'
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-action --case-id case_xxx --action-name generate_pdf
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-action --case-id case_xxx --action-name confirm_payload --confirmation-token TOKEN_FROM_STATUS
```
