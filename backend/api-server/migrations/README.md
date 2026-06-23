# Alembic 迁移目录

当前仓库先放入初始化配置，后续建议执行：

```bash
alembic init migrations
alembic revision -m "init schema"
alembic upgrade head
```

建议首版 migration 覆盖以下表：
- projects
- project_persona
- knowledge
- knowledge_dedup_records
- chat_sessions
- chat_messages

当前目录为占位说明，后续可继续补：
- env.py
- script.py.mako
- versions/*.py
