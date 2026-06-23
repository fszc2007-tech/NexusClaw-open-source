from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, index=True)
    file_name: Mapped[str] = mapped_column(String(255), index=True)
    file_ext: Mapped[str | None] = mapped_column(String(16), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    storage_path: Mapped[str] = mapped_column(String(255))
    preview_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parsed_document_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parser_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parse_meta_json: Mapped[dict] = mapped_column(JSON, default=dict)
    overwrite_same_name: Mapped[bool] = mapped_column(default=False)
    parse_status: Mapped[str] = mapped_column(String(32), default="uploaded")
    chunk_status: Mapped[str] = mapped_column(String(32), default="pending")
    qa_status: Mapped[str] = mapped_column(String(32), default="pending")
    parse_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class FileTask(Base):
    __tablename__ = "file_tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, index=True)
    file_id: Mapped[int] = mapped_column(BigInteger, index=True)
    task_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
