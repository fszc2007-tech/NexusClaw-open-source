"""scene framework

Revision ID: 20260406_0006
Revises: 20260406_0005
Create Date: 2026-04-06 22:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260406_0006"
down_revision = "20260406_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("project_settings") as batch_op:
        batch_op.add_column(sa.Column("enabled_scene_keys_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("scene_entry_mode", sa.String(length=32), nullable=False, server_default="chat"))
        batch_op.add_column(sa.Column("scene_runtime_config_json", sa.JSON(), nullable=True))

    op.execute(
        """
        UPDATE project_settings
        SET enabled_scene_keys_json = JSON_ARRAY('hk_tax_address_change')
        WHERE enabled_scene_keys_json IS NULL
        """
    )
    op.execute(
        """
        UPDATE project_settings
        SET scene_runtime_config_json = JSON_OBJECT('mail_delivery_mode', 'draft_only')
        WHERE scene_runtime_config_json IS NULL
        """
    )

    with op.batch_alter_table("project_settings") as batch_op:
        batch_op.alter_column("enabled_scene_keys_json", existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column("scene_runtime_config_json", existing_type=sa.JSON(), nullable=False)

    op.create_table(
        "scene_cases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("case_code", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("session_id", sa.BigInteger(), nullable=False),
        sa.Column("scene_key", sa.String(length=64), nullable=False),
        sa.Column("route_key", sa.String(length=64), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=False, server_default="START"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("artifacts_json", sa.JSON(), nullable=False),
        sa.Column("flags_json", sa.JSON(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("last_error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_scene_cases_case_code", "scene_cases", ["case_code"], unique=True)
    op.create_index("ix_scene_cases_project_id", "scene_cases", ["project_id"], unique=False)
    op.create_index("ix_scene_cases_session_id", "scene_cases", ["session_id"], unique=False)
    op.create_index("ix_scene_cases_scene_key", "scene_cases", ["scene_key"], unique=False)
    op.create_index("ix_scene_cases_route_key", "scene_cases", ["route_key"], unique=False)
    op.create_index("ix_scene_cases_state", "scene_cases", ["state"], unique=False)
    op.create_index("ix_scene_cases_status", "scene_cases", ["status"], unique=False)

    op.create_table(
        "scene_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("case_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False, server_default="system"),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_scene_events_case_id", "scene_events", ["case_id"], unique=False)
    op.create_index("ix_scene_events_event_type", "scene_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_scene_events_event_type", table_name="scene_events")
    op.drop_index("ix_scene_events_case_id", table_name="scene_events")
    op.drop_table("scene_events")

    op.drop_index("ix_scene_cases_status", table_name="scene_cases")
    op.drop_index("ix_scene_cases_state", table_name="scene_cases")
    op.drop_index("ix_scene_cases_route_key", table_name="scene_cases")
    op.drop_index("ix_scene_cases_scene_key", table_name="scene_cases")
    op.drop_index("ix_scene_cases_session_id", table_name="scene_cases")
    op.drop_index("ix_scene_cases_project_id", table_name="scene_cases")
    op.drop_index("ix_scene_cases_case_code", table_name="scene_cases")
    op.drop_table("scene_cases")

    with op.batch_alter_table("project_settings") as batch_op:
        batch_op.drop_column("scene_runtime_config_json")
        batch_op.drop_column("scene_entry_mode")
        batch_op.drop_column("enabled_scene_keys_json")
