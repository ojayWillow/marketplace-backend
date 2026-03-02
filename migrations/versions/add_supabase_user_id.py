"""Add supabase_user_id column to users table

Revision ID: add_supabase_user_id
Revises: merge_all_heads_feb2026
Create Date: 2026-03-02

Adds a UUID column to link local users to Supabase Auth users.
Part of the Supabase Auth migration (#48).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_supabase_user_id'
down_revision = 'merge_all_heads_feb2026'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('supabase_user_id', sa.String(36), nullable=True))
    op.create_unique_constraint('uq_users_supabase_user_id', 'users', ['supabase_user_id'])
    op.create_index('ix_users_supabase_user_id', 'users', ['supabase_user_id'])


def downgrade():
    op.drop_index('ix_users_supabase_user_id', table_name='users')
    op.drop_constraint('uq_users_supabase_user_id', 'users', type_='unique')
    op.drop_column('users', 'supabase_user_id')
