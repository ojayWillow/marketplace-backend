"""merge all heads

Revision ID: 096005df6b4d
Revises: 959f3683a5c3, add_notifications_table
Create Date: 2026-01-13 10:41:41.730577+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '096005df6b4d'
down_revision = ('959f3683a5c3', 'add_notifications_table')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass