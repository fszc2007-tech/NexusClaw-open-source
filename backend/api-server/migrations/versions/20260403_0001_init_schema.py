"""init schema

Revision ID: 20260403_0001
Revises: 
Create Date: 2026-04-03 06:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = '20260403_0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'projects',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('project_key', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_projects_project_key', 'projects', ['project_key'], unique=True)
    op.create_index('ix_projects_name', 'projects', ['name'], unique=False)

    op.create_table(
        'project_persona',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('assistant_name', sa.String(length=64), nullable=False),
        sa.Column('assistant_role', sa.String(length=128), nullable=False),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('style_rules', sa.Text(), nullable=True),
        sa.Column('opening_text', sa.Text(), nullable=True),
        sa.Column('recommended_questions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_project_persona_project_id', 'project_persona', ['project_id'], unique=True)

    op.create_table(
        'knowledge',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('kb_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='draft'),
        sa.Column('version_no', sa.BigInteger(), nullable=False, server_default='1'),
        sa.Column('replaced_by_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_knowledge_project_id', 'knowledge', ['project_id'], unique=False)
    op.create_index('ix_knowledge_kb_id', 'knowledge', ['kb_id'], unique=False)
    op.create_index('ix_knowledge_title', 'knowledge', ['title'], unique=False)
    op.create_index('ix_knowledge_status', 'knowledge', ['status'], unique=False)

    op.create_table(
        'knowledge_dedup_records',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('new_knowledge_id', sa.BigInteger(), nullable=False),
        sa.Column('old_knowledge_id', sa.BigInteger(), nullable=False),
        sa.Column('score', sa.Numeric(5, 4), nullable=False),
        sa.Column('dedup_level', sa.String(length=16), nullable=False, server_default='low'),
        sa.Column('action', sa.String(length=32), nullable=False, server_default='pending'),
        sa.Column('reason_json', sa.Text(), nullable=True),
        sa.Column('comment', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_knowledge_dedup_project_id', 'knowledge_dedup_records', ['project_id'], unique=False)

    op.create_table(
        'chat_sessions',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('session_code', sa.String(length=64), nullable=False),
        sa.Column('project_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_chat_sessions_session_code', 'chat_sessions', ['session_code'], unique=True)

    op.create_table(
        'chat_messages',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('session_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False, server_default='user'),
        sa.Column('query_raw', sa.Text(), nullable=True),
        sa.Column('query_rewritten', sa.Text(), nullable=True),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('source_docs', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chat_messages_session_id', table_name='chat_messages')
    op.drop_table('chat_messages')
    op.drop_index('ix_chat_sessions_session_code', table_name='chat_sessions')
    op.drop_table('chat_sessions')
    op.drop_index('ix_knowledge_dedup_project_id', table_name='knowledge_dedup_records')
    op.drop_table('knowledge_dedup_records')
    op.drop_index('ix_knowledge_status', table_name='knowledge')
    op.drop_index('ix_knowledge_title', table_name='knowledge')
    op.drop_index('ix_knowledge_kb_id', table_name='knowledge')
    op.drop_index('ix_knowledge_project_id', table_name='knowledge')
    op.drop_table('knowledge')
    op.drop_index('ix_project_persona_project_id', table_name='project_persona')
    op.drop_table('project_persona')
    op.drop_index('ix_projects_name', table_name='projects')
    op.drop_index('ix_projects_project_key', table_name='projects')
    op.drop_table('projects')
