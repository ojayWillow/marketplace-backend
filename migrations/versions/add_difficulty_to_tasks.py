"""add difficulty to tasks

Revision ID: add_difficulty_to_tasks
Revises: 096005df6b4d
Create Date: 2026-01-23 08:42:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_difficulty_to_tasks'
down_revision = '096005df6b4d'
branch_labels = None
depends_on = None


def upgrade():
    # Add difficulty column with default 'medium'
    op.add_column('task_requests', sa.Column('difficulty', sa.String(length=10), nullable=False, server_default='medium'))


def downgrade():
    op.drop_column('task_requests', 'difficulty')
