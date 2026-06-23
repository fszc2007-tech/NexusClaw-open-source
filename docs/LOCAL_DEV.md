# 本地开发说明

## 1. 启动依赖

在仓库根目录执行：

```bash
docker compose up -d
```

启动后会得到：
- MySQL: `127.0.0.1:3306`
- Redis: `127.0.0.1:6379`

默认数据库名和用户为 `nexusclaw`。本地密码仅用于开发环境，请在 `.env` 中改成你自己的值，不要提交 `.env`。

## 2. 启动后端

推荐环境：

- 后端与本地 RAG 统一使用 `Python 3.13`
- 已验证 `python3.13 + backend/api-server/requirements.txt` 可直接安装成功
- `Python 3.14` 可用于主 API 临时联调，但不建议作为本地 RAG 默认版本
进入目录：

```bash
cd backend/api-server
cp .env.example .env
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload --port 8000
```

访问：
- 健康检查：`http://127.0.0.1:8000/health`
- Swagger：`http://127.0.0.1:8000/docs`

## 2.1 启动本地 RAG 服务

当前主 API 已经支持通过 HTTP 接入向量检索和重排服务。仓库内提供了一个本地可跑的最小 RAG 服务，兼容以下接口：

- `POST /vector/upsert`
- `POST /vector/delete`
- `POST /vector/search`
- `POST /rerank`

启动方式：

```bash
cd backend/api-server
source .venv/bin/activate
uvicorn main_rag:app --reload --port 8101
```

更推荐直接使用仓库内的稳态启动脚本，它会优先做几件事：
- 默认把 embedding / rerank 都压到 `cpu`
- 默认 `LOCAL_RAG_RERANK_BATCH_SIZE=4`
- 默认 `LOCAL_RAG_TORCH_NUM_THREADS=1`
- 默认关闭 `reload`，减少额外进程和文件监听开销
- 自动探测本机 HuggingFace 缓存里的 `text2vec-base-chinese` 与 `bge-reranker-base`
- 在需要下载模型时，自动补上 `HF_ENDPOINT=https://hf-mirror.com`

```bash
cd backend/api-server
chmod +x scripts/run_local_rag.sh
./scripts/run_local_rag.sh
```

如果你就是在频繁改本地 RAG 代码，需要热更新，再临时这样跑：

```bash
cd backend/api-server
LOCAL_RAG_RELOAD=true ./scripts/run_local_rag.sh
```

如果想先确认脚本会使用什么配置，不真正启动服务：

```bash
cd backend/api-server
./scripts/run_local_rag.sh --print-env
```

如果主 API 也要一起接到这套本地 RAG，可直接参考：

```bash
cd backend/api-server
cp .env.local-rag.example .env.local-rag
```

然后把 `.env.local-rag` 里的关键项合并进你正在使用的 `.env`。

如果只想先跑通链路，可使用默认 `hash` embedding，无需外部模型。

如果要接入本机已有 HuggingFace embedding 模型，可直接在 `.env` 中配置本地路径：

```bash
VECTOR_SEARCH_URL=http://127.0.0.1:8101/vector/search
VECTOR_UPSERT_URL=http://127.0.0.1:8101/vector/upsert
VECTOR_DELETE_URL=http://127.0.0.1:8101/vector/delete
RERANK_URL=http://127.0.0.1:8101/rerank

LOCAL_RAG_EMBEDDING_PROVIDER=sentence_transformers
LOCAL_RAG_EMBEDDING_MODEL_PATH=/path/to/local/huggingface/model
LOCAL_RAG_EMBEDDING_DEVICE=cpu
```

如果要接入已经在本地运行的 embedding HTTP 服务，请在 `.env` 中配置：

```bash
VECTOR_SEARCH_URL=http://127.0.0.1:8101/vector/search
VECTOR_UPSERT_URL=http://127.0.0.1:8101/vector/upsert
VECTOR_DELETE_URL=http://127.0.0.1:8101/vector/delete
RERANK_URL=http://127.0.0.1:8101/rerank

LOCAL_RAG_EMBEDDING_PROVIDER=openai_compat
LOCAL_RAG_EMBEDDING_URL=http://127.0.0.1:9997/v1/embeddings
LOCAL_RAG_EMBEDDING_MODEL=bge-m3
```

如果要让这台 M3 机器本地跑 rerank，建议优先使用轻量配置：

```bash
LOCAL_RAG_RERANK_PROVIDER=cross_encoder
LOCAL_RAG_RERANK_MODEL=BAAI/bge-reranker-base
LOCAL_RAG_RERANK_DEVICE=cpu
LOCAL_RAG_RERANK_BATCH_SIZE=4
LOCAL_RAG_TORCH_NUM_THREADS=1
LOCAL_RAG_PRELOAD_MODELS=false
```

这样在同时开着 OCR、前后端和数据库时更稳。如果机器主要跑问答联调，不跑大批量 OCR，可再把 `LOCAL_RAG_RERANK_DEVICE` 切到 `mps`。

如果想减少首个请求的冷启动时间，也可以手动预热：

```bash
curl -X POST http://127.0.0.1:8101/warmup
```

预热结果和当前真实运行态也能从健康检查里直接看到：

```bash
curl http://127.0.0.1:8101/health
```

返回里会包含：
- `embedding_device_resolved`
- `rerank_device_resolved`
- `embedding_model_loaded`
- `rerank_model_loaded`
- `preload_models`
- `degraded_fallback_enabled`

如果本地模型依赖暂时没装好，或者机器当下负载太高，默认会自动退化到轻量的 `embedding_cosine` 重排，不会直接让问答链路不可用：

```bash
LOCAL_RAG_ALLOW_DEGRADED_FALLBACK=true
```

如果已有独立 rerank 服务，可继续让主 API 指向本地 RAG 服务，再由本地 RAG 服务转发：

```bash
LOCAL_RAG_RERANK_PROVIDER=upstream
LOCAL_RAG_RERANK_UPSTREAM_URL=http://127.0.0.1:9998/rerank
LOCAL_RAG_RERANK_UPSTREAM_MODEL=bge-reranker-v2-m3
```

## 2.2 安装本地 RAG 可选依赖

为了不影响主 API 的最小安装，embedding/rerank 的本地模型依赖拆到了单独文件：

```bash
cd backend/api-server
source .venv/bin/activate
pip install -r requirements-local-rag.txt
```

如果只使用远程 embedding 服务和上游 rerank 服务，这一步可以跳过。

建议：

- `requirements-local-rag.txt` 这组依赖优先放在 `Python 3.13` 环境里安装
- 如果你已经误用其他 Python 版本创建了 `.venv`，最稳妥的做法是删掉重建：

```bash
cd backend/api-server
rm -rf .venv
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-local-rag.txt
```

## 3. 启动前台门户

```bash
cd frontend/portal-web
pnpm install
pnpm dev
```

如需覆盖默认接口地址，可在启动前设置：

```bash
UMI_APP_API_BASE_URL=http://127.0.0.1:8000/api/v1 pnpm dev
```

## 4. 启动后台管理端

```bash
cd frontend/admin-web
pnpm install
pnpm dev
```

如需覆盖默认接口地址，可在启动前设置：

```bash
UMI_APP_API_BASE_URL=http://127.0.0.1:8000/api/v1 pnpm dev
```

## 5. Current Status

This repository is an early open-source release of NexusClaw.

Implemented:

- FastAPI backend with service modules and Alembic migrations
- Admin and portal frontend applications
- Project configuration, knowledge management, chat, file, log, and evaluation modules
- File upload, parsing, chunking, preview, and document Q&A paths
- Local RAG service with vector/search/rerank-compatible endpoints
- Retrieval orchestration with keyword, vector, rerank, chunk, and fallback paths
- Knowledge deduplication, freshness, conflict, compilation, and governance flows
- OpenClaw-compatible plugin bundle with RAG and scene runtime helpers

Partially implemented:

- Production-grade vector search backend
- Unified snippet-level citation across all chat paths
- Full RBAC, authentication hardening, and project-level authorization
- Turnkey deployment packaging for production environments

Not production-ready yet:

- Public multi-tenant SaaS usage without additional security hardening
- Strict regulated enterprise deployments
- External connector ecosystems without custom integration work
- Fully unattended production operations
