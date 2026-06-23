"""knowledge freshness mvp

Revision ID: 20260424_0012
Revises: 20260424_0011
Create Date: 2026-04-24 14:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0012"
down_revision = "20260424_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.add_column(sa.Column("source_url", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("source_org", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("review_due_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_knowledge_items_review_due_at", ["review_due_at"], unique=False)

    op.create_table(
        "knowledge_governance_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("knowledge_id", sa.BigInteger(), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("comment", sa.String(length=255), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_knowledge_governance_tasks_project_id", "knowledge_governance_tasks", ["project_id"], unique=False)
    op.create_index("ix_knowledge_governance_tasks_knowledge_id", "knowledge_governance_tasks", ["knowledge_id"], unique=False)
    op.create_index("ix_knowledge_governance_tasks_task_type", "knowledge_governance_tasks", ["task_type"], unique=False)
    op.create_index("ix_knowledge_governance_tasks_status", "knowledge_governance_tasks", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_knowledge_governance_tasks_status", table_name="knowledge_governance_tasks")
    op.drop_index("ix_knowledge_governance_tasks_task_type", table_name="knowledge_governance_tasks")
    op.drop_index("ix_knowledge_governance_tasks_knowledge_id", table_name="knowledge_governance_tasks")
    op.drop_index("ix_knowledge_governance_tasks_project_id", table_name="knowledge_governance_tasks")
    op.drop_table("knowledge_governance_tasks")

    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.drop_index("ix_knowledge_items_review_due_at")
        batch_op.drop_column("review_due_at")
        batch_op.drop_column("source_org")
        batch_op.drop_column("source_url")
