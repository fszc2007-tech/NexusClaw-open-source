from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import re

import httpx
from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeGovernanceTask, KnowledgeItem


NON_SERVING_GOVERNANCE_STATUSES = {"review_pending", "duplicate", "superseded", "stale", "archived", "conflict"}


class FreshnessService:
    DEFAULT_REVIEW_WINDOW_DAYS = 90
    SOURCE_FETCH_TIMEOUT_SECONDS = 10
    SOURCE_PREVIEW_LENGTH = 280

    def __init__(self, db: Session):
        self.db = db

    def scan_stale_items(
        self,
        *,
        project_id: int,
        kb_id: int | None = None,
        stale_after_days: int | None = None,
    ) -> dict:
        window_days = max(int(stale_after_days or self.DEFAULT_REVIEW_WINDOW_DAYS), 1)
        now = datetime.utcnow()
        threshold = now - timedelta(days=window_days)

        query = self.db.query(KnowledgeItem).filter(
            KnowledgeItem.project_id == project_id,
            KnowledgeItem.status == "active",
        )
        if kb_id is not None:
            query = query.filter(KnowledgeItem.kb_id == kb_id)

        created_count = 0
        checked_count = 0
        changed_count = 0
        for item in query.order_by(KnowledgeItem.updated_at.desc(), KnowledgeItem.id.desc()).all():
            if item.governance_status in NON_SERVING_GOVERNANCE_STATUSES:
                continue
            checked_count += 1
            reason, payload = self._check_source_change(item)
            if reason:
                if not self._has_pending_task(item.id):
                    self.db.add(
                        KnowledgeGovernanceTask(
                            project_id=project_id,
                            knowledge_id=item.id,
                            task_type="stale",
                            status="pending",
                            reason=reason,
                            payload_json=payload,
                        )
                    )
                    created_count += 1
                changed_count += 1
                continue
            reason, payload = self._build_stale_reason(item=item, now=now, threshold=threshold, window_days=window_days)
            if not reason:
                continue
            if self._has_pending_task(item.id):
                continue
            self.db.add(
                KnowledgeGovernanceTask(
                    project_id=project_id,
                    knowledge_id=item.id,
                    task_type="stale",
                    status="pending",
                    reason=reason,
                    payload_json=payload,
                )
            )
            created_count += 1

        self.db.commit()
        return {
            "checked_count": checked_count,
            "created_task_count": created_count,
            "source_change_count": changed_count,
            "stale_after_days": window_days,
        }

    def list_stale_tasks(
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
                KnowledgeGovernanceTask.task_type == "stale",
            )
        )
        if status:
            query = query.filter(KnowledgeGovernanceTask.status == status)
        if kb_id is not None:
            query = query.filter(KnowledgeItem.kb_id == kb_id)

        rows = query.order_by(KnowledgeGovernanceTask.created_at.desc(), KnowledgeGovernanceTask.id.desc()).all()
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
            }
            for task, item in rows
        ]

    def resolve_stale_task(
        self,
        *,
        project_id: int,
        task_id: int,
        action: str,
        reviewer_id: int | None = None,
        comment: str | None = None,
        next_review_days: int | None = None,
    ) -> dict | None:
        task = (
            self.db.query(KnowledgeGovernanceTask)
            .filter(
                KnowledgeGovernanceTask.project_id == project_id,
                KnowledgeGovernanceTask.task_type == "stale",
                KnowledgeGovernanceTask.id == task_id,
            )
            .first()
        )
        if not task:
            return None

        data = self._resolve_stale_task_instance(
            task=task,
            action=action,
            reviewer_id=reviewer_id,
            comment=comment,
            next_review_days=next_review_days,
        )
        if not data:
            return None
        self.db.commit()
        return data

    def bulk_resolve_stale_tasks(
        self,
        *,
        project_id: int,
        task_ids: list[int],
        action: str,
        reviewer_id: int | None = None,
        comment: str | None = None,
        next_review_days: int | None = None,
    ) -> dict:
        resolved_ids: list[int] = []
        for task_id in task_ids:
            task = (
                self.db.query(KnowledgeGovernanceTask)
                .filter(
                    KnowledgeGovernanceTask.project_id == project_id,
                    KnowledgeGovernanceTask.task_type == "stale",
                    KnowledgeGovernanceTask.id == int(task_id),
                )
                .first()
            )
            if not task:
                continue
            data = self._resolve_stale_task_instance(
                task=task,
                action=action,
                reviewer_id=reviewer_id,
                comment=comment,
                next_review_days=next_review_days,
            )
            if data:
                resolved_ids.append(task.id)
        self.db.commit()
        return {
            "action": action,
            "resolved_count": len(resolved_ids),
            "resolved_task_ids": resolved_ids,
        }

    def _resolve_stale_task_instance(
        self,
        *,
        task: KnowledgeGovernanceTask,
        action: str,
        reviewer_id: int | None = None,
        comment: str | None = None,
        next_review_days: int | None = None,
    ) -> dict | None:

        item = self.db.query(KnowledgeItem).filter(KnowledgeItem.id == task.knowledge_id).first()
        if not item:
            return None

        now = datetime.utcnow()
        task.status = "resolved"
        task.comment = comment
        task.reviewed_by = reviewer_id
        task.reviewed_at = now

        if action == "mark_stale":
            item.governance_status = "stale"
        elif action == "revalidate":
            item.last_verified_at = now
            item.review_sla_days = max(int(next_review_days or item.review_sla_days or self.DEFAULT_REVIEW_WINDOW_DAYS), 1)
            item.review_due_at = now + timedelta(days=item.review_sla_days)
            if item.governance_status == "stale":
                item.governance_status = "active"
        else:
            raise ValueError(f"unsupported_action: {action}")

        self._close_other_pending_tasks(item.id)
        return {
            "id": task.id,
            "action": action,
            "knowledge_id": item.id,
            "new_governance_status": item.governance_status,
            "review_due_at": item.review_due_at.isoformat() if item.review_due_at else None,
        }

    def refresh_item_metadata(self, item: KnowledgeItem) -> None:
        if item.governance_status == "stale":
            item.governance_status = "active"
        item.last_verified_at = datetime.utcnow()
        if item.review_due_at is None and item.status == "active":
            item.review_due_at = item.last_verified_at + timedelta(days=item.review_sla_days or self.DEFAULT_REVIEW_WINDOW_DAYS)
        self._close_other_pending_tasks(item.id)

    def _has_pending_task(self, knowledge_id: int) -> bool:
        return (
            self.db.query(KnowledgeGovernanceTask)
            .filter(
                KnowledgeGovernanceTask.knowledge_id == knowledge_id,
                KnowledgeGovernanceTask.task_type == "stale",
                KnowledgeGovernanceTask.status == "pending",
            )
            .first()
            is not None
        )

    def _close_other_pending_tasks(self, knowledge_id: int) -> None:
        for task in (
            self.db.query(KnowledgeGovernanceTask)
            .filter(
                KnowledgeGovernanceTask.knowledge_id == knowledge_id,
                KnowledgeGovernanceTask.task_type == "stale",
                KnowledgeGovernanceTask.status == "pending",
            )
            .all()
        ):
            task.status = "closed"
            task.reviewed_at = datetime.utcnow()

    def _build_stale_reason(
        self,
        *,
        item: KnowledgeItem,
        now: datetime,
        threshold: datetime,
        window_days: int,
    ) -> tuple[str | None, dict]:
        if item.review_due_at and item.review_due_at <= now:
            return (
                "已超过复核截止时间",
                {
                    "rule": "review_due_at_expired",
                    "review_due_at": item.review_due_at.isoformat(),
                    "stale_after_days": window_days,
                },
            )

        anchor = item.last_verified_at or item.updated_at or item.published_at or item.created_at
        if anchor and anchor <= threshold:
            return (
                f"已超过 {window_days} 天未复核",
                {
                    "rule": "review_window_expired",
                    "anchor_time": anchor.isoformat(),
                    "stale_after_days": window_days,
                },
            )
        return None, {}

    def _check_source_change(self, item: KnowledgeItem) -> tuple[str | None, dict]:
        source_url = (item.source_url or "").strip()
        if not source_url:
            return None, {}

        try:
            with httpx.Client(timeout=self.SOURCE_FETCH_TIMEOUT_SECONDS, follow_redirects=True) as client:
                response = client.get(source_url)
                response.raise_for_status()
        except Exception as exc:
            item.source_last_checked_at = datetime.utcnow()
            return (
                "来源抓取失败，需人工复核",
                {
                    "rule": "source_fetch_failed",
                    "source_url": source_url,
                    "error": str(exc),
                },
            )

        content_hash, content_preview = self._build_snapshot(response)
        item.source_last_checked_at = datetime.utcnow()
        if not content_hash:
            return None, {}
        if not item.source_snapshot_hash:
            item.source_snapshot_hash = content_hash
            item.source_snapshot_preview = content_preview
            return None, {}
        if item.source_snapshot_hash != content_hash:
            previous_hash = item.source_snapshot_hash
            previous_preview = item.source_snapshot_preview
            item.source_snapshot_hash = content_hash
            item.source_snapshot_preview = content_preview
            return (
                "来源内容已变更，需重新复核",
                {
                    "rule": "source_content_changed",
                    "source_url": source_url,
                    "previous_hash": previous_hash,
                    "current_hash": content_hash,
                    "previous_preview": previous_preview,
                    "current_preview": content_preview,
                },
            )
        if content_preview and not item.source_snapshot_preview:
            item.source_snapshot_preview = content_preview
        return None, {}

    def _build_snapshot(self, response: httpx.Response) -> tuple[str | None, str | None]:
        body = response.content[:200_000]
        if not body:
            return None, None
        content_type = (response.headers.get("content-type") or "").lower()
        if "html" in content_type:
            text = body.decode(response.encoding or "utf-8", errors="ignore")
            text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
        else:
            text = body.decode(response.encoding or "utf-8", errors="ignore")
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        if not normalized:
            return None, None
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest(), normalized[: self.SOURCE_PREVIEW_LENGTH]

    def _serialize_item(self, item: KnowledgeItem) -> dict:
        return {
            "id": item.id,
            "kb_id": item.kb_id,
            "title": item.title,
            "document_name": item.document_name,
            "status": item.status,
            "governance_status": item.governance_status,
            "source_url": item.source_url,
            "source_org": item.source_org,
            "owner_user_id": item.owner_user_id,
            "review_due_at": item.review_due_at.isoformat() if item.review_due_at else None,
            "review_sla_days": item.review_sla_days,
            "last_verified_at": item.last_verified_at.isoformat() if item.last_verified_at else None,
            "source_last_checked_at": item.source_last_checked_at.isoformat() if item.source_last_checked_at else None,
            "source_snapshot_preview": item.source_snapshot_preview,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
