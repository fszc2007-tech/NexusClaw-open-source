"""chat memory mvp

Revision ID: 20260405_0004
Revises: 20260405_0003
Create Date: 2026-04-05 23:59:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0004"
down_revision = "20260405_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_settings") as batch_op:
        batch_op.add_column(
            sa.Column("capability_memory", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        )
        batch_op.add_column(
            sa.Column("memory_scope", sa.String(length=32), nullable=False, server_default="session_only")
        )
        batch_op.add_column(
            sa.Column("memory_ttl_days", sa.Integer(), nullable=False, server_default="7")
        )
        batch_op.add_column(
            sa.Column("preference_memory_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )

    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.add_column(sa.Column("state_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.add_column(
            sa.Column("used_memory", sa.Boolean(), nullable=False, server_default=sa.text("0"))
        )
        batch_op.add_column(sa.Column("memory_snapshot_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("safety_flags_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_column("safety_flags_json")
        batch_op.drop_column("memory_snapshot_json")
        batch_op.drop_column("used_memory")

    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.drop_column("state_json")

    with op.batch_alter_table("project_settings") as batch_op:
        batch_op.drop_column("preference_memory_enabled")
        batch_op.drop_column("memory_ttl_days")
        batch_op.drop_column("memory_scope")
        batch_op.drop_column("capability_memory")
