from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.core.config import settings
from app.core.database import Base
from app.models.project import Project, ProjectMember, ProjectSetting
from app.models.knowledge import (
    ChunkRelation,
    KnowledgeBase,
    KnowledgeChunk,
    KnowledgeDedupRecord,
    KnowledgeGovernanceTask,
    KnowledgeItem,
)
from app.models.chat import ChatSession, ChatMessage
from app.models.evaluation import EvaluationDataset, EvaluationDatasetItem
from app.models.file import FileRecord, FileTask
from app.models.scene import SceneCase, SceneEvent
from app.models.user import OperationLog, User, UserSession
from app.models.knowledge_compilation import (
    KnowledgeCompilationHealthFinding,
    KnowledgeCompilationHealthRun,
    KnowledgeCompilationPage,
    KnowledgeCompilationPageLink,
    KnowledgeCompilationPageSource,
    KnowledgeCompilationPageTreeLink,
    KnowledgeCompilationPageVersion,
    KnowledgeCompilationRun,
    KnowledgeCompilationRunItem,
    KnowledgeCompilationWritebackCandidate,
)

config = context.config
config.set_main_option("sqlalchemy.url", settings.mysql_dsn)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.mysql_dsn,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
