# backend/api-server

## 目标

提供 NexusClaw 后端统一 API 入口，负责：

- 鉴权
- 权限校验
- 项目级路由
- 统一响应格式
- 审计埋点

## 建议初始化结构

```text
backend/api-server/
  main.py
  requirements.txt
  app/
    api/
    core/
    models/
    schemas/
    services/
    repositories/
    middleware/
    deps/
```

## 首批模块建议

- auth
- project
- persona
- knowledge
- files
- dedup
- chat
- logs

## 首批待建能力

1. 登录 / 获取当前用户
2. 项目 CRUD
3. 项目级人设 CRUD
4. 知识 CRUD 与上线下线
5. 文件上传与切分入库任务
6. 问答接口
7. 查重接口与处理接口
8. 日志查询接口
