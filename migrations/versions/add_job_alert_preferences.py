"""Add job_alert_preferences column to users table.

Revision ID: job_alert_prefs_001
Create Date: 2026-02-18
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'job_alert_prefs_001'
down_revision = None  # Update this to your latest migration revision
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('job_alert_preferences', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('users', 'job_alert_preferences')
