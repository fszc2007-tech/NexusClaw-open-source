"""knowledge chunks projection

Revision ID: 20260409_0009
Revises: 20260409_0008
Create Date: 2026-04-09 21:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260409_0009"
down_revision = "20260409_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("source_item_id", sa.BigInteger(), nullable=True),
        sa.Column("file_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("document_name", sa.Text(), nullable=True),
        sa.Column("lexical_text", sa.Text(), nullable=False),
        sa.Column("contextual_text", sa.Text(), nullable=False),
        sa.Column("citation_text", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("parent_chunk_id", sa.BigInteger(), nullable=True),
        sa.Column("chunk_meta_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("authority_level", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("source_rank", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("region", sa.String(length=16), nullable=True),
        sa.Column("route_kind", sa.String(length=64), nullable=True),
        sa.Column("subject_type", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["parent_chunk_id"], ["knowledge_chunks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_item_id"], ["knowledge_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_project_kb_status_kind", "knowledge_chunks", ["project_id", "kb_id", "status", "source_kind"])
    op.create_index("ix_knowledge_chunks_project_file_chunkidx", "knowledge_chunks", ["project_id", "file_id", "chunk_index"])
    op.create_index(op.f("ix_knowledge_chunks_project_id"), "knowledge_chunks", ["project_id"])
    op.create_index(op.f("ix_knowledge_chunks_kb_id"), "knowledge_chunks", ["kb_id"])
    op.create_index(op.f("ix_knowledge_chunks_source_kind"), "knowledge_chunks", ["source_kind"])
    op.create_index(op.f("ix_knowledge_chunks_source_item_id"), "knowledge_chunks", ["source_item_id"])
    op.create_index(op.f("ix_knowledge_chunks_file_id"), "knowledge_chunks", ["file_id"])
    op.create_index(op.f("ix_knowledge_chunks_parent_chunk_id"), "knowledge_chunks", ["parent_chunk_id"])
    op.create_index(op.f("ix_knowledge_chunks_status"), "knowledge_chunks", ["status"])
    op.create_index(op.f("ix_knowledge_chunks_authority_level"), "knowledge_chunks", ["authority_level"])
    op.create_index(op.f("ix_knowledge_chunks_region"), "knowledge_chunks", ["region"])
    op.create_index(op.f("ix_knowledge_chunks_route_kind"), "knowledge_chunks", ["route_kind"])
    op.create_index(op.f("ix_knowledge_chunks_subject_type"), "knowledge_chunks", ["subject_type"])

    op.create_table(
        "chunk_relations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("from_chunk_id", sa.BigInteger(), nullable=False),
        sa.Column("to_chunk_id", sa.BigInteger(), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["from_chunk_id"], ["knowledge_chunks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_chunk_id"], ["knowledge_chunks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chunk_relations_from_type", "chunk_relations", ["from_chunk_id", "relation_type"])
    op.create_index(op.f("ix_chunk_relations_from_chunk_id"), "chunk_relations", ["from_chunk_id"])
    op.create_index(op.f("ix_chunk_relations_to_chunk_id"), "chunk_relations", ["to_chunk_id"])
    op.create_index(op.f("ix_chunk_relations_relation_type"), "chunk_relations", ["relation_type"])


def downgrade() -> None:
    op.drop_index(op.f("ix_chunk_relations_relation_type"), table_name="chunk_relations")
    op.drop_index(op.f("ix_chunk_relations_to_chunk_id"), table_name="chunk_relations")
    op.drop_index(op.f("ix_chunk_relations_from_chunk_id"), table_name="chunk_relations")
    op.drop_index("ix_chunk_relations_from_type", table_name="chunk_relations")
    op.drop_table("chunk_relations")

    op.drop_index(op.f("ix_knowledge_chunks_subject_type"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_route_kind"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_region"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_authority_level"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_status"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_parent_chunk_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_file_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_source_item_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_source_kind"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_kb_id"), table_name="knowledge_chunks")
    op.drop_index(op.f("ix_knowledge_chunks_project_id"), table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_project_file_chunkidx", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_project_kb_status_kind", table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
