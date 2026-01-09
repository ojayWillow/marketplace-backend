"""Add last_seen to users table

Revision ID: add_last_seen_001
Revises: 
Create Date: 2026-01-09

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = 'add_last_seen_001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add last_seen column to users table
    op.add_column('users', sa.Column('last_seen', sa.DateTime(), nullable=True, default=datetime.utcnow))


def downgrade():
    # Remove last_seen column from users table
    op.drop_column('users', 'last_seen')
