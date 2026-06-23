# services 模块说明

当前已初始化的服务层：

- `project_service.py`
- `knowledge_service.py`
- `dedup_service.py`
- `chat_service.py`

建议后续职责：

## project_service
- 项目列表/详情
- 项目级人设读取与保存

## knowledge_service
- 知识创建
- 知识上线/下线
- 创建时触发查重

## dedup_service
- 文本标准化
- 相似知识召回
- 相似度打分
- 替换/保留决策辅助

## chat_service
- query 改写
- 检索调用
- rerank
- prompt 组装
- 生成回答
