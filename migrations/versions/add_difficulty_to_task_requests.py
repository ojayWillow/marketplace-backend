"""Add difficulty column to task_requests table.

Revision ID: add_difficulty_001
Revises: (auto-detect)
Create Date: 2026-02-08
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'add_difficulty_001'
down_revision = None  # Update this to your latest migration revision ID
branch_labels = None
depends_on = None


def upgrade():
    """Add difficulty column with default 'medium' for existing rows."""
    op.add_column(
        'task_requests',
        sa.Column('difficulty', sa.String(20), nullable=False, server_default='medium')
    )


def downgrade():
    """Remove difficulty column."""
    op.drop_column('task_requests', 'difficulty')
