"""Add onboarding_completed field to users table.

Revision ID: onboarding_001
Revises: 
Create Date: 2026-02-19
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'onboarding_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add onboarding_completed column with default False
    op.add_column('users', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade():
    op.drop_column('users', 'onboarding_completed')
