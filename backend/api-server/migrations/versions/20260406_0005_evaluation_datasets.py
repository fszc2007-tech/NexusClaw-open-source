"""evaluation datasets

Revision ID: 20260406_0005
Revises: 20260405_0004
Create Date: 2026-04-06 13:55:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260406_0005"
down_revision = "20260405_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_datasets",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_evaluation_datasets_project_id", "evaluation_datasets", ["project_id"], unique=False)
    op.create_index("ix_evaluation_datasets_name", "evaluation_datasets", ["name"], unique=False)

    op.create_table(
        "evaluation_dataset_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.BigInteger(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("ref_answer", sa.Text(), nullable=True),
        sa.Column("expected_knowledge_ids", sa.Text(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_evaluation_dataset_items_dataset_id", "evaluation_dataset_items", ["dataset_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_evaluation_dataset_items_dataset_id", table_name="evaluation_dataset_items")
    op.drop_table("evaluation_dataset_items")

    op.drop_index("ix_evaluation_datasets_name", table_name="evaluation_datasets")
    op.drop_index("ix_evaluation_datasets_project_id", table_name="evaluation_datasets")
    op.drop_table("evaluation_datasets")
