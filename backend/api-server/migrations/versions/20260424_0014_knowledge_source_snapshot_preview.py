"""knowledge source snapshot preview

Revision ID: 20260424_0014
Revises: 20260424_0013
Create Date: 2026-04-24 18:35:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260424_0014"
down_revision = "20260424_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.add_column(sa.Column("source_snapshot_preview", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.drop_column("source_snapshot_preview")
