"""Add payment fields to task_requests table

Revision ID: add_payment_fields
Revises: 096005df6b4d
Create Date: 2026-01-28 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_payment_fields'
down_revision = '096005df6b4d'
branch_labels = None
depends_on = None


def upgrade():
    # Add payment_required column
    op.add_column('task_requests', sa.Column('payment_required', sa.Boolean(), nullable=True, server_default='false'))
    
    # Add payment_status column
    op.add_column('task_requests', sa.Column('payment_status', sa.String(length=50), nullable=True))
    
    # Add transaction_id column
    op.add_column('task_requests', sa.Column('transaction_id', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('task_requests', 'transaction_id')
    op.drop_column('task_requests', 'payment_status')
    op.drop_column('task_requests', 'payment_required')
