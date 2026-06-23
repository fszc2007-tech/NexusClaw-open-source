from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.knowledge import ChunkRelation, KnowledgeChunk, KnowledgeItem


class ChunkSyncService:
    BUSINESS_ROUTE_KINDS = {"address_change", "ir1249", "irc3111a", "hk_tax_address_change"}

    def __init__(self, db: Session):
        self.db = db

    def sync_item(self, item: KnowledgeItem) -> list[KnowledgeChunk]:
        self.delete_by_source_item(item.id)
        if item.status != "active":
            return []
        chunk_model = self._build_item_chunk_model(item)
        self.db.add(chunk_model)
        self.db.flush()
        return [chunk_model]

    def delete_by_file(self, project_id: int, kb_id: int, file_id: int, source_kind: str | None = None) -> int:
        query = self.db.query(KnowledgeChunk).filter(
            KnowledgeChunk.project_id == project_id,
            KnowledgeChunk.kb_id == kb_id,
            KnowledgeChunk.file_id == file_id,
        )
        if source_kind is not None:
            query = query.filter(KnowledgeChunk.source_kind == source_kind)
        chunk_ids = [item.id for item in query.all()]
        self._delete_relations(chunk_ids)
        deleted = query.delete(synchronize_session=False)
        return int(deleted or 0)

    def delete_by_source_item(self, source_item_id: int) -> int:
        chunks = self.db.query(KnowledgeChunk).filter(KnowledgeChunk.source_item_id == source_item_id).all()
        chunk_ids = [item.id for item in chunks]
        self._delete_relations(chunk_ids)
        (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.source_item_id == source_item_id)
            .delete(synchronize_session=False)
        )
        return len(chunk_ids)

    def delete_by_kb(self, project_id: int, kb_id: int) -> int:
        chunks = (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.project_id == project_id, KnowledgeChunk.kb_id == kb_id)
            .all()
        )
        chunk_ids = [item.id for item in chunks]
        self._delete_relations(chunk_ids)
        (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.project_id == project_id, KnowledgeChunk.kb_id == kb_id)
            .delete(synchronize_session=False)
        )
        return len(chunk_ids)

    def rebuild_file_chunks(
        self,
        project_id: int,
        kb_id: int,
        file_id: int,
        document_name: str,
        chunks: list[dict[str, Any]],
        source_items: list[KnowledgeItem],
        source_kind: str = "file",
    ) -> list[KnowledgeChunk]:
        self.delete_by_file(project_id, kb_id, file_id, source_kind=source_kind)
        chunk_models = self._build_file_chunk_models(
            project_id=project_id,
            kb_id=kb_id,
            file_id=file_id,
            document_name=document_name,
            chunks=chunks,
            source_items=source_items,
            source_kind=source_kind,
        )
        self.db.add_all(chunk_models)
        self.db.flush()
        self._create_relations_for_chunks(chunk_models)
        return chunk_models

    def sync_manual_item(self, item: KnowledgeItem) -> list[KnowledgeChunk]:
        return self.sync_item(item)

    def _delete_relations(self, chunk_ids: list[int]) -> None:
        if not chunk_ids:
            return
        (
            self.db.query(ChunkRelation)
            .filter((ChunkRelation.from_chunk_id.in_(chunk_ids)) | (ChunkRelation.to_chunk_id.in_(chunk_ids)))
            .delete(synchronize_session=False)
        )

    def _create_relations_for_chunks(self, chunks: list[KnowledgeChunk]) -> None:
        if not chunks:
            return
        relations: list[ChunkRelation] = []
        previous: KnowledgeChunk | None = None
        for chunk in chunks:
            if previous is not None:
                relations.append(
                    ChunkRelation(from_chunk_id=previous.id, to_chunk_id=chunk.id, relation_type="next")
                )
                relations.append(
                    ChunkRelation(from_chunk_id=chunk.id, to_chunk_id=previous.id, relation_type="prev")
                )
                previous_section = tuple((previous.chunk_meta_json or {}).get("heading_path") or [])
                current_section = tuple((chunk.chunk_meta_json or {}).get("heading_path") or [])
                if previous_section and previous_section == current_section:
                    relations.append(
                        ChunkRelation(
                            from_chunk_id=previous.id,
                            to_chunk_id=chunk.id,
                            relation_type="same_section",
                        )
                    )
                    relations.append(
                        ChunkRelation(
                            from_chunk_id=chunk.id,
                            to_chunk_id=previous.id,
                            relation_type="same_section",
                        )
                    )
            previous = chunk
        if relations:
            self.db.add_all(relations)

    def _build_file_chunk_models(
        self,
        project_id: int,
        kb_id: int,
        file_id: int,
        document_name: str,
        chunks: list[dict[str, Any]],
        source_items: list[KnowledgeItem],
        source_kind: str,
    ) -> list[KnowledgeChunk]:
        models: list[KnowledgeChunk] = []
        for index, chunk in enumerate(chunks, start=1):
            source_meta = dict(chunk.get("source_meta") or {})
            source_item = source_items[index - 1] if index - 1 < len(source_items) else None
            authority_level, source_rank = self._resolve_source_weights(source_kind)
            models.append(
                KnowledgeChunk(
                    project_id=project_id,
                    kb_id=kb_id,
                    source_kind=source_kind,
                    source_item_id=source_item.id if source_item else None,
                    file_id=file_id,
                    title=str(chunk.get("title") or document_name or f"文檔分塊 {index}"),
                    document_name=document_name,
                    lexical_text=self.build_lexical_text(chunk),
                    contextual_text=self.build_contextual_text(chunk),
                    citation_text=self.build_citation_text(chunk),
                    chunk_index=int(source_meta.get("chunk_index") or index),
                    chunk_meta_json=source_meta,
                    status="active",
                    is_active=True,
                    authority_level=authority_level,
                    source_rank=source_rank,
                    region=self._resolve_region(source_meta),
                    route_kind=self._resolve_route_kind(source_meta),
                    subject_type=self._resolve_subject_type(source_meta),
                )
            )
        return models

    def _build_item_chunk_model(self, item: KnowledgeItem) -> KnowledgeChunk:
        source_meta = dict(item.source_meta_json or {})
        chunk_payload = {
            "title": item.title,
            "content": item.content,
            "source_meta": source_meta,
        }
        authority_level, source_rank = self._resolve_source_weights(item.source_type or "manual")
        return KnowledgeChunk(
            project_id=item.project_id,
            kb_id=item.kb_id,
            source_kind=item.source_type or "manual",
            source_item_id=item.id,
            file_id=item.source_file_id,
            title=item.title,
            document_name=item.document_name,
            lexical_text=self.build_lexical_text(chunk_payload),
            contextual_text=self.build_contextual_text(chunk_payload),
            citation_text=self.build_citation_text(chunk_payload),
            chunk_index=int(source_meta.get("chunk_index") or 1),
            chunk_meta_json=source_meta,
            status="active" if item.status == "active" else item.status,
            is_active=item.status == "active",
            authority_level=authority_level,
            source_rank=source_rank,
            region=self._resolve_region(source_meta),
            route_kind=self._resolve_route_kind(source_meta),
            subject_type=self._resolve_subject_type(source_meta),
        )

    def _resolve_source_weights(self, source_kind: str) -> tuple[int, float]:
        if source_kind == "official_web":
            return 110, 1.05
        if source_kind == "file":
            return 100, 1.0
        if source_kind == "manual":
            return 85, 0.9
        if source_kind == "file_qa":
            return 30, 0.6
        return 50, 0.8

    def _resolve_region(self, source_meta: dict[str, Any]) -> str | None:
        region = source_meta.get("region")
        if isinstance(region, str) and region.strip():
            return region.strip()
        return "HK"

    def _resolve_route_kind(self, source_meta: dict[str, Any]) -> str | None:
        route_kind = source_meta.get("route_kind")
        normalized = str(route_kind).strip().lower() if route_kind else ""
        if normalized in self.BUSINESS_ROUTE_KINDS:
            return normalized
        return None

    def _resolve_subject_type(self, source_meta: dict[str, Any]) -> str | None:
        subject_type = source_meta.get("subject_type")
        if subject_type:
            return str(subject_type).strip()
        heading_path = " ".join(str(item) for item in source_meta.get("heading_path") or [])
        if "公司" in heading_path or "業務" in heading_path:
            return "company"
        if "個人" in heading_path or "通訊地址" in heading_path:
            return "individual"
        return None

    @staticmethod
    def build_lexical_text(chunk: dict[str, Any]) -> str:
        meta = chunk.get("source_meta") or {}
        heading_path = " ".join(meta.get("heading_path") or [])
        section_title = meta.get("section_title") or ""
        sheet_names = " ".join(meta.get("sheet_names") or [])
        route_kind = meta.get("route_kind") or ""
        title = chunk.get("title") or ""
        content = chunk.get("content") or ""
        return "\n".join(
            part
            for part in [title, heading_path, section_title, sheet_names, route_kind, content]
            if part
        )

    @staticmethod
    def build_contextual_text(chunk: dict[str, Any]) -> str:
        meta = chunk.get("source_meta") or {}
        heading_path = " > ".join(meta.get("heading_path") or [])
        pages = meta.get("page_numbers") or []
        rows = meta.get("row_range") or []
        route_kind = meta.get("route_kind") or ""
        chunk_strategy = meta.get("chunk_strategy") or ""
        parts = [
            f"文檔標題：{chunk.get('title') or ''}",
            f"章節：{heading_path}" if heading_path else "",
            f"頁碼：{pages}" if pages else "",
            f"行範圍：{rows}" if rows else "",
            f"路由類型：{route_kind}" if route_kind else "",
            f"切塊策略：{chunk_strategy}" if chunk_strategy else "",
            "",
            "正文：",
            chunk.get("content") or "",
        ]
        return "\n".join(part for part in parts if part is not None)

    @staticmethod
    def build_citation_text(chunk: dict[str, Any], max_chars: int = 800) -> str:
        content = str(chunk.get("content") or "").strip()
        if len(content) <= max_chars:
            return content
        return content[:max_chars]
