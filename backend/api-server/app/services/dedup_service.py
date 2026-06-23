from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import re

from sqlalchemy.orm import Session, aliased

from app.models.knowledge import KnowledgeDedupRecord, KnowledgeItem


BLOCKED_GOVERNANCE_STATUSES = {"duplicate", "superseded", "archived"}


@dataclass
class DedupCandidate:
    knowledge_id: int
    title: str
    score: float
    reason: list[str]
    dedup_level: str


class DedupService:
    def __init__(self, db: Session):
        self.db = db

    def check(
        self,
        project_id: int,
        title: str,
        keywords: list[str],
        content: str,
        exclude_knowledge_id: int | None = None,
    ) -> dict:
        del keywords
        candidates = self._find_candidates(
            project_id=project_id,
            title=title,
            content=content,
            normalized_hash=self.build_normalized_hash(title=title, content=content),
            exclude_knowledge_id=exclude_knowledge_id,
        )
        top_score = candidates[0].score if candidates else 0.0
        return {
            "has_duplicate": bool(candidates),
            "level": self._level_for_score(top_score),
            "candidates": [candidate.__dict__ for candidate in candidates],
        }

    def sync_item_records(self, item: KnowledgeItem) -> dict:
        item.normalized_content_hash = self.build_normalized_hash(title=item.title, content=item.content)
        item.last_verified_at = datetime.utcnow()

        self._clear_pending_records(item.id)
        if item.governance_status in BLOCKED_GOVERNANCE_STATUSES:
            return {"has_duplicate": False, "level": "none", "candidates": []}

        result = self.check(
            project_id=item.project_id,
            title=item.title,
            keywords=item.keywords_json or [],
            content=item.content,
            exclude_knowledge_id=item.id,
        )
        candidates = result.get("candidates") or []
        for candidate in candidates:
            record = KnowledgeDedupRecord(
                project_id=item.project_id,
                new_knowledge_id=item.id,
                old_knowledge_id=int(candidate["knowledge_id"]),
                score=float(candidate["score"]),
                dedup_level=str(candidate["dedup_level"]),
                action="pending",
                reason_json=list(candidate["reason"] or []),
            )
            self.db.add(record)

        item.duplicate_of_knowledge_id = None
        item.superseded_by_knowledge_id = None
        item.governance_status = "review_pending" if candidates else "active"
        return result

    def rebuild_project_records(self, project_id: int, kb_id: int | None = None) -> dict:
        query = self.db.query(KnowledgeItem).filter(KnowledgeItem.project_id == project_id)
        if kb_id is not None:
            query = query.filter(KnowledgeItem.kb_id == kb_id)
        items = query.order_by(KnowledgeItem.updated_at.desc(), KnowledgeItem.id.desc()).all()

        count = 0
        pending_count = 0
        for item in items:
            result = self.sync_item_records(item)
            pending_count += len(result.get("candidates") or [])
            count += 1
        self.db.commit()
        return {"knowledge_count": count, "pending_candidate_count": pending_count}

    def list_records(
        self,
        project_id: int,
        action: str | None = "pending",
        kb_id: int | None = None,
    ) -> list[dict]:
        new_item = aliased(KnowledgeItem)
        old_item = aliased(KnowledgeItem)
        query = (
            self.db.query(KnowledgeDedupRecord, new_item, old_item)
            .join(new_item, new_item.id == KnowledgeDedupRecord.new_knowledge_id)
            .join(old_item, old_item.id == KnowledgeDedupRecord.old_knowledge_id)
            .filter(KnowledgeDedupRecord.project_id == project_id)
        )
        if action:
            query = query.filter(KnowledgeDedupRecord.action == action)
        if kb_id is not None:
            query = query.filter(new_item.kb_id == kb_id)

        records = query.order_by(
            KnowledgeDedupRecord.created_at.desc(),
            KnowledgeDedupRecord.id.desc(),
        ).all()
        return [
            {
                "id": record.id,
                "project_id": record.project_id,
                "new_knowledge_id": record.new_knowledge_id,
                "old_knowledge_id": record.old_knowledge_id,
                "score": float(record.score),
                "dedup_level": record.dedup_level,
                "action": record.action,
                "reason": record.reason_json or [],
                "comment": record.comment,
                "reviewed_by": record.reviewed_by,
                "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "new_knowledge": self._serialize_related_item(new_item_record),
                "old_knowledge": self._serialize_related_item(old_item_record),
            }
            for record, new_item_record, old_item_record in records
        ]

    def resolve_record(
        self,
        project_id: int,
        record_id: int,
        action: str,
        reviewer_id: int | None = None,
        comment: str | None = None,
    ) -> dict | None:
        record = (
            self.db.query(KnowledgeDedupRecord)
            .filter(KnowledgeDedupRecord.project_id == project_id, KnowledgeDedupRecord.id == record_id)
            .first()
        )
        if not record:
            return None

        data = self._resolve_record_instance(
            record=record,
            action=action,
            reviewer_id=reviewer_id,
            comment=comment,
        )
        if not data:
            return None
        self.db.commit()
        return data

    def bulk_resolve_records(
        self,
        *,
        project_id: int,
        record_ids: list[int],
        action: str,
        reviewer_id: int | None = None,
        comment: str | None = None,
    ) -> dict:
        resolved_ids: list[int] = []
        for record_id in record_ids:
            record = (
                self.db.query(KnowledgeDedupRecord)
                .filter(KnowledgeDedupRecord.project_id == project_id, KnowledgeDedupRecord.id == int(record_id))
                .first()
            )
            if not record:
                continue
            data = self._resolve_record_instance(
                record=record,
                action=action,
                reviewer_id=reviewer_id,
                comment=comment,
            )
            if data:
                resolved_ids.append(record.id)
        self.db.commit()
        return {
            "action": action,
            "resolved_count": len(resolved_ids),
            "resolved_record_ids": resolved_ids,
        }

    def _resolve_record_instance(
        self,
        *,
        record: KnowledgeDedupRecord,
        action: str,
        reviewer_id: int | None = None,
        comment: str | None = None,
    ) -> dict | None:

        new_item = self.db.query(KnowledgeItem).filter(KnowledgeItem.id == record.new_knowledge_id).first()
        old_item = self.db.query(KnowledgeItem).filter(KnowledgeItem.id == record.old_knowledge_id).first()
        if not new_item or not old_item:
            return None

        now = datetime.utcnow()
        record.action = action
        record.comment = comment
        record.reviewed_by = reviewer_id
        record.reviewed_at = now

        if action == "confirm_duplicate":
            new_item.governance_status = "duplicate"
            new_item.duplicate_of_knowledge_id = old_item.id
            new_item.superseded_by_knowledge_id = None
            self._close_other_pending_records(new_item.id, keep_record_id=record.id)
        elif action == "mark_superseded":
            new_item.governance_status = "superseded"
            new_item.superseded_by_knowledge_id = old_item.id
            new_item.duplicate_of_knowledge_id = None
            self._close_other_pending_records(new_item.id, keep_record_id=record.id)
        elif action == "reject":
            self._refresh_governance_status(new_item)
        else:
            raise ValueError(f"unsupported_action: {action}")

        new_item.last_verified_at = now
        return {
            "id": record.id,
            "action": record.action,
            "comment": record.comment,
            "new_knowledge_id": new_item.id,
            "new_governance_status": new_item.governance_status,
        }

    def build_normalized_hash(self, title: str, content: str) -> str | None:
        normalized = self._normalize_text(f"{title or ''}\n{content or ''}")
        if not normalized:
            return None
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _find_candidates(
        self,
        *,
        project_id: int,
        title: str,
        content: str,
        normalized_hash: str | None,
        exclude_knowledge_id: int | None,
    ) -> list[DedupCandidate]:
        query = self.db.query(KnowledgeItem).filter(KnowledgeItem.project_id == project_id)
        if exclude_knowledge_id is not None:
            query = query.filter(KnowledgeItem.id != exclude_knowledge_id)
        query = query.filter(~KnowledgeItem.governance_status.in_(BLOCKED_GOVERNANCE_STATUSES))
        candidates: list[DedupCandidate] = []

        exact_hash_ids: set[int] = set()
        if normalized_hash:
            for item in query.filter(KnowledgeItem.normalized_content_hash == normalized_hash).all():
                reasons = ["标准化文本完全一致"]
                if title and item.title and title.strip().lower() == item.title.strip().lower():
                    reasons.append("标题完全相同")
                candidates.append(
                    DedupCandidate(
                        knowledge_id=item.id,
                        title=item.title,
                        score=1.0,
                        reason=reasons,
                        dedup_level="high",
                    )
                )
                exact_hash_ids.add(item.id)

        for item in query.order_by(KnowledgeItem.updated_at.desc()).limit(200).all():
            if item.id in exact_hash_ids:
                continue
            score = self._score(title=title, content=content, existing=item)
            if score < 0.45:
                continue
            reasons = []
            if title and item.title and title.strip().lower() == item.title.strip().lower():
                reasons.append("标题完全相同")
            if title and item.title and (title.strip() in item.title or item.title in title.strip()):
                reasons.append("标题高度相似")
            if content and item.content and content[:120] and content[:120].lower() in item.content.lower():
                reasons.append("内容片段重复")
            if not reasons:
                reasons.append("文本相似度较高")
            candidates.append(
                DedupCandidate(
                    knowledge_id=item.id,
                    title=item.title,
                    score=round(score, 4),
                    reason=reasons,
                    dedup_level=self._level_for_score(score),
                )
            )

        return sorted(candidates, key=lambda item: item.score, reverse=True)[:5]

    def _score(self, title: str, content: str, existing: KnowledgeItem) -> float:
        title_score = 0.0
        if title and existing.title:
            title_lower = self._normalize_text(title)
            existing_title = self._normalize_text(existing.title)
            if title_lower == existing_title:
                title_score = 1.0
            elif title_lower in existing_title or existing_title in title_lower:
                title_score = 0.75

        content_score = 0.0
        if content and existing.content:
            content_lower = self._normalize_text(content)
            existing_content = self._normalize_text(existing.content)
            tokens = {token for token in re.split(r"[\s,，。！？；：、/()（）]+", content_lower) if token}
            intersection = sum(1 for token in tokens if token in existing_content)
            denominator = max(len(tokens), 1)
            content_score = min(intersection / denominator, 1.0)
            if content_lower[:160] and content_lower[:160] in existing_content:
                content_score = max(content_score, 0.85)

        return round(title_score * 0.6 + content_score * 0.4, 4)

    def _level_for_score(self, score: float) -> str:
        if score >= 0.85:
            return "high"
        if score >= 0.65:
            return "medium"
        if score > 0:
            return "low"
        return "none"

    def _clear_pending_records(self, knowledge_id: int) -> None:
        (
            self.db.query(KnowledgeDedupRecord)
            .filter(KnowledgeDedupRecord.new_knowledge_id == knowledge_id, KnowledgeDedupRecord.action == "pending")
            .delete(synchronize_session=False)
        )

    def _close_other_pending_records(self, knowledge_id: int, keep_record_id: int) -> None:
        for record in (
            self.db.query(KnowledgeDedupRecord)
            .filter(
                KnowledgeDedupRecord.new_knowledge_id == knowledge_id,
                KnowledgeDedupRecord.action == "pending",
                KnowledgeDedupRecord.id != keep_record_id,
            )
            .all()
        ):
            record.action = "closed"
            record.reviewed_at = datetime.utcnow()

    def _refresh_governance_status(self, item: KnowledgeItem) -> None:
        if item.governance_status in BLOCKED_GOVERNANCE_STATUSES:
            return
        has_pending = (
            self.db.query(KnowledgeDedupRecord)
            .filter(KnowledgeDedupRecord.new_knowledge_id == item.id, KnowledgeDedupRecord.action == "pending")
            .first()
            is not None
        )
        item.governance_status = "review_pending" if has_pending else "active"
        if item.governance_status == "active":
            item.duplicate_of_knowledge_id = None
            item.superseded_by_knowledge_id = None

    def _serialize_related_item(self, item: KnowledgeItem) -> dict:
        return {
            "id": item.id,
            "kb_id": item.kb_id,
            "title": item.title,
            "document_name": item.document_name,
            "status": item.status,
            "governance_status": item.governance_status,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    def _normalize_text(self, text: str) -> str:
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        return normalized
