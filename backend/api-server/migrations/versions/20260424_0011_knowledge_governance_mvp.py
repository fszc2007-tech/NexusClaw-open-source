"""knowledge governance mvp

Revision ID: 20260424_0011
Revises: 20260413_0010
Create Date: 2026-04-24 12:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0011"
down_revision = "20260413_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.add_column(sa.Column("governance_status", sa.String(length=32), nullable=False, server_default="active"))
        batch_op.add_column(sa.Column("normalized_content_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("duplicate_of_knowledge_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("superseded_by_knowledge_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("last_verified_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_knowledge_items_governance_status", ["governance_status"], unique=False)
        batch_op.create_index("ix_knowledge_items_normalized_content_hash", ["normalized_content_hash"], unique=False)

    with op.batch_alter_table("knowledge_dedup_records") as batch_op:
        batch_op.add_column(sa.Column("reviewed_by", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("reviewed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("knowledge_dedup_records") as batch_op:
        batch_op.drop_column("reviewed_at")
        batch_op.drop_column("reviewed_by")

    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.drop_index("ix_knowledge_items_normalized_content_hash")
        batch_op.drop_index("ix_knowledge_items_governance_status")
        batch_op.drop_column("last_verified_at")
        batch_op.drop_column("superseded_by_knowledge_id")
        batch_op.drop_column("duplicate_of_knowledge_id")
        batch_op.drop_column("normalized_content_hash")
        batch_op.drop_column("governance_status")
