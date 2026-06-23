"""knowledge source governance

Revision ID: 20260424_0013
Revises: 20260424_0012
Create Date: 2026-04-24 16:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0013"
down_revision = "20260424_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.BigInteger(), nullable=True))
        batch_op.add_column(sa.Column("review_sla_days", sa.Integer(), nullable=False, server_default="90"))
        batch_op.add_column(sa.Column("source_snapshot_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("source_last_checked_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_knowledge_items_owner_user_id", ["owner_user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.drop_index("ix_knowledge_items_owner_user_id")
        batch_op.drop_column("source_last_checked_at")
        batch_op.drop_column("source_snapshot_hash")
        batch_op.drop_column("review_sla_days")
        batch_op.drop_column("owner_user_id")
