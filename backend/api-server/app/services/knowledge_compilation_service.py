from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.chat import ChatMessage, ChatSession
from app.models.knowledge_compilation import (
    KnowledgeCompilationHealthFinding,
    KnowledgeCompilationHealthRun,
    KnowledgeCompilationPage,
    KnowledgeCompilationPageLink,
    KnowledgeCompilationPageSource,
    KnowledgeCompilationPageTreeLink,
    KnowledgeCompilationPageVersion,
    KnowledgeCompilationRun,
    KnowledgeCompilationWritebackCandidate,
)
from app.models.user import OperationLog


class KnowledgeCompilationService:
    def __init__(self, db: Session):
        self.db = db

    def list_pages(
        self,
        project_id: int,
        kb_id: int,
        keyword: str | None = None,
        page_type: str | None = None,
        status: str | None = None,
        health_status: str | None = None,
        topic_key: str | None = None,
        tree_node_id: int | None = None,
    ) -> list[dict]:
        query = self.db.query(KnowledgeCompilationPage).filter(
            KnowledgeCompilationPage.project_id == project_id,
            KnowledgeCompilationPage.kb_id == kb_id,
            KnowledgeCompilationPage.deleted_at.is_(None),
        )
        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                (KnowledgeCompilationPage.title.like(like))
                | (KnowledgeCompilationPage.canonical_title.like(like))
            )
        if page_type:
            query = query.filter(KnowledgeCompilationPage.page_type == page_type)
        if status:
            query = query.filter(KnowledgeCompilationPage.status == status)
        if health_status:
            query = query.filter(KnowledgeCompilationPage.health_status == health_status)
        if topic_key:
            query = query.filter(KnowledgeCompilationPage.topic_key == topic_key)
        if tree_node_id is not None:
            query = query.join(
                KnowledgeCompilationPageTreeLink,
                KnowledgeCompilationPageTreeLink.page_id == KnowledgeCompilationPage.id,
            ).filter(KnowledgeCompilationPageTreeLink.node_id == tree_node_id)
        items = query.order_by(KnowledgeCompilationPage.updated_at.desc(), KnowledgeCompilationPage.id.desc()).all()
        return [self._serialize_page(item) for item in items]

    def create_page(self, project_id: int, kb_id: int, payload: dict[str, Any], current_user_id: int | None = None) -> dict:
        page = self._create_page_record(
            project_id=project_id,
            kb_id=kb_id,
            payload=payload,
            current_user_id=current_user_id,
        )
        self.db.commit()
        self.db.refresh(page)
        return self.get_page_detail(project_id, kb_id, page.id) or self._serialize_page(page)

    def get_page_detail(self, project_id: int, kb_id: int, page_id: int) -> dict | None:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return None
        versions = (
            self.db.query(KnowledgeCompilationPageVersion)
            .filter(KnowledgeCompilationPageVersion.page_id == page.id)
            .order_by(KnowledgeCompilationPageVersion.version_no.desc(), KnowledgeCompilationPageVersion.id.desc())
            .all()
        )
        sources = self.list_sources(project_id, kb_id, page_id)
        links = self.list_links(project_id, kb_id, page_id)
        return {
            **self._serialize_page(page),
            "current_version": self._serialize_version(next((item for item in versions if item.id == page.current_version_id), None)),
            "published_version": self._serialize_version(next((item for item in versions if item.id == page.published_version_id), None)),
            "versions": [self._serialize_version(item) for item in versions],
            "sources": sources,
            "links": links,
        }

    def update_page(
        self,
        project_id: int,
        kb_id: int,
        page_id: int,
        payload: dict[str, Any],
        current_user_id: int | None = None,
    ) -> dict | None:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return None
        page.page_type = payload.get("page_type", page.page_type)
        page.topic_key = payload.get("topic_key", page.topic_key)
        page.canonical_title = payload.get("canonical_title", page.canonical_title)
        page.title = payload.get("title", page.title)
        page.summary = payload.get("summary", page.summary)
        page.content_markdown = payload.get("content_markdown", page.content_markdown)
        page.tags_json = payload.get("tags", page.tags_json or [])
        page.metadata_json = payload.get("metadata", page.metadata_json or {})
        page.status = payload.get("status", page.status)
        page.updated_by = current_user_id
        version = self._create_version(
            page=page,
            title=page.title,
            summary=page.summary,
            content_markdown=page.content_markdown,
            change_summary=payload.get("change_summary") or "manual_update",
            created_by=current_user_id,
            sources_snapshot=self._list_page_source_snapshots(page.id),
        )
        page.current_version_id = version.id
        page.version_no = version.version_no
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="update_compilation_page",
            target_type="knowledge_compilation_page",
            target_id=page.id,
            detail={"kb_id": kb_id, "version_no": page.version_no},
        )
        self.db.commit()
        return self.get_page_detail(project_id, kb_id, page_id)

    def archive_page(self, project_id: int, kb_id: int, page_id: int, current_user_id: int | None = None) -> bool:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return False
        page.status = "archived"
        page.deleted_at = datetime.utcnow()
        page.updated_by = current_user_id
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="archive_compilation_page",
            target_type="knowledge_compilation_page",
            target_id=page.id,
            detail={"kb_id": kb_id},
        )
        self.db.commit()
        return True

    def list_versions(self, project_id: int, kb_id: int, page_id: int) -> list[dict]:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return []
        items = (
            self.db.query(KnowledgeCompilationPageVersion)
            .filter(KnowledgeCompilationPageVersion.page_id == page.id)
            .order_by(KnowledgeCompilationPageVersion.version_no.desc(), KnowledgeCompilationPageVersion.id.desc())
            .all()
        )
        return [self._serialize_version(item) for item in items]

    def get_version_detail(self, project_id: int, kb_id: int, page_id: int, version_id: int) -> dict | None:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return None
        item = (
            self.db.query(KnowledgeCompilationPageVersion)
            .filter(
                KnowledgeCompilationPageVersion.page_id == page.id,
                KnowledgeCompilationPageVersion.id == version_id,
            )
            .first()
        )
        return self._serialize_version(item) if item else None

    def publish_version(
        self, project_id: int, kb_id: int, page_id: int, version_id: int, current_user_id: int | None = None
    ) -> dict | None:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return None
        version = (
            self.db.query(KnowledgeCompilationPageVersion)
            .filter(
                KnowledgeCompilationPageVersion.page_id == page.id,
                KnowledgeCompilationPageVersion.id == version_id,
            )
            .first()
        )
        if not version:
            return None
        page.published_version_id = version.id
        page.current_version_id = version.id
        page.version_no = version.version_no
        page.status = "published"
        page.published_at = datetime.utcnow()
        page.updated_by = current_user_id
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="publish_compilation_page_version",
            target_type="knowledge_compilation_page_version",
            target_id=version.id,
            detail={"page_id": page.id, "kb_id": kb_id, "version_no": version.version_no},
        )
        self.db.commit()
        return self.get_page_detail(project_id, kb_id, page_id)

    def list_sources(self, project_id: int, kb_id: int, page_id: int) -> list[dict]:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return []
        items = (
            self.db.query(KnowledgeCompilationPageSource)
            .filter(KnowledgeCompilationPageSource.page_id == page.id)
            .order_by(KnowledgeCompilationPageSource.order_no.asc(), KnowledgeCompilationPageSource.id.asc())
            .all()
        )
        return [self._serialize_source(item) for item in items]

    def add_source(
        self, project_id: int, kb_id: int, page_id: int, payload: dict[str, Any], current_user_id: int | None = None
    ) -> dict | None:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return None
        version_id = page.current_version_id
        item = KnowledgeCompilationPageSource(
            page_id=page.id,
            version_id=version_id,
            source_type=payload.get("source_type", "manual"),
            source_id=str(payload.get("source_id") or ""),
            source_ref_id=payload.get("source_ref_id"),
            source_title=payload.get("source_title") or payload.get("source_id") or "source",
            source_locator_json=payload.get("source_locator") or {},
            source_quote=payload.get("quote"),
            source_snapshot=payload.get("source_snapshot") or {},
            claim_text=payload.get("claim_text"),
            support_type=payload.get("support_type", "supports"),
            weight=float(payload.get("weight", 1)),
            order_no=int(payload.get("order_no", 0)),
        )
        self.db.add(item)
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="add_compilation_source",
            target_type="knowledge_compilation_page_source",
            target_id=item.id,
            detail={"kb_id": kb_id, "source_type": item.source_type, "source_id": item.source_id},
        )
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_source(item)

    def delete_source(
        self,
        project_id: int,
        kb_id: int,
        page_id: int,
        source_link_id: int,
        current_user_id: int | None = None,
    ) -> bool:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return False
        item = (
            self.db.query(KnowledgeCompilationPageSource)
            .filter(
                KnowledgeCompilationPageSource.page_id == page.id,
                KnowledgeCompilationPageSource.id == source_link_id,
            )
            .first()
        )
        if not item:
            return False
        self.db.delete(item)
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="delete_compilation_source",
            target_type="knowledge_compilation_page_source",
            target_id=source_link_id,
            detail={"page_id": page.id, "kb_id": kb_id},
        )
        self.db.commit()
        return True

    def list_links(self, project_id: int, kb_id: int, page_id: int) -> list[dict]:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return []
        items = (
            self.db.query(KnowledgeCompilationPageLink)
            .filter(
                KnowledgeCompilationPageLink.project_id == project_id,
                KnowledgeCompilationPageLink.kb_id == kb_id,
                KnowledgeCompilationPageLink.from_page_id == page.id,
            )
            .order_by(KnowledgeCompilationPageLink.id.asc())
            .all()
        )
        return [self._serialize_link(item) for item in items]

    def add_link(
        self, project_id: int, kb_id: int, page_id: int, payload: dict[str, Any], current_user_id: int | None = None
    ) -> dict | None:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return None
        item = KnowledgeCompilationPageLink(
            project_id=project_id,
            kb_id=kb_id,
            from_page_id=page.id,
            to_page_id=int(payload.get("to_page_id")),
            link_type=payload.get("link_type", "related"),
            anchor_text=payload.get("anchor_text"),
        )
        self.db.add(item)
        self.db.flush()
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="add_compilation_link",
            target_type="knowledge_compilation_page_link",
            target_id=item.id,
            detail={"kb_id": kb_id, "to_page_id": item.to_page_id, "link_type": item.link_type},
        )
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_link(item)

    def delete_link(
        self,
        project_id: int,
        kb_id: int,
        page_id: int,
        link_id: int,
        current_user_id: int | None = None,
    ) -> bool:
        page = self._get_page(project_id, kb_id, page_id)
        if not page:
            return False
        item = (
            self.db.query(KnowledgeCompilationPageLink)
            .filter(
                KnowledgeCompilationPageLink.project_id == project_id,
                KnowledgeCompilationPageLink.kb_id == kb_id,
                KnowledgeCompilationPageLink.from_page_id == page.id,
                KnowledgeCompilationPageLink.id == link_id,
            )
            .first()
        )
        if not item:
            return False
        self.db.delete(item)
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="delete_compilation_link",
            target_type="knowledge_compilation_page_link",
            target_id=link_id,
            detail={"page_id": page.id, "kb_id": kb_id},
        )
        self.db.commit()
        return True

    def create_run(
        self,
        project_id: int,
        kb_id: int,
        page_id: int | None,
        payload: dict[str, Any],
        current_user_id: int | None = None,
    ) -> dict:
        idempotency_key = payload.get("idempotency_key")
        if idempotency_key:
            existing = (
                self.db.query(KnowledgeCompilationRun)
                .filter(KnowledgeCompilationRun.idempotency_key == idempotency_key)
                .first()
            )
            if existing:
                return self._serialize_run(existing)
        if page_id is not None and payload.get("run_type", "recompile") in {"recompile", "backfill"}:
            running = (
                self.db.query(KnowledgeCompilationRun)
                .filter(
                    KnowledgeCompilationRun.project_id == project_id,
                    KnowledgeCompilationRun.kb_id == kb_id,
                    KnowledgeCompilationRun.page_id == page_id,
                    KnowledgeCompilationRun.run_type.in_(["recompile", "backfill"]),
                    KnowledgeCompilationRun.status.in_(["queued", "running"]),
                )
                .order_by(KnowledgeCompilationRun.created_at.desc(), KnowledgeCompilationRun.id.desc())
                .first()
            )
            if running:
                return self._serialize_run(running)
        run = KnowledgeCompilationRun(
            project_id=project_id,
            kb_id=kb_id,
            page_id=page_id,
            run_type=payload.get("run_type", "recompile"),
            trigger_type=payload.get("trigger_type", "manual"),
            strategy=payload.get("strategy", "compiled_first"),
            status="queued",
            idempotency_key=idempotency_key,
            request_payload=payload,
            result_payload={},
            created_by=current_user_id,
        )
        self.db.add(run)
        self.db.flush()
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="create_compilation_run",
            target_type="knowledge_compilation_run",
            target_id=run.id,
            detail={"kb_id": kb_id, "page_id": page_id, "run_type": run.run_type, "idempotency_key": idempotency_key},
        )
        self.db.commit()
        self.db.refresh(run)
        return self._serialize_run(run)

    def list_runs(self, project_id: int, kb_id: int, page_id: int) -> list[dict]:
        items = (
            self.db.query(KnowledgeCompilationRun)
            .filter(
                KnowledgeCompilationRun.project_id == project_id,
                KnowledgeCompilationRun.kb_id == kb_id,
                KnowledgeCompilationRun.page_id == page_id,
            )
            .order_by(KnowledgeCompilationRun.created_at.desc(), KnowledgeCompilationRun.id.desc())
            .all()
        )
        return [self._serialize_run(item) for item in items]

    def get_run_detail(self, project_id: int, kb_id: int, run_id: int) -> dict | None:
        item = (
            self.db.query(KnowledgeCompilationRun)
            .filter(
                KnowledgeCompilationRun.project_id == project_id,
                KnowledgeCompilationRun.kb_id == kb_id,
                KnowledgeCompilationRun.id == run_id,
            )
            .first()
        )
        return self._serialize_run(item) if item else None

    def create_health_run(
        self, project_id: int, kb_id: int, payload: dict[str, Any], current_user_id: int | None = None
    ) -> dict:
        item = KnowledgeCompilationHealthRun(
            project_id=project_id,
            kb_id=kb_id,
            run_type=payload.get("run_type", "full_scan"),
            status="queued",
            summary_json={},
            created_by=current_user_id,
        )
        self.db.add(item)
        self.db.flush()
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="create_compilation_health_run",
            target_type="knowledge_compilation_health_run",
            target_id=item.id,
            detail={"kb_id": kb_id, "run_type": item.run_type},
        )
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_health_run(item)

    def get_health_run_detail(self, project_id: int, kb_id: int, run_id: int) -> dict | None:
        item = (
            self.db.query(KnowledgeCompilationHealthRun)
            .filter(
                KnowledgeCompilationHealthRun.project_id == project_id,
                KnowledgeCompilationHealthRun.kb_id == kb_id,
                KnowledgeCompilationHealthRun.id == run_id,
            )
            .first()
        )
        return self._serialize_health_run(item) if item else None

    def list_health_findings(
        self,
        project_id: int,
        kb_id: int,
        page_id: int | None = None,
        check_type: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        query = self.db.query(KnowledgeCompilationHealthFinding).join(
            KnowledgeCompilationHealthRun,
            KnowledgeCompilationHealthRun.id == KnowledgeCompilationHealthFinding.health_run_id,
        ).filter(
            KnowledgeCompilationHealthRun.project_id == project_id,
            KnowledgeCompilationHealthRun.kb_id == kb_id,
        )
        if page_id is not None:
            query = query.filter(KnowledgeCompilationHealthFinding.page_id == page_id)
        if check_type:
            query = query.filter(KnowledgeCompilationHealthFinding.check_type == check_type)
        if severity:
            query = query.filter(KnowledgeCompilationHealthFinding.severity == severity)
        if status:
            query = query.filter(KnowledgeCompilationHealthFinding.status == status)
        items = query.order_by(KnowledgeCompilationHealthFinding.created_at.desc(), KnowledgeCompilationHealthFinding.id.desc()).all()
        return [self._serialize_health_finding(item) for item in items]

    def update_health_finding(
        self, project_id: int, kb_id: int, finding_id: int, payload: dict[str, Any], current_user_id: int | None = None
    ) -> dict | None:
        item = (
            self.db.query(KnowledgeCompilationHealthFinding)
            .join(KnowledgeCompilationHealthRun, KnowledgeCompilationHealthRun.id == KnowledgeCompilationHealthFinding.health_run_id)
            .filter(
                KnowledgeCompilationHealthRun.project_id == project_id,
                KnowledgeCompilationHealthRun.kb_id == kb_id,
                KnowledgeCompilationHealthFinding.id == finding_id,
            )
            .first()
        )
        if not item:
            return None
        item.status = payload.get("status", item.status)
        if item.status == "resolved":
            item.resolved_by = current_user_id
            item.resolved_at = datetime.utcnow()
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="update_compilation_health_finding",
            target_type="knowledge_compilation_health_finding",
            target_id=item.id,
            detail={"kb_id": kb_id, "status": item.status},
        )
        self.db.commit()
        return self._serialize_health_finding(item)

    def create_writeback_candidate(
        self, project_id: int, kb_id: int, payload: dict[str, Any], current_user_id: int | None = None
    ) -> dict | None:
        session = self._find_chat_session(project_id, payload.get("chat_session_id"))
        message = self._find_chat_message(session.id if session else None, payload.get("chat_message_id"))
        if not session or not message:
            return None
        item = KnowledgeCompilationWritebackCandidate(
            project_id=project_id,
            kb_id=kb_id,
            chat_session_id=session.id,
            chat_message_id=message.id,
            question=message.query_raw or "",
            answer=message.answer or "",
            source_docs_snapshot=message.source_docs or [],
            suggested_page_id=payload.get("suggested_page_id"),
            suggested_page_type=payload.get("suggested_page_type", "answer_writeback"),
            suggested_title=payload.get("suggested_title"),
            status="pending",
            review_note=payload.get("review_note"),
            created_by=current_user_id,
        )
        self.db.add(item)
        self.db.flush()
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="create_compilation_writeback_candidate",
            target_type="knowledge_compilation_writeback_candidate",
            target_id=item.id,
            detail={"kb_id": kb_id, "chat_message_id": message.id, "suggested_page_id": item.suggested_page_id},
        )
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_writeback_candidate(item)

    def list_writeback_candidates(
        self, project_id: int, kb_id: int, status: str | None = None, suggested_page_id: int | None = None
    ) -> list[dict]:
        query = self.db.query(KnowledgeCompilationWritebackCandidate).filter(
            KnowledgeCompilationWritebackCandidate.project_id == project_id,
            KnowledgeCompilationWritebackCandidate.kb_id == kb_id,
        )
        if status:
            query = query.filter(KnowledgeCompilationWritebackCandidate.status == status)
        if suggested_page_id is not None:
            query = query.filter(KnowledgeCompilationWritebackCandidate.suggested_page_id == suggested_page_id)
        items = query.order_by(
            KnowledgeCompilationWritebackCandidate.created_at.desc(),
            KnowledgeCompilationWritebackCandidate.id.desc(),
        ).all()
        return [self._serialize_writeback_candidate(item) for item in items]

    def merge_writeback_candidate(
        self, project_id: int, kb_id: int, candidate_id: int, current_user_id: int | None = None
    ) -> dict | None:
        item = self._get_writeback_candidate(project_id, kb_id, candidate_id)
        if not item:
            return None
        if item.status == "merged":
            return self._serialize_writeback_candidate(item)
        target_page_id = item.suggested_page_id
        if target_page_id:
            page = self._get_page(project_id, kb_id, target_page_id)
        else:
            page = None
        writeback_source_refs = self._build_writeback_source_refs(item)
        if page:
            merged_content = f"{page.content_markdown}\n\n## 問答回流補充\n\n問題：{item.question}\n\n回答：{item.answer}"
            version = self._create_version(
                page=page,
                title=page.title,
                summary=page.summary,
                content_markdown=merged_content,
                change_summary="writeback_merge",
                created_by=current_user_id,
                sources_snapshot=self._merge_source_snapshots(self._list_page_source_snapshots(page.id), writeback_source_refs),
            )
            page.content_markdown = merged_content
            page.current_version_id = version.id
            page.version_no = version.version_no
            page.updated_by = current_user_id
            self._attach_page_sources(
                page_id=page.id,
                version_id=version.id,
                source_refs=writeback_source_refs,
                skip_existing=True,
            )
            item.merged_version_id = version.id
        else:
            page = self._create_page_record(
                project_id=project_id,
                kb_id=kb_id,
                payload={
                    "page_type": item.suggested_page_type or "answer_writeback",
                    "canonical_title": item.suggested_title or item.question[:80],
                    "title": item.suggested_title or item.question[:80],
                    "summary": item.question[:120],
                    "content_markdown": f"## 問題\n\n{item.question}\n\n## 回答\n\n{item.answer}",
                    "tags": [],
                    "metadata": {"source": "writeback_candidate"},
                    "source_refs": writeback_source_refs,
                    "status": "draft",
                    "change_summary": "writeback_create",
                },
                current_user_id=current_user_id,
            )
            item.suggested_page_id = page.id
            item.merged_version_id = page.current_version_id or page.published_version_id
        item.status = "merged"
        item.reviewed_by = current_user_id
        item.reviewed_at = datetime.utcnow()
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="merge_compilation_writeback_candidate",
            target_type="knowledge_compilation_writeback_candidate",
            target_id=item.id,
            detail={"kb_id": kb_id, "suggested_page_id": item.suggested_page_id, "merged_version_id": item.merged_version_id},
        )
        self.db.commit()
        return self._serialize_writeback_candidate(item)

    def reject_writeback_candidate(
        self, project_id: int, kb_id: int, candidate_id: int, current_user_id: int | None = None
    ) -> dict | None:
        item = self._get_writeback_candidate(project_id, kb_id, candidate_id)
        if not item:
            return None
        item.status = "rejected"
        item.reviewed_by = current_user_id
        item.reviewed_at = datetime.utcnow()
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="reject_compilation_writeback_candidate",
            target_type="knowledge_compilation_writeback_candidate",
            target_id=item.id,
            detail={"kb_id": kb_id},
        )
        self.db.commit()
        return self._serialize_writeback_candidate(item)

    def build_chat_compilation_context(
        self,
        project_id: int,
        kb_ids: list[int] | None,
        query: str,
        settings: dict[str, Any],
        switches: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        strategy = str((switches or {}).get("compilation_strategy") or settings.get("compilation_strategy") or "compiled_first")
        enabled = bool(settings.get("capability_knowledge_compilation")) and bool(
            (switches or {}).get("knowledge_compilation", settings.get("capability_knowledge_compilation"))
        )
        if not enabled or strategy == "disabled":
            return {
                "enabled": False,
                "strategy": strategy,
                "page_hits": [],
                "fallback_reason": "knowledge_compilation_disabled",
                "reference_items": [],
                "usable": False,
                "selected_mode": "disabled",
                "raw_sources": [],
            }

        page_query = self.db.query(KnowledgeCompilationPage).filter(
            KnowledgeCompilationPage.project_id == project_id,
            KnowledgeCompilationPage.deleted_at.is_(None),
            KnowledgeCompilationPage.status == "published",
        )
        if kb_ids:
            page_query = page_query.filter(KnowledgeCompilationPage.kb_id.in_(kb_ids))
        pages = page_query.order_by(
            KnowledgeCompilationPage.retrieval_priority.asc(),
            KnowledgeCompilationPage.updated_at.desc(),
            KnowledgeCompilationPage.id.desc(),
        ).limit(24).all()
        query_tokens = self._tokenize_text(query)

        scored_pages: list[dict[str, Any]] = []
        for page in pages:
            page_sources = self._list_page_source_entities(page.id, limit=8)
            score = self._score_compilation_page(query=query, query_tokens=query_tokens, page=page, sources=page_sources)
            if score <= 0:
                continue
            reference_item = self._build_reference_item(page)
            raw_sources = [self._serialize_chat_source(item) for item in page_sources]
            scored_pages.append(
                {
                    "page": page,
                    "score": score,
                    "source_count": len(raw_sources),
                    "reference_item": reference_item,
                    "raw_sources": raw_sources,
                }
            )
        scored_pages.sort(key=lambda item: (-item["score"], item["page"].retrieval_priority, -int(item["page"].id)))
        top_pages = scored_pages[:3]

        page_hits = [
            {
                "page_id": item["page"].id,
                "title": item["page"].title,
                "page_type": item["page"].page_type,
                "score": round(item["score"], 4),
                "version_no": item["page"].version_no,
                "health_status": item["page"].health_status,
                "supporting_source_count": item["source_count"],
                "retrieval_priority": item["page"].retrieval_priority,
            }
            for item in top_pages
        ]
        sources: list[dict[str, Any]] = []
        for item in top_pages:
            sources.extend(item["raw_sources"])
        sources = self._dedupe_chat_sources(sources)

        min_score = float(settings.get("compilation_min_score", 0.82))
        min_sources = int(settings.get("compilation_min_supporting_source_count", 2))
        allow_warning = bool(settings.get("compilation_allow_with_warning", False))

        fallback_reason = None
        if not page_hits:
            fallback_reason = "no_compiled_page_hit"
        elif page_hits[0]["score"] < min_score:
            fallback_reason = "score_below_threshold"
        elif page_hits[0]["supporting_source_count"] < min_sources:
            fallback_reason = "supporting_sources_insufficient"
        elif page_hits[0]["health_status"] == "warning" and not allow_warning:
            fallback_reason = "warning_page_not_allowed"

        reference_items: list[dict[str, Any]] = []
        if not fallback_reason:
            reference_items = [item["reference_item"] for item in top_pages]

        return {
            "enabled": True,
            "strategy": strategy,
            "page_hits": page_hits,
            "fallback_reason": fallback_reason,
            "reference_items": reference_items,
            "usable": not fallback_reason,
            "selected_mode": "compiled" if not fallback_reason else "fallback_to_raw",
            "raw_sources": sources,
        }

    def _get_page(self, project_id: int, kb_id: int, page_id: int) -> KnowledgeCompilationPage | None:
        return (
            self.db.query(KnowledgeCompilationPage)
            .filter(
                KnowledgeCompilationPage.project_id == project_id,
                KnowledgeCompilationPage.kb_id == kb_id,
                KnowledgeCompilationPage.id == page_id,
                KnowledgeCompilationPage.deleted_at.is_(None),
            )
            .first()
        )

    def _get_writeback_candidate(
        self, project_id: int, kb_id: int, candidate_id: int
    ) -> KnowledgeCompilationWritebackCandidate | None:
        return (
            self.db.query(KnowledgeCompilationWritebackCandidate)
            .filter(
                KnowledgeCompilationWritebackCandidate.project_id == project_id,
                KnowledgeCompilationWritebackCandidate.kb_id == kb_id,
                KnowledgeCompilationWritebackCandidate.id == candidate_id,
            )
            .first()
        )

    def _find_chat_session(self, project_id: int, session_ref: Any) -> ChatSession | None:
        if session_ref is None:
            return None
        return (
            self.db.query(ChatSession)
            .filter(
                ChatSession.project_id == project_id,
                or_(
                    ChatSession.session_code == str(session_ref),
                    ChatSession.id == int(session_ref) if str(session_ref).isdigit() else -1,
                ),
            )
            .first()
        )

    def _find_chat_message(self, session_id: int | None, message_id: Any) -> ChatMessage | None:
        if session_id is None or message_id is None:
            return None
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.id == int(message_id))
            .first()
        )

    def _create_version(
        self,
        page: KnowledgeCompilationPage,
        title: str,
        summary: str | None,
        content_markdown: str,
        change_summary: str,
        created_by: int | None,
        sources_snapshot: list[dict[str, Any]] | None = None,
    ) -> KnowledgeCompilationPageVersion:
        latest_version = (
            self.db.query(KnowledgeCompilationPageVersion)
            .filter(KnowledgeCompilationPageVersion.page_id == page.id)
            .order_by(KnowledgeCompilationPageVersion.version_no.desc(), KnowledgeCompilationPageVersion.id.desc())
            .first()
        )
        if latest_version:
            latest_version.is_current = False
            next_version = int(latest_version.version_no or 0) + 1
        else:
            next_version = 1
        version = KnowledgeCompilationPageVersion(
            page_id=page.id,
            version_no=next_version,
            title=title,
            summary=summary,
            content_markdown=content_markdown,
            sources_snapshot_json=sources_snapshot or [],
            change_summary=change_summary,
            is_current=True,
            created_by=created_by,
        )
        self.db.add(version)
        self.db.flush()
        return version

    def _build_reference_item(self, page: KnowledgeCompilationPage) -> dict[str, Any]:
        snippet_source = (page.summary or page.content_markdown or "").strip()
        snippet = re.sub(r"\s+", " ", snippet_source)[:320]
        return {
            "title": page.title,
            "document_name": f"編譯知識頁/{page.page_type}",
            "snippet": snippet,
            "source_url": None,
            "source_kind": "compiled_page",
            "compilation_page_id": page.id,
            "compilation_page_type": page.page_type,
            "compilation_version_no": page.version_no,
            "score": round(float(page.retrieval_priority or 100), 4),
        }

    def _list_page_source_entities(self, page_id: int, limit: int | None = None) -> list[KnowledgeCompilationPageSource]:
        query = (
            self.db.query(KnowledgeCompilationPageSource)
            .filter(KnowledgeCompilationPageSource.page_id == page_id)
            .order_by(KnowledgeCompilationPageSource.order_no.asc(), KnowledgeCompilationPageSource.id.asc())
        )
        if limit is not None:
            query = query.limit(limit)
        return query.all()

    def _score_compilation_page(
        self,
        *,
        query: str,
        query_tokens: set[str],
        page: KnowledgeCompilationPage,
        sources: list[KnowledgeCompilationPageSource],
    ) -> float:
        title_text = " ".join(filter(None, [page.title, page.canonical_title]))
        summary_text = page.summary or ""
        content_text = page.content_markdown or ""
        title_tokens = self._tokenize_text(title_text)
        summary_tokens = self._tokenize_text(summary_text)
        content_tokens = self._tokenize_text(content_text[:1200])

        if not query_tokens:
            return 0.0

        title_overlap = len(query_tokens & title_tokens) / max(len(query_tokens), 1)
        summary_overlap = len(query_tokens & summary_tokens) / max(len(query_tokens), 1)
        content_overlap = len(query_tokens & content_tokens) / max(len(query_tokens), 1)
        exact_title_hit = query.strip() and query.strip().lower() in title_text.lower()
        exact_summary_hit = query.strip() and query.strip().lower() in summary_text.lower()
        if title_overlap <= 0 and summary_overlap <= 0 and content_overlap <= 0 and not exact_title_hit and not exact_summary_hit:
            return 0.0

        base_score = (
            title_overlap * 0.48
            + summary_overlap * 0.22
            + content_overlap * 0.18
            + (0.12 if exact_title_hit else 0.0)
            + (0.06 if exact_summary_hit else 0.0)
        )
        source_bonus = min(len(sources), 5) * 0.03
        health_bonus = 0.0
        if page.health_status == "healthy":
            health_bonus = 0.04
        elif page.health_status == "warning":
            health_bonus = -0.04
        elif page.health_status == "critical":
            health_bonus = -0.12

        freshness_bonus = 0.0
        freshness_anchor = page.last_compiled_at or page.published_at or page.updated_at
        if freshness_anchor:
            age_days = max((datetime.utcnow() - freshness_anchor).days, 0)
            if age_days <= 30:
                freshness_bonus = 0.05
            elif age_days <= 90:
                freshness_bonus = 0.02
            elif age_days >= 365:
                freshness_bonus = -0.04

        return round(min(max(base_score + source_bonus + health_bonus + freshness_bonus, 0.0), 1.0), 4)

    def _tokenize_text(self, text: str | None) -> set[str]:
        normalized = re.sub(r"\s+", " ", str(text or "").strip().lower())
        if not normalized:
            return set()
        ascii_tokens = {token for token in re.split(r"[^0-9a-z]+", normalized) if len(token) >= 2}
        han_segments = re.findall(r"[\u4e00-\u9fff]{2,}", normalized)
        han_tokens: set[str] = set()
        for segment in han_segments:
            han_tokens.add(segment)
            if len(segment) <= 4:
                continue
            for start in range(len(segment) - 1):
                han_tokens.add(segment[start : start + 2])
            for start in range(len(segment) - 2):
                han_tokens.add(segment[start : start + 3])
        return ascii_tokens | han_tokens

    def _serialize_chat_source(self, source: KnowledgeCompilationPageSource) -> dict[str, Any]:
        return {
            "source_type": source.source_type,
            "source_id": source.source_id,
            "source_ref_id": source.source_ref_id,
            "title": source.source_title,
            "score": float(source.weight or 1),
            "support_type": source.support_type,
            "source_locator": dict(source.source_locator_json or {}),
            "quote": source.source_quote,
        }

    def _dedupe_chat_sources(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for item in items:
            key = (
                str(item.get("source_type") or ""),
                str(item.get("source_id") or ""),
                str(item.get("source_ref_id") or ""),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _create_page_record(
        self,
        project_id: int,
        kb_id: int,
        payload: dict[str, Any],
        current_user_id: int | None,
    ) -> KnowledgeCompilationPage:
        page = KnowledgeCompilationPage(
            project_id=project_id,
            kb_id=kb_id,
            page_type=payload.get("page_type", "topic"),
            topic_key=payload.get("topic_key"),
            canonical_title=payload.get("canonical_title") or payload.get("title") or "未命名頁面",
            title=payload.get("title") or payload.get("canonical_title") or "未命名頁面",
            summary=payload.get("summary"),
            content_markdown=payload.get("content_markdown") or "",
            tags_json=payload.get("tags") or [],
            metadata_json=payload.get("metadata") or {},
            status=payload.get("status", "draft"),
            created_by=current_user_id,
            updated_by=current_user_id,
        )
        self.db.add(page)
        self.db.flush()

        source_refs = payload.get("source_refs") or []
        version = self._create_version(
            page=page,
            title=page.title,
            summary=page.summary,
            content_markdown=page.content_markdown,
            change_summary=payload.get("change_summary") or "initial_create",
            created_by=current_user_id,
            sources_snapshot=self._merge_source_snapshots([], source_refs),
        )
        page.current_version_id = version.id
        page.version_no = version.version_no
        if page.status == "published":
            page.published_version_id = version.id
            page.published_at = datetime.utcnow()

        for node_id in payload.get("tree_node_ids") or []:
            self.db.add(
                KnowledgeCompilationPageTreeLink(
                    page_id=page.id,
                    node_id=int(node_id),
                    link_type="primary",
                )
            )

        self._attach_page_sources(page_id=page.id, version_id=version.id, source_refs=source_refs)
        self._log_operation(
            project_id=project_id,
            operator_id=current_user_id,
            operation_type="create_compilation_page",
            target_type="knowledge_compilation_page",
            target_id=page.id,
            detail={
                "kb_id": kb_id,
                "page_type": page.page_type,
                "status": page.status,
            },
        )
        return page

    def _attach_page_sources(
        self,
        *,
        page_id: int,
        version_id: int | None,
        source_refs: list[dict[str, Any]],
        skip_existing: bool = False,
    ) -> None:
        next_order = self._get_next_source_order(page_id)
        for source_ref in source_refs:
            source_type = source_ref.get("source_type", "manual")
            source_id = str(source_ref.get("source_id") or "")
            source_ref_id = source_ref.get("source_ref_id")
            if skip_existing and self._page_source_exists(page_id, source_type, source_id, source_ref_id):
                continue
            self.db.add(
                KnowledgeCompilationPageSource(
                    page_id=page_id,
                    version_id=version_id,
                    source_type=source_type,
                    source_id=source_id,
                    source_ref_id=source_ref_id,
                    source_title=source_ref.get("source_title") or source_ref.get("source_id") or "source",
                    source_locator_json=source_ref.get("source_locator") or {},
                    source_quote=source_ref.get("quote"),
                    source_snapshot=source_ref.get("source_snapshot") or {},
                    claim_text=source_ref.get("claim_text"),
                    support_type=source_ref.get("support_type", "supports"),
                    weight=float(source_ref.get("weight", 1)),
                    order_no=int(source_ref.get("order_no", next_order)),
                )
            )
            next_order += 1

    def _get_next_source_order(self, page_id: int) -> int:
        latest = (
            self.db.query(KnowledgeCompilationPageSource)
            .filter(KnowledgeCompilationPageSource.page_id == page_id)
            .order_by(KnowledgeCompilationPageSource.order_no.desc(), KnowledgeCompilationPageSource.id.desc())
            .first()
        )
        return int((latest.order_no if latest else 0) or 0) + 1

    def _page_source_exists(self, page_id: int, source_type: str, source_id: str, source_ref_id: str | None) -> bool:
        query = self.db.query(KnowledgeCompilationPageSource).filter(
            KnowledgeCompilationPageSource.page_id == page_id,
            KnowledgeCompilationPageSource.source_type == source_type,
            KnowledgeCompilationPageSource.source_id == source_id,
        )
        if source_ref_id is None:
            query = query.filter(KnowledgeCompilationPageSource.source_ref_id.is_(None))
        else:
            query = query.filter(KnowledgeCompilationPageSource.source_ref_id == source_ref_id)
        return self.db.query(query.exists()).scalar() or False

    def _list_page_source_snapshots(self, page_id: int) -> list[dict[str, Any]]:
        items = (
            self.db.query(KnowledgeCompilationPageSource)
            .filter(KnowledgeCompilationPageSource.page_id == page_id)
            .order_by(KnowledgeCompilationPageSource.order_no.asc(), KnowledgeCompilationPageSource.id.asc())
            .all()
        )
        return [self._serialize_source(item) for item in items]

    def _build_writeback_source_refs(self, item: KnowledgeCompilationWritebackCandidate) -> list[dict[str, Any]]:
        source_refs: list[dict[str, Any]] = []
        for index, source in enumerate(item.source_docs_snapshot or [], start=1):
            source_type = str(source.get("source_type") or "manual")
            source_id = source.get("source_id")
            if not source_id:
                continue
            source_refs.append(
                {
                    "source_type": source_type,
                    "source_id": str(source_id),
                    "source_ref_id": source.get("source_ref_id"),
                    "source_title": source.get("title") or source.get("document_name") or str(source_id),
                    "source_locator": source.get("source_locator") or {},
                    "quote": source.get("quote") or source.get("snippet"),
                    "source_snapshot": source,
                    "claim_text": item.question,
                    "support_type": str(source.get("support_type") or "derived_from"),
                    "weight": float(source.get("score") or 1),
                    "order_no": index,
                }
            )
        if not source_refs:
            source_refs.append(
                {
                    "source_type": "chat_message",
                    "source_id": str(item.chat_message_id),
                    "source_ref_id": str(item.chat_session_id),
                    "source_title": item.suggested_title or f"chat_message:{item.chat_message_id}",
                    "source_locator": {"chat_session_id": item.chat_session_id, "chat_message_id": item.chat_message_id},
                    "quote": item.answer[:500],
                    "source_snapshot": {
                        "question": item.question,
                        "answer": item.answer,
                    },
                    "claim_text": item.question,
                    "support_type": "derived_from",
                    "weight": 1,
                    "order_no": 1,
                }
            )
        return source_refs

    def _merge_source_snapshots(
        self, base_sources: list[dict[str, Any]], extra_source_refs: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        merged = list(base_sources)
        seen = {
            (
                str(item.get("source_type") or ""),
                str(item.get("source_id") or ""),
                str(item.get("source_ref_id") or ""),
            )
            for item in merged
        }
        for source_ref in extra_source_refs:
            key = (
                str(source_ref.get("source_type") or ""),
                str(source_ref.get("source_id") or ""),
                str(source_ref.get("source_ref_id") or ""),
            )
            if key in seen:
                continue
            merged.append(
                {
                    "source_type": source_ref.get("source_type"),
                    "source_id": source_ref.get("source_id"),
                    "source_ref_id": source_ref.get("source_ref_id"),
                    "source_title": source_ref.get("source_title"),
                    "source_locator": source_ref.get("source_locator") or {},
                    "quote": source_ref.get("quote"),
                    "source_snapshot": source_ref.get("source_snapshot") or {},
                    "claim_text": source_ref.get("claim_text"),
                    "support_type": source_ref.get("support_type", "supports"),
                    "weight": float(source_ref.get("weight", 1)),
                    "order_no": int(source_ref.get("order_no", len(merged) + 1)),
                }
            )
            seen.add(key)
        return merged

    def _log_operation(
        self,
        *,
        project_id: int | None,
        operator_id: int | None,
        operation_type: str,
        target_type: str,
        target_id: int | None,
        detail: dict[str, Any],
    ) -> None:
        if operator_id is None:
            return
        self.db.add(
            OperationLog(
                project_id=project_id,
                operator_id=operator_id,
                operation_type=operation_type,
                target_type=target_type,
                target_id=target_id,
                detail_json=detail,
            )
        )

    def _serialize_page(self, item: KnowledgeCompilationPage | None) -> dict | None:
        if not item:
            return None
        return {
            "id": item.id,
            "project_id": item.project_id,
            "kb_id": item.kb_id,
            "page_type": item.page_type,
            "topic_key": item.topic_key,
            "canonical_title": item.canonical_title,
            "title": item.title,
            "summary": item.summary,
            "content_markdown": item.content_markdown,
            "tags": item.tags_json or [],
            "metadata": item.metadata_json or {},
            "status": item.status,
            "health_status": item.health_status,
            "retrieval_priority": item.retrieval_priority,
            "version_no": item.version_no,
            "current_version_id": item.current_version_id,
            "published_version_id": item.published_version_id,
            "last_compiled_at": item.last_compiled_at.isoformat() if item.last_compiled_at else None,
            "published_at": item.published_at.isoformat() if item.published_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    def _serialize_version(self, item: KnowledgeCompilationPageVersion | None) -> dict | None:
        if not item:
            return None
        return {
            "id": item.id,
            "page_id": item.page_id,
            "version_no": item.version_no,
            "title": item.title,
            "summary": item.summary,
            "content_markdown": item.content_markdown,
            "sources_snapshot_json": item.sources_snapshot_json or [],
            "change_summary": item.change_summary,
            "run_id": item.run_id,
            "is_current": item.is_current,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_source(self, item: KnowledgeCompilationPageSource) -> dict:
        return {
            "id": item.id,
            "page_id": item.page_id,
            "version_id": item.version_id,
            "source_type": item.source_type,
            "source_id": item.source_id,
            "source_ref_id": item.source_ref_id,
            "source_title": item.source_title,
            "source_locator": item.source_locator_json or {},
            "quote": item.source_quote,
            "source_snapshot": item.source_snapshot or {},
            "claim_text": item.claim_text,
            "support_type": item.support_type,
            "weight": float(item.weight or 0),
            "order_no": item.order_no,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_link(self, item: KnowledgeCompilationPageLink) -> dict:
        return {
            "id": item.id,
            "project_id": item.project_id,
            "kb_id": item.kb_id,
            "from_page_id": item.from_page_id,
            "to_page_id": item.to_page_id,
            "link_type": item.link_type,
            "anchor_text": item.anchor_text,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_run(self, item: KnowledgeCompilationRun | None) -> dict | None:
        if not item:
            return None
        return {
            "id": item.id,
            "project_id": item.project_id,
            "kb_id": item.kb_id,
            "page_id": item.page_id,
            "run_type": item.run_type,
            "trigger_type": item.trigger_type,
            "strategy": item.strategy,
            "status": item.status,
            "idempotency_key": item.idempotency_key,
            "request_payload": item.request_payload or {},
            "result_payload": item.result_payload or {},
            "error_message": item.error_message,
            "started_at": item.started_at.isoformat() if item.started_at else None,
            "finished_at": item.finished_at.isoformat() if item.finished_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_health_run(self, item: KnowledgeCompilationHealthRun | None) -> dict | None:
        if not item:
            return None
        return {
            "id": item.id,
            "project_id": item.project_id,
            "kb_id": item.kb_id,
            "page_id": item.page_id,
            "version_id": item.version_id,
            "run_type": item.run_type,
            "status": item.status,
            "summary": item.summary_json or {},
            "started_at": item.started_at.isoformat() if item.started_at else None,
            "finished_at": item.finished_at.isoformat() if item.finished_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_health_finding(self, item: KnowledgeCompilationHealthFinding) -> dict:
        return {
            "id": item.id,
            "health_run_id": item.health_run_id,
            "page_id": item.page_id,
            "page_version_id": item.page_version_id,
            "check_type": item.check_type,
            "severity": item.severity,
            "status": item.status,
            "finding_title": item.finding_title,
            "finding_detail": item.finding_detail,
            "evidence": item.evidence_json or {},
            "suggested_action": item.suggested_action,
            "resolved_by": item.resolved_by,
            "resolved_at": item.resolved_at.isoformat() if item.resolved_at else None,
            "created_at": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_writeback_candidate(self, item: KnowledgeCompilationWritebackCandidate) -> dict:
        return {
            "id": item.id,
            "project_id": item.project_id,
            "kb_id": item.kb_id,
            "chat_session_id": item.chat_session_id,
            "chat_message_id": item.chat_message_id,
            "question": item.question,
            "answer": item.answer,
            "source_docs_snapshot": item.source_docs_snapshot or [],
            "suggested_page_id": item.suggested_page_id,
            "suggested_page_type": item.suggested_page_type,
            "suggested_title": item.suggested_title,
            "status": item.status,
            "review_note": item.review_note,
            "merged_version_id": item.merged_version_id,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
        }
