"""Add boost fields to offerings table

Revision ID: add_boost_001
Revises: add_last_seen_001
Create Date: 2026-01-09

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_boost_001'
down_revision = 'add_last_seen_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add is_boosted column to offerings table
    op.add_column('offerings', sa.Column('is_boosted', sa.Boolean(), nullable=False, server_default='false'))
    # Add boost_expires_at column to offerings table
    op.add_column('offerings', sa.Column('boost_expires_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove boost columns from offerings table
    op.drop_column('offerings', 'boost_expires_at')
    op.drop_column('offerings', 'is_boosted')
