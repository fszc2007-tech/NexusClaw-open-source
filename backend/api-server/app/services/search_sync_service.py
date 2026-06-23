from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.models.knowledge import KnowledgeChunk, KnowledgeItem


class SearchSyncService:
    KNOWLEDGE_DOCUMENT_KIND = "knowledge_item"
    CHUNK_DOCUMENT_KIND = "knowledge_chunk"

    def upsert_knowledge(self, item: KnowledgeItem) -> None:
        if item.status != "active":
            self.delete_knowledge(item.id)
            return

        self._upsert_elasticsearch_document(
            document_id=self.build_knowledge_document_id(item.id),
            payload={
                "document_id": self.build_knowledge_document_id(item.id),
                "document_kind": self.KNOWLEDGE_DOCUMENT_KIND,
                "knowledge_id": item.id,
                "project_id": item.project_id,
                "kb_id": item.kb_id,
                "status": item.status,
                "title": item.title,
                "content": item.content,
                "keywords": item.keywords_json or [],
                "document_name": item.document_name,
                "source_type": item.source_type,
                "source_file_id": item.source_file_id,
                "source_meta": item.source_meta_json or {},
            },
        )
        self._upsert_vector_documents(
            [
                {
                    "document_id": self.build_knowledge_document_id(item.id),
                    "document_kind": self.KNOWLEDGE_DOCUMENT_KIND,
                    "knowledge_id": item.id,
                    "project_id": item.project_id,
                    "kb_id": item.kb_id,
                    "title": item.title,
                    "content": item.content,
                    "document_name": item.document_name,
                    "source_type": item.source_type,
                    "metadata": item.source_meta_json or {},
                }
            ]
        )

    def delete_knowledge(self, knowledge_id: int) -> None:
        self._delete_elasticsearch_document(self.build_knowledge_document_id(knowledge_id))
        self._delete_vector_documents(
            document_ids=[self.build_knowledge_document_id(knowledge_id)],
            knowledge_ids=[knowledge_id],
        )

    def upsert_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        active_chunks = [chunk for chunk in chunks if chunk.status == "active" and chunk.is_active]
        if not active_chunks:
            return
        for chunk in active_chunks:
            payload = self._build_chunk_search_payload(chunk)
            self._upsert_elasticsearch_document(
                document_id=payload["document_id"],
                payload=payload,
            )
        self._upsert_vector_documents(
            [
                {
                    "document_id": self.build_chunk_document_id(chunk),
                    "document_kind": self.CHUNK_DOCUMENT_KIND,
                    "knowledge_id": int(chunk.source_item_id) if chunk.source_item_id is not None else None,
                    "chunk_id": int(chunk.id),
                    "project_id": chunk.project_id,
                    "kb_id": chunk.kb_id,
                    "title": chunk.title,
                    "content": chunk.contextual_text,
                    "document_name": chunk.document_name,
                    "source_type": chunk.source_kind,
                    "metadata": self._build_chunk_vector_metadata(chunk),
                }
                for chunk in active_chunks
            ]
        )

    def delete_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        document_ids = [self.build_chunk_document_id(chunk) for chunk in chunks]
        if not document_ids:
            return
        for document_id in document_ids:
            self._delete_elasticsearch_document(document_id)
        self._delete_vector_documents(document_ids=document_ids)

    @classmethod
    def build_knowledge_document_id(cls, knowledge_id: int) -> str:
        return f"knowledge:{knowledge_id}"

    @classmethod
    def build_chunk_document_id(cls, chunk: KnowledgeChunk) -> str:
        if chunk.file_id is not None:
            return f"chunk:file:{chunk.project_id}:{chunk.kb_id}:{chunk.file_id}:{chunk.source_kind}:{chunk.chunk_index}"
        if chunk.source_item_id is not None:
            return f"chunk:item:{chunk.project_id}:{chunk.kb_id}:{chunk.source_item_id}:{chunk.source_kind}:{chunk.chunk_index}"
        return f"chunk:row:{chunk.project_id}:{chunk.kb_id}:{chunk.source_kind}:{chunk.id}"

    def _build_chunk_search_payload(self, chunk: KnowledgeChunk) -> dict[str, Any]:
        return {
            "document_id": self.build_chunk_document_id(chunk),
            "document_kind": self.CHUNK_DOCUMENT_KIND,
            "knowledge_id": int(chunk.source_item_id) if chunk.source_item_id is not None else None,
            "chunk_id": int(chunk.id),
            "project_id": chunk.project_id,
            "kb_id": chunk.kb_id,
            "status": chunk.status,
            "title": chunk.title,
            "content": chunk.contextual_text,
            "citation_text": chunk.citation_text,
            "document_name": chunk.document_name,
            "source_type": chunk.source_kind,
            "source_kind": chunk.source_kind,
            "source_item_id": chunk.source_item_id,
            "source_file_id": chunk.file_id,
            "authority_level": chunk.authority_level,
            "source_rank": chunk.source_rank,
            "chunk_index": chunk.chunk_index,
            "region": chunk.region,
            "route_kind": chunk.route_kind,
            "subject_type": chunk.subject_type,
            "source_meta": chunk.chunk_meta_json or {},
        }

    def _build_chunk_vector_metadata(self, chunk: KnowledgeChunk) -> dict[str, Any]:
        return {
            **(chunk.chunk_meta_json or {}),
            "chunk_id": int(chunk.id),
            "source_item_id": int(chunk.source_item_id) if chunk.source_item_id is not None else None,
            "file_id": int(chunk.file_id) if chunk.file_id is not None else None,
            "source_kind": chunk.source_kind,
            "authority_level": int(chunk.authority_level or 0),
            "source_rank": float(chunk.source_rank or 1.0),
            "region": chunk.region,
            "route_kind": chunk.route_kind,
            "subject_type": chunk.subject_type,
            "chunk_index": int(chunk.chunk_index or 0),
        }

    def _upsert_elasticsearch_document(self, document_id: str, payload: dict[str, Any]) -> None:
        if not settings.ELASTICSEARCH_URL:
            return
        auth = None
        if settings.ELASTICSEARCH_USERNAME and settings.ELASTICSEARCH_PASSWORD:
            auth = (settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD)

        url = (
            f"{settings.ELASTICSEARCH_URL.rstrip('/')}/"
            f"{settings.ELASTICSEARCH_INDEX}/_doc/{document_id}"
        )
        try:
            with httpx.Client(timeout=settings.ELASTICSEARCH_TIMEOUT_SECONDS, auth=auth) as client:
                response = client.put(url, json=payload)
                response.raise_for_status()
        except Exception:  # noqa: BLE001
            return

    def _delete_elasticsearch_document(self, document_id: str) -> None:
        if not settings.ELASTICSEARCH_URL:
            return

        auth = None
        if settings.ELASTICSEARCH_USERNAME and settings.ELASTICSEARCH_PASSWORD:
            auth = (settings.ELASTICSEARCH_USERNAME, settings.ELASTICSEARCH_PASSWORD)

        url = (
            f"{settings.ELASTICSEARCH_URL.rstrip('/')}/"
            f"{settings.ELASTICSEARCH_INDEX}/_doc/{document_id}"
        )
        try:
            with httpx.Client(timeout=settings.ELASTICSEARCH_TIMEOUT_SECONDS, auth=auth) as client:
                client.delete(url)
        except Exception:  # noqa: BLE001
            return

    def _upsert_vector_documents(self, documents: list[dict[str, Any]]) -> None:
        if not settings.VECTOR_UPSERT_URL:
            return
        if not documents:
            return
        payload: dict[str, Any] = {"documents": documents}
        try:
            with httpx.Client(timeout=settings.VECTOR_TIMEOUT_SECONDS) as client:
                response = client.post(settings.VECTOR_UPSERT_URL, json=payload)
                response.raise_for_status()
        except Exception:  # noqa: BLE001
            return

    def _delete_vector_documents(
        self,
        document_ids: list[str] | None = None,
        knowledge_ids: list[int] | None = None,
    ) -> None:
        if not settings.VECTOR_DELETE_URL:
            return
        payload = {
            "document_ids": [document_id for document_id in (document_ids or []) if document_id],
            "knowledge_ids": [knowledge_id for knowledge_id in (knowledge_ids or []) if isinstance(knowledge_id, int)],
        }
        if not payload["document_ids"] and not payload["knowledge_ids"]:
            return
        try:
            with httpx.Client(timeout=settings.VECTOR_TIMEOUT_SECONDS) as client:
                response = client.post(settings.VECTOR_DELETE_URL, json=payload)
                response.raise_for_status()
        except Exception:  # noqa: BLE001
            return
