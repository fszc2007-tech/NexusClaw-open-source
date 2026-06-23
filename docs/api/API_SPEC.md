# Nexus RAG 平台 V2.0 API 基线

## 1. 约定

### 1.1 Base URL

`/api/v1`

### 1.2 通用返回格式

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

### 1.3 通用错误格式

```json
{
  "code": 4001,
  "message": "invalid params",
  "data": null
}
```

### 1.4 鉴权方式

- 后台接口默认要求 Bearer Token
- 门户接口可按项目策略支持匿名或登录态

### 1.5 分页格式

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [],
    "page": 1,
    "page_size": 20,
    "total": 0
  }
}
```

---

## 2. 认证与用户会话

### 2.1 登录

`POST /auth/login`

请求：

```json
{
  "username": "admin",
  "password": "******"
}
```

返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "access_token": "token",
    "refresh_token": "refresh-token",
    "user": {
      "id": 1,
      "username": "admin",
      "system_role": "super_admin",
      "nickname": "管理员"
    }
  }
}
```

### 2.2 获取当前用户

`GET /auth/me`

### 2.3 退出登录

`POST /auth/logout`

### 2.4 修改个人信息

`PUT /users/me/profile`

请求：

```json
{
  "nickname": "新昵称",
  "profile": "用户简介"
}
```

### 2.5 修改密码

`PUT /users/me/password`

---

## 3. 门户基础能力

### 3.1 获取可访问项目列表

`GET /portal/projects`

查询参数：

- `department`
- `business`
- `keyword`

### 3.2 获取项目门户配置

`GET /portal/projects/{project_id}/home`

返回内容：

- 功能推荐
- 使用帮助
- 开头语
- 推荐问题
- 热门问题/热门政策

### 3.3 获取个人中心信息

`GET /portal/profile`

---

## 4. 体验广场

## 4.1 知识问答

### 4.1.1 新建会话

`POST /projects/{project_id}/chat/sessions`

请求：

```json
{
  "title": "新对话",
  "selected_kb_ids": [1, 2],
  "switches": {
    "sensitive_detection": true,
    "retrieval_filter": true,
    "knowledge_tree": true,
    "knowledge_compilation": true,
    "compilation_strategy": "compiled_first"
  }
}
```

说明：

- `knowledge_compilation` 是否可用仍受项目级 `capability_knowledge_compilation` 控制。
- 当项目禁用知识编译层时，传入 `knowledge_compilation=true` 也不得绕过项目配置。

### 4.1.2 获取会话列表

`GET /projects/{project_id}/chat/sessions`

### 4.1.3 获取会话详情

`GET /projects/{project_id}/chat/sessions/{session_id}`

### 4.1.4 问答

`POST /projects/{project_id}/chat/ask`

请求：

```json
{
  "session_id": "sess_001",
  "query": "如何办理港澳通行证？",
  "use_memory": true,
  "selected_kb_ids": [1],
  "switches": {
    "sensitive_detection": true,
    "retrieval_filter": true,
    "knowledge_tree": false,
    "knowledge_compilation": true,
    "compilation_strategy": "compiled_first"
  }
}
```

返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "session_id": "sess_001",
    "query_raw": "如何办理港澳通行证？",
    "query_rewritten": "如何办理港澳通行证，需要哪些材料和流程？",
    "answer": "……",
    "memory": {
      "used": true,
      "summary_hit": true,
      "state_hit": true,
      "preference_hit": false
    },
    "policy_basis": {
      "source_mode": "compiled_knowledge",
      "source_count": 2,
      "compiled_page_count": 1,
      "raw_source_count": 2,
      "conflict_detected": false
    },
    "compilation": {
      "enabled": true,
      "strategy": "compiled_first",
      "page_hits": [
        {
          "page_id": 501,
          "title": "港澳通行证办理事项页",
          "page_type": "procedure",
          "score": 0.91,
          "version_no": 3,
          "health_status": "healthy"
        }
      ],
      "fallback_reason": null
    },
    "sources": [
      {
        "source_type": "file_chunk",
        "source_id": "chunk_123",
        "title": "港澳通行证办理指南.pdf",
        "score": 0.94,
        "support_type": "supports",
        "source_locator": {
          "file_id": 123,
          "chunk_id": "chunk_123",
          "page_no": 4,
          "section": "申请条件"
        },
        "quote": "……"
      }
    ],
    "trace_id": "trace_xxx"
  }
}
```

说明：

- `use_memory=true` 表示允许系统在当前项目配置范围内启用会话记忆。
- `memory` 仅反映本轮是否使用上下文，不表示记忆可以作为事实依据。
- `policy_basis` 用于强调答案事实基础仍来自编译页和原始来源的组合，不允许只引用编译页作为唯一事实来源。
- `compilation.strategy=compiled_first` 表示先查询编译知识页，证据不足时回退原始检索。
- `sources` 仍必须保留原始来源结构；编译页命中结果应通过 `compilation.page_hits` 体现。
- 编译页命中建议至少满足以下条件后才可直接进入回答上下文：
  - `min_compilation_score`
  - `min_supporting_source_count`
  - `allow_compilation_with_warning`

### 4.1.5 专家评测答案

`POST /projects/{project_id}/chat/messages/{message_id}/feedback`

请求：

```json
{
  "rating": "good",
  "comment": "答案准确"
}
```

### 4.1.6 获取生效知识库列表

`GET /projects/{project_id}/knowledge-bases/active-options`

## 4.2 知识检索

### 4.2.1 检索知识

`POST /projects/{project_id}/search`

请求：

```json
{
  "query": "港澳通行证怎么办理",
  "top_k": 10,
  "selected_kb_ids": [1]
}
```

返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "results": [
      {
        "knowledge_id": 88,
        "title": "港澳通行证办理流程",
        "keywords": ["港澳通行证", "办理"],
        "content": "……",
        "updated_at": "2026-04-05 12:00:00",
        "source_file_name": "通行证办理须知.pdf",
        "highlight": {
          "title": ["港澳通行证"],
          "content": ["办理流程"]
        }
      }
    ],
    "assistant_answer": "……"
  }
}
```

### 4.2.2 评测检索结果

`POST /projects/{project_id}/search/feedback`

## 4.3 文档问答

### 4.3.1 获取文档列表

`GET /projects/{project_id}/document-qa/files`

### 4.3.2 上传文档

`POST /projects/{project_id}/document-qa/files/upload`

form-data：

- `file`
- `overwrite_same_name`

### 4.3.3 获取文档预览

`GET /projects/{project_id}/document-qa/files/{file_id}/preview`

### 4.3.4 文档问答

`POST /projects/{project_id}/document-qa/ask`

请求：

```json
{
  "file_id": 1001,
  "query": "这份文档提到的申请条件是什么？"
}
```

---

## 5. 系统配置

## 5.1 开头语配置

### 5.1.1 获取配置

`GET /projects/{project_id}/settings/opening`

### 5.1.2 更新配置

`PUT /projects/{project_id}/settings/opening`

请求：

```json
{
  "mode": "card",
  "opening_text": "您好，欢迎使用 Nexus。",
  "recommended_questions": ["如何办理港澳通行证？"],
  "hot_questions": ["公积金怎么提取？"],
  "hot_policies": ["居住证办理政策"],
  "enabled": true
}
```

## 5.2 Prompt 配置

### 5.2.1 获取 Prompt

`GET /projects/{project_id}/settings/prompt`

### 5.2.2 更新 Prompt

`PUT /projects/{project_id}/settings/prompt`

请求：

```json
{
  "prompt_template": "你是一个专业问答助手。参考资料：{qa} 历史：{history} 问题：{query}",
  "version_note": "优化风格约束"
}
```

## 5.3 记忆配置

### 5.3.1 获取记忆配置

`GET /projects/{project_id}/settings/memory`

### 5.3.2 更新记忆配置

`PUT /projects/{project_id}/settings/memory`

请求：

```json
{
  "capability_memory": true,
  "memory_scope": "session_only",
  "memory_ttl_days": 7,
  "preference_memory_enabled": false
}
```

约束：

- 默认推荐 `memory_scope=session_only`
- `preference_memory_enabled=true` 时，仍只允许低风险偏好进入长期记忆

### 5.3.3 获取知识编译配置

`GET /projects/{project_id}/settings/knowledge-compilation`

返回：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "capability_knowledge_compilation": true,
    "compilation_strategy": "compiled_first",
    "compilation_min_score": 0.82,
    "compilation_min_supporting_source_count": 2,
    "compilation_allow_with_warning": false
  }
}
```

### 5.3.4 更新知识编译配置

`PUT /projects/{project_id}/settings/knowledge-compilation`

请求：

```json
{
  "capability_knowledge_compilation": true,
  "compilation_strategy": "compiled_first",
  "compilation_min_score": 0.82,
  "compilation_min_supporting_source_count": 2,
  "compilation_allow_with_warning": false
}
```

说明：

- 默认推荐 `compilation_strategy=compiled_first`
- 当 `capability_knowledge_compilation=false` 时，问答链路不得读取编译页作为回答上下文
- 任何记忆配置都不得改变“政策结论必须有来源”的规则

## 5.4 记忆删除

### 5.4.1 清空会话记忆

`DELETE /projects/{project_id}/chat/sessions/{session_id}/memory`

效果：

- 清空 `summary`
- 清空 `state_json`
- 保留原始对话日志与删除审计

---

## 6. 知识管理

## 6.1 知识库管理

### 6.1.1 获取知识库列表

`GET /projects/{project_id}/knowledge-bases`

查询参数：

- `keyword`
- `creator_id`
- `only_mine`
- `page`
- `page_size`

### 6.1.2 新建知识库

`POST /projects/{project_id}/knowledge-bases`

### 6.1.3 获取知识库详情

`GET /projects/{project_id}/knowledge-bases/{kb_id}`

### 6.1.4 更新知识库

`PUT /projects/{project_id}/knowledge-bases/{kb_id}`

### 6.1.5 删除知识库

`DELETE /projects/{project_id}/knowledge-bases/{kb_id}`

## 6.2 知识条目管理

### 6.2.1 获取知识列表

`GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge`

查询参数：

- `keyword`
- `status`
- `knowledge_id`
- `page`
- `page_size`

### 6.2.2 获取知识看板

`GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/dashboard`

### 6.2.3 新建知识

`POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge`

请求：

```json
{
  "document_name": "港澳通行证办理指南",
  "title": "港澳通行证办理指南",
  "keywords": ["港澳通行证", "办理"],
  "content": "……",
  "similar_questions": ["港澳通行证如何办理"],
  "check_duplicate": true
}
```

### 6.2.4 批量导入知识

`POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/import`

### 6.2.5 获取知识详情

`GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/{knowledge_id}`

### 6.2.6 更新知识

`PUT /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/{knowledge_id}`

### 6.2.7 上线知识

`POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/{knowledge_id}/publish`

### 6.2.8 下线知识

`POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/{knowledge_id}/offline`

### 6.2.9 删除知识

`DELETE /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/{knowledge_id}`

## 6.3 知识树

### 6.3.1 获取知识树当前版本

`GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/current`

### 6.3.2 获取知识树版本列表

`GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/versions`

### 6.3.3 保存编辑稿

`PUT /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/draft`

### 6.3.4 规整知识树

`POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/normalize`

### 6.3.5 重置知识树编辑稿

`POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/reset`

### 6.3.6 发布知识树版本

`POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/versions/{version_id}/publish`

### 6.3.7 下载知识树 JSON

`GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/versions/{version_id}/download`

### 6.3.8 上传知识树 JSON

`POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/upload`

## 6.4 文件库

### 6.4.1 获取文件列表

`GET /projects/{project_id}/knowledge-bases/{kb_id}/files`

### 6.4.2 上传文件

`POST /projects/{project_id}/knowledge/bases/{kb_id}/files`

说明：

- 使用 `multipart/form-data`
- 表单字段：
  - `upload`: 文件本体
  - `overwrite_same_name`: 是否覆盖同名文件，默认 `false`
  - `auto_process`: 是否在上传成功后自动后台处理，默认 `true`
- 当 `auto_process=true` 且文件解析成功时，系统会在后台自动执行：
  - 普通文件：默认切分入库 + QA 生成
  - 复杂表格 PDF：自动切换到 `table_aware` 模式做结构化表格入库 + QA 生成
- 上传接口返回后，前端应通过文件列表轮询状态，不需要再串行调用“切分入库 / QA 生成”

### 6.4.3 获取文件详情

`GET /projects/{project_id}/knowledge-bases/{kb_id}/files/{file_id}`

### 6.4.4 预览文件

`GET /projects/{project_id}/knowledge-bases/{kb_id}/files/{file_id}/preview`

### 6.4.5 下载文件

`GET /projects/{project_id}/knowledge-bases/{kb_id}/files/{file_id}/download`

### 6.4.6 删除文件

`DELETE /projects/{project_id}/knowledge-bases/{kb_id}/files/{file_id}`

### 6.4.7 生成 QA

`POST /projects/{project_id}/knowledge/bases/{kb_id}/files/{file_id}/generate-qa`

请求：

```json
{
  "chunk_size": 700,
  "max_pairs": 12
}
```

### 6.4.8 切分入库

`POST /projects/{project_id}/knowledge/bases/{kb_id}/files/{file_id}/import`

请求：

```json
{
  "chunk_size": 500,
  "generate_qa": false,
  "import_mode": "default",
  "table_schema_hint": null
}
```

说明：

- `import_mode` 支持：
  - `default`：走原有分页 / 分块入库
  - `table_aware`：在默认入库基础上，额外执行复杂表格抽取，生成行级、表头定义、脚注定义等结构化知识
- `table_schema_hint` 可选，用于给表格抽取阶段补充领域提示，例如“这是服务统计概览，保留不同用户群体、状态、数量、比例等分组”
- `table_aware` 返回体会额外包含：
  - `table_count`
  - `row_item_count`
  - `meta_item_count`
  - `validation_query_count`
  - `created_item_count`
  - `validation_summary`
- 文件列表返回体新增：
  - `auto_process_task`
  - 其中包含 `status`、`result_payload`、`error_message`
  - 可用于 admin 文件页展示自动处理中的状态、自动判定出的 `import_mode`、以及失败原因
 - 当项目启用知识编译层时，文件完成切分入库后可继续触发编译任务，但编译结果不会直接替代原始知识条目。

## 6.5 知识编译层（编译知识页）

说明：

- 对外产品名词统一使用“编译知识页”。
- 内部服务与数据库命名可使用 `knowledge_compilation`。
- 编译知识页是长期维护的整理层，不是原始事实来源。
- 权限映射建议：
  - `super_admin`：可执行全部编译页相关操作
  - `project_admin`：可创建、编辑、发布、运行编译、处理回流候选、处理健康问题
  - `project_member`：默认只读，可查看编译页、版本、来源、健康结果；不得发布、运行编译、合并回流
- 若后续引入更细粒度的 `kb read / kb write / kb manage / kb admin`，需作为现有系统角色与项目角色的派生权限层，不应替代当前角色模型。

### 6.5.1 获取编译知识页列表

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages`

查询参数：

- `keyword`
- `page_type`
- `status`
- `health_status`
- `topic_key`
- `tree_node_id`
- `page`
- `page_size`

### 6.5.2 新建编译知识页

`POST /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages`

请求：

```json
{
  "page_type": "procedure",
  "topic_key": "hk_pass_apply",
  "canonical_title": "港澳通行证办理",
  "title": "港澳通行证办理事项页",
  "summary": "面向市民的办理资格、材料和流程总览。",
  "content_markdown": "# 港澳通行证办理\n\n……",
  "tags": ["港澳通行证", "出入境", "办理流程"],
  "metadata": {
    "audience": "citizen",
    "language": "zh-Hant"
  },
  "tree_node_ids": [1001],
  "source_refs": [
    {
      "source_type": "knowledge_item",
      "source_id": 88,
      "claim_text": "首次办理所需材料",
      "support_type": "supports"
    }
  ],
  "status": "draft"
}
```

### 6.5.3 获取编译知识页详情

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}`

返回内容：

- 页面基础信息
- 当前发布版本
- 最新编辑版本
- 来源绑定列表
- 页面关系
- 健康状态摘要

### 6.5.4 更新编译知识页

`PUT /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}`

### 6.5.5 归档编译知识页

`DELETE /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}`

说明：

- 仅做软删除/归档，不删除原始 `knowledge_items`、`files` 与既有问答日志。

### 6.5.6 获取页面版本列表

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/versions`

### 6.5.7 获取页面版本详情

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/versions/{version_id}`

### 6.5.8 发布页面版本

`POST /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/versions/{version_id}/publish`

说明：

- 发布新版本后，旧发布版本自动转为历史版本。
- 编译运行失败不得覆盖当前已发布版本。
- 仅 `super_admin` 或目标项目 `project_admin` 可执行发布动作。

### 6.5.9 获取页面来源绑定

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/sources`

### 6.5.10 绑定来源

`POST /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/sources`

请求：

```json
{
  "source_type": "file_chunk",
  "source_id": "chunk_123",
  "source_ref_id": "file_123:block_9",
  "source_title": "港澳通行证办理指南.pdf",
  "source_locator": {
    "file_id": 123,
    "chunk_id": "chunk_123",
    "page_no": 4,
    "section": "申请条件",
    "block_id": "block_9"
  },
  "quote": "……",
  "claim_text": "首次办理须提交身份证明文件",
  "support_type": "supports",
  "weight": 1
}
```

### 6.5.11 解绑来源

`DELETE /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/sources/{source_link_id}`

### 6.5.12 获取页面关系

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/links`

### 6.5.13 新建页面关系

`POST /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/links`

### 6.5.14 删除页面关系

`DELETE /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/links/{link_id}`

### 6.5.15 运行编译任务

`POST /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/runs`

请求：

```json
{
  "idempotency_key": "compile-page-501-20260507T120000Z",
  "run_type": "recompile",
  "source_refs": [
    {
      "source_type": "file_chunk",
      "source_id": "chunk_123"
    }
  ],
  "options": {
    "create_version": true,
    "update_links": true,
    "run_health_check": true
  }
}
```

说明：

- 同一 `page_id` 同时只允许一个 `running` 状态的 `recompile` / `backfill` 任务。
- 当重复提交相同 `idempotency_key` 时，接口应返回已有任务，不得创建重复运行。
- 任务失败不得覆盖当前 `published_version_id`。

### 6.5.16 获取页面编译运行列表

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/pages/{page_id}/runs`

### 6.5.17 获取编译运行详情

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/runs/{run_id}`

### 6.5.18 发起健康检查

`POST /projects/{project_id}/knowledge-bases/{kb_id}/compilation/health-runs`

请求：

```json
{
  "idempotency_key": "health-kb-1-20260507",
  "run_type": "full_scan",
  "page_ids": [501, 502]
}
```

说明：

- 健康检查支持项目级批量扫描与页面级扫描。
- 同一 `project_id + kb_id + run_type + page_ids` 在短窗口内重复提交时，应优先复用已存在任务或返回冲突提示。

### 6.5.19 获取健康检查运行详情

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/health-runs/{run_id}`

### 6.5.20 获取健康问题列表

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/health-findings`

查询参数：

- `page_id`
- `check_type`
- `severity`
- `status`
- `page`
- `page_size`

### 6.5.21 更新健康问题状态

`PUT /projects/{project_id}/knowledge-bases/{kb_id}/compilation/health-findings/{finding_id}`

### 6.5.22 创建问答回流候选

`POST /projects/{project_id}/knowledge-bases/{kb_id}/compilation/writeback-candidates`

请求：

```json
{
  "chat_session_id": "sess_001",
  "chat_message_id": 9001,
  "suggested_page_id": 501,
  "suggested_page_type": "answer_writeback",
  "suggested_title": "港澳通行证办理补充问答",
  "review_note": "这轮回答可作为 FAQ 候选。"
}
```

### 6.5.23 获取问答回流候选列表

`GET /projects/{project_id}/knowledge-bases/{kb_id}/compilation/writeback-candidates`

查询参数：

- `status`
- `suggested_page_id`
- `page`
- `page_size`

### 6.5.24 合并问答回流候选

`POST /projects/{project_id}/knowledge-bases/{kb_id}/compilation/writeback-candidates/{candidate_id}/merge`

说明：

- 合并动作会生成页面新版本或新页面草稿，不直接覆盖当前发布内容。
- 仅 `super_admin` 或目标项目 `project_admin` 可执行合并动作。
- 同一候选仅允许成功合并一次；重复合并请求应返回当前状态或幂等成功结果。

### 6.5.25 拒绝问答回流候选

`POST /projects/{project_id}/knowledge-bases/{kb_id}/compilation/writeback-candidates/{candidate_id}/reject`

---

## 7. 测试管理

## 7.1 测试集

### 7.1.1 获取测试集列表

`GET /projects/{project_id}/datasets`

### 7.1.2 新建测试集

`POST /projects/{project_id}/datasets`

### 7.1.3 更新测试集

`PUT /projects/{project_id}/datasets/{dataset_id}`

### 7.1.4 删除测试集

`DELETE /projects/{project_id}/datasets/{dataset_id}`

### 7.1.5 获取测试集条目列表

`GET /projects/{project_id}/datasets/{dataset_id}/items`

### 7.1.6 新建测试集条目

`POST /projects/{project_id}/datasets/{dataset_id}/items`

### 7.1.7 批量上传测试集条目

`POST /projects/{project_id}/datasets/{dataset_id}/items/import`

### 7.1.8 更新测试集条目

`PUT /projects/{project_id}/datasets/{dataset_id}/items/{item_id}`

### 7.1.9 删除测试集条目

`DELETE /projects/{project_id}/datasets/{dataset_id}/items/{item_id}`

## 7.2 测试任务

### 7.2.1 获取测试任务列表

`GET /projects/{project_id}/evaluation-tasks`

### 7.2.2 新建测试任务

`POST /projects/{project_id}/evaluation-tasks`

请求：

```json
{
  "name": "检索效果测试-4月",
  "dataset_id": 100,
  "task_type": "retrieval_only"
}
```

### 7.2.3 运行测试任务

`POST /projects/{project_id}/evaluation-tasks/{task_id}/run`

### 7.2.4 重新运行测试任务

`POST /projects/{project_id}/evaluation-tasks/{task_id}/rerun`

### 7.2.5 获取测试任务详情

`GET /projects/{project_id}/evaluation-tasks/{task_id}`

### 7.2.6 获取测试任务结果列表

`GET /projects/{project_id}/evaluation-tasks/{task_id}/items`

### 7.2.7 删除测试任务

`DELETE /projects/{project_id}/evaluation-tasks/{task_id}`

---

## 8. 日志查询

### 8.1 获取历史对话日志

`GET /projects/{project_id}/chat-logs`

查询参数：

- `session_id`
- `query_keyword`
- `answer_keyword`
- `user_name`
- `user_ip`
- `source`
- `feedback`
- `start_time`
- `end_time`
- `page`
- `page_size`

### 8.2 获取日志详情

`GET /projects/{project_id}/chat-logs/{log_id}`

返回内容：

- 原始问题
- 改写问题
- Prompt 快照
- 回答
- 引用文献
- 来源知识
- 用户信息

### 8.3 复制日志内容

`POST /projects/{project_id}/chat-logs/{log_id}/copy`

---

## 9. 用户管理

### 9.1 获取用户列表

`GET /admin/users`

查询参数：

- `username`
- `system_role`
- `page`
- `page_size`

### 9.2 创建用户

`POST /admin/users`

### 9.3 更新用户

`PUT /admin/users/{user_id}`

### 9.4 删除用户

`DELETE /admin/users/{user_id}`

### 9.5 获取用户详情

`GET /admin/users/{user_id}`

---

## 10. 项目管理

### 10.1 获取项目列表

`GET /admin/projects`

查询参数：

- `project_key`
- `company_name`
- `page`
- `page_size`

### 10.2 新建项目

`POST /admin/projects`

请求：

```json
{
  "project_key": "nexus_gov",
  "company_name": "某政务中心",
  "description": "政务问答平台",
  "admin_user_ids": [2, 3],
  "capabilities": {
    "multi_turn": true,
    "sensitive_detection": true,
    "gov_domain_check": true,
    "knowledge_tree": true
  },
  "logo_url": "https://..."
}
```

### 10.3 获取项目详情

`GET /admin/projects/{project_id}`

### 10.4 更新项目

`PUT /admin/projects/{project_id}`

### 10.5 获取项目成员列表

`GET /admin/projects/{project_id}/members`

### 10.6 添加项目成员

`POST /admin/projects/{project_id}/members`

请求：

```json
{
  "user_ids": [5, 6],
  "project_role": "project_member"
}
```

### 10.7 更新项目成员角色

`PUT /admin/projects/{project_id}/members/{member_id}`

### 10.8 移出项目成员

`DELETE /admin/projects/{project_id}/members/{member_id}`

---

## 11. 任务与状态接口

### 11.1 获取文件任务状态

`GET /projects/{project_id}/tasks/files/{task_id}`

### 11.2 获取评测任务状态

`GET /projects/{project_id}/tasks/evaluation/{task_id}`

### 11.3 获取通用任务状态

`GET /projects/{project_id}/tasks/{task_id}`

---

## 12. 错误码建议

| code | 含义 |
|---|---|
| 4001 | 参数错误 |
| 4003 | 无权限 |
| 4004 | 资源不存在 |
| 4009 | 状态不允许当前操作 |
| 4010 | 未登录或 token 无效 |
| 4101 | 模型服务不可用 |
| 4102 | 检索服务不可用 |
| 4103 | 文件解析失败 |
| 4104 | 知识树发布失败 |
| 4105 | 测试任务执行失败 |
| 4106 | 知识编译服务不可用 |
| 4107 | 编译知识页版本冲突 |
| 4108 | 问答回流候选处理失败 |

---

## 13. 文档说明

本文件定义的是目标 API 基线，不代表当前仓库已有实现。若当前代码返回 mock 数据或缺失接口，应按本基线补齐。
