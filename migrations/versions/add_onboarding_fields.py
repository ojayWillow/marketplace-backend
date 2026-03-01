"""Add onboarding fields to users table.

Adds onboarding_completed and username_changes_remaining columns.
Uses server_default so existing rows get sensible defaults.

Revision ID: add_onboarding_fields
Revises: merge_all_heads_feb2026, job_alert_prefs_001
Create Date: 2026-03-01
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'add_onboarding_fields'
down_revision = ('merge_all_heads_feb2026', 'job_alert_prefs_001')
branch_labels = None
depends_on = None


def upgrade():
    # Add onboarding_completed (default False for existing users)
    op.add_column(
        'users',
        sa.Column(
            'onboarding_completed',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false')
        )
    )

    # Add username_changes_remaining (default 1 for existing users)
    op.add_column(
        'users',
        sa.Column(
            'username_changes_remaining',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('1')
        )
    )

    # Mark all existing users as onboarding completed
    # (they already have usernames set up)
    op.execute(
        "UPDATE users SET onboarding_completed = true "
        "WHERE username IS NOT NULL AND username NOT LIKE 'user_%'"
    )


def downgrade():
    op.drop_column('users', 'username_changes_remaining')
    op.drop_column('users', 'onboarding_completed')
