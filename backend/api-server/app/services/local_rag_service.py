from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from typing import Any

import httpx

from app.core.config import settings


@dataclass
class LocalVectorDocument:
    document_id: str | None
    document_kind: str
    knowledge_id: int | None
    chunk_id: int | None
    project_id: int
    kb_id: int
    title: str
    content: str
    document_name: str | None = None
    source_type: str | None = None
    metadata: dict[str, Any] | None = None


class LocalRagService:
    KNOWLEDGE_DOCUMENT_KIND = "knowledge_item"
    CHUNK_DOCUMENT_KIND = "knowledge_chunk"

    def __init__(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.db_path = self._resolve_path(settings.LOCAL_RAG_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._embedding_model: Any = None
        self._rerank_model: Any = None
        self._torch_ready = False
        self._ensure_schema()
        if settings.LOCAL_RAG_PRELOAD_MODELS:
            self.warmup()

    def runtime_status(self) -> dict[str, Any]:
        embedding_model = self._resolve_optional_path(settings.LOCAL_RAG_EMBEDDING_MODEL_PATH) or settings.LOCAL_RAG_EMBEDDING_MODEL
        rerank_model = (
            settings.LOCAL_RAG_RERANK_UPSTREAM_MODEL
            if settings.LOCAL_RAG_RERANK_PROVIDER.lower() == "upstream"
            else self._resolve_optional_path(settings.LOCAL_RAG_RERANK_MODEL_PATH) or settings.LOCAL_RAG_RERANK_MODEL
        )
        return {
            "db_path": str(self.db_path),
            "embedding_provider": settings.LOCAL_RAG_EMBEDDING_PROVIDER,
            "embedding_model": embedding_model,
            "embedding_device_requested": settings.LOCAL_RAG_EMBEDDING_DEVICE,
            "embedding_device_resolved": self._resolve_torch_device(settings.LOCAL_RAG_EMBEDDING_DEVICE),
            "embedding_model_loaded": self._embedding_model is not None,
            "rerank_provider": settings.LOCAL_RAG_RERANK_PROVIDER,
            "rerank_model": rerank_model,
            "rerank_device_requested": settings.LOCAL_RAG_RERANK_DEVICE,
            "rerank_device_resolved": self._resolve_torch_device(settings.LOCAL_RAG_RERANK_DEVICE),
            "rerank_model_loaded": self._rerank_model is not None,
            "degraded_fallback_enabled": settings.LOCAL_RAG_ALLOW_DEGRADED_FALLBACK,
            "torch_num_threads": max(int(settings.LOCAL_RAG_TORCH_NUM_THREADS or 1), 1),
            "preload_models": settings.LOCAL_RAG_PRELOAD_MODELS,
        }

    def warmup(self) -> dict[str, Any]:
        result: dict[str, Any] = {"embedding": {"status": "skipped"}, "rerank": {"status": "skipped"}}

        embedding_provider = settings.LOCAL_RAG_EMBEDDING_PROVIDER.lower()
        if embedding_provider == "sentence_transformers":
            try:
                self._load_sentence_transformer_model()
                result["embedding"] = {
                    "status": "ready",
                    "provider": embedding_provider,
                    "model": self._resolve_optional_path(settings.LOCAL_RAG_EMBEDDING_MODEL_PATH)
                    or settings.LOCAL_RAG_EMBEDDING_MODEL,
                    "device": self._resolve_torch_device(settings.LOCAL_RAG_EMBEDDING_DEVICE),
                }
            except Exception as exc:
                result["embedding"] = {
                    "status": "degraded" if settings.LOCAL_RAG_ALLOW_DEGRADED_FALLBACK else "failed",
                    "provider": embedding_provider,
                    "error": str(exc),
                }
                if not settings.LOCAL_RAG_ALLOW_DEGRADED_FALLBACK:
                    raise
        elif embedding_provider == "openai_compat":
            result["embedding"] = {
                "status": "configured" if settings.LOCAL_RAG_EMBEDDING_URL else "missing_config",
                "provider": embedding_provider,
                "endpoint": settings.LOCAL_RAG_EMBEDDING_URL,
            }
        else:
            result["embedding"] = {"status": "ready", "provider": embedding_provider}

        rerank_provider = settings.LOCAL_RAG_RERANK_PROVIDER.lower()
        if rerank_provider == "cross_encoder":
            try:
                self._load_cross_encoder_model()
                result["rerank"] = {
                    "status": "ready",
                    "provider": rerank_provider,
                    "model": self._resolve_optional_path(settings.LOCAL_RAG_RERANK_MODEL_PATH)
                    or settings.LOCAL_RAG_RERANK_MODEL,
                    "device": self._resolve_torch_device(settings.LOCAL_RAG_RERANK_DEVICE),
                }
            except Exception as exc:
                result["rerank"] = {
                    "status": "degraded" if settings.LOCAL_RAG_ALLOW_DEGRADED_FALLBACK else "failed",
                    "provider": rerank_provider,
                    "error": str(exc),
                }
                if not settings.LOCAL_RAG_ALLOW_DEGRADED_FALLBACK:
                    raise
        elif rerank_provider == "upstream":
            result["rerank"] = {
                "status": "configured" if settings.LOCAL_RAG_RERANK_UPSTREAM_URL else "missing_config",
                "provider": rerank_provider,
                "endpoint": settings.LOCAL_RAG_RERANK_UPSTREAM_URL,
            }
        else:
            result["rerank"] = {"status": "ready", "provider": rerank_provider}

        return result

    def upsert_documents(self, documents: list[LocalVectorDocument]) -> dict[str, Any]:
        normalized_docs = [self._normalize_document(document) for document in documents if document.content.strip()]
        if not normalized_docs:
            return {"count": 0}

        embeddings = self._embed_texts([self._document_text(document.title, document.content) for document in normalized_docs])
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO vector_documents (
                    document_id, document_kind, knowledge_id, chunk_id, project_id, kb_id,
                    title, content, document_name, source_type, metadata_json, embedding_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(document_id) DO UPDATE SET
                    document_kind=excluded.document_kind,
                    project_id=excluded.project_id,
                    kb_id=excluded.kb_id,
                    knowledge_id=excluded.knowledge_id,
                    chunk_id=excluded.chunk_id,
                    title=excluded.title,
                    content=excluded.content,
                    document_name=excluded.document_name,
                    source_type=excluded.source_type,
                    metadata_json=excluded.metadata_json,
                    embedding_json=excluded.embedding_json,
                    updated_at=excluded.updated_at
                """,
                [
                    (
                        document.document_id,
                        document.document_kind,
                        document.knowledge_id,
                        document.chunk_id,
                        document.project_id,
                        document.kb_id,
                        document.title,
                        document.content,
                        document.document_name,
                        document.source_type,
                        json.dumps(document.metadata or {}, ensure_ascii=False),
                        json.dumps(embedding),
                        timestamp,
                    )
                    for document, embedding in zip(normalized_docs, embeddings, strict=False)
                ],
            )
        return {"count": len(normalized_docs)}

    def delete_documents(
        self,
        document_ids: list[str] | None = None,
        knowledge_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        normalized_document_ids = {self._normalize_document_id(document_id) for document_id in (document_ids or [])}
        normalized_document_ids = {document_id for document_id in normalized_document_ids if document_id}
        normalized_knowledge_ids = sorted({knowledge_id for knowledge_id in (knowledge_ids or []) if isinstance(knowledge_id, int)})
        normalized_document_ids.update(self._legacy_document_id(knowledge_id) for knowledge_id in normalized_knowledge_ids)
        if not normalized_document_ids:
            return {"count": 0}
        ordered_ids = sorted(normalized_document_ids)
        placeholders = ",".join("?" for _ in ordered_ids)
        with self._connect() as conn:
            cursor = conn.execute(
                f"DELETE FROM vector_documents WHERE document_id IN ({placeholders})",
                ordered_ids,
            )
        return {"count": int(cursor.rowcount or 0)}

    def search(
        self,
        query: str,
        project_id: int,
        kb_ids: list[int] | None = None,
        top_k: int = 10,
        document_kind: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_query = " ".join(query.strip().split())
        if not normalized_query:
            return []

        query_vector = self._embed_texts([normalized_query])[0]
        rows = self._list_documents(project_id=project_id, kb_ids=kb_ids, document_kind=document_kind)
        query_tokens = self._tokenize(normalized_query)
        hits: list[dict[str, Any]] = []
        for row in rows:
            embedding = json.loads(row["embedding_json"])
            dense_score = self._cosine_similarity(query_vector, embedding)
            lexical_score = self._lexical_overlap(query_tokens, self._tokenize(f"{row['title']} {row['content']}"))
            score = dense_score * 0.85 + lexical_score * 0.15
            hits.append(
                {
                    "document_id": row["document_id"],
                    "document_kind": row["document_kind"],
                    "knowledge_id": int(row["knowledge_id"]) if row["knowledge_id"] is not None else None,
                    "chunk_id": int(row["chunk_id"]) if row["chunk_id"] is not None else None,
                    "kb_id": int(row["kb_id"]),
                    "title": row["title"],
                    "document_name": row["document_name"],
                    "snippet": self._build_snippet(query_tokens, row["content"]),
                    "content": row["content"],
                    "score": round(score, 6),
                    "metadata": json.loads(row["metadata_json"] or "{}"),
                }
            )
        return sorted(hits, key=lambda item: item["score"], reverse=True)[: max(top_k, 1)]

    def rerank(self, query: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        provider = settings.LOCAL_RAG_RERANK_PROVIDER.lower()
        if provider == "upstream" and settings.LOCAL_RAG_RERANK_UPSTREAM_URL:
            upstream_hits = self._rerank_with_upstream(query, documents)
            if upstream_hits:
                return upstream_hits
        if provider == "cross_encoder":
            try:
                return self._rerank_with_cross_encoder(query, documents)
            except Exception:
                if not settings.LOCAL_RAG_ALLOW_DEGRADED_FALLBACK:
                    raise

        normalized_query = " ".join(query.strip().split())
        if not normalized_query or not documents:
            return []

        query_vector = self._embed_texts([normalized_query])[0]
        doc_texts = [
            self._document_text(
                str(document.get("title") or ""),
                str(document.get("content") or document.get("snippet") or ""),
            )
            for document in documents
        ]
        doc_vectors = self._embed_texts(doc_texts)
        query_tokens = self._tokenize(normalized_query)
        reranked: list[dict[str, Any]] = []
        for index, (document, doc_vector) in enumerate(zip(documents, doc_vectors, strict=False)):
            lexical_score = self._lexical_overlap(query_tokens, self._tokenize(doc_texts[index]))
            score = self._cosine_similarity(query_vector, doc_vector) * 0.9 + lexical_score * 0.1
            identifiers = self._extract_document_identifiers(document)
            if identifiers["document_id"] is None and identifiers["knowledge_id"] is None and identifiers["chunk_id"] is None:
                continue
            reranked.append({**identifiers, "score": round(score, 6)})
        return sorted(reranked, key=lambda item: item["score"], reverse=True)

    def _rerank_with_upstream(self, query: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        headers = {"Content-Type": "application/json"}
        if settings.LOCAL_RAG_RERANK_UPSTREAM_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LOCAL_RAG_RERANK_UPSTREAM_API_KEY}"

        payload: dict[str, Any] = {
            "query": query,
            "documents": documents,
        }
        if settings.LOCAL_RAG_RERANK_UPSTREAM_MODEL:
            payload["model"] = settings.LOCAL_RAG_RERANK_UPSTREAM_MODEL

        try:
            with httpx.Client(timeout=settings.LOCAL_RAG_TIMEOUT_SECONDS) as client:
                response = client.post(settings.LOCAL_RAG_RERANK_UPSTREAM_URL, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
        except Exception:
            return []

        records = result.get("data") if isinstance(result, dict) else result
        if not isinstance(records, list):
            return []

        normalized: list[dict[str, Any]] = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                continue
            identifiers = self._extract_document_identifiers(record)
            if identifiers["document_id"] is None and identifiers["knowledge_id"] is None and identifiers["chunk_id"] is None:
                result_index = record.get("index")
                if isinstance(result_index, int) and 0 <= result_index < len(documents):
                    identifiers = self._extract_document_identifiers(documents[result_index])
            if identifiers["document_id"] is None and identifiers["knowledge_id"] is None and identifiers["chunk_id"] is None:
                continue
            raw_score = record.get("score")
            if raw_score is None:
                raw_score = record.get("relevance_score")
            if raw_score is None:
                raw_score = record.get("similarity")
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                continue
            normalized.append({**identifiers, "score": round(score, 6)})
        return sorted(normalized, key=lambda item: item["score"], reverse=True)

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        provider = settings.LOCAL_RAG_EMBEDDING_PROVIDER.lower()
        if provider == "hash":
            return [self._hash_embedding(text) for text in texts]
        if provider == "sentence_transformers":
            try:
                return self._embed_with_sentence_transformers(texts)
            except Exception:
                if not settings.LOCAL_RAG_ALLOW_DEGRADED_FALLBACK:
                    raise
                return [self._hash_embedding(text) for text in texts]
        if provider == "openai_compat":
            return self._embed_with_openai_compatible(texts)
        raise RuntimeError(f"unsupported_local_rag_embedding_provider: {provider}")

    def _embed_with_sentence_transformers(self, texts: list[str]) -> list[list[float]]:
        model = self._load_sentence_transformer_model()
        try:
            embeddings = model.encode(
                texts,
                batch_size=max(int(settings.LOCAL_RAG_EMBEDDING_BATCH_SIZE or 16), 1),
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        except TypeError:
            embeddings = model.encode(
                texts,
                batch_size=max(int(settings.LOCAL_RAG_EMBEDDING_BATCH_SIZE or 16), 1),
                convert_to_numpy=True,
                show_progress_bar=False,
            )
        return [self._normalize_vector([float(value) for value in vector]) for vector in embeddings]

    def _embed_with_openai_compatible(self, texts: list[str]) -> list[list[float]]:
        if not settings.LOCAL_RAG_EMBEDDING_URL:
            raise RuntimeError("LOCAL_RAG_EMBEDDING_URL is required when LOCAL_RAG_EMBEDDING_PROVIDER=openai_compat")

        payload: dict[str, Any] = {"input": texts}
        if settings.LOCAL_RAG_EMBEDDING_MODEL:
            payload["model"] = settings.LOCAL_RAG_EMBEDDING_MODEL

        headers = {"Content-Type": "application/json"}
        if settings.LOCAL_RAG_EMBEDDING_API_KEY:
            headers["Authorization"] = f"Bearer {settings.LOCAL_RAG_EMBEDDING_API_KEY}"

        with httpx.Client(timeout=settings.LOCAL_RAG_TIMEOUT_SECONDS) as client:
            response = client.post(settings.LOCAL_RAG_EMBEDDING_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
        return self._parse_embedding_payload(result)

    def _parse_embedding_payload(self, payload: Any) -> list[list[float]]:
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                vectors = []
                for item in payload["data"]:
                    if isinstance(item, dict) and isinstance(item.get("embedding"), list):
                        vectors.append([float(value) for value in item["embedding"]])
                if vectors:
                    return [self._normalize_vector(vector) for vector in vectors]
            if isinstance(payload.get("embeddings"), list):
                return [self._normalize_vector([float(value) for value in vector]) for vector in payload["embeddings"]]
        if isinstance(payload, list):
            return [self._normalize_vector([float(value) for value in vector]) for vector in payload if isinstance(vector, list)]
        raise RuntimeError("invalid_embedding_response")

    def _rerank_with_cross_encoder(self, query: str, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized_query = " ".join(query.strip().split())
        if not normalized_query or not documents:
            return []

        model = self._load_cross_encoder_model()
        pairs: list[list[str]] = []
        identifier_list: list[dict[str, Any]] = []
        for document in documents:
            identifiers = self._extract_document_identifiers(document)
            if identifiers["document_id"] is None and identifiers["knowledge_id"] is None and identifiers["chunk_id"] is None:
                continue
            text = self._document_text(
                str(document.get("title") or ""),
                str(document.get("content") or document.get("snippet") or ""),
            )
            pairs.append([normalized_query, text])
            identifier_list.append(identifiers)

        if not pairs:
            return []

        scores = model.predict(
            pairs,
            batch_size=max(int(settings.LOCAL_RAG_RERANK_BATCH_SIZE or 8), 1),
            show_progress_bar=False,
        )
        reranked = [
            {**identifiers, "score": round(float(score), 6)}
            for identifiers, score in zip(identifier_list, scores, strict=False)
        ]
        return sorted(reranked, key=lambda item: item["score"], reverse=True)

    def _list_documents(
        self,
        project_id: int,
        kb_ids: list[int] | None,
        document_kind: str | None = None,
    ) -> list[sqlite3.Row]:
        clauses = ["project_id = ?"]
        params: list[Any] = [project_id]
        normalized_kb_ids = sorted({kb_id for kb_id in (kb_ids or []) if isinstance(kb_id, int)})
        if normalized_kb_ids:
            placeholders = ",".join("?" for _ in normalized_kb_ids)
            clauses.append(f"kb_id IN ({placeholders})")
            params.extend(normalized_kb_ids)
        normalized_kind = (document_kind or "").strip()
        if normalized_kind:
            clauses.append("document_kind = ?")
            params.append(normalized_kind)
        where_clause = " AND ".join(clauses)
        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                SELECT document_id, document_kind, knowledge_id, chunk_id,
                       project_id, kb_id, title, content, document_name,
                       source_type, metadata_json, embedding_json, updated_at
                FROM vector_documents
                WHERE {where_clause}
                """,
                params,
            )
            return list(cursor.fetchall())

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            columns = {
                row["name"]: row
                for row in conn.execute("PRAGMA table_info(vector_documents)").fetchall()
            }
            if columns and "document_id" not in columns:
                conn.execute("ALTER TABLE vector_documents RENAME TO vector_documents_legacy")
                self._create_vector_documents_table(conn)
                conn.execute(
                    """
                    INSERT INTO vector_documents (
                        document_id, document_kind, knowledge_id, chunk_id, project_id, kb_id,
                        title, content, document_name, source_type, metadata_json, embedding_json, updated_at
                    )
                    SELECT
                        'knowledge:' || CAST(knowledge_id AS TEXT),
                        ?,
                        knowledge_id,
                        NULL,
                        project_id,
                        kb_id,
                        title,
                        content,
                        document_name,
                        source_type,
                        metadata_json,
                        embedding_json,
                        updated_at
                    FROM vector_documents_legacy
                    """,
                    (self.KNOWLEDGE_DOCUMENT_KIND,),
                )
                conn.execute("DROP TABLE vector_documents_legacy")
            else:
                self._create_vector_documents_table(conn)
                existing_columns = {
                    row["name"]
                    for row in conn.execute("PRAGMA table_info(vector_documents)").fetchall()
                }
                if "document_kind" not in existing_columns:
                    conn.execute(
                        "ALTER TABLE vector_documents ADD COLUMN document_kind TEXT NOT NULL DEFAULT 'knowledge_item'"
                    )
                if "document_id" not in existing_columns:
                    conn.execute("ALTER TABLE vector_documents ADD COLUMN document_id TEXT")
                    conn.execute(
                        """
                        UPDATE vector_documents
                        SET document_id = 'knowledge:' || CAST(knowledge_id AS TEXT)
                        WHERE document_id IS NULL AND knowledge_id IS NOT NULL
                        """
                    )
                if "chunk_id" not in existing_columns:
                    conn.execute("ALTER TABLE vector_documents ADD COLUMN chunk_id INTEGER")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_vector_documents_document_id
                ON vector_documents(document_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vector_documents_project_kb
                ON vector_documents(project_id, kb_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_vector_documents_project_kb_kind
                ON vector_documents(project_id, kb_id, document_kind)
                """
            )

    def _create_vector_documents_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vector_documents (
                document_id TEXT PRIMARY KEY,
                document_kind TEXT NOT NULL DEFAULT 'knowledge_item',
                knowledge_id INTEGER,
                chunk_id INTEGER,
                project_id INTEGER NOT NULL,
                kb_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                document_name TEXT,
                source_type TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                embedding_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

    @contextmanager
    def _connect(self) -> Any:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _resolve_path(self, raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        if path.is_absolute():
            return path
        return self.project_root / path

    def _resolve_optional_path(self, raw_path: str | None) -> str | None:
        if not raw_path:
            return None
        path = Path(raw_path).expanduser()
        if not path.is_absolute():
            path = self.project_root / path
        snapshots_dir = path / "snapshots"
        if snapshots_dir.exists() and snapshots_dir.is_dir():
            snapshot_candidates = sorted(candidate for candidate in snapshots_dir.iterdir() if candidate.is_dir())
            if snapshot_candidates:
                return str(snapshot_candidates[-1])
        if path.exists():
            return str(path)
        return raw_path

    def _load_sentence_transformer_model(self) -> Any:
        if self._embedding_model is not None:
            return self._embedding_model
        self._prepare_torch_runtime()
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError("缺少 sentence-transformers 依赖，请先执行 pip install -r requirements-local-rag.txt") from exc

        model_name_or_path = self._resolve_optional_path(settings.LOCAL_RAG_EMBEDDING_MODEL_PATH) or settings.LOCAL_RAG_EMBEDDING_MODEL
        if not model_name_or_path:
            raise RuntimeError("LOCAL_RAG_EMBEDDING_MODEL_PATH 或 LOCAL_RAG_EMBEDDING_MODEL 至少需要配置一个")
        self._embedding_model = SentenceTransformer(
            model_name_or_path,
            device=self._resolve_torch_device(settings.LOCAL_RAG_EMBEDDING_DEVICE),
        )
        return self._embedding_model

    def _load_cross_encoder_model(self) -> Any:
        if self._rerank_model is not None:
            return self._rerank_model
        self._prepare_torch_runtime()
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:
            raise RuntimeError("缺少 sentence-transformers 依赖，请先执行 pip install -r requirements-local-rag.txt") from exc

        model_name_or_path = self._resolve_optional_path(settings.LOCAL_RAG_RERANK_MODEL_PATH) or settings.LOCAL_RAG_RERANK_MODEL
        if not model_name_or_path:
            raise RuntimeError("LOCAL_RAG_RERANK_MODEL_PATH 或 LOCAL_RAG_RERANK_MODEL 至少需要配置一个")
        self._rerank_model = CrossEncoder(
            model_name_or_path,
            device=self._resolve_torch_device(settings.LOCAL_RAG_RERANK_DEVICE),
        )
        return self._rerank_model

    def _prepare_torch_runtime(self) -> None:
        if self._torch_ready:
            return
        threads = max(int(settings.LOCAL_RAG_TORCH_NUM_THREADS or 1), 1)
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("缺少 torch 依赖，请先执行 pip install -r requirements-local-rag.txt") from exc
        torch.set_num_threads(threads)
        self._torch_ready = True

    def _resolve_torch_device(self, raw_device: str | None) -> str:
        requested = (raw_device or "auto").lower()
        if requested != "auto":
            return requested
        try:
            import torch
        except ImportError:
            return "cpu"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
        return "cpu"

    def _hash_embedding(self, text: str) -> list[float]:
        dimension = max(int(settings.LOCAL_RAG_EMBEDDING_DIMENSION or 64), 8)
        vector = [0.0] * dimension
        tokens = self._tokenize(text) or ["__empty__"]
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:2], "big") % dimension
            sign = 1.0 if digest[2] % 2 == 0 else -1.0
            weight = 1.0 + (digest[3] / 255.0)
            vector[slot] += sign * weight
        return self._normalize_vector(vector)

    def _normalize_vector(self, vector: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 1e-12:
            normalized = [0.0 for _ in vector]
            if normalized:
                normalized[0] = 1.0
            return normalized
        return [value / norm for value in vector]

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        size = min(len(left), len(right))
        if size == 0:
            return 0.0
        return sum(left[index] * right[index] for index in range(size))

    def _lexical_overlap(self, query_tokens: set[str], doc_tokens: set[str]) -> float:
        if not query_tokens or not doc_tokens:
            return 0.0
        return len(query_tokens & doc_tokens) / max(len(query_tokens), 1)

    def _tokenize(self, text: str) -> set[str]:
        latin_tokens = re.findall(r"[a-z0-9]{2,}", text.lower())
        han_tokens = re.findall(r"[\u4e00-\u9fff]{1,4}", text)
        return {token for token in [*latin_tokens, *han_tokens] if token}

    def _build_snippet(self, query_tokens: set[str], content: str) -> str:
        normalized = " ".join(content.split())
        if len(normalized) <= 220:
            return normalized
        best_index = 0
        if query_tokens:
            lowered = normalized.lower()
            for token in query_tokens:
                position = lowered.find(token.lower())
                if position >= 0:
                    best_index = max(position - 60, 0)
                    break
        return normalized[best_index : best_index + 220]

    def _document_text(self, title: str, content: str) -> str:
        if title and content:
            return f"{title}\n\n{content}"
        return title or content or ""

    def _normalize_document(self, document: LocalVectorDocument) -> LocalVectorDocument:
        document_id = self._normalize_document_id(document.document_id)
        knowledge_id = document.knowledge_id if isinstance(document.knowledge_id, int) else None
        chunk_id = document.chunk_id if isinstance(document.chunk_id, int) else None
        if document_id is None and knowledge_id is not None:
            document_id = self._legacy_document_id(knowledge_id)
        if document_id is None and chunk_id is not None:
            document_id = f"chunk:{chunk_id}"
        if document_id is None:
            raise RuntimeError("document_id_or_knowledge_id_required")
        document_kind = (document.document_kind or self.KNOWLEDGE_DOCUMENT_KIND).strip() or self.KNOWLEDGE_DOCUMENT_KIND
        return LocalVectorDocument(
            document_id=document_id,
            document_kind=document_kind,
            knowledge_id=knowledge_id,
            chunk_id=chunk_id,
            project_id=document.project_id,
            kb_id=document.kb_id,
            title=document.title,
            content=document.content,
            document_name=document.document_name,
            source_type=document.source_type,
            metadata=document.metadata,
        )

    def _extract_document_identifiers(self, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = self._normalize_document_id(payload.get("document_id"))
        knowledge_id = payload.get("knowledge_id")
        if not isinstance(knowledge_id, int):
            knowledge_id = None
        chunk_id = payload.get("chunk_id")
        if not isinstance(chunk_id, int):
            chunk_id = None
        if document_id is None and knowledge_id is not None:
            document_id = self._legacy_document_id(knowledge_id)
        return {
            "document_id": document_id,
            "knowledge_id": knowledge_id,
            "chunk_id": chunk_id,
        }

    def _normalize_document_id(self, value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        normalized = value.strip()
        return normalized or None

    def _legacy_document_id(self, knowledge_id: int) -> str:
        return f"knowledge:{knowledge_id}"
