"""rag file parser upgrade

Revision ID: 20260405_0003
Revises: 20260405_0002
Create Date: 2026-04-05 23:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0003"
down_revision = "20260405_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("files") as batch_op:
        batch_op.add_column(sa.Column("mime_type", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("content_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("parsed_document_path", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("parser_name", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("parse_meta_json", sa.JSON(), nullable=True))
        batch_op.create_index("ix_files_content_hash", ["content_hash"], unique=False)

    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.add_column(sa.Column("source_meta_json", sa.JSON(), nullable=True))

    op.execute("UPDATE files SET parse_meta_json = '{}' WHERE parse_meta_json IS NULL")
    op.execute("UPDATE knowledge_items SET source_meta_json = '{}' WHERE source_meta_json IS NULL")


def downgrade() -> None:
    with op.batch_alter_table("knowledge_items") as batch_op:
        batch_op.drop_column("source_meta_json")

    with op.batch_alter_table("files") as batch_op:
        batch_op.drop_index("ix_files_content_hash")
        batch_op.drop_column("parse_meta_json")
        batch_op.drop_column("parser_name")
        batch_op.drop_column("parsed_document_path")
        batch_op.drop_column("content_hash")
        batch_op.drop_column("mime_type")
