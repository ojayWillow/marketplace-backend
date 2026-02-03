"""Add data column to notifications table

Revision ID: add_data_column_to_notifications
Revises: add_notifications_table
Create Date: 2026-02-03

This migration adds the 'data' column that was missing from the original
notifications table creation. The column stores JSON data for i18n support.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'add_data_column_to_notifications'
down_revision = 'add_notifications_table'
branch_labels = None
depends_on = None


def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def table_exists(table_name):
    """Check if a table exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    # Only add column if table exists and column doesn't
    if table_exists('notifications'):
        if not column_exists('notifications', 'data'):
            op.add_column('notifications', sa.Column('data', sa.Text(), nullable=True))
            print("Added 'data' column to notifications table")
        else:
            print("Column 'data' already exists in notifications table")
    else:
        print("Notifications table doesn't exist yet - will be created by previous migration")


def downgrade():
    if table_exists('notifications') and column_exists('notifications', 'data'):
        op.drop_column('notifications', 'data')
