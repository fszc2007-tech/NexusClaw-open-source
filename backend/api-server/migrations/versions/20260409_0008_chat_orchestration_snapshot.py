"""chat orchestration snapshot

Revision ID: 20260409_0008
Revises: 20260406_0007
Create Date: 2026-04-09 15:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260409_0008"
down_revision = "20260406_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.add_column(sa.Column("orchestration_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_column("orchestration_json")
