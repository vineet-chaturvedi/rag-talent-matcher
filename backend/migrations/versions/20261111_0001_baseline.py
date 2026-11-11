"""baseline schema (steps 3-14)

The tables as they were before migrations existed (Steps 3-14), on any database. A database created by the
app before Step 15 is "stamped" at this revision instead of running it (app/db/session.py: init_db).

PostgreSQL also gets, here:
  - the pgvector extension (vectors live next to the data: app/rag/vector_store.py)
  - resume_chunks.search_vector: a generated full-text column + GIN index (keyword search, app/rag/keyword_index.py)
  - vector_collections: which embedding model's vectors are in which table, and their size
SQLite keeps its FTS5 table (created at startup) and ChromaDB.

Revision ID: 0001
Revises:
Created: 2026-11-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('employees',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_code', sa.String(length=50), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('department', sa.String(length=100), nullable=True),
    sa.Column('designation', sa.String(length=100), nullable=True),
    sa.Column('location', sa.String(length=100), nullable=True),
    sa.Column('date_joined', sa.Date(), nullable=True),
    sa.Column('availability_status', sa.Enum('available', 'partial', 'allocated', 'on_leave', name='availabilitystatus', native_enum=False, length=30), nullable=False),
    sa.Column('allocation_percent', sa.Integer(), nullable=False),
    sa.Column('available_from', sa.Date(), nullable=True),
    sa.Column('current_project_name', sa.String(length=200), nullable=True),
    sa.Column('manager_name', sa.String(length=200), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint('allocation_percent BETWEEN 0 AND 100', name=op.f('ck_employees_allocation_range')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_employees')),
    sa.UniqueConstraint('email', name=op.f('uq_employees_email')),
    sa.UniqueConstraint('employee_code', name=op.f('uq_employees_employee_code'))
    )
    op.create_index(op.f('ix_employees_availability_status'), 'employees', ['availability_status'], unique=False)
    op.create_index(op.f('ix_employees_department'), 'employees', ['department'], unique=False)
    op.create_index(op.f('ix_employees_is_active'), 'employees', ['is_active'], unique=False)
    op.create_index(op.f('ix_employees_location'), 'employees', ['location'], unique=False)
    op.create_table('skills',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_skills')),
    sa.UniqueConstraint('name', name=op.f('uq_skills_name'))
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('admin', 'resource_manager', name='userrole', native_enum=False, length=30), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('agent_conversations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_agent_conversations_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_conversations'))
    )
    op.create_index(op.f('ix_agent_conversations_user_id'), 'agent_conversations', ['user_id'], unique=False)
    op.create_table('projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('client_name', sa.String(length=200), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('planned', 'active', 'on_hold', 'completed', name='projectstatus', native_enum=False, length=30), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_projects_created_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_projects'))
    )
    op.create_table('resumes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('stored_path', sa.String(length=500), nullable=False),
    sa.Column('file_hash', sa.String(length=64), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('status', sa.Enum('queued', 'parsing', 'parsed', 'extracting', 'extracted', 'embedding', 'ready', 'failed', name='resumestatus', native_enum=False, length=30), nullable=False),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=True),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('processed_at', sa.DateTime(), nullable=True),
    sa.Column('uploaded_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_resumes_employee_id_employees'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], name=op.f('fk_resumes_uploaded_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_resumes')),
    sa.UniqueConstraint('file_hash', name=op.f('uq_resumes_file_hash'))
    )
    op.create_index(op.f('ix_resumes_employee_id'), 'resumes', ['employee_id'], unique=False)
    op.create_index(op.f('ix_resumes_is_current'), 'resumes', ['is_current'], unique=False)
    op.create_index(op.f('ix_resumes_status'), 'resumes', ['status'], unique=False)
    op.create_table('agent_messages',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('conversation_id', sa.Integer(), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('tool_calls', sa.JSON(), nullable=True),
    sa.Column('tool_name', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['agent_conversations.id'], name=op.f('fk_agent_messages_conversation_id_agent_conversations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_messages'))
    )
    op.create_index(op.f('ix_agent_messages_conversation_id'), 'agent_messages', ['conversation_id'], unique=False)
    op.create_table('experiences',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('company', sa.String(length=200), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('end_date', sa.Date(), nullable=True),
    sa.Column('is_current', sa.Boolean(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], name=op.f('fk_experiences_resume_id_resumes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_experiences'))
    )
    op.create_index(op.f('ix_experiences_resume_id'), 'experiences', ['resume_id'], unique=False)
    op.create_table('project_roles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('requirements', sa.JSON(), nullable=True),
    sa.Column('min_experience_years', sa.Double(), nullable=True),
    sa.Column('location', sa.String(length=100), nullable=True),
    sa.Column('allocation_percent', sa.Integer(), nullable=False),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('headcount', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('open', 'filled', 'closed', name='rolestatus', native_enum=False, length=30), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], name=op.f('fk_project_roles_project_id_projects'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_project_roles'))
    )
    op.create_index(op.f('ix_project_roles_project_id'), 'project_roles', ['project_id'], unique=False)
    op.create_index(op.f('ix_project_roles_status'), 'project_roles', ['status'], unique=False)
    op.create_table('resume_chunks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('section', sa.Enum('summary', 'skills', 'experience', 'project', 'education', 'certification', 'other', name='chunksection', native_enum=False, length=30), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('token_count', sa.Integer(), nullable=True),
    sa.Column('embedding_model', sa.String(length=100), nullable=True),
    sa.Column('meta', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], name=op.f('fk_resume_chunks_resume_id_resumes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_resume_chunks')),
    sa.UniqueConstraint('resume_id', 'chunk_index', name=op.f('uq_resume_chunks_resume_id'))
    )
    op.create_index(op.f('ix_resume_chunks_resume_id'), 'resume_chunks', ['resume_id'], unique=False)
    op.create_table('resume_profiles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('headline', sa.String(length=300), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('total_experience_years', sa.Double(), nullable=True),
    sa.Column('education', sa.JSON(), nullable=True),
    sa.Column('certifications', sa.JSON(), nullable=True),
    sa.Column('raw_extraction', sa.JSON(), nullable=True),
    sa.Column('extraction_model', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], name=op.f('fk_resume_profiles_resume_id_resumes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_resume_profiles')),
    sa.UniqueConstraint('resume_id', name=op.f('uq_resume_profiles_resume_id'))
    )
    op.create_table('resume_projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('role', sa.String(length=200), nullable=True),
    sa.Column('duration_months', sa.Integer(), nullable=True),
    sa.Column('duration_text', sa.String(length=100), nullable=True),
    sa.Column('technologies', sa.JSON(), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('link', sa.String(length=500), nullable=True),
    sa.Column('company', sa.String(length=200), nullable=True),
    sa.Column('company_basis', sa.String(length=30), nullable=True),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], name=op.f('fk_resume_projects_resume_id_resumes'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_resume_projects'))
    )
    op.create_index(op.f('ix_resume_projects_resume_id'), 'resume_projects', ['resume_id'], unique=False)
    op.create_table('resume_skills',
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('skill_id', sa.Integer(), nullable=False),
    sa.Column('years', sa.Double(), nullable=True),
    sa.Column('last_used_year', sa.Integer(), nullable=True),
    sa.Column('evidence', sa.Text(), nullable=True),
    sa.Column('uses', sa.Integer(), nullable=True),
    sa.Column('source', sa.String(length=20), nullable=True),
    sa.Column('years_basis', sa.String(length=20), nullable=True),
    sa.Column('level', sa.String(length=10), nullable=True),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], name=op.f('fk_resume_skills_resume_id_resumes'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['skill_id'], ['skills.id'], name=op.f('fk_resume_skills_skill_id_skills'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('resume_id', 'skill_id', name=op.f('pk_resume_skills'))
    )
    op.create_index(op.f('ix_resume_skills_skill_id'), 'resume_skills', ['skill_id'], unique=False)
    op.create_table('match_runs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('running', 'completed', 'failed', name='matchrunstatus', native_enum=False, length=30), nullable=False),
    sa.Column('settings', sa.JSON(), nullable=True),
    sa.Column('started_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name=op.f('fk_match_runs_created_by_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['role_id'], ['project_roles.id'], name=op.f('fk_match_runs_role_id_project_roles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_match_runs'))
    )
    op.create_index(op.f('ix_match_runs_role_id'), 'match_runs', ['role_id'], unique=False)
    op.create_table('match_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('run_id', sa.Integer(), nullable=False),
    sa.Column('employee_id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=True),
    sa.Column('rank', sa.Integer(), nullable=False),
    sa.Column('final_score', sa.Double(), nullable=False),
    sa.Column('score_breakdown', sa.JSON(), nullable=False),
    sa.Column('explanation', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_match_results_employee_id_employees'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], name=op.f('fk_match_results_resume_id_resumes'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['run_id'], ['match_runs.id'], name=op.f('fk_match_results_run_id_match_runs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_match_results')),
    sa.UniqueConstraint('run_id', 'employee_id', name=op.f('uq_match_results_run_id'))
    )
    op.create_index(op.f('ix_match_results_employee_id'), 'match_results', ['employee_id'], unique=False)
    op.create_index(op.f('ix_match_results_run_id'), 'match_results', ['run_id'], unique=False)
    op.create_table('feedback',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('target', sa.Enum('match_result', 'agent_answer', name='feedbacktarget', native_enum=False, length=30), nullable=False),
    sa.Column('rating', sa.Enum('up', 'down', name='feedbackrating', native_enum=False, length=30), nullable=False),
    sa.Column('reason', sa.String(length=40), nullable=True),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('match_result_id', sa.Integer(), nullable=True),
    sa.Column('match_run_id', sa.Integer(), nullable=True),
    sa.Column('role_id', sa.Integer(), nullable=True),
    sa.Column('employee_id', sa.Integer(), nullable=True),
    sa.Column('agent_message_id', sa.Integer(), nullable=True),
    sa.Column('context', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['agent_message_id'], ['agent_messages.id'], name=op.f('fk_feedback_agent_message_id_agent_messages'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_feedback_employee_id_employees'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['match_result_id'], ['match_results.id'], name=op.f('fk_feedback_match_result_id_match_results'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['match_run_id'], ['match_runs.id'], name=op.f('fk_feedback_match_run_id_match_runs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['role_id'], ['project_roles.id'], name=op.f('fk_feedback_role_id_project_roles'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_feedback_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_feedback')),
    sa.UniqueConstraint('user_id', 'agent_message_id', name='uq_feedback_user_message'),
    sa.UniqueConstraint('user_id', 'match_result_id', name='uq_feedback_user_result')
    )
    op.create_index(op.f('ix_feedback_employee_id'), 'feedback', ['employee_id'], unique=False)
    op.create_index(op.f('ix_feedback_role_id'), 'feedback', ['role_id'], unique=False)
    op.create_index(op.f('ix_feedback_target'), 'feedback', ['target'], unique=False)
    op.create_index(op.f('ix_feedback_user_id'), 'feedback', ['user_id'], unique=False)

    if op.get_bind().dialect.name == "postgresql":
        _postgresql_upgrade()


def _postgresql_upgrade() -> None:
    # Managed PostgreSQL: RDS/Aurora and Cloud SQL allow this for the admin user; Azure needs "VECTOR" in the
    # server parameter azure.extensions first (doc 21).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Words as SQLite FTS5's unicode61 tokenizer sees them, so both databases find the same chunks: every
    # character that is not a letter or digit separates words ("node.js" -> node js, "ci/cd" -> ci cd), and the
    # 'simple' configuration only lower-cases (no stemming, no stop words: "Go", "R" and "C" stay searchable).
    # The same expression is applied to the search terms (app/rag/keyword_index.py: WORDS_SQL).
    op.execute("ALTER TABLE resume_chunks ADD COLUMN search_vector tsvector GENERATED ALWAYS AS "
               "(to_tsvector('simple', regexp_replace(coalesce(text, ''), '[^[:alnum:]]+', ' ', 'g'))) STORED")
    op.execute("CREATE INDEX ix_resume_chunks_search_vector ON resume_chunks USING gin (search_vector)")
    op.create_table(
        'vector_collections',
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('table_name', sa.String(length=63), nullable=False),
        sa.Column('dimensions', sa.Integer(), nullable=False),
        sa.Column('column_type', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('name', name=op.f('pk_vector_collections')),
        sa.UniqueConstraint('table_name', name=op.f('uq_vector_collections_table_name')),
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for (table,) in op.get_bind().execute(sa.text("SELECT table_name FROM vector_collections")):
            op.execute(f'DROP TABLE IF EXISTS "{table}"')
        op.drop_table('vector_collections')
        op.execute("DROP INDEX IF EXISTS ix_resume_chunks_search_vector")
        op.execute("ALTER TABLE resume_chunks DROP COLUMN IF EXISTS search_vector")
    op.drop_index(op.f('ix_feedback_user_id'), table_name='feedback')
    op.drop_index(op.f('ix_feedback_target'), table_name='feedback')
    op.drop_index(op.f('ix_feedback_role_id'), table_name='feedback')
    op.drop_index(op.f('ix_feedback_employee_id'), table_name='feedback')
    op.drop_table('feedback')
    op.drop_index(op.f('ix_match_results_run_id'), table_name='match_results')
    op.drop_index(op.f('ix_match_results_employee_id'), table_name='match_results')
    op.drop_table('match_results')
    op.drop_index(op.f('ix_match_runs_role_id'), table_name='match_runs')
    op.drop_table('match_runs')
    op.drop_index(op.f('ix_resume_skills_skill_id'), table_name='resume_skills')
    op.drop_table('resume_skills')
    op.drop_index(op.f('ix_resume_projects_resume_id'), table_name='resume_projects')
    op.drop_table('resume_projects')
    op.drop_table('resume_profiles')
    op.drop_index(op.f('ix_resume_chunks_resume_id'), table_name='resume_chunks')
    op.drop_table('resume_chunks')
    op.drop_index(op.f('ix_project_roles_status'), table_name='project_roles')
    op.drop_index(op.f('ix_project_roles_project_id'), table_name='project_roles')
    op.drop_table('project_roles')
    op.drop_index(op.f('ix_experiences_resume_id'), table_name='experiences')
    op.drop_table('experiences')
    op.drop_index(op.f('ix_agent_messages_conversation_id'), table_name='agent_messages')
    op.drop_table('agent_messages')
    op.drop_index(op.f('ix_resumes_status'), table_name='resumes')
    op.drop_index(op.f('ix_resumes_is_current'), table_name='resumes')
    op.drop_index(op.f('ix_resumes_employee_id'), table_name='resumes')
    op.drop_table('resumes')
    op.drop_table('projects')
    op.drop_index(op.f('ix_agent_conversations_user_id'), table_name='agent_conversations')
    op.drop_table('agent_conversations')
    op.drop_table('users')
    op.drop_table('skills')
    op.drop_index(op.f('ix_employees_location'), table_name='employees')
    op.drop_index(op.f('ix_employees_is_active'), table_name='employees')
    op.drop_index(op.f('ix_employees_department'), table_name='employees')
    op.drop_index(op.f('ix_employees_availability_status'), table_name='employees')
    op.drop_table('employees')
