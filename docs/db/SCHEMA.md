# Nexus RAG 平台 V2.0 数据库基线

## 1. 设计原则

- 所有业务数据按项目隔离。
- 平台级用户与项目级成员关系分层管理。
- 问答、检索、文件、知识树、测试任务均要求可追溯。
- 编辑态与发布态分离，避免直接覆盖线上版本。
- 编译知识页属于派生知识资产，不替代原始事实来源，关键事实必须可追溯回原始来源。
- 异步任务必须具备状态字段与失败原因。

---

## 2. 核心表概览

```text
users
user_sessions
projects
project_members
project_settings
user_preference_memories
knowledge_bases
knowledge_items
knowledge_similar_questions
knowledge_tags
knowledge_item_tags
knowledge_tree_versions
knowledge_tree_nodes
knowledge_tree_node_knowledge_links
files
file_tasks
chat_sessions
chat_messages
chat_feedback
search_feedback
evaluation_datasets
evaluation_dataset_items
evaluation_tasks
evaluation_task_items
operation_logs
knowledge_compilation_pages
knowledge_compilation_page_versions
knowledge_compilation_page_sources
knowledge_compilation_page_links
knowledge_compilation_page_tree_links
knowledge_compilation_runs
knowledge_compilation_run_items
knowledge_compilation_health_runs
knowledge_compilation_health_findings
knowledge_compilation_writeback_candidates
```

---

## 3. 表结构明细

## 3.1 users

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| username | varchar(64) unique | 用户名 |
| password_hash | varchar(255) | 密码哈希 |
| nickname | varchar(64) | 昵称 |
| profile | varchar(255) | 简介 |
| system_role | varchar(32) | `super_admin` / `normal_user` |
| status | varchar(32) | `active` / `disabled` |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `uk_users_username(username)`
- `idx_users_role(system_role)`

## 3.2 user_sessions

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| user_id | bigint | 用户 ID |
| access_token | varchar(255) | 访问 token 摘要 |
| refresh_token | varchar(255) | 刷新 token 摘要 |
| expires_at | datetime | 过期时间 |
| status | varchar(32) | `active` / `revoked` |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3.3 projects

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_key | varchar(64) unique | 项目标识 |
| company_name | varchar(128) | 公司/部门名称 |
| description | text | 项目简介 |
| logo_url | varchar(255) | 项目 logo |
| status | varchar(32) | `active` / `inactive` |
| created_by | bigint | 创建人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `uk_projects_project_key(project_key)`
- `idx_projects_company(company_name)`

## 3.4 project_members

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| user_id | bigint | 用户 ID |
| project_role | varchar(32) | `project_admin` / `project_member` |
| joined_at | datetime | 加入时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `uk_project_members(project_id, user_id)`
- `idx_project_members_user(user_id)`

## 3.5 project_settings

用于承载项目配置、门户配置与 Prompt 配置。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint unique | 项目 ID |
| opening_mode | varchar(32) | `text` / `card` |
| opening_text | text | 开头语 |
| recommended_questions | json | 推荐问题 |
| hot_questions | json | 热门问题 |
| hot_policies | json | 热门政策 |
| prompt_template | longtext | 项目 Prompt |
| capability_multi_turn | tinyint | 多轮问答 |
| capability_memory | tinyint | 会话记忆能力 |
| capability_sensitive_detection | tinyint | 敏感检测 |
| capability_gov_domain_check | tinyint | 政务相关校验 |
| capability_knowledge_tree | tinyint | 知识树能力 |
| capability_knowledge_compilation | tinyint | 知识编译层能力 |
| memory_scope | varchar(32) | `off` / `session_only` / `session_and_preference` |
| memory_ttl_days | int | 会话记忆保留天数 |
| preference_memory_enabled | tinyint | 是否启用长期偏好记忆 |
| compilation_strategy | varchar(32) | `compiled_first` / `raw_first` / `hybrid` / `disabled` |
| compilation_min_score | decimal(8,4) | 编译页最小命中分 |
| compilation_min_supporting_source_count | int | 最小支撑来源数 |
| compilation_allow_with_warning | tinyint | `warning` 页面是否允许进入回答上下文 |
| enabled | tinyint | 是否启用 |
| updated_by | bigint | 更新人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

说明：

- `capability_memory` 控制门户问答是否启用记忆链路。
- `memory_scope` 推荐默认值为 `session_only`。
- `preference_memory_enabled` 仅允许存储低风险偏好，不得承载敏感个人信息。
- `capability_knowledge_compilation` 控制项目是否启用编译知识页参与问答。
- `compilation_strategy` 推荐默认值为 `compiled_first`。
- `compilation_min_score`、`compilation_min_supporting_source_count`、`compilation_allow_with_warning` 共同决定编译页是否可直接进入回答上下文。

## 3.6 knowledge_bases

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| name | varchar(128) | 知识库名称 |
| description | varchar(255) | 描述 |
| is_default | tinyint | 是否默认知识库 |
| created_by | bigint | 创建人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `idx_knowledge_bases_project(project_id)`

## 3.7 knowledge_items

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| kb_id | bigint | 知识库 ID |
| document_name | varchar(255) | 文档名称 |
| title | varchar(255) | 标题 |
| content | longtext | 内容 |
| source_type | varchar(32) | `manual` / `file` / `import` / `qa_generated` |
| source_file_id | bigint null | 来源文件 ID |
| status | varchar(32) | `editing` / `publishing` / `active` / `publish_failed` / `offline` / `offline_failed` |
| generated_keywords | json | 自动抽取关键词 |
| version_no | int | 版本号 |
| published_at | datetime null | 发布时间 |
| offline_at | datetime null | 下线时间 |
| created_by | bigint | 创建人 |
| updated_by | bigint | 更新人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `idx_knowledge_items_project_kb_status(project_id, kb_id, status)`
- `idx_knowledge_items_title(title)`
- `idx_knowledge_items_source_file(source_file_id)`

## 3.8 knowledge_similar_questions

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| knowledge_id | bigint | 知识 ID |
| question | varchar(255) | 相似问题 |
| source | varchar(32) | `manual` / `generated` |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3.9 knowledge_tags

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| name | varchar(64) | 标签名 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3.10 knowledge_item_tags

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| knowledge_id | bigint | 知识 ID |
| tag_id | bigint | 标签 ID |

索引：

- `uk_knowledge_item_tags(knowledge_id, tag_id)`

## 3.11 knowledge_tree_versions

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| kb_id | bigint | 知识库 ID |
| version_no | int | 版本号 |
| status | varchar(32) | `draft` / `published` / `archived` |
| source_type | varchar(32) | `ui` / `upload` |
| snapshot_json | longtext | 树快照 |
| published_at | datetime null | 发布时间 |
| created_by | bigint | 创建人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `idx_tree_versions_project_kb(project_id, kb_id)`
- `idx_tree_versions_status(status)`

## 3.12 knowledge_tree_nodes

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| version_id | bigint | 版本 ID |
| parent_id | bigint null | 父节点 ID |
| node_code | varchar(64) | 节点编码 |
| node_type | varchar(32) | `branch` / `leaf` |
| name | varchar(128) | 节点名称 |
| description | text | 节点信息 |
| weight | decimal(5,2) | 权重 |
| link_url | varchar(255) null | 参考链接 |
| condition_operator | varchar(16) | `and` / `or` |
| conditions_json | json | 条件列表 |
| remark | varchar(255) | 备注 |
| sort_order | int | 排序 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3.13 knowledge_tree_node_knowledge_links

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| node_id | bigint | 节点 ID |
| knowledge_id | bigint | 知识 ID |
| created_at | datetime | 创建时间 |

索引：

- `uk_tree_node_knowledge(node_id, knowledge_id)`

## 3.14 files

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| kb_id | bigint | 知识库 ID |
| file_name | varchar(255) | 文件名 |
| file_ext | varchar(16) | 扩展名 |
| file_size | bigint | 文件大小 |
| storage_path | varchar(255) | 存储路径 |
| preview_path | varchar(255) null | 预览路径 |
| overwrite_same_name | tinyint | 是否覆盖同名 |
| parse_status | varchar(32) | `uploaded` / `parsing` / `parsed` / `failed` |
| chunk_status | varchar(32) | `pending` / `processing` / `success` / `failed` |
| qa_status | varchar(32) | `pending` / `processing` / `success` / `failed` |
| parse_error | varchar(255) null | 解析失败原因 |
| created_by | bigint | 上传人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `idx_files_project_kb(project_id, kb_id)`
- `idx_files_name(file_name)`

## 3.15 file_tasks

记录文件解析、QA 生成、切分入库等异步任务。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| kb_id | bigint | 知识库 ID |
| file_id | bigint | 文件 ID |
| task_type | varchar(32) | `parse` / `generate_qa` / `chunk_import` |
| status | varchar(32) | `pending` / `running` / `success` / `failed` / `cancelled` |
| request_payload | json | 请求参数 |
| result_payload | json | 结果摘要 |
| error_message | varchar(255) null | 错误信息 |
| created_by | bigint | 操作人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3.16 chat_sessions

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| session_code | varchar(64) unique | 会话编码 |
| project_id | bigint | 项目 ID |
| user_id | bigint null | 用户 ID |
| source | varchar(32) | `portal` / `admin` |
| title | varchar(255) | 会话标题 |
| selected_kb_ids | json | 生效知识库列表 |
| switches_json | json | 会话级开关 |
| status | varchar(32) | `active` / `closed` |
| summary | text null | 会话摘要 |
| state_json | json null | 结构化任务状态 |
| last_active_at | datetime | 最近活跃时间 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `uk_chat_sessions_code(session_code)`
- `idx_chat_sessions_project_user(project_id, user_id)`

## 3.17 chat_messages

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| session_id | bigint | 会话 ID |
| role | varchar(16) | `user` / `assistant` / `system` |
| query_raw | text null | 原始问题 |
| query_rewritten | text null | 改写问题 |
| answer | longtext null | 回答 |
| source_docs | json | 来源知识 |
| used_memory | tinyint | 本轮是否使用记忆 |
| memory_snapshot_json | json null | 本轮上下文拼装使用的记忆快照 |
| safety_flags_json | json null | 敏感信息检测与脱敏标记 |
| prompt_snapshot | longtext null | Prompt 快照 |
| model_name | varchar(64) null | 模型名称 |
| trace_id | varchar(64) null | 链路追踪 ID |
| created_at | datetime | 创建时间 |

索引：

- `idx_chat_messages_session_time(session_id, created_at)`

## 3.18 chat_feedback

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| message_id | bigint | 助手消息 ID |
| user_id | bigint | 反馈人 |
| rating | varchar(32) | `good` / `bad` / `expert_score` |
| score | decimal(5,2) null | 分值 |
| comment | varchar(255) null | 反馈说明 |
| created_at | datetime | 创建时间 |

## 3.19 search_feedback

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| user_id | bigint | 用户 ID |
| query | varchar(255) | 搜索词 |
| knowledge_id | bigint | 关联知识 |
| rating | varchar(32) | `relevant` / `irrelevant` |
| comment | varchar(255) null | 备注 |
| created_at | datetime | 创建时间 |

## 3.20 evaluation_datasets

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| name | varchar(128) | 测试集名称 |
| description | varchar(255) | 描述 |
| created_by | bigint | 创建人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3.21 evaluation_dataset_items

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| dataset_id | bigint | 测试集 ID |
| query | text | 问题 |
| ref_answer | longtext null | 参考答案 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `idx_dataset_items_dataset(dataset_id)`

## 3.22 evaluation_tasks

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| dataset_id | bigint | 测试集 ID |
| name | varchar(128) | 任务名称 |
| task_type | varchar(64) | `compare_ref` / `compare_retrieval` / `retrieval_only` / `answer_only` |
| status | varchar(32) | `pending` / `running` / `success` / `failed` / `cancelled` |
| started_at | datetime null | 开始时间 |
| finished_at | datetime null | 结束时间 |
| created_by | bigint | 创建人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3.23 user_preference_memories

仅存储低风险长期偏好，不存储身份证号、手机号、住址等敏感信息。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| user_id | bigint | 用户 ID |
| preferences_json | json | 低风险偏好 |
| source | varchar(32) | `explicit_confirmed` / `implicit_inferred` |
| status | varchar(32) | `active` / `disabled` / `deleted` |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `uk_user_preference_memories(project_id, user_id)`

## 3.24 evaluation_task_items

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| task_id | bigint | 测试任务 ID |
| dataset_item_id | bigint | 测试集条目 ID |
| generated_answer | longtext null | 机跑答案 |
| retrieval_docs | json null | 检索结果 |
| evaluation_result | json null | 自动评测结果 |
| manual_review_result | json null | 人工评测结果 |
| status | varchar(32) | `pending` / `running` / `success` / `failed` |
| error_message | varchar(255) null | 错误信息 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

## 3.25 operation_logs

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint null | 项目 ID |
| operator_id | bigint | 操作人 |
| operation_type | varchar(64) | 操作类型 |
| target_type | varchar(64) | 目标类型 |
| target_id | bigint null | 目标 ID |
| detail_json | json | 详情 |
| ip_address | varchar(64) null | IP |
| created_at | datetime | 创建时间 |

索引：

- `idx_operation_logs_project(project_id)`
- `idx_operation_logs_operator(operator_id)`

## 3.26 knowledge_compilation_pages

编译知识页主表。页面为长期维护的整理层，不是原始事实来源。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| kb_id | bigint | 知识库 ID |
| page_type | varchar(32) | `overview` / `topic` / `procedure` / `policy` / `faq` / `comparison` / `entity` / `form_guide` / `case_note` / `answer_writeback` |
| topic_key | varchar(128) | 主题键，便于去重与归并 |
| canonical_title | varchar(255) | 规范标题 |
| title | varchar(255) | 当前展示标题 |
| summary | text null | 页面摘要 |
| content_markdown | longtext | 页面正文 |
| tags_json | json | 标签 |
| metadata_json | json | 扩展元数据 |
| status | varchar(32) | `draft` / `published` / `archived` / `disabled` |
| health_status | varchar(32) | `healthy` / `warning` / `critical` / `unknown` |
| retrieval_priority | int | 问答命中优先级 |
| version_no | int | 当前版本号 |
| current_version_id | bigint null | 当前版本 ID |
| published_version_id | bigint null | 当前发布版本 ID |
| last_compiled_at | datetime null | 最近编译时间 |
| published_at | datetime null | 最近发布时间 |
| created_by | bigint | 创建人 |
| updated_by | bigint | 更新人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |
| deleted_at | datetime null | 软删除时间 |

索引：

- `idx_compilation_pages_project_kb_status(project_id, kb_id, status)`
- `idx_compilation_pages_topic_key(topic_key)`
- `idx_compilation_pages_page_type(page_type)`
- `idx_compilation_pages_health_status(health_status)`

## 3.27 knowledge_compilation_page_versions

编译知识页版本表。用于版本回滚、审计和差异比对。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| page_id | bigint | 页面 ID |
| version_no | int | 版本号 |
| title | varchar(255) | 版本标题 |
| summary | text null | 版本摘要 |
| content_markdown | longtext | 版本正文 |
| sources_snapshot_json | json | 版本级来源快照 |
| change_summary | varchar(255) null | 变更摘要 |
| run_id | bigint null | 关联编译运行 ID |
| is_current | tinyint | 是否当前编辑版本 |
| created_by | bigint | 创建人 |
| created_at | datetime | 创建时间 |

索引：

- `uk_compilation_page_versions(page_id, version_no)`
- `idx_compilation_page_versions_run(run_id)`

## 3.28 knowledge_compilation_page_sources

编译知识页来源映射表。支持证据级引用，不仅绑定来源 ID，还记录定位信息与 claim。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| page_id | bigint | 页面 ID |
| version_id | bigint null | 页面版本 ID，为空表示当前生效绑定 |
| source_type | varchar(32) | `knowledge_item` / `file` / `file_chunk` / `chat_message` / `manual` |
| source_id | varchar(128) | 来源主键或引用 ID |
| source_ref_id | varchar(128) null | 来源细粒度引用 ID |
| source_title | varchar(255) | 来源标题 |
| source_locator_json | json | 页码、块号、section 等定位信息 |
| source_quote | text null | 原文摘录 |
| source_snapshot | json null | 编译时来源快照 |
| claim_text | text null | 当前来源支撑的 claim |
| support_type | varchar(32) | `supports` / `contradicts` / `updates` / `background` / `derived_from` |
| weight | decimal(8,4) | 来源权重 |
| order_no | int | 展示顺序 |
| created_at | datetime | 创建时间 |

索引：

- `idx_compilation_page_sources_page(page_id)`
- `idx_compilation_page_sources_source(source_type, source_id)`
- `idx_compilation_page_sources_version(version_id)`

## 3.29 knowledge_compilation_page_links

编译知识页之间的关系链接表。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| kb_id | bigint | 知识库 ID |
| from_page_id | bigint | 来源页面 ID |
| to_page_id | bigint | 目标页面 ID |
| link_type | varchar(32) | `related` / `parent` / `child` / `contrasts` / `depends_on` / `supersedes` / `mentions` |
| anchor_text | varchar(255) null | 锚文本 |
| created_at | datetime | 创建时间 |

索引：

- `idx_compilation_page_links_from(from_page_id)`
- `idx_compilation_page_links_to(to_page_id)`

## 3.30 knowledge_compilation_page_tree_links

编译知识页与知识树节点的挂接关系表。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| page_id | bigint | 页面 ID |
| node_id | bigint | 知识树节点 ID |
| link_type | varchar(32) | `primary` / `secondary` |
| created_at | datetime | 创建时间 |

索引：

- `uk_compilation_page_tree_links(page_id, node_id)`
- `idx_compilation_page_tree_links_node(node_id)`

## 3.31 knowledge_compilation_runs

编译运行主表。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| kb_id | bigint | 知识库 ID |
| page_id | bigint null | 页面 ID |
| run_type | varchar(32) | `ingest` / `recompile` / `writeback_merge` / `health_check` / `backfill` |
| trigger_type | varchar(32) | `manual` / `file_task_completed` / `knowledge_item_updated` / `chat_writeback` / `scheduled` |
| strategy | varchar(32) | `compiled_first` / `raw_first` / `hybrid` / `disabled` |
| status | varchar(32) | `queued` / `running` / `succeeded` / `failed` / `cancelled` / `partial` |
| idempotency_key | varchar(128) null | 幂等键 |
| request_payload | json | 请求参数 |
| result_payload | json null | 结果摘要 |
| error_message | varchar(255) null | 失败信息 |
| started_at | datetime null | 开始时间 |
| finished_at | datetime null | 结束时间 |
| created_by | bigint | 创建人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `idx_compilation_runs_project_kb(project_id, kb_id)`
- `idx_compilation_runs_page(page_id)`
- `idx_compilation_runs_status(status)`
- `uk_compilation_runs_idempotency(idempotency_key)`

## 3.32 knowledge_compilation_run_items

编译运行明细表。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| run_id | bigint | 运行 ID |
| page_id | bigint null | 页面 ID |
| source_type | varchar(32) | 来源类型 |
| source_id | varchar(128) | 来源 ID |
| action_type | varchar(32) | `create_page` / `update_page` / `link_source` / `unlink_source` / `detect_conflict` / `create_health_finding` |
| status | varchar(32) | `queued` / `running` / `succeeded` / `failed` / `skipped` |
| before_version_no | int null | 变更前版本 |
| after_version_no | int null | 变更后版本 |
| error_message | varchar(255) null | 错误信息 |
| created_at | datetime | 创建时间 |

索引：

- `idx_compilation_run_items_run(run_id)`
- `idx_compilation_run_items_page(page_id)`

## 3.33 knowledge_compilation_health_runs

健康检查运行表。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| kb_id | bigint | 知识库 ID |
| page_id | bigint null | 页面 ID，为空表示批量扫描 |
| version_id | bigint null | 页面版本 ID |
| run_type | varchar(32) | `full_scan` / `page_scan` / `post_compile_scan` |
| status | varchar(32) | `queued` / `running` / `succeeded` / `failed` / `cancelled` |
| summary_json | json null | 统计摘要 |
| started_at | datetime null | 开始时间 |
| finished_at | datetime null | 结束时间 |
| created_by | bigint | 发起人 |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

索引：

- `idx_compilation_health_runs_project_kb(project_id, kb_id)`
- `idx_compilation_health_runs_page(page_id)`

## 3.34 knowledge_compilation_health_findings

健康检查发现表。支持按类型、严重级别和状态筛选。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| health_run_id | bigint | 健康检查运行 ID |
| page_id | bigint | 页面 ID |
| page_version_id | bigint null | 页面版本 ID |
| check_type | varchar(32) | `stale_claim` / `source_conflict` / `missing_citation` / `orphan_page` / `broken_link` / `duplicate_page` / `low_source_coverage` / `outdated_source` / `unlinked_entity` |
| severity | varchar(16) | `info` / `warning` / `critical` |
| status | varchar(32) | `open` / `resolved` / `ignored` / `superseded` |
| finding_title | varchar(255) | 标题 |
| finding_detail | text | 详情 |
| evidence_json | json null | 证据 |
| suggested_action | varchar(255) null | 建议动作 |
| resolved_by | bigint null | 处理人 |
| resolved_at | datetime null | 处理时间 |
| created_at | datetime | 创建时间 |

索引：

- `idx_compilation_health_findings_run(health_run_id)`
- `idx_compilation_health_findings_page(page_id)`
- `idx_compilation_health_findings_type_status(check_type, status)`
- `idx_compilation_health_findings_severity(severity)`

## 3.35 knowledge_compilation_writeback_candidates

问答回流候选表。优质问答不得直接写入正式页面，需先进入候选态。

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint pk | 主键 |
| project_id | bigint | 项目 ID |
| kb_id | bigint | 知识库 ID |
| chat_session_id | bigint | 会话 ID |
| chat_message_id | bigint | 助手消息 ID |
| question | text | 原问题 |
| answer | longtext | 原回答 |
| source_docs_snapshot | json | 回流时的来源快照 |
| suggested_page_id | bigint null | 建议合并到的页面 |
| suggested_page_type | varchar(32) | 建议页面类型 |
| suggested_title | varchar(255) null | 建议标题 |
| status | varchar(32) | `pending` / `approved` / `rejected` / `merged` / `superseded` |
| review_note | varchar(255) null | 审核备注 |
| merged_version_id | bigint null | 合并后的页面版本 ID |
| created_by | bigint | 创建人 |
| reviewed_by | bigint null | 审核人 |
| created_at | datetime | 创建时间 |
| reviewed_at | datetime null | 审核时间 |

索引：

- `idx_compilation_writeback_candidates_project_kb(project_id, kb_id)`
- `idx_compilation_writeback_candidates_status(status)`
- `idx_compilation_writeback_candidates_page(suggested_page_id)`

---

## 4. 关键关系

- `projects` 1:N `project_members`
- `projects` 1:1 `project_settings`
- `projects` 1:N `user_preference_memories`
- `projects` 1:N `knowledge_bases`
- `knowledge_bases` 1:N `knowledge_items`
- `knowledge_bases` 1:N `files`
- `knowledge_bases` 1:N `knowledge_tree_versions`
- `knowledge_bases` 1:N `knowledge_compilation_pages`
- `knowledge_tree_versions` 1:N `knowledge_tree_nodes`
- `knowledge_tree_nodes` N:N `knowledge_items`
- `knowledge_tree_nodes` N:N `knowledge_compilation_pages`
- `projects` 1:N `evaluation_datasets`
- `evaluation_datasets` 1:N `evaluation_dataset_items`
- `projects` 1:N `evaluation_tasks`
- `evaluation_tasks` 1:N `evaluation_task_items`
- `projects` 1:N `chat_sessions`
- `chat_sessions` 1:N `chat_messages`
- `knowledge_compilation_pages` 1:N `knowledge_compilation_page_versions`
- `knowledge_compilation_pages` 1:N `knowledge_compilation_page_sources`
- `knowledge_compilation_pages` N:N `knowledge_compilation_pages` via `knowledge_compilation_page_links`
- `knowledge_compilation_pages` 1:N `knowledge_compilation_runs`
- `knowledge_compilation_health_runs` 1:N `knowledge_compilation_health_findings`

---

## 5. 状态枚举建议

## 5.1 文件任务

- `pending`
- `running`
- `success`
- `failed`
- `cancelled`

## 5.2 知识树版本

- `draft`
- `published`
- `archived`

## 5.3 测试任务

- `pending`
- `running`
- `success`
- `failed`
- `cancelled`

## 5.4 编译知识页

- `draft`
- `published`
- `archived`
- `disabled`

## 5.5 编译运行

- `queued`
- `running`
- `succeeded`
- `failed`
- `cancelled`
- `partial`

## 5.6 健康问题

- `open`
- `resolved`
- `ignored`
- `superseded`

## 5.7 回流候选

- `pending`
- `approved`
- `rejected`
- `merged`
- `superseded`

## 5.8 编译权限映射建议

- `super_admin`
  - 可查看、创建、编辑、发布、归档编译页
  - 可运行编译任务、健康检查、回流合并
- `project_admin`
  - 可查看、创建、编辑、发布、归档本项目编译页
  - 可运行本项目编译任务、健康检查、回流合并
- `project_member`
  - 默认只读
  - 可查看编译页、版本、来源、健康结果
  - 不可发布、运行编译、处理回流候选

## 5.9 编译命中阈值建议

- `compilation_strategy`
  - `compiled_first`
  - `raw_first`
  - `hybrid`
  - `disabled`
- `compilation_min_score`
  - 建议项目级配置，默认由 `project_settings` 管控
- `compilation_min_supporting_source_count`
  - 建议项目级配置，默认由 `project_settings` 管控
- `compilation_allow_with_warning`
  - 建议项目级配置，默认由 `project_settings` 管控

---

## 6. 数据保留与审计

- 会话消息、日志、测试任务结果默认长期保留。
- 删除用户时不物理删除历史日志中的业务留痕。
- 删除知识库或测试集需考虑级联规则，但不能破坏审计记录。
- 删除编译知识页时仅允许软删除/归档，不得级联删除原始知识、原始文件、历史问答与来源快照。
- 编译页不得作为唯一事实来源对外返回，引用链路必须可追溯回原始 `knowledge_items`、`files`、`file chunks` 或已审计的手工来源。

---

## 7. 文档说明

本文件为目标数据库基线，不代表当前仓库数据库已全部实现。后续建模、迁移与接口联调以本文件为准。
