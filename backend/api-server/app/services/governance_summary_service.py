from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.knowledge import KnowledgeDedupRecord, KnowledgeGovernanceTask, KnowledgeItem


class GovernanceSummaryService:
    def __init__(self, db: Session):
        self.db = db

    def build_summary(self, *, project_id: int, kb_id: int | None = None) -> dict:
        knowledge_query = self.db.query(KnowledgeItem).filter(KnowledgeItem.project_id == project_id)
        if kb_id is not None:
            knowledge_query = knowledge_query.filter(KnowledgeItem.kb_id == kb_id)

        knowledge_items = knowledge_query.all()
        status_counts: dict[str, int] = {}
        for item in knowledge_items:
            status = str(item.governance_status or "active")
            status_counts[status] = status_counts.get(status, 0) + 1

        dedup_query = (
            self.db.query(KnowledgeDedupRecord)
            .join(KnowledgeItem, KnowledgeItem.id == KnowledgeDedupRecord.new_knowledge_id)
            .filter(
                KnowledgeDedupRecord.project_id == project_id,
                KnowledgeDedupRecord.action == "pending",
            )
        )
        if kb_id is not None:
            dedup_query = dedup_query.filter(KnowledgeItem.kb_id == kb_id)
        pending_duplicate_count = dedup_query.count()

        task_query = (
            self.db.query(KnowledgeGovernanceTask, KnowledgeItem)
            .join(KnowledgeItem, KnowledgeItem.id == KnowledgeGovernanceTask.knowledge_id)
            .filter(
                KnowledgeGovernanceTask.project_id == project_id,
                KnowledgeGovernanceTask.status == "pending",
                KnowledgeGovernanceTask.task_type.in_(("stale", "conflict")),
            )
        )
        if kb_id is not None:
            task_query = task_query.filter(KnowledgeItem.kb_id == kb_id)
        tasks = task_query.all()

        pending_stale_count = 0
        pending_conflict_count = 0
        source_changed_count = 0
        source_fetch_failed_count = 0
        for task, _ in tasks:
            if task.task_type == "stale":
                pending_stale_count += 1
                rule = str((task.payload_json or {}).get("rule") or "").strip().lower()
                if rule == "source_content_changed":
                    source_changed_count += 1
                elif rule == "source_fetch_failed":
                    source_fetch_failed_count += 1
            elif task.task_type == "conflict":
                pending_conflict_count += 1

        return {
            "knowledge_total_count": len(knowledge_items),
            "active_knowledge_count": status_counts.get("active", 0),
            "blocked_knowledge_count": sum(count for status, count in status_counts.items() if status != "active"),
            "pending_duplicate_count": pending_duplicate_count,
            "pending_stale_count": pending_stale_count,
            "pending_conflict_count": pending_conflict_count,
            "source_changed_task_count": source_changed_count,
            "source_fetch_failed_task_count": source_fetch_failed_count,
            "governance_status_counts": status_counts,
        }
