# frontend/admin-web

## 目标

提供 NexusClaw 后台管理界面，服务于超级管理员、项目管理员和项目成员。

## 核心模块

- 项目管理
- 项目人设配置
- 知识库管理
- 文件库管理
- 知识查重处理
- 会话日志查询
- 操作日志查询

## 建议首批页面

1. `/projects`
2. `/projects/:id/persona`
3. `/projects/:id/knowledge`
4. `/projects/:id/files`
5. `/projects/:id/dedup`
6. `/projects/:id/logs/chat`
7. `/projects/:id/logs/operations`

## 核心组件建议

- ProjectForm
- PersonaForm
- KnowledgeTable
- DedupDecisionDrawer
- FileUploadPanel
- LogFilterForm
