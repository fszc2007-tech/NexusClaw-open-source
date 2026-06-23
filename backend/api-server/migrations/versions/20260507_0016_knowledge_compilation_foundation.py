"""knowledge compilation foundation

Revision ID: 20260507_0016
Revises: 20260424_0015
Create Date: 2026-05-07 18:00:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260507_0016"
down_revision = "20260424_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operation_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.BigInteger(), nullable=True),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_operation_logs_project_id", "operation_logs", ["project_id"], unique=False)
    op.create_index("ix_operation_logs_operator_id", "operation_logs", ["operator_id"], unique=False)

    op.add_column("project_settings", sa.Column("capability_knowledge_compilation", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("project_settings", sa.Column("compilation_strategy", sa.String(length=32), nullable=False, server_default="compiled_first"))
    op.add_column("project_settings", sa.Column("compilation_min_score", sa.Numeric(8, 4), nullable=False, server_default="0.8200"))
    op.add_column("project_settings", sa.Column("compilation_min_supporting_source_count", sa.Integer(), nullable=False, server_default="2"))
    op.add_column("project_settings", sa.Column("compilation_allow_with_warning", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "knowledge_compilation_pages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("page_type", sa.String(length=32), nullable=False, server_default="topic"),
        sa.Column("topic_key", sa.String(length=128), nullable=True),
        sa.Column("canonical_title", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("tags_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("health_status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("retrieval_priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_version_id", sa.BigInteger(), nullable=True),
        sa.Column("published_version_id", sa.BigInteger(), nullable=True),
        sa.Column("last_compiled_at", sa.DateTime(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_compilation_pages_project_kb_status", "knowledge_compilation_pages", ["project_id", "kb_id", "status"])
    op.create_index("idx_compilation_pages_topic_key", "knowledge_compilation_pages", ["topic_key"])
    op.create_index("idx_compilation_pages_page_type", "knowledge_compilation_pages", ["page_type"])
    op.create_index("idx_compilation_pages_health_status", "knowledge_compilation_pages", ["health_status"])

    op.create_table(
        "knowledge_compilation_page_versions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("page_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("sources_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.String(length=255), nullable=True),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_compilation_page_versions_run", "knowledge_compilation_page_versions", ["run_id"])
    op.create_unique_constraint("uk_compilation_page_versions", "knowledge_compilation_page_versions", ["page_id", "version_no"])

    op.create_table(
        "knowledge_compilation_page_sources",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("page_id", sa.BigInteger(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_ref_id", sa.String(length=128), nullable=True),
        sa.Column("source_title", sa.String(length=255), nullable=False),
        sa.Column("source_locator_json", sa.JSON(), nullable=False),
        sa.Column("source_quote", sa.Text(), nullable=True),
        sa.Column("source_snapshot", sa.JSON(), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=True),
        sa.Column("support_type", sa.String(length=32), nullable=False, server_default="supports"),
        sa.Column("weight", sa.Numeric(8, 4), nullable=False, server_default="1.0000"),
        sa.Column("order_no", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_compilation_page_sources_page", "knowledge_compilation_page_sources", ["page_id"])
    op.create_index("idx_compilation_page_sources_source", "knowledge_compilation_page_sources", ["source_type", "source_id"])
    op.create_index("idx_compilation_page_sources_version", "knowledge_compilation_page_sources", ["version_id"])

    op.create_table(
        "knowledge_compilation_page_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("from_page_id", sa.BigInteger(), nullable=False),
        sa.Column("to_page_id", sa.BigInteger(), nullable=False),
        sa.Column("link_type", sa.String(length=32), nullable=False, server_default="related"),
        sa.Column("anchor_text", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_compilation_page_links_from", "knowledge_compilation_page_links", ["from_page_id"])
    op.create_index("idx_compilation_page_links_to", "knowledge_compilation_page_links", ["to_page_id"])

    op.create_table(
        "knowledge_compilation_page_tree_links",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("page_id", sa.BigInteger(), nullable=False),
        sa.Column("node_id", sa.BigInteger(), nullable=False),
        sa.Column("link_type", sa.String(length=32), nullable=False, server_default="primary"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_compilation_page_tree_links_node", "knowledge_compilation_page_tree_links", ["node_id"])
    op.create_unique_constraint("uk_compilation_page_tree_links", "knowledge_compilation_page_tree_links", ["page_id", "node_id"])

    op.create_table(
        "knowledge_compilation_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("page_id", sa.BigInteger(), nullable=True),
        sa.Column("run_type", sa.String(length=32), nullable=False, server_default="recompile"),
        sa.Column("trigger_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("strategy", sa.String(length=32), nullable=False, server_default="compiled_first"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_compilation_runs_project_kb", "knowledge_compilation_runs", ["project_id", "kb_id"])
    op.create_index("idx_compilation_runs_page", "knowledge_compilation_runs", ["page_id"])
    op.create_index("idx_compilation_runs_status", "knowledge_compilation_runs", ["status"])
    op.create_unique_constraint("uk_compilation_runs_idempotency", "knowledge_compilation_runs", ["idempotency_key"])

    op.create_table(
        "knowledge_compilation_run_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("page_id", sa.BigInteger(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("before_version_no", sa.Integer(), nullable=True),
        sa.Column("after_version_no", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_compilation_run_items_run", "knowledge_compilation_run_items", ["run_id"])
    op.create_index("idx_compilation_run_items_page", "knowledge_compilation_run_items", ["page_id"])

    op.create_table(
        "knowledge_compilation_health_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("page_id", sa.BigInteger(), nullable=True),
        sa.Column("version_id", sa.BigInteger(), nullable=True),
        sa.Column("run_type", sa.String(length=32), nullable=False, server_default="full_scan"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("summary_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_compilation_health_runs_project_kb", "knowledge_compilation_health_runs", ["project_id", "kb_id"])
    op.create_index("idx_compilation_health_runs_page", "knowledge_compilation_health_runs", ["page_id"])

    op.create_table(
        "knowledge_compilation_health_findings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("health_run_id", sa.BigInteger(), nullable=False),
        sa.Column("page_id", sa.BigInteger(), nullable=False),
        sa.Column("page_version_id", sa.BigInteger(), nullable=True),
        sa.Column("check_type", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("finding_title", sa.String(length=255), nullable=False),
        sa.Column("finding_detail", sa.Text(), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("suggested_action", sa.String(length=255), nullable=True),
        sa.Column("resolved_by", sa.BigInteger(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_compilation_health_findings_run", "knowledge_compilation_health_findings", ["health_run_id"])
    op.create_index("idx_compilation_health_findings_page", "knowledge_compilation_health_findings", ["page_id"])
    op.create_index("idx_compilation_health_findings_type_status", "knowledge_compilation_health_findings", ["check_type", "status"])
    op.create_index("idx_compilation_health_findings_severity", "knowledge_compilation_health_findings", ["severity"])

    op.create_table(
        "knowledge_compilation_writeback_candidates",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_session_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_message_id", sa.BigInteger(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("source_docs_snapshot", sa.JSON(), nullable=False),
        sa.Column("suggested_page_id", sa.BigInteger(), nullable=True),
        sa.Column("suggested_page_type", sa.String(length=32), nullable=False, server_default="answer_writeback"),
        sa.Column("suggested_title", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("review_note", sa.String(length=255), nullable=True),
        sa.Column("merged_version_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("idx_compilation_writeback_candidates_project_kb", "knowledge_compilation_writeback_candidates", ["project_id", "kb_id"])
    op.create_index("idx_compilation_writeback_candidates_status", "knowledge_compilation_writeback_candidates", ["status"])
    op.create_index("idx_compilation_writeback_candidates_page", "knowledge_compilation_writeback_candidates", ["suggested_page_id"])


def downgrade() -> None:
    op.drop_index("ix_operation_logs_operator_id", table_name="operation_logs")
    op.drop_index("ix_operation_logs_project_id", table_name="operation_logs")
    op.drop_table("operation_logs")

    op.drop_index("idx_compilation_writeback_candidates_page", table_name="knowledge_compilation_writeback_candidates")
    op.drop_index("idx_compilation_writeback_candidates_status", table_name="knowledge_compilation_writeback_candidates")
    op.drop_index("idx_compilation_writeback_candidates_project_kb", table_name="knowledge_compilation_writeback_candidates")
    op.drop_table("knowledge_compilation_writeback_candidates")

    op.drop_index("idx_compilation_health_findings_severity", table_name="knowledge_compilation_health_findings")
    op.drop_index("idx_compilation_health_findings_type_status", table_name="knowledge_compilation_health_findings")
    op.drop_index("idx_compilation_health_findings_page", table_name="knowledge_compilation_health_findings")
    op.drop_index("idx_compilation_health_findings_run", table_name="knowledge_compilation_health_findings")
    op.drop_table("knowledge_compilation_health_findings")

    op.drop_index("idx_compilation_health_runs_page", table_name="knowledge_compilation_health_runs")
    op.drop_index("idx_compilation_health_runs_project_kb", table_name="knowledge_compilation_health_runs")
    op.drop_table("knowledge_compilation_health_runs")

    op.drop_index("idx_compilation_run_items_page", table_name="knowledge_compilation_run_items")
    op.drop_index("idx_compilation_run_items_run", table_name="knowledge_compilation_run_items")
    op.drop_table("knowledge_compilation_run_items")

    op.drop_constraint("uk_compilation_runs_idempotency", "knowledge_compilation_runs", type_="unique")
    op.drop_index("idx_compilation_runs_status", table_name="knowledge_compilation_runs")
    op.drop_index("idx_compilation_runs_page", table_name="knowledge_compilation_runs")
    op.drop_index("idx_compilation_runs_project_kb", table_name="knowledge_compilation_runs")
    op.drop_table("knowledge_compilation_runs")

    op.drop_constraint("uk_compilation_page_tree_links", "knowledge_compilation_page_tree_links", type_="unique")
    op.drop_index("idx_compilation_page_tree_links_node", table_name="knowledge_compilation_page_tree_links")
    op.drop_table("knowledge_compilation_page_tree_links")

    op.drop_index("idx_compilation_page_links_to", table_name="knowledge_compilation_page_links")
    op.drop_index("idx_compilation_page_links_from", table_name="knowledge_compilation_page_links")
    op.drop_table("knowledge_compilation_page_links")

    op.drop_index("idx_compilation_page_sources_version", table_name="knowledge_compilation_page_sources")
    op.drop_index("idx_compilation_page_sources_source", table_name="knowledge_compilation_page_sources")
    op.drop_index("idx_compilation_page_sources_page", table_name="knowledge_compilation_page_sources")
    op.drop_table("knowledge_compilation_page_sources")

    op.drop_constraint("uk_compilation_page_versions", "knowledge_compilation_page_versions", type_="unique")
    op.drop_index("idx_compilation_page_versions_run", table_name="knowledge_compilation_page_versions")
    op.drop_table("knowledge_compilation_page_versions")

    op.drop_index("idx_compilation_pages_health_status", table_name="knowledge_compilation_pages")
    op.drop_index("idx_compilation_pages_page_type", table_name="knowledge_compilation_pages")
    op.drop_index("idx_compilation_pages_topic_key", table_name="knowledge_compilation_pages")
    op.drop_index("idx_compilation_pages_project_kb_status", table_name="knowledge_compilation_pages")
    op.drop_table("knowledge_compilation_pages")

    op.drop_column("project_settings", "compilation_allow_with_warning")
    op.drop_column("project_settings", "compilation_min_supporting_source_count")
    op.drop_column("project_settings", "compilation_min_score")
    op.drop_column("project_settings", "compilation_strategy")
    op.drop_column("project_settings", "capability_knowledge_compilation")
