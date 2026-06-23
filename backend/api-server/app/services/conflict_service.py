from __future__ import annotations

from collections import defaultdict
from datetime import datetime
import re

from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeGovernanceTask, KnowledgeItem


BLOCKED_GOVERNANCE_STATUSES = {"duplicate", "superseded", "archived", "stale", "conflict"}


class ConflictService:
    PREVIEW_LENGTH = 160

    def __init__(self, db: Session):
        self.db = db

    def scan_conflicts(
        self,
        *,
        project_id: int,
        kb_id: int | None = None,
    ) -> dict:
        query = self.db.query(KnowledgeItem).filter(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.status == "active",
            KnowledgeItem.governance_status == "active",
        )
        if kb_id is not None:
            query = query.filter(KnowledgeItem.kb_id == kb_id)

        items = query.order_by(KnowledgeItem.created_at.asc(), KnowledgeItem.id.asc()).all()
        scoped_ids = [item.id for item in items]
        if scoped_ids:
            (
                self.db.query(KnowledgeGovernanceTask)
                .filter(
                    KnowledgeGovernanceTask.task_type == "conflict",
                    KnowledgeGovernanceTask.status == "pending",
                    KnowledgeGovernanceTask.project_id == project_id,
                    KnowledgeGovernanceTask.knowledge_id.in_(scoped_ids),
                )
                .delete(synchronize_session=False)
            )

        groups: dict[str, list[KnowledgeItem]] = defaultdict(list)
        checked_count = 0
        created_count = 0
        for item in items:
            normalized_title = self._normalize_title(item.title)
            if not normalized_title:
                continue
            checked_count += 1
            group = groups[normalized_title]
            counterpart = self._find_latest_counterpart(item, group)
            if counterpart is not None:
                self.db.add(self._build_task(project_id=project_id, item=item, counterpart=counterpart, normalized_title=normalized_title))
                created_count += 1
            group.append(item)

        self.db.commit()
        return {
            "checked_count": checked_count,
            "created_task_count": created_count,
        }

    def sync_item_task(self, item: KnowledgeItem) -> dict | None:
        self._clear_pending_tasks(item.id)
        if item.status != "active" or item.governance_status != "active":
            return None

        normalized_title = self._normalize_title(item.title)
        if not normalized_title:
            return None

        counterpart = self._find_latest_counterpart(
            item,
            self._query_candidate_items(item.project_id).all(),
        )
        if counterpart is None:
            return None

        task = self._build_task(
            project_id=item.project_id,
            item=item,
            counterpart=counterpart,
            normalized_title=normalized_title,
        )
        self.db.add(task)
        return {
            "knowledge_id": item.id,
            "counterpart_knowledge_id": counterpart.id,
            "reason": task.reason,
        }

    def list_conflict_tasks(
        self,
        *,
        project_id: int,
        status: str | None = "pending",
        kb_id: int | None = None,
    ) -> list[dict]:
        query = (
            self.db.query(KnowledgeGovernanceTask, KnowledgeItem)
            .join(KnowledgeItem, KnowledgeItem.id == KnowledgeGovernanceTask.knowledge_id)
            .filter(
                KnowledgeGovernanceTask.project_id == project_id,
                KnowledgeGovernanceTask.task_type == "conflict",
            )
        )
        if status:
            query = query.filter(KnowledgeGovernanceTask.status == status)
        if kb_id is not None:
            query = query.filter(KnowledgeItem.kb_id == kb_id)

        rows = query.order_by(KnowledgeGovernanceTask.created_at.desc(), KnowledgeGovernanceTask.id.desc()).all()
        counterpart_ids = {
            int((task.payload_json or {}).get("counterpart_knowledge_id") or 0)
            for task, _ in rows
            if (task.payload_json or {}).get("counterpart_knowledge_id")
        }
        counterpart_map = {
            item.id: item
            for item in self.db.query(KnowledgeItem).filter(KnowledgeItem.id.in_(counterpart_ids)).all()
        } if counterpart_ids else {}

        return [
            {
                "id": task.id,
                "project_id": task.project_id,
                "knowledge_id": task.knowledge_id,
                "task_type": task.task_type,
                "status": task.status,
                "reason": task.reason,
                "payload": task.payload_json or {},
                "comment": task.comment,
                "reviewed_by": task.reviewed_by,
                "reviewed_at": task.reviewed_at.isoformat() if task.reviewed_at else None,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "knowledge": self._serialize_item(item),
                "counterpart": self._serialize_item(
                    counterpart_map.get(int((task.payload_json or {}).get("counterpart_knowledge_id") or 0))
                ),
            }
            for task, item in rows
        ]

    def resolve_conflict_task(
        self,
        *,
        project_id: int,
        task_id: int,
        action: str,
        reviewer_id: int | None = None,
        comment: str | None = None,
    ) -> dict | None:
        task = (
            self.db.query(KnowledgeGovernanceTask)
            .filter(
                KnowledgeGovernanceTask.project_id == project_id,
                KnowledgeGovernanceTask.task_type == "conflict",
                KnowledgeGovernanceTask.id == task_id,
            )
            .first()
        )
        if not task:
            return None

        data = self._resolve_conflict_task_instance(
            task=task,
            action=action,
            reviewer_id=reviewer_id,
            comment=comment,
        )
        if not data:
            return None
        self.db.commit()
        return data

    def bulk_resolve_conflict_tasks(
        self,
        *,
        project_id: int,
        task_ids: list[int],
        action: str,
        reviewer_id: int | None = None,
        comment: str | None = None,
    ) -> dict:
        resolved_ids: list[int] = []
        for task_id in task_ids:
            task = (
                self.db.query(KnowledgeGovernanceTask)
                .filter(
                    KnowledgeGovernanceTask.project_id == project_id,
                    KnowledgeGovernanceTask.task_type == "conflict",
                    KnowledgeGovernanceTask.id == int(task_id),
                )
                .first()
            )
            if not task:
                continue
            data = self._resolve_conflict_task_instance(
                task=task,
                action=action,
                reviewer_id=reviewer_id,
                comment=comment,
            )
            if data:
                resolved_ids.append(task.id)
        self.db.commit()
        return {
            "action": action,
            "resolved_count": len(resolved_ids),
            "resolved_task_ids": resolved_ids,
        }

    def _resolve_conflict_task_instance(
        self,
        *,
        task: KnowledgeGovernanceTask,
        action: str,
        reviewer_id: int | None = None,
        comment: str | None = None,
    ) -> dict | None:

        item = self.db.query(KnowledgeItem).filter(KnowledgeItem.id == task.knowledge_id).first()
        if not item:
            return None

        now = datetime.utcnow()
        task.status = "resolved"
        task.comment = comment
        task.reviewed_by = reviewer_id
        task.reviewed_at = now

        if action == "mark_conflict":
            item.governance_status = "conflict"
        elif action == "reject":
            item.governance_status = "active"
        else:
            raise ValueError(f"unsupported_action: {action}")

        item.last_verified_at = now
        self._close_other_pending_tasks(item.id)
        return {
            "id": task.id,
            "action": action,
            "knowledge_id": item.id,
            "new_governance_status": item.governance_status,
        }

    def _query_candidate_items(self, project_id: int, kb_id: int | None = None):
        query = self.db.query(KnowledgeItem).filter(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.status == "active",
            KnowledgeItem.governance_status == "active",
        )
        if kb_id is not None:
            query = query.filter(KnowledgeItem.kb_id == kb_id)
        return query.order_by(KnowledgeItem.created_at.asc(), KnowledgeItem.id.asc())

    def _find_latest_counterpart(self, item: KnowledgeItem, candidates: list[KnowledgeItem]) -> KnowledgeItem | None:
        normalized_title = self._normalize_title(item.title)
        if not normalized_title:
            return None
        for candidate in reversed(candidates):
            if candidate.id == item.id:
                continue
            if candidate.project_id != item.project_id:
                continue
            if candidate.status != "active" or candidate.governance_status in BLOCKED_GOVERNANCE_STATUSES:
                continue
            if self._normalize_title(candidate.title) != normalized_title:
                continue
            if candidate.normalized_content_hash and candidate.normalized_content_hash == item.normalized_content_hash:
                continue
            return candidate
        return None

    def _build_task(
        self,
        *,
        project_id: int,
        item: KnowledgeItem,
        counterpart: KnowledgeItem,
        normalized_title: str,
    ) -> KnowledgeGovernanceTask:
        return KnowledgeGovernanceTask(
            project_id=project_id,
            knowledge_id=item.id,
            task_type="conflict",
            status="pending",
            reason="同标题知识内容不一致，需人工确认",
            payload_json={
                "rule": "same_title_different_content",
                "normalized_title": normalized_title,
                "counterpart_knowledge_id": counterpart.id,
                "counterpart_title": counterpart.title,
                "current_preview": self._build_preview(item.content),
                "counterpart_preview": self._build_preview(counterpart.content),
                "current_hash": item.normalized_content_hash,
                "counterpart_hash": counterpart.normalized_content_hash,
            },
        )

    def _clear_pending_tasks(self, knowledge_id: int) -> None:
        (
            self.db.query(KnowledgeGovernanceTask)
            .filter(
                KnowledgeGovernanceTask.knowledge_id == knowledge_id,
                KnowledgeGovernanceTask.task_type == "conflict",
                KnowledgeGovernanceTask.status == "pending",
            )
            .delete(synchronize_session=False)
        )

    def _close_other_pending_tasks(self, knowledge_id: int) -> None:
        for task in (
            self.db.query(KnowledgeGovernanceTask)
            .filter(
                KnowledgeGovernanceTask.knowledge_id == knowledge_id,
                KnowledgeGovernanceTask.task_type == "conflict",
                KnowledgeGovernanceTask.status == "pending",
            )
            .all()
        ):
            task.status = "closed"
            task.reviewed_at = datetime.utcnow()

    def _normalize_title(self, value: str | None) -> str:
        normalized = re.sub(r"\s+", " ", str(value or "")).strip().lower()
        return normalized

    def _build_preview(self, value: str | None) -> str | None:
        normalized = re.sub(r"\s+", " ", str(value or "")).strip()
        if not normalized:
            return None
        return normalized[: self.PREVIEW_LENGTH]

    def _serialize_item(self, item: KnowledgeItem | None) -> dict | None:
        if not item:
            return None
        return {
            "id": item.id,
            "kb_id": item.kb_id,
            "title": item.title,
            "document_name": item.document_name,
            "status": item.status,
            "governance_status": item.governance_status,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
