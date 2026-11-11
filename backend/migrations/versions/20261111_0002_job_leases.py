"""job leases and worker heartbeats (Step 15d: background jobs through a queue)

  resumes.lease_expires_at       the worker processing a resume holds it until then (renewed while it works)
  match_runs.lease_expires_at    the same for the LLM judge of a run
  match_runs.attempts            how many workers have tried to judge the run (it gives up after the limit)
  worker_heartbeats              each worker process reports here every 30 s: "how many workers are running?"

batch_alter_table: SQLite can't alter most things in place, so Alembic copies the table there; PostgreSQL
gets plain ALTER TABLE statements.

Revision ID: 0002
Revises: 0001
Created: 2026-11-11
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'worker_heartbeats',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('hostname', sa.String(length=255), nullable=False),
        sa.Column('pid', sa.Integer(), nullable=False),
        sa.Column('queue_backend', sa.String(length=20), nullable=False),
        sa.Column('concurrency', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_worker_heartbeats')),
    )
    op.create_index(op.f('ix_worker_heartbeats_last_seen_at'), 'worker_heartbeats', ['last_seen_at'], unique=False)
    with op.batch_alter_table('match_runs') as batch:
        batch.add_column(sa.Column('lease_expires_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('attempts', sa.Integer(), server_default='0', nullable=False))
    with op.batch_alter_table('resumes') as batch:
        batch.add_column(sa.Column('lease_expires_at', sa.DateTime(), nullable=True))
        batch.create_index(batch.f('ix_resumes_lease_expires_at'), ['lease_expires_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('resumes') as batch:
        batch.drop_index(batch.f('ix_resumes_lease_expires_at'))
        batch.drop_column('lease_expires_at')
    with op.batch_alter_table('match_runs') as batch:
        batch.drop_column('attempts')
        batch.drop_column('lease_expires_at')
    op.drop_index(op.f('ix_worker_heartbeats_last_seen_at'), table_name='worker_heartbeats')
    op.drop_table('worker_heartbeats')
