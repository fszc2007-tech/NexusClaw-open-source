# RAG 能力盘点与专题改造建议

## 1. 文档目的

本文件用于沉淀当前仓库在 RAG 关键链路上的实现现状，区分：

- 已做
- 部分做了
- 基本没做

并给出后续专题改造时可优先复用或改造的开源方案，以及基于当前开发机器性能的落地建议。

适用范围：

- 文件接入与文档处理
- 检索增强问答
- 引用链路
- 基础权限与系统治理

---

## 2. 总结结论

当前 8 项能力的判断如下：

- 已做：文档接入、解析与切分、answer generation
- 部分做了：embedding、向量检索 / 混合检索、rerank、citation 引用
- 基本没做：基础权限

当前系统不是“从 0 到 1 都没做”，也不是“已经生产级完成”。更准确地说：

- 文档处理链路已经打通，且具备一定可用性
- 检索链路已经有骨架和接口层，但底层向量能力仍偏轻量
- 引用链路只在文档问答体验页相对完整，主聊天链路仍是来源级引用
- 鉴权与权限控制几乎还是开发占位态

补充判断：

- 当前仓库已经具备“临时检索后生成答案”的 RAG 主链路
- 但还缺少“把综合结果长期沉淀成可维护知识页”的知识编译层
- 因此后续重点不应被理解为“推翻现有 RAG”，而应理解为“在现有 RAG 之前补一层长期沉淀和治理能力”

---

## 3. 分项盘点

### 3.1 文档接入

状态：已做

当前能力：

- 支持文件上传
- 支持文件预览
- 支持导入知识库
- 支持基于文件生成 QA
- 支持删除文件及关联知识

代码位置：

- `backend/api-server/app/api/v1/endpoints/files.py`
- `backend/api-server/app/services/file_service.py`

说明：

- 当前更像“本地文件上传型接入”
- 暂未看到飞书、OSS、网页、对象存储、网盘、Git 仓库等外部 connector

结论：

- 文件型文档接入已做
- 多来源文档接入未做

### 3.2 解析与切分

状态：已做

当前能力：

- 支持 `txt/md/csv/html/docx/xlsx/xlsm/pptx/pptm/pdf`
- 支持图片 OCR 解析
- 按文档类型采用不同 chunk 策略
- 保留了 `page_no / sheet_name / slide_no / section_title` 等结构信息

代码位置：

- `backend/api-server/app/services/document_parser.py`
- `backend/api-server/app/services/file_service.py`

说明：

- 这部分完成度已经不低
- 但目前仍主要是规则式 chunking
- 还不是版面感知、语义切分、标题层级自适应、表格图文联合理解那种更强的生产方案

结论：

- 可用
- 后续重点应是增强精度，不是推倒重来

### 3.3 embedding

状态：部分做了

当前能力：

- 支持 `hash`
- 支持 `sentence_transformers`
- 支持 `openai_compat`
- 提供向量写入、删除、查询能力

代码位置：

- `backend/api-server/app/services/local_rag_service.py`
- `backend/api-server/app/services/search_sync_service.py`

说明：

- `LocalRagService` 已具备 embedding 抽象层
- 但本地 fallback 方案是 SQLite 中存 `embedding_json`，再做余弦相似度计算
- 这更适合开发验证、小规模数据或本地兜底
- 还不算正式的生产向量检索底座

结论：

- embedding 接口和能力抽象已做
- 生产级 embedding 基础设施未完全落地

### 3.4 向量检索 / 混合检索

状态：部分做了

当前能力：

- term search
- vector search
- RRF 融合
- fallback lexical search

代码位置：

- `backend/api-server/app/services/retrieval_service.py`
- `backend/api-server/app/services/search_sync_service.py`

说明：

- 检索编排层已经有了
- 但向量检索主要依赖外部 `VECTOR_SEARCH_URL`
- 仓库内并没有一个完整成熟的 ANN 向量引擎实现
- Elasticsearch/OpenSearch 也只是对接，不是完整内建检索平台

结论：

- 混合检索框架已搭好
- 真正稳态可扩展的检索底层仍需补齐

### 3.5 rerank

状态：部分做了

当前能力：

- 支持远程 `RERANK_URL`
- 支持本地 `cross_encoder`
- 支持降级 fallback rerank

代码位置：

- `backend/api-server/app/services/retrieval_service.py`
- `backend/api-server/app/services/local_rag_service.py`

说明：

- 已具备 rerank 插槽
- 但模型选型、推理吞吐、批量化、缓存与线上资源规划都还没真正产品化

结论：

- rerank 机制已接入
- rerank 工程化和稳定性建设未完成

### 3.6 answer generation

状态：已做

当前能力：

- 主聊天链路调用大模型生成回答
- 支持 query rewrite
- 支持 retrieval guard
- 文件 QA 生成优先走 DeepSeek
- 模型失败时存在规则降级

代码位置：

- `backend/api-server/app/services/chat_service.py`
- `backend/api-server/app/services/deepseek_service.py`
- `backend/api-server/app/services/file_service.py`

结论：

- 回答生成主链路已打通
- 后续更多是替换模型供应方式与增强约束，而不是补空白功能

### 3.7 citation 引用

状态：部分做了

当前能力：

- 文档问答体验页有 block 级 citation
- 可返回 `quote / page_no / sheet_name / slide_no / block_id`
- 前端支持高亮命中片段

代码位置：

- `backend/api-server/app/services/document_qa_service.py`
- `frontend/admin-web/src/pages/experience/DocumentQA.tsx`

当前不足：

- 主聊天链路返回的是 `sources`
- 更偏“来源知识条目级”
- 不是严格的 snippet 级、quote 级、可回跳原文位置的统一 citation 体系

代码位置：

- `backend/api-server/app/services/chat_service.py`

结论：

- 文档问答链路的 citation 基本可用
- 全局统一 citation 体系未做完

### 3.8 基础权限

状态：基本没做

当前能力：

- 登录接口返回固定 token
- `/me` 返回固定用户
- 角色基本是写死的 `super_admin`

代码位置：

- `backend/api-server/app/api/v1/endpoints/auth.py`

当前不足：

- 没有真实 JWT 校验
- 没有 session/token 生命周期管理
- 没有接口级鉴权中间层
- 没有项目级 RBAC
- 没有成员、角色、资源、动作之间的授权模型

结论：

- 当前权限仍是开发占位实现
- 这是后续最应该优先补齐的治理能力

---

## 4. 开源方案建议

以下建议以“优先复用，不建议重造轮子”为原则。

### 4.1 文档接入与解析

优先候选：

- Docling
- Unstructured

建议：

- 如果重点是提升 PDF / Office 文档解析质量，优先考虑 `Docling`
- 如果重点是扩展多来源接入与通用 partition 流程，优先考虑 `Unstructured`

适配方式：

- 保留现有 `FileService`
- 将 `DocumentParser` 改造成多实现适配层
- 先接入新 parser，不要一次性推翻现有文件链路

### 4.2 embedding

优先候选：

- `BAAI/bge-m3`
- `TEI`

建议：

- `bge-m3` 更适合中文、多语和混合检索场景
- 现有代码已支持 `openai_compat` 风格接口，适合平滑接 TEI 或兼容服务

### 4.3 向量检索 / 混合检索

优先候选：

- Qdrant
- OpenSearch

建议：

- 如果想尽量贴合当前 term + vector + 融合的思路，可选 `OpenSearch`
- 如果更重视向量能力、开发便利性和轻量部署，可选 `Qdrant`

适配方式：

- 保留 `RetrievalService`
- 替换底层 `VECTOR_SEARCH_URL` 指向的服务
- 不先动上层 chat orchestration

### 4.4 rerank

优先候选：

- `BAAI/bge-reranker-v2-m3`

建议：

- 直接作为统一 rerank 模型
- 后续可以通过独立 rerank 服务挂到现有 `RERANK_URL`

### 4.5 answer generation

优先候选：

- vLLM

建议：

- 如果后续想减少外部 API 依赖，或希望统一模型网关，可以用 `vLLM` 托管开源指令模型
- 但这部分对本机显存与内存要求更高，不建议作为当前机器上的第一优先改造项

### 4.6 citation

优先候选：

- LlamaIndex CitationQueryEngine

建议：

- 不一定要整套接入 LlamaIndex
- 更现实的做法是借它的 citation 组织方式，把现有主聊天链路升级成 chunk/snippet 级引用

### 4.7 基础权限

优先候选：

- FastAPI Users
- Casbin
- Keycloak

建议：

- 轻量版本：`FastAPI Users + Casbin`
- 完整版本：`Keycloak + Casbin`

适配方式：

- 先补 JWT 登录和用户表
- 再补项目级 RBAC
- 最后再考虑统一 SSO 或组织级身份系统

### 4.8 知识编译层

目标：

- 让知识从“每次临时检索”变成“长期沉淀、持续整理、可复用”

建议建设内容：

- 知识页生成与更新
- 页面交叉引用
- `index` 目录与 `log` 变更记录
- 知识健康检查，例如矛盾、过时、孤立页和缺失概念识别
- 优质问答回流为知识页

边界要求：

- 知识编译层不替代原始资料
- 知识编译层不替代向量检索、term 检索和 rerank
- 问答时可优先读取知识页，但高风险问题仍要支持回查原始来源

---

## 5. 当前机器性能约束建议

结论先说：

- 当前机器不适合一次性本地自建整套重型 RAG 基础设施
- 更适合“保留现有业务主链路 + 分阶段替换薄弱底层”

不建议在当前机器上一次性本地全开：

- Docling 高质量解析 + OCR 批处理
- OpenSearch / Elasticsearch
- 正式向量库
- reranker 服务
- vLLM 大模型服务

原因：

- 这些组件叠加后，对 CPU、内存、磁盘 I/O，甚至 GPU / 显存都有明显要求
- 当前仓库还处于“产品链路梳理 + 能力补齐”阶段
- 现在更应该优先做结构正确，而不是先做全本地重部署

更适合当前机器的做法：

- 保留现有 FastAPI + 前端主链路
- 先补基础权限
- 先把 citation 做统一
- embedding / rerank / vector search 优先走外部兼容服务
- 本地仅保留轻量开发 fallback

推荐的轻量路线：

1. 保留当前文件上传、解析、知识入库链路
2. 保留当前 `RetrievalService` 编排层
3. 把 embedding 换成外部兼容服务
4. 把 rerank 换成独立远程服务
5. 把向量检索换成 Qdrant 或 OpenSearch
6. 最后再决定是否引入更重的文档解析与模型服务

这条路线的优势：

- 不会一次性把开发机压垮
- 改造边界清晰
- 每一步都能回滚
- 能优先解决真正影响产品质量的问题

---

## 6. 后续专题改造优先级

建议按以下顺序推进：

1. 基础权限
2. 主聊天链路 citation 升级
3. embedding / rerank / vector search 正式化
4. 文档解析质量升级
5. 多来源文档接入
6. 本地模型网关或自托管问答模型

说明：

- 权限是治理底座，应该先补
- citation 直接影响答案可追溯性和可用性
- 检索链路正式化会明显提升问答质量
- 知识编译层会明显提升长期复用率和知识资产质量
- 文档解析和接入扩展更适合在检索基础稳定后再做

---

## 7. 现阶段推荐策略

现阶段不建议做“大而全重构”，建议做“专题式、分批改造”：

- 先记录清楚问题边界
- 每次只替换一段底层能力
- 上层接口尽量不变
- 通过兼容层逐步替换旧实现

对当前仓库而言，最现实的目标不是一次性变成完整生产平台，而是：

- 先把系统从“可演示”推到“可稳定迭代”
- 再把薄弱链路逐项升级成可复用基础设施
