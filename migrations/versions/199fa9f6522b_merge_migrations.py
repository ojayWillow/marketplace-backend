"""merge_migrations

Revision ID: 199fa9f6522b
Revises: add_boost_001, f46fc4dc5909
Create Date: 2026-01-09 14:40:43.940281

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '199fa9f6522b'
down_revision = ('add_boost_001', 'f46fc4dc5909')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
