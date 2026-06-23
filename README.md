# NexusClaw

NexusClaw 是一个面向政务场景的知识问答平台，服务对象为市民和工作人员。

本地仓库目录已统一为 `NexusClaw`；正式产品名统一为 `NexusClaw`。

## 开源定位

NexusClaw 采用 open-core 路线。公开仓库包含可复用的政务知识问答框架、后台管理端、公众门户端、本地 RAG 能力和场景运行时辅助工具。

以下内容不应进入公开仓库：

- 客户项目配置、报价材料、RFI/RFP 材料和内部交接记录
- 真实知识库数据、上传文件、数据库文件、日志和生成结果
- API key、token、OTP、私钥、服务账号、生产环境配置
- 商业部署脚本、高级治理插件和客户专属集成

## 项目目标

- 为市民提供政策咨询、办事流程、材料要求、常见问题解答
- 为工作人员提供知识检索、政策口径参考、业务辅助问答
- 支持项目级 Bot 配置、知识库管理、多轮会话记忆、知识条目查重与替换

## 当前范围

- 政务场景知识问答
- 项目级人设与 Prompt 配置
- 知识库与文件库管理
- 本项目知识入库统一使用繁體中文；新入库内容会在服务端自动转繁體，历史简体知识需回填为繁體
- 知识条目查重
- 项目管理员直接处理“替换旧知识 / 不替换旧知识”
- 多轮对话与会话记忆
- 日志查询与操作审计

## 明确不做

- 文档考试 / 练习 / 评分
- 文件级查重
- 审批流（仅预留扩展）
- 一个项目内多助手切换

## 仓库建议结构

```text
frontend/
  portal-web/
  admin-web/
backend/
  api-server/
  app/
    modules/
      auth/
      project/
      persona/
      knowledge/
      dedup/
      retrieval/
      chat/
      logs/
docs/
  prd/
  tech-design/
  api/
  db/
scripts/
deploy/
```

## 文档入口

- `docs/prd/PRD.md`
- `docs/tech-design/TECH_DESIGN.md`
- `docs/tech-design/RAG_CAPABILITY_AUDIT.md`
- `docs/api/API_SPEC.md`
- `docs/db/SCHEMA.md`
- `docs/LOCAL_DEV.md`
- `docs/openclaw/NEXUSCLAW_LOCAL_DEPLOY.md`

## License

NexusClaw is licensed under the Apache License, Version 2.0. See `LICENSE` and `NOTICE`.

## 本地环境基线

- 后端推荐使用 `Python 3.13`
- 推荐直接在 `backend/api-server` 目录读取 `.python-version`
- OpenClaw 插件已从纯 RAG bundle 升级为 scene agent runtime，支持显式 scene 控制面与 CLI fallback

## 下一步建议

1. 先按文档完成后端基础骨架与数据库建模
2. 优先打通“项目配置 -> 知识入库 -> 问答 -> 日志”主链路
3. 第二阶段落知识条目查重与替换
4. 再做会话记忆优化和政务知识树增强
