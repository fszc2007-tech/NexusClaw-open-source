# 后台 IA 与页面/API/表结构映射

## 1. 文档目的

本文件用于把“功能清单 -> 后台信息架构 -> 页面清单 -> API -> 表结构”打通，作为后台开发与联调的直接依据。

统一口径来源：

- [PRD.md](./PRD.md)
- [TECH_DESIGN.md](../tech-design/TECH_DESIGN.md)
- [API_SPEC.md](../api/API_SPEC.md)
- [SCHEMA.md](../db/SCHEMA.md)

---

## 2. 后台信息架构

```text
后台管理端
├── 登录
├── 工作台
├── 体验广场
│   ├── 知识问答
│   ├── 知识检索
│   └── 文档问答
├── 系统配置
│   ├── 开头语配置
│   └── Prompt 配置
├── 知识管理
│   ├── 知识库列表
│   ├── 知识条目列表
│   ├── 知识条目编辑
│   ├── 知识树编辑
│   └── 文件库
├── 测试管理
│   ├── 测试集列表
│   ├── 测试集条目列表
│   ├── 测试任务列表
│   └── 测试任务详情
├── 日志查询
│   ├── 历史对话日志列表
│   └── 日志详情
├── 用户管理
│   ├── 用户列表
│   └── 用户编辑
└── 项目管理
    ├── 项目列表
    ├── 项目编辑
    └── 项目成员
```

---

## 3. 路由建议

| 路由 | 页面 | 说明 | 权限 |
|---|---|---|---|
| `/login` | 登录页 | 后台登录 | 全部 |
| `/workbench` | 工作台 | 汇总项目、任务、统计 | 登录用户 |
| `/experience/chat` | 知识问答 | 后台体验问答 | 登录用户 |
| `/experience/search` | 知识检索 | 后台体验检索 | 登录用户 |
| `/experience/document-qa` | 文档问答 | 后台体验文档问答 | 登录用户 |
| `/settings/opening` | 开头语配置 | 配置门户开头语 | 超级管理员、项目管理员 |
| `/settings/prompt` | Prompt 配置 | 配置项目 Prompt | 超级管理员、项目管理员 |
| `/knowledge/bases` | 知识库列表 | 管理知识库 | 超级管理员、项目管理员 |
| `/knowledge/bases/:kbId/items` | 知识条目列表 | 管理知识条目 | 超级管理员、项目管理员 |
| `/knowledge/bases/:kbId/items/new` | 新建知识 | 新建知识条目 | 超级管理员、项目管理员 |
| `/knowledge/bases/:kbId/items/:id/edit` | 编辑知识 | 编辑知识条目 | 超级管理员、项目管理员 |
| `/knowledge/bases/:kbId/tree` | 知识树编辑 | 管理知识树版本与节点 | 超级管理员、项目管理员 |
| `/knowledge/bases/:kbId/files` | 文件库 | 管理文件、解析、QA、切分 | 超级管理员、项目管理员 |
| `/testing/datasets` | 测试集列表 | 管理测试集 | 登录用户 |
| `/testing/datasets/:id/items` | 测试集条目 | 管理测试样本 | 登录用户 |
| `/testing/tasks` | 测试任务列表 | 管理测试任务 | 登录用户 |
| `/testing/tasks/:id` | 测试任务详情 | 查看明细、结果与人工评测 | 登录用户 |
| `/logs/chat` | 对话日志列表 | 查询问答日志 | 登录用户 |
| `/logs/chat/:id` | 对话日志详情 | 查看改写、Prompt、来源 | 登录用户 |
| `/users` | 用户列表 | 平台用户管理 | 超级管理员 |
| `/users/:id/edit` | 用户编辑 | 编辑系统用户 | 超级管理员 |
| `/projects` | 项目列表 | 项目管理 | 超级管理员、项目管理员 |
| `/projects/new` | 新建项目 | 新建项目 | 超级管理员 |
| `/projects/:id/edit` | 项目编辑 | 编辑项目信息和能力 | 超级管理员、项目管理员 |
| `/projects/:id/members` | 项目成员 | 管理项目成员与角色 | 超级管理员、项目管理员 |

---

## 4. 页面清单与状态要求

## 4.1 登录

- 目标：完成后台鉴权进入系统。
- 模块：
  - 用户名
  - 密码
  - 登录按钮
- 状态：
  - loading
  - 登录失败
  - 登录成功跳转

## 4.2 工作台

- 目标：展示当前用户可访问项目、近期任务、待处理事项。
- 模块：
  - 项目切换
  - 统计卡片
  - 最近任务
  - 快捷入口
- 状态：
  - 无项目
  - 有项目但无数据
  - 加载失败

## 4.3 体验广场

### 知识问答

- 模块：
  - 会话列表
  - 对话区域
  - 开关配置
  - 生效知识库选择
  - 来源知识
  - 专家评测

### 知识检索

- 模块：
  - 搜索框
  - Top10 结果列表
  - 检索问答助手
  - 结果评测

### 文档问答

- 模块：
  - 文件上传
  - 文件列表
  - 原文预览
  - 文档问答区

## 4.4 系统配置

### 开头语配置

- 模块：
  - 模式切换
  - 文本输入
  - 推荐问题
  - 热门问题
  - 热门政策
  - 生效开关

### Prompt 配置

- 模块：
  - Prompt 编辑器
  - 变量说明
  - 提交按钮
  - 历史版本说明

## 4.5 知识管理

### 知识库列表

- 模块：
  - 筛选栏
  - 知识库表格
  - 新建按钮
  - 查看/编辑/删除

### 知识条目列表

- 模块：
  - 状态看板
  - 条件筛选
  - 表格
  - 新建/导入
  - 上线/下线/编辑

### 知识条目编辑

- 模块：
  - 文档名称
  - 标题
  - 关键词
  - 内容
  - 相似问题
  - 保存/上线

### 知识树编辑

- 模块：
  - 树画布
  - 节点编辑抽屉
  - 版本列表
  - 发布/下载/上传

### 文件库

- 模块：
  - 上传
  - 搜索
  - 文件表格
  - 预览
  - 下载
  - 生成 QA
  - 切分入库

## 4.6 测试管理

### 测试集列表

- 模块：
  - 搜索
  - 新建
  - 上传
  - 删除

### 测试集条目列表

- 模块：
  - 搜索
  - 新建
  - 上传 Excel
  - 编辑
  - 删除

### 测试任务列表

- 模块：
  - 搜索
  - 新建任务
  - 运行
  - 重跑
  - 详情
  - 删除

### 测试任务详情

- 模块：
  - 任务汇总
  - 明细表格
  - 自动评测结果
  - 人工评测

## 4.7 日志查询

### 对话日志列表

- 模块：
  - 基础搜索
  - 高级筛选
  - 复制
  - 详情

### 对话日志详情

- 模块：
  - 原始问题
  - 改写问题
  - Prompt 快照
  - 回答
  - 来源知识
  - 用户信息

## 4.8 用户管理

- 模块：
  - 搜索
  - 创建用户
  - 编辑用户
  - 删除用户

## 4.9 项目管理

### 项目列表

- 模块：
  - 搜索
  - 新建
  - 编辑
  - 成员

### 项目编辑

- 模块：
  - 项目 ID
  - 公司名称
  - 项目简介
  - 项目能力
  - 项目 logo

### 项目成员

- 模块：
  - 成员列表
  - 添加成员
  - 编辑角色
  - 移出成员

---

## 5. 页面 -> API -> 表结构映射

| 页面 | 核心 API | 核心表 |
|---|---|---|
| 登录 | `POST /auth/login` `GET /auth/me` | `users` `user_sessions` |
| 工作台 | `GET /admin/projects` `GET /projects/{project_id}/tasks/{task_id}` | `projects` `project_members` `file_tasks` `evaluation_tasks` |
| 知识问答 | `POST /projects/{project_id}/chat/sessions` `GET /projects/{project_id}/chat/sessions` `POST /projects/{project_id}/chat/ask` `POST /projects/{project_id}/chat/messages/{message_id}/feedback` | `chat_sessions` `chat_messages` `chat_feedback` `project_settings` |
| 知识检索 | `POST /projects/{project_id}/search` `POST /projects/{project_id}/search/feedback` | `knowledge_items` `search_feedback` |
| 文档问答 | `GET /projects/{project_id}/document-qa/files` `POST /projects/{project_id}/document-qa/files/upload` `GET /projects/{project_id}/document-qa/files/{file_id}/preview` `POST /projects/{project_id}/document-qa/ask` | `files` `file_tasks` |
| 开头语配置 | `GET /projects/{project_id}/settings/opening` `PUT /projects/{project_id}/settings/opening` | `project_settings` |
| Prompt 配置 | `GET /projects/{project_id}/settings/prompt` `PUT /projects/{project_id}/settings/prompt` | `project_settings` |
| 知识库列表 | `GET /projects/{project_id}/knowledge-bases` `POST /projects/{project_id}/knowledge-bases` `PUT /projects/{project_id}/knowledge-bases/{kb_id}` `DELETE /projects/{project_id}/knowledge-bases/{kb_id}` | `knowledge_bases` |
| 知识条目列表 | `GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge` `GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/dashboard` `POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/import` | `knowledge_items` `knowledge_similar_questions` `knowledge_tags` `knowledge_item_tags` |
| 知识条目编辑 | `POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge` `GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/{knowledge_id}` `PUT /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/{knowledge_id}` `POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/{knowledge_id}/publish` `POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge/{knowledge_id}/offline` | `knowledge_items` `knowledge_similar_questions` `knowledge_tags` `knowledge_item_tags` |
| 知识树编辑 | `GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/current` `GET /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/versions` `PUT /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/draft` `POST /projects/{project_id}/knowledge-bases/{kb_id}/knowledge-tree/versions/{version_id}/publish` | `knowledge_tree_versions` `knowledge_tree_nodes` `knowledge_tree_node_knowledge_links` |
| 文件库 | `GET /projects/{project_id}/knowledge-bases/{kb_id}/files` `POST /projects/{project_id}/knowledge-bases/{kb_id}/files/upload` `GET /projects/{project_id}/knowledge-bases/{kb_id}/files/{file_id}/preview` `POST /projects/{project_id}/knowledge-bases/{kb_id}/files/{file_id}/generate-qa` `POST /projects/{project_id}/knowledge-bases/{kb_id}/files/{file_id}/chunk-and-import` | `files` `file_tasks` `knowledge_items` |
| 测试集列表 | `GET /projects/{project_id}/datasets` `POST /projects/{project_id}/datasets` `PUT /projects/{project_id}/datasets/{dataset_id}` `DELETE /projects/{project_id}/datasets/{dataset_id}` | `evaluation_datasets` |
| 测试集条目 | `GET /projects/{project_id}/datasets/{dataset_id}/items` `POST /projects/{project_id}/datasets/{dataset_id}/items` `POST /projects/{project_id}/datasets/{dataset_id}/items/import` `PUT /projects/{project_id}/datasets/{dataset_id}/items/{item_id}` `DELETE /projects/{project_id}/datasets/{dataset_id}/items/{item_id}` | `evaluation_dataset_items` |
| 测试任务列表 | `GET /projects/{project_id}/evaluation-tasks` `POST /projects/{project_id}/evaluation-tasks` `POST /projects/{project_id}/evaluation-tasks/{task_id}/run` `POST /projects/{project_id}/evaluation-tasks/{task_id}/rerun` | `evaluation_tasks` |
| 测试任务详情 | `GET /projects/{project_id}/evaluation-tasks/{task_id}` `GET /projects/{project_id}/evaluation-tasks/{task_id}/items` | `evaluation_tasks` `evaluation_task_items` |
| 对话日志列表 | `GET /projects/{project_id}/chat-logs` | `chat_sessions` `chat_messages` `chat_feedback` |
| 对话日志详情 | `GET /projects/{project_id}/chat-logs/{log_id}` `POST /projects/{project_id}/chat-logs/{log_id}/copy` | `chat_messages` `operation_logs` |
| 用户列表 | `GET /admin/users` `POST /admin/users` `PUT /admin/users/{user_id}` `DELETE /admin/users/{user_id}` | `users` |
| 项目列表 | `GET /admin/projects` `POST /admin/projects` | `projects` `project_settings` |
| 项目编辑 | `GET /admin/projects/{project_id}` `PUT /admin/projects/{project_id}` | `projects` `project_settings` |
| 项目成员 | `GET /admin/projects/{project_id}/members` `POST /admin/projects/{project_id}/members` `PUT /admin/projects/{project_id}/members/{member_id}` `DELETE /admin/projects/{project_id}/members/{member_id}` | `project_members` `users` |

---

## 6. 权限矩阵

| 页面/模块 | 超级管理员 | 项目管理员 | 项目成员 |
|---|---|---|---|
| 登录/工作台/体验广场 | 可访问 | 可访问 | 可访问 |
| 开头语配置 | 可编辑 | 可编辑 | 只读或不可见 |
| Prompt 配置 | 可编辑 | 可编辑 | 只读或不可见 |
| 知识库/知识条目/知识树/文件库 | 可编辑 | 可编辑 | 只读或不可见 |
| 测试管理 | 可访问 | 可访问 | 可访问 |
| 日志查询 | 可访问 | 可访问 | 可访问 |
| 用户管理 | 可编辑 | 不可见 | 不可见 |
| 项目列表 | 可访问全部 | 仅可访问参与项目 | 不可见 |
| 项目成员 | 可编辑 | 可编辑参与项目成员 | 不可见 |

---

## 7. 开发落地建议

推荐按以下顺序实现后台：

1. 登录 + 布局 + 权限框架
2. 项目管理 + 项目切换
3. 开头语配置 + Prompt 配置
4. 知识库 + 知识条目
5. 文件库
6. 体验广场
7. 知识树
8. 日志查询
9. 测试管理
10. 用户管理

这样可以先打通“项目配置 -> 知识入库 -> 问答 -> 日志”，再补知识树和测试闭环。
