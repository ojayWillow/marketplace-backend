"""Merge all migration heads into single head

Revision ID: merge_all_heads_feb2026
Revises: 199fa9f6522b, 54ed49768a8a, add_data_column_to_notifications, add_difficulty_to_tasks, add_disputes_table, add_password_reset_tokens, add_payment_fields
Create Date: 2026-02-10

This migration merges 7 unmerged heads that were causing
`flask db upgrade` to fail with 'Multiple heads detected'.
The error was silently swallowed in start.sh, preventing
the notifications table (and potentially others) from being
created in production.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_all_heads_feb2026'
down_revision = (
    '199fa9f6522b',
    '54ed49768a8a',
    'add_data_column_to_notifications',
    'add_difficulty_to_tasks',
    'add_disputes_table',
    'add_password_reset_tokens',
    'add_payment_fields',
)
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
