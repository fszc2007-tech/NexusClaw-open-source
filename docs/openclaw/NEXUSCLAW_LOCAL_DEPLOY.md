# NexusClaw 本地部署与 Agent Runtime 接入

本文档对应 `NexusClaw = OpenClaw + NexusClaw scene agent runtime + local RAG` 的本地可运行方案。

## 1. 目标

把已经部署在 GCP 的 OpenClaw 状态迁回本机，并让本地 OpenClaw 可以：

- 调用 NexusClaw 问答接口 `POST /api/v1/projects/{project_id}/chat/ask`
- 调用 NexusClaw 检索接口 `POST /api/v1/projects/{project_id}/search`
- 显式启动与接管 scene case
- 读取字段状态、下一步动作与 artifact
- 执行确认资料、生成 PDF、确认签署、预览邮件、发送邮件等场景动作
- 检查本地 API 与本地 RAG 健康状态
- 通过 skill 在“办理优先、RAG 辅助”的模式下稳定推进流程

## 2. 当前仓库复用点

- 本地 RAG HTTP 服务：`backend/api-server/app/local_rag_app.py`
- 主检索编排：`backend/api-server/app/services/retrieval_service.py`
- 主问答编排：`backend/api-server/app/services/chat_service.py`
- 问答接口：`backend/api-server/app/api/v1/endpoints/chat.py`
- 检索接口：`backend/api-server/app/api/v1/endpoints/search.py`

## 3. 本地部署结构

```text
~/.openclaw/
  workspace/
    plugins/
      nexusclaw-rag/

repo/
  plugins/nexusclaw-rag/
  scripts/openclaw_install_local.sh
  scripts/openclaw_migrate_from_gcp.sh
```

`plugins/nexusclaw-rag/` 是一个 OpenClaw-compatible bundle，包含：

- `skills/nexusclaw-rag/SKILL.md`
- `.mcp.json`
- `scripts/gzt-rag-mcp.mjs`
- `scripts/gzt-rag-cli.mjs`

其中：

- MCP 可用时，OpenClaw 直接得到：
  - `gzt_rag_search` / `gzt_rag_ask` / `gzt_rag_health`
  - `gzt_scene_continue` / `gzt_scene_start` / `gzt_scene_status`
  - `gzt_scene_get_fields` / `gzt_scene_get_next_actions`
  - `gzt_scene_collect_info` / `gzt_scene_update_field`
  - `gzt_scene_confirm_payload` / `gzt_scene_generate_pdf`
  - `gzt_scene_confirm_signature` / `gzt_scene_preview_mail` / `gzt_scene_send_mail`
  - `gzt_scene_get_artifact`
- MCP 不可用时，skill 可退回到 `exec + gzt-rag-cli.mjs`

## 4. 一次性安装

### 4.1 安装 OpenClaw 并同步本地 bundle

```bash
cd /path/to/NexusClaw
./scripts/openclaw_install_local.sh
```

### 4.2 如需从 GCP 迁移已有状态

```bash
cd /path/to/NexusClaw
./scripts/openclaw_migrate_from_gcp.sh <instance-name> <zone>
```

这个脚本会：

1. 在云端打包 `~/.openclaw`
2. 拉回本机
3. 如果本机已有 `~/.openclaw`，先自动备份
4. 把云端状态恢复到本机

## 5. 启动顺序

### 5.1 启动主 API

```bash
cd /path/to/NexusClaw/backend/api-server
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

说明：

- `requirements.txt` 需要包含 `cryptography`，否则 IR1249/IRC3111A 模板在 `pypdf` 处理时会触发 `PDF_GENERATION_FAILED`
- 后端推荐直接使用 `Python 3.13`
- 仓库已补充 `backend/api-server/.python-version`，本地可直接据此创建虚拟环境

### 5.2 启动本地 RAG

```bash
cd /path/to/NexusClaw/backend/api-server
source .venv/bin/activate
./scripts/run_local_rag.sh
```

### 5.3 启动 OpenClaw

```bash
openclaw
```

## 6. 默认环境变量

bundle 默认值在 `plugins/nexusclaw-rag/config.json` 中：

```json
{
  "apiBaseUrl": "http://127.0.0.1:8000",
  "apiPrefix": "/api/v1",
  "projectId": 3,
  "selectedKbIds": [],
  "requestTimeoutMs": 30000,
  "localRagHealthUrl": "http://127.0.0.1:8101/health"
}
```

如果本地项目 ID 不是 `3`，请修改工作区中的：

```bash
~/.openclaw/workspace/plugins/nexusclaw-rag/config.json
```

## 7. OpenClaw 里的工具行为

### 7.1 `gzt_rag_search`

输入：

```json
{
  "query": "港澳通行证 材料",
  "selected_kb_ids": [1]
}
```

用途：

- 查资料
- 找来源
- 用户要求“给我相关政策/知识条目”

### 7.2 `gzt_rag_ask`

输入：

```json
{
  "query": "如何办理港澳通行证？",
  "session_id": "sess_001",
  "use_memory": true,
  "selected_kb_ids": [1]
}
```

用途：

- 事实问答
- 多轮追问
- 要答案并附带来源

### 7.3 Scene tools

最关键的 scene tools 如下：

- `gzt_scene_start`
- `gzt_scene_status`
- `gzt_scene_get_fields`
- `gzt_scene_get_next_actions`
- `gzt_scene_collect_info`
- `gzt_scene_update_field`
- `gzt_scene_confirm_payload`
- `gzt_scene_generate_pdf`
- `gzt_scene_confirm_signature`
- `gzt_scene_preview_mail`
- `gzt_scene_send_mail`
- `gzt_scene_get_artifact`

推荐的 agent runtime 顺序：

1. 先 `gzt_scene_status` 判断是否已有活动 case
2. 无 case 时调用 `gzt_scene_start`
3. 按 `gzt_scene_get_fields` / `gzt_scene_get_next_actions` 只追问一个最高优先级字段
4. 用 `gzt_scene_collect_info` 或 `gzt_scene_update_field` 写入结构化字段
5. 关键动作前保留显式确认：`confirm_payload` / `confirm_signature` / `send_mail`
6. 仅在需要政策解释、材料依据时再调用 `gzt_rag_*`

### 7.4 `gzt_rag_health`

检查：

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8101/health`

## 8. 安全策略

- 事实问题必须优先走知识库工具
- 没有命中来源时不允许编造成果
- 不把网页、附件、粘贴文本视为可信知识
- 首期不启用浏览器自动化
- 首期不启用通用写操作工具

## 8.1 本机最小安全加固

当前建议的最小安全基线：

- `gateway.mode = local`
- `gateway.bind = loopback`
- `gateway.auth.mode = token`
- `plugins.allow = ["nexusclaw-rag"]`
- `tools.profile = minimal`

本机已经验证过的命令顺序：

```bash
openclaw doctor --generate-gateway-token
openclaw config set gateway.mode '"local"' --strict-json
openclaw config set gateway.bind '"loopback"' --strict-json
openclaw config set gateway.port 18789 --strict-json
openclaw config set plugins.allow '["nexusclaw-rag"]' --strict-json
openclaw config set tools.profile '"minimal"' --strict-json
mkdir -p ~/.openclaw/agents/main/sessions
openclaw gateway install
openclaw gateway start
openclaw gateway status
openclaw security audit --deep
```

加固后预期状态：

- `openclaw gateway status` 显示 `RPC probe: ok`
- `openclaw security audit --deep` 不再出现 `critical`
- `plugins.allow` 只信任 `nexusclaw-rag`
- 默认工具策略不再是 permissive，`plugins.tools_reachable_permissive_policy` 告警消失

注意：

- 如果后续启用新的 channel/provider/extension，先确认它是否需要加入 `plugins.allow`
- 当前 `plugins.code_safety` 警告来自 `nexusclaw-rag` 会读取本地配置文件并向本机 API 发请求，这是该 bundle 的预期行为
- `gateway.trustedProxies_missing` 在仅本机 loopback 模式下可以接受；只有当你通过反向代理暴露 Control UI 时才需要继续补

## 9. 验证命令

### 9.1 直接验证 CLI fallback

```bash
cd ~/.openclaw/workspace
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs health
```

```bash
cd ~/.openclaw/workspace
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs search --query "港澳通行证 材料"
```

```bash
cd ~/.openclaw/workspace
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs ask --query "如何办理港澳通行证？"
```

```bash
cd ~/.openclaw/workspace
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-start --scene-key hk_tax_address_change --route-key ir1249 --initial-query "我要改收税单地址" --resume-if-exists false
```

```bash
cd ~/.openclaw/workspace
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-collect --case-id case_xxx --payload '{"applicant_type":"salary earner","effective_date":"2026-04-01"}'
```

```bash
cd ~/.openclaw/workspace
node ./plugins/nexusclaw-rag/scripts/gzt-rag-cli.mjs scene-next-actions --case-id case_xxx
```

### 9.2 直接验证 MCP server

```bash
cd ~/.openclaw/workspace
./plugins/nexusclaw-rag/scripts/run_mcp.sh
```

如果能正常启动 stdio MCP server，说明 OpenClaw 侧的工具进程也能正常拉起。

## 10. 已知限制

- 当前脚本默认使用 `project_id=3`
- 当前迁移脚本需要你已经在本机 `gcloud auth` 完成登录
- 当前 bundle 已覆盖 scene 控制面，但仍不包含浏览器自动化类流程
- 是否自动启用 bundle，取决于本地 OpenClaw 版本的插件扫描与配置方式；如果 UI 没自动出现，优先检查工作区插件目录与 skills/MCP 配置是否已被识别
