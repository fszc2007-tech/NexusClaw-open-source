# 前端真实接口页面说明

当前仓库中，前端页面分为两类：

## 1. 静态骨架页
用于展示页面结构与字段布局，例如：
- `Projects.tsx`
- `Persona.tsx`
- `Knowledge.tsx`
- `Dedup.tsx`
- `Chat.tsx`
- `History.tsx`

## 2. 真实接口联调页
用于直接调用当前后端接口，例如：
- `ProjectsReal.tsx`
- `PersonaReal.tsx`
- `KnowledgeReal.tsx`
- `DedupReal.tsx`
- `ChatReal.tsx`
- `HistoryReal.tsx`
- `ChatLogsRealV2.tsx`

## 3. 推荐联调入口
当前建议优先联调以下页面：
- admin: `ProjectsReal.tsx`
- admin: `PersonaReal.tsx`
- admin: `KnowledgeReal.tsx`
- admin: `DedupReal.tsx`
- admin: `ChatLogsRealV2.tsx`
- portal: `ChatReal.tsx`
- portal: `HistoryReal.tsx`

## 4. 后续整理建议
当 GitHub 连接允许直接覆盖旧文件时，建议：
1. 将 `.umirc.ts` 路由切换到真实接口页面
2. 删除静态骨架页或合并为单一实现
3. 将 portal/admin 的 API base URL 提到环境变量中
