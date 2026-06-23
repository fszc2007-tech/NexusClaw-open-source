from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.text_locale import to_traditional_data
from app.models.file import FileRecord, FileTask
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDedupRecord, KnowledgeGovernanceTask, KnowledgeItem
from app.services.chunk_sync_service import ChunkSyncService
from app.services.conflict_service import ConflictService
from app.services.dedup_service import DedupService
from app.services.freshness_service import FreshnessService
from app.services.search_sync_service import SearchSyncService


class KnowledgeService:
    def __init__(self, db: Session):
        self.db = db
        self.dedup_service = DedupService(db)
        self.conflict_service = ConflictService(db)
        self.freshness_service = FreshnessService(db)
        self.search_sync_service = SearchSyncService()
        self.chunk_sync_service = ChunkSyncService(db)

    def list_bases(self, project_id: int) -> list[dict]:
        items = (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.project_id == project_id)
            .order_by(KnowledgeBase.is_default.desc(), KnowledgeBase.id.asc())
            .all()
        )
        return [self._serialize_base(item) for item in items]

    def create_base(self, project_id: int, payload: dict) -> dict:
        payload = to_traditional_data(payload)
        if payload.get("is_default"):
            self._clear_project_default_base(project_id)
        item = KnowledgeBase(
            project_id=project_id,
            name=payload["name"],
            description=payload.get("description"),
            is_default=payload.get("is_default", False),
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_base(item)

    def update_base(self, project_id: int, kb_id: int, payload: dict) -> dict | None:
        payload = to_traditional_data(payload)
        item = (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.project_id == project_id, KnowledgeBase.id == kb_id)
            .first()
        )
        if not item:
            return None

        if payload.get("is_default"):
            self._clear_project_default_base(project_id, exclude_kb_id=kb_id)

        item.name = payload.get("name", item.name)
        item.description = payload.get("description", item.description)
        item.is_default = payload.get("is_default", item.is_default)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_base(item)

    def delete_base(self, project_id: int, kb_id: int) -> dict | None:
        item = (
            self.db.query(KnowledgeBase)
            .filter(KnowledgeBase.project_id == project_id, KnowledgeBase.id == kb_id)
            .first()
        )
        if not item:
            return None

        knowledge_items = (
            self.db.query(KnowledgeItem)
            .filter(KnowledgeItem.project_id == project_id, KnowledgeItem.kb_id == kb_id)
            .all()
        )
        for knowledge_item in knowledge_items:
            self.search_sync_service.delete_knowledge(knowledge_item.id)
            self.search_sync_service.delete_chunks(self._list_chunks_by_source_item(knowledge_item.id))
            self.chunk_sync_service.delete_by_source_item(knowledge_item.id)
            self.db.delete(knowledge_item)

        file_tasks = (
            self.db.query(FileTask)
            .filter(FileTask.project_id == project_id, FileTask.kb_id == kb_id)
            .all()
        )
        for task in file_tasks:
            self.db.delete(task)

        files = (
            self.db.query(FileRecord)
            .filter(FileRecord.project_id == project_id, FileRecord.kb_id == kb_id)
            .all()
        )
        for file_item in files:
            self.db.delete(file_item)

        self.chunk_sync_service.delete_by_kb(project_id, kb_id)

        serialized = self._serialize_base(item)
        self.db.delete(item)
        self.db.commit()
        return serialized

    def list_items(self, project_id: int, kb_id: int, status: str | None = None) -> list[dict]:
        query = self.db.query(KnowledgeItem).filter(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.kb_id == kb_id,
        )
        if status:
            query = query.filter(KnowledgeItem.status == status)
        items = query.order_by(KnowledgeItem.id.desc()).all()
        return [self._serialize_item(item) for item in items]

    def dashboard(self, project_id: int, kb_id: int) -> dict:
        status_counts = (
            self.db.query(KnowledgeItem.status, func.count(KnowledgeItem.id))
            .filter(KnowledgeItem.project_id == project_id, KnowledgeItem.kb_id == kb_id)
            .group_by(KnowledgeItem.status)
            .all()
        )
        result = {
            "all": 0,
            "editing": 0,
            "publishing": 0,
            "active": 0,
            "publish_failed": 0,
            "offline": 0,
            "offline_failed": 0,
        }
        for status, count in status_counts:
            result["all"] += count
            result[status] = count
        return result

    def get_item(self, project_id: int, kb_id: int, knowledge_id: int) -> dict | None:
        item = (
            self.db.query(KnowledgeItem)
            .filter(
                KnowledgeItem.project_id == project_id,
                KnowledgeItem.kb_id == kb_id,
                KnowledgeItem.id == knowledge_id,
            )
            .first()
        )
        return self._serialize_item(item) if item else None

    def create_item(self, project_id: int, kb_id: int, payload: dict, acting_user_id: int | None = None) -> dict:
        payload = self._normalize_item_payload(payload)
        dedup_result = None
        if payload.get("check_duplicate", True):
            dedup_result = self.dedup_service.check(
                project_id=project_id,
                title=payload["title"],
                keywords=payload.get("keywords", []),
                content=payload["content"],
            )

        item = KnowledgeItem(
            project_id=project_id,
            kb_id=kb_id,
            document_name=payload.get("document_name"),
            title=payload["title"],
            content=payload["content"],
            keywords_json=payload.get("keywords", []),
            source_type=payload.get("source_type", "manual"),
            source_file_id=payload.get("source_file_id"),
            source_url=payload.get("source_url"),
            source_org=payload.get("source_org"),
            owner_user_id=payload.get("owner_user_id") or acting_user_id,
            status=payload.get("status", "editing"),
            review_due_at=self._parse_datetime(payload.get("review_due_at")),
            review_sla_days=max(int(payload.get("review_sla_days") or self.freshness_service.DEFAULT_REVIEW_WINDOW_DAYS), 1),
            version_no=1,
        )
        if item.status == "active":
            item.published_at = datetime.utcnow()
            if item.review_due_at is None:
                item.review_due_at = datetime.utcnow() + timedelta(days=item.review_sla_days)

        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        self.dedup_service.sync_item_records(item)
        self.freshness_service.refresh_item_metadata(item)
        self.conflict_service.sync_item_task(item)
        self.db.commit()
        self.db.refresh(item)
        self.search_sync_service.upsert_knowledge(item)
        if item.source_type == "manual":
            self.search_sync_service.delete_chunks(self._list_chunks_by_source_item(item.id))
            chunks = self.chunk_sync_service.sync_manual_item(item)
            self.search_sync_service.upsert_chunks(chunks)
            self.db.commit()
        result = self._serialize_item(item)
        result["duplicate_check"] = dedup_result
        return result

    def update_item(
        self,
        project_id: int,
        kb_id: int,
        knowledge_id: int,
        payload: dict,
        acting_user_id: int | None = None,
    ) -> dict | None:
        payload = self._normalize_item_payload(payload)
        item = (
            self.db.query(KnowledgeItem)
            .filter(
                KnowledgeItem.project_id == project_id,
                KnowledgeItem.kb_id == kb_id,
                KnowledgeItem.id == knowledge_id,
            )
            .first()
        )
        if not item:
            return None

        item.document_name = payload.get("document_name", item.document_name)
        item.title = payload.get("title", item.title)
        item.content = payload.get("content", item.content)
        item.keywords_json = payload.get("keywords", item.keywords_json)
        next_source_url = payload.get("source_url", item.source_url)
        if next_source_url != item.source_url:
            item.source_snapshot_hash = None
            item.source_snapshot_preview = None
            item.source_last_checked_at = None
        item.source_url = next_source_url
        item.source_org = payload.get("source_org", item.source_org)
        if payload.get("owner_user_id") is not None:
            item.owner_user_id = payload.get("owner_user_id")
        else:
            item.owner_user_id = item.owner_user_id or acting_user_id
        item.status = payload.get("status", item.status)
        item.review_due_at = self._parse_datetime(payload.get("review_due_at"), fallback=item.review_due_at)
        if payload.get("review_sla_days") is not None:
            item.review_sla_days = max(int(payload.get("review_sla_days") or self.freshness_service.DEFAULT_REVIEW_WINDOW_DAYS), 1)
        item.version_no = (item.version_no or 1) + 1
        if item.status == "active":
            item.published_at = datetime.utcnow()
            if item.review_due_at is None:
                item.review_due_at = datetime.utcnow() + timedelta(days=item.review_sla_days or self.freshness_service.DEFAULT_REVIEW_WINDOW_DAYS)
        self.dedup_service.sync_item_records(item)
        self.freshness_service.refresh_item_metadata(item)
        self.conflict_service.sync_item_task(item)
        self.db.commit()
        self.db.refresh(item)
        self.search_sync_service.upsert_knowledge(item)
        if item.source_type == "manual":
            self.search_sync_service.delete_chunks(self._list_chunks_by_source_item(item.id))
            chunks = self.chunk_sync_service.sync_manual_item(item)
            self.search_sync_service.upsert_chunks(chunks)
            self.db.commit()
        return self._serialize_item(item)

    def publish_item(self, project_id: int, kb_id: int, knowledge_id: int, acting_user_id: int | None = None) -> dict | None:
        item = (
            self.db.query(KnowledgeItem)
            .filter(
                KnowledgeItem.project_id == project_id,
                KnowledgeItem.kb_id == kb_id,
                KnowledgeItem.id == knowledge_id,
            )
            .first()
        )
        if not item:
            return None
        item.status = "active"
        item.published_at = datetime.utcnow()
        item.owner_user_id = item.owner_user_id or acting_user_id
        if item.review_due_at is None:
            item.review_due_at = datetime.utcnow() + timedelta(days=item.review_sla_days or self.freshness_service.DEFAULT_REVIEW_WINDOW_DAYS)
        self.dedup_service.sync_item_records(item)
        self.freshness_service.refresh_item_metadata(item)
        self.conflict_service.sync_item_task(item)
        self.db.commit()
        self.db.refresh(item)
        self.search_sync_service.upsert_knowledge(item)
        if item.source_type == "manual":
            self.search_sync_service.delete_chunks(self._list_chunks_by_source_item(item.id))
            chunks = self.chunk_sync_service.sync_manual_item(item)
            self.search_sync_service.upsert_chunks(chunks)
            self.db.commit()
        return self._serialize_item(item)

    def delete_item(self, project_id: int, kb_id: int, knowledge_id: int) -> dict | None:
        item = (
            self.db.query(KnowledgeItem)
            .filter(
                KnowledgeItem.project_id == project_id,
                KnowledgeItem.kb_id == kb_id,
                KnowledgeItem.id == knowledge_id,
            )
            .first()
        )
        if not item:
            return None

        serialized = self._serialize_item(item)
        (
            self.db.query(KnowledgeDedupRecord)
            .filter(
                (KnowledgeDedupRecord.new_knowledge_id == item.id) | (KnowledgeDedupRecord.old_knowledge_id == item.id)
            )
            .delete(synchronize_session=False)
        )
        (
            self.db.query(KnowledgeGovernanceTask)
            .filter(KnowledgeGovernanceTask.knowledge_id == item.id)
            .delete(synchronize_session=False)
        )
        self.search_sync_service.delete_knowledge(item.id)
        self.search_sync_service.delete_chunks(self._list_chunks_by_source_item(item.id))
        self.chunk_sync_service.delete_by_source_item(item.id)
        self.db.delete(item)
        self.db.commit()
        return serialized

    def active_items_for_chat(self, project_id: int, selected_kb_ids: list[int] | None = None) -> list[KnowledgeItem]:
        query = self.db.query(KnowledgeItem).filter(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.status == "active",
            KnowledgeItem.governance_status == "active",
        )
        if selected_kb_ids:
            query = query.filter(KnowledgeItem.kb_id.in_(selected_kb_ids))
        return query.order_by(KnowledgeItem.updated_at.desc()).all()

    def _serialize_base(self, item: KnowledgeBase | None) -> dict | None:
        if not item:
            return None
        return {
            "id": item.id,
            "project_id": item.project_id,
            "name": item.name,
            "description": item.description,
            "is_default": item.is_default,
        }

    def _serialize_item(self, item: KnowledgeItem | None) -> dict | None:
        if not item:
            return None
        return {
            "id": item.id,
            "project_id": item.project_id,
            "kb_id": item.kb_id,
            "document_name": item.document_name,
            "title": item.title,
            "content": item.content,
            "keywords": item.keywords_json or [],
            "source_type": item.source_type,
            "source_file_id": item.source_file_id,
            "source_meta": item.source_meta_json or {},
            "source_url": item.source_url,
            "source_org": item.source_org,
            "owner_user_id": item.owner_user_id,
            "status": item.status,
            "governance_status": item.governance_status,
            "normalized_content_hash": item.normalized_content_hash,
            "duplicate_of_knowledge_id": item.duplicate_of_knowledge_id,
            "superseded_by_knowledge_id": item.superseded_by_knowledge_id,
            "last_verified_at": item.last_verified_at.isoformat() if item.last_verified_at else None,
            "review_due_at": item.review_due_at.isoformat() if item.review_due_at else None,
            "review_sla_days": item.review_sla_days,
            "source_snapshot_preview": item.source_snapshot_preview,
            "source_last_checked_at": item.source_last_checked_at.isoformat() if item.source_last_checked_at else None,
            "version_no": item.version_no,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    def _list_chunks_by_source_item(self, source_item_id: int) -> list[KnowledgeChunk]:
        return (
            self.db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.source_item_id == source_item_id)
            .order_by(KnowledgeChunk.id.asc())
            .all()
        )

    def _clear_project_default_base(self, project_id: int, exclude_kb_id: int | None = None) -> None:
        query = self.db.query(KnowledgeBase).filter(KnowledgeBase.project_id == project_id, KnowledgeBase.is_default.is_(True))
        if exclude_kb_id is not None:
            query = query.filter(KnowledgeBase.id != exclude_kb_id)

        for item in query.all():
            item.is_default = False

    def _normalize_item_payload(self, payload: dict) -> dict:
        normalized = dict(payload)
        normalized["document_name"] = to_traditional_data(normalized.get("document_name"))
        normalized["title"] = to_traditional_data(normalized.get("title"))
        normalized["content"] = to_traditional_data(normalized.get("content"))
        normalized["keywords"] = to_traditional_data(normalized.get("keywords", []))
        normalized["source_meta_json"] = to_traditional_data(normalized.get("source_meta_json", {}))
        normalized["source_url"] = to_traditional_data(normalized.get("source_url"))
        normalized["source_org"] = to_traditional_data(normalized.get("source_org"))
        return normalized

    def _parse_datetime(self, value: str | None, fallback: datetime | None = None) -> datetime | None:
        if value is None:
            return fallback
        normalized = str(value).strip()
        if not normalized:
            return None
        normalized = normalized.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return fallback
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
