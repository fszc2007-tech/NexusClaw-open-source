from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    legacy_name: Mapped[str] = mapped_column("name", String(128), index=True)
    company_name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ProjectMember(Base):
    __tablename__ = "project_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    project_role: Mapped[str] = mapped_column(String(32), default="project_member")
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ProjectPersona(Base):
    __tablename__ = "project_persona"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    assistant_name: Mapped[str] = mapped_column(String(64))
    assistant_role: Mapped[str] = mapped_column(String(128))
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    opening_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_questions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ProjectSetting(Base):
    __tablename__ = "project_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    opening_mode: Mapped[str] = mapped_column(String(32), default="card")
    opening_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    hot_questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    hot_policies: Mapped[list[str]] = mapped_column(JSON, default=list)
    prompt_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    capability_multi_turn: Mapped[bool] = mapped_column(Boolean, default=True)
    capability_memory: Mapped[bool] = mapped_column(Boolean, default=True)
    capability_sensitive_detection: Mapped[bool] = mapped_column(Boolean, default=True)
    capability_gov_domain_check: Mapped[bool] = mapped_column(Boolean, default=True)
    capability_knowledge_tree: Mapped[bool] = mapped_column(Boolean, default=False)
    capability_knowledge_compilation: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_scope: Mapped[str] = mapped_column(String(32), default="session_only")
    memory_ttl_days: Mapped[int] = mapped_column(Integer, default=7)
    preference_memory_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    compilation_strategy: Mapped[str] = mapped_column(String(32), default="compiled_first")
    compilation_min_score: Mapped[float] = mapped_column(default=0.82)
    compilation_min_supporting_source_count: Mapped[int] = mapped_column(Integer, default=2)
    compilation_allow_with_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled_scene_keys_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    scene_entry_mode: Mapped[str] = mapped_column(String(32), default="chat")
    scene_runtime_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
