"""service backbone

Revision ID: 20260405_0002
Revises: 20260403_0001
Create Date: 2026-04-05 21:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260405_0002"
down_revision = "20260403_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("company_name", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("logo_url", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("created_by", sa.BigInteger(), nullable=True))
        batch_op.create_index("ix_projects_company_name", ["company_name"], unique=False)

    op.execute("UPDATE projects SET company_name = name WHERE company_name IS NULL")

    op.create_table(
        "project_members",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("project_role", sa.String(length=32), nullable=False, server_default="project_member"),
        sa.Column("joined_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_project_members_project_id", "project_members", ["project_id"], unique=False)
    op.create_index("ix_project_members_user_id", "project_members", ["user_id"], unique=False)

    op.create_table(
        "project_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("opening_mode", sa.String(length=32), nullable=False, server_default="card"),
        sa.Column("opening_text", sa.Text(), nullable=True),
        sa.Column("recommended_questions", sa.JSON(), nullable=True),
        sa.Column("hot_questions", sa.JSON(), nullable=True),
        sa.Column("hot_policies", sa.JSON(), nullable=True),
        sa.Column("prompt_template", sa.Text(), nullable=True),
        sa.Column("capability_multi_turn", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("capability_sensitive_detection", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("capability_gov_domain_check", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("capability_knowledge_tree", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_project_settings_project_id", "project_settings", ["project_id"], unique=True)

    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_knowledge_bases_project_id", "knowledge_bases", ["project_id"], unique=False)

    op.create_table(
        "knowledge_items",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("document_name", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("keywords_json", sa.JSON(), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False, server_default="manual"),
        sa.Column("source_file_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="editing"),
        sa.Column("version_no", sa.BigInteger(), nullable=False, server_default="1"),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_knowledge_items_project_id", "knowledge_items", ["project_id"], unique=False)
    op.create_index("ix_knowledge_items_kb_id", "knowledge_items", ["kb_id"], unique=False)
    op.create_index("ix_knowledge_items_title", "knowledge_items", ["title"], unique=False)
    op.create_index("ix_knowledge_items_status", "knowledge_items", ["status"], unique=False)

    op.create_table(
        "files",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_ext", sa.String(length=16), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("storage_path", sa.String(length=255), nullable=False),
        sa.Column("preview_path", sa.String(length=255), nullable=True),
        sa.Column("overwrite_same_name", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("parse_status", sa.String(length=32), nullable=False, server_default="uploaded"),
        sa.Column("chunk_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("qa_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("parse_error", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_files_project_id", "files", ["project_id"], unique=False)
    op.create_index("ix_files_kb_id", "files", ["kb_id"], unique=False)
    op.create_index("ix_files_file_name", "files", ["file_name"], unique=False)

    op.create_table(
        "file_tasks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", sa.BigInteger(), nullable=False),
        sa.Column("kb_id", sa.BigInteger(), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("request_payload", sa.JSON(), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(length=255), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_file_tasks_project_id", "file_tasks", ["project_id"], unique=False)
    op.create_index("ix_file_tasks_file_id", "file_tasks", ["file_id"], unique=False)

    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.add_column(sa.Column("source", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("selected_kb_ids", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("switches_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("last_active_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_chat_sessions_project_id", ["project_id"], unique=False)

    op.execute("UPDATE chat_sessions SET source = 'portal' WHERE source IS NULL")
    op.execute("UPDATE chat_sessions SET title = '新对话' WHERE title IS NULL")
    op.execute("UPDATE chat_sessions SET selected_kb_ids = '[]' WHERE selected_kb_ids IS NULL")
    op.execute("UPDATE chat_sessions SET switches_json = '{}' WHERE switches_json IS NULL")
    op.execute("UPDATE chat_sessions SET last_active_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP) WHERE last_active_at IS NULL")

    op.execute("UPDATE chat_messages SET source_docs = '[]'")
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.alter_column("source_docs", existing_type=sa.Text(), type_=sa.JSON(), existing_nullable=True)
        batch_op.add_column(sa.Column("prompt_snapshot", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("model_name", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("trace_id", sa.String(length=64), nullable=True))

    op.execute(
        """
        INSERT INTO project_settings (
            project_id, opening_mode, opening_text, recommended_questions, hot_questions, hot_policies,
            prompt_template, capability_multi_turn, capability_sensitive_detection, capability_gov_domain_check,
            capability_knowledge_tree, enabled, created_at, updated_at
        )
        SELECT
            p.id,
            'card',
            COALESCE(pp.opening_text, CONCAT('您好，欢迎使用', p.company_name, '智能问答平台。')),
            '[]',
            '[]',
            '[]',
            COALESCE(pp.system_prompt, '你是一个专业的业务问答助手。参考资料：{qa}\n历史对话：{history}\n用户问题：{query}'),
            1,
            1,
            1,
            0,
            1,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM projects p
        LEFT JOIN project_persona pp ON pp.project_id = p.id
        WHERE NOT EXISTS (
            SELECT 1 FROM project_settings ps WHERE ps.project_id = p.id
        )
        """
    )

    op.execute(
        """
        INSERT INTO knowledge_bases (project_id, name, description, is_default, created_at, updated_at)
        SELECT
            p.id,
            CONCAT('kb_', p.project_key),
            '项目默认知识库',
            1,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM projects p
        WHERE NOT EXISTS (
            SELECT 1 FROM knowledge_bases kb WHERE kb.project_id = p.id
        )
        """
    )

    op.execute(
        """
        INSERT INTO knowledge_items (
            project_id, kb_id, document_name, title, content, keywords_json, source_type, status,
            version_no, published_at, created_at, updated_at
        )
        SELECT
            k.project_id,
            kb.id,
            NULL,
            k.title,
            k.content,
            CASE
                WHEN k.keywords IS NULL OR k.keywords = '' THEN JSON_ARRAY()
                ELSE JSON_ARRAY(k.keywords)
            END,
            'legacy',
            CASE
                WHEN k.status = 'draft' THEN 'editing'
                WHEN k.status = 'active' THEN 'active'
                ELSE k.status
            END,
            COALESCE(k.version_no, 1),
            CASE WHEN k.status = 'active' THEN CURRENT_TIMESTAMP ELSE NULL END,
            COALESCE(k.created_at, CURRENT_TIMESTAMP),
            COALESCE(k.updated_at, CURRENT_TIMESTAMP)
        FROM knowledge k
        INNER JOIN knowledge_bases kb
            ON kb.project_id = k.project_id AND kb.is_default = 1
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch_op:
        batch_op.drop_column("trace_id")
        batch_op.drop_column("model_name")
        batch_op.drop_column("prompt_snapshot")
        batch_op.alter_column("source_docs", existing_type=sa.JSON(), type_=sa.Text(), existing_nullable=True)

    with op.batch_alter_table("chat_sessions") as batch_op:
        batch_op.drop_index("ix_chat_sessions_project_id")
        batch_op.drop_column("last_active_at")
        batch_op.drop_column("switches_json")
        batch_op.drop_column("selected_kb_ids")
        batch_op.drop_column("title")
        batch_op.drop_column("source")

    op.drop_index("ix_file_tasks_file_id", table_name="file_tasks")
    op.drop_index("ix_file_tasks_project_id", table_name="file_tasks")
    op.drop_table("file_tasks")

    op.drop_index("ix_files_file_name", table_name="files")
    op.drop_index("ix_files_kb_id", table_name="files")
    op.drop_index("ix_files_project_id", table_name="files")
    op.drop_table("files")

    op.drop_index("ix_knowledge_items_status", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_title", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_kb_id", table_name="knowledge_items")
    op.drop_index("ix_knowledge_items_project_id", table_name="knowledge_items")
    op.drop_table("knowledge_items")

    op.drop_index("ix_knowledge_bases_project_id", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")

    op.drop_index("ix_project_settings_project_id", table_name="project_settings")
    op.drop_table("project_settings")

    op.drop_index("ix_project_members_user_id", table_name="project_members")
    op.drop_index("ix_project_members_project_id", table_name="project_members")
    op.drop_table("project_members")

    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_index("ix_projects_company_name")
        batch_op.drop_column("created_by")
        batch_op.drop_column("logo_url")
        batch_op.drop_column("company_name")
