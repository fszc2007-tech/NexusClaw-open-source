from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, index=True)
    document_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    content: Mapped[str] = mapped_column(Text)
    keywords_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    source_type: Mapped[str] = mapped_column(String(32), default="manual")
    source_file_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    source_meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    source_org: Mapped[str | None] = mapped_column(String(128), nullable=True)
    owner_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="editing", index=True)
    governance_status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    normalized_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    duplicate_of_knowledge_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    superseded_by_knowledge_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    review_sla_days: Mapped[int] = mapped_column(Integer, default=90)
    source_snapshot_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_snapshot_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version_no: Mapped[int] = mapped_column(BigInteger, default=1)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, index=True)
    source_kind: Mapped[str] = mapped_column(String(32), index=True)
    source_item_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    file_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    document_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    lexical_text: Mapped[str] = mapped_column(Text)
    contextual_text: Mapped[str] = mapped_column(Text)
    citation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    parent_chunk_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chunk_meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    authority_level: Mapped[int] = mapped_column(Integer, default=50, index=True)
    source_rank: Mapped[float] = mapped_column(Float, default=1.0)
    region: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    route_kind: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    subject_type: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    parent: Mapped["KnowledgeChunk | None"] = relationship(
        "KnowledgeChunk",
        remote_side=[id],
        foreign_keys=[parent_chunk_id],
        uselist=False,
    )


Index(
    "ix_knowledge_chunks_project_kb_status_kind",
    KnowledgeChunk.project_id,
    KnowledgeChunk.kb_id,
    KnowledgeChunk.status,
    KnowledgeChunk.source_kind,
)

Index(
    "ix_knowledge_chunks_project_file_chunkidx",
    KnowledgeChunk.project_id,
    KnowledgeChunk.file_id,
    KnowledgeChunk.chunk_index,
)


class ChunkRelation(Base):
    __tablename__ = "chunk_relations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    from_chunk_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        index=True,
    )
    to_chunk_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("knowledge_chunks.id", ondelete="CASCADE"),
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String(32), index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


Index(
    "ix_chunk_relations_from_type",
    ChunkRelation.from_chunk_id,
    ChunkRelation.relation_type,
)


class KnowledgeDedupRecord(Base):
    __tablename__ = "knowledge_dedup_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    new_knowledge_id: Mapped[int] = mapped_column(BigInteger, index=True)
    old_knowledge_id: Mapped[int] = mapped_column(BigInteger, index=True)
    score: Mapped[float] = mapped_column(Numeric(5, 4))
    dedup_level: Mapped[str] = mapped_column(String(16), default="low")
    action: Mapped[str] = mapped_column(String(32), default="pending")
    reason_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class KnowledgeGovernanceTask(Base):
    __tablename__ = "knowledge_governance_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    knowledge_id: Mapped[int] = mapped_column(BigInteger, index=True)
    task_type: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    reason: Mapped[str] = mapped_column(String(255))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
