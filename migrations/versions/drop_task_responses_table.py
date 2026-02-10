"""Drop unused task_responses table

Revision ID: drop_task_responses
Revises: merge_all_heads_feb2026
Create Date: 2026-02-10

The task_responses table was superseded by task_applications which has:
- Unique constraint (one application per user per task)
- Status field (pending/accepted/rejected) instead of boolean is_accepted
- Richer serialization with applicant stats

All code references to TaskResponse have been removed.
This migration drops the orphaned table from the database.
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'drop_task_responses'
down_revision = 'merge_all_heads_feb2026'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the task_responses table if it exists
    # Using IF EXISTS for safety in case table was already removed manually
    op.execute('DROP TABLE IF EXISTS task_responses CASCADE')


def downgrade():
    # Recreate the table if we need to roll back
    # (matches the original TaskResponse model schema)
    op.create_table(
        'task_responses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('responder_id', sa.Integer(), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('is_accepted', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['task_id'], ['task_requests.id']),
        sa.ForeignKeyConstraint(['responder_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
