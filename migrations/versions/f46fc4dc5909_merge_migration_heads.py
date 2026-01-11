"""merge migration heads

Revision ID: f46fc4dc5909
Revises: 718f1abd1e2f, add_last_seen_001
Create Date: 2026-01-09 08:54:39.105800

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f46fc4dc5909'
down_revision = ('718f1abd1e2f', 'add_last_seen_001')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
