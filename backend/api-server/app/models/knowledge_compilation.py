from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KnowledgeCompilationPage(Base):
    __tablename__ = "knowledge_compilation_pages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, index=True)
    page_type: Mapped[str] = mapped_column(String(32), default="topic", index=True)
    topic_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    canonical_title: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_markdown: Mapped[str] = mapped_column(Text)
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    health_status: Mapped[str] = mapped_column(String(32), default="unknown", index=True)
    retrieval_priority: Mapped[int] = mapped_column(Integer, default=100)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    current_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    published_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_compiled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class KnowledgeCompilationPageVersion(Base):
    __tablename__ = "knowledge_compilation_page_versions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    page_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_compilation_pages.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_markdown: Mapped[str] = mapped_column(Text)
    sources_snapshot_json: Mapped[list[dict]] = mapped_column(JSON, default=list)
    change_summary: Mapped[str | None] = mapped_column(String(255), nullable=True)
    run_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeCompilationPageSource(Base):
    __tablename__ = "knowledge_compilation_page_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    page_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_compilation_pages.id"), index=True)
    version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    source_ref_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_title: Mapped[str] = mapped_column(String(255))
    source_locator_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    claim_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_type: Mapped[str] = mapped_column(String(32), default="supports")
    weight: Mapped[float] = mapped_column(Numeric(8, 4), default=1)
    order_no: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeCompilationPageLink(Base):
    __tablename__ = "knowledge_compilation_page_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, index=True)
    from_page_id: Mapped[int] = mapped_column(BigInteger, index=True)
    to_page_id: Mapped[int] = mapped_column(BigInteger, index=True)
    link_type: Mapped[str] = mapped_column(String(32), default="related")
    anchor_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeCompilationPageTreeLink(Base):
    __tablename__ = "knowledge_compilation_page_tree_links"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    page_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_compilation_pages.id"), index=True)
    node_id: Mapped[int] = mapped_column(BigInteger, index=True)
    link_type: Mapped[str] = mapped_column(String(32), default="primary")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeCompilationRun(Base):
    __tablename__ = "knowledge_compilation_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, index=True)
    page_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    run_type: Mapped[str] = mapped_column(String(32), default="recompile")
    trigger_type: Mapped[str] = mapped_column(String(32), default="manual")
    strategy: Mapped[str] = mapped_column(String(32), default="compiled_first")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KnowledgeCompilationRunItem(Base):
    __tablename__ = "knowledge_compilation_run_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_compilation_runs.id"), index=True)
    page_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(128))
    action_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    before_version_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    after_version_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeCompilationHealthRun(Base):
    __tablename__ = "knowledge_compilation_health_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, index=True)
    page_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    run_type: Mapped[str] = mapped_column(String(32), default="full_scan")
    status: Mapped[str] = mapped_column(String(32), default="queued")
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KnowledgeCompilationHealthFinding(Base):
    __tablename__ = "knowledge_compilation_health_findings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    health_run_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("knowledge_compilation_health_runs.id"), index=True)
    page_id: Mapped[int] = mapped_column(BigInteger, index=True)
    page_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    check_type: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="warning", index=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    finding_title: Mapped[str] = mapped_column(String(255))
    finding_detail: Mapped[str] = mapped_column(Text)
    evidence_json: Mapped[dict] = mapped_column(JSON, default=dict)
    suggested_action: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeCompilationWritebackCandidate(Base):
    __tablename__ = "knowledge_compilation_writeback_candidates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_session_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    source_docs_snapshot: Mapped[list[dict]] = mapped_column(JSON, default=list)
    suggested_page_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    suggested_page_type: Mapped[str] = mapped_column(String(32), default="answer_writeback")
    suggested_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    review_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    merged_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
