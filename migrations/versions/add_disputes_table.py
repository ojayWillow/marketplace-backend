"""Add disputes table for task conflict resolution.

Revision ID: add_disputes_table
Revises: 096005df6b4d
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_disputes_table'
down_revision = '096005df6b4d'
branch_labels = None
depends_on = None


def upgrade():
    # Create disputes table
    op.create_table('disputes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('filed_by_id', sa.Integer(), nullable=False),
        sa.Column('filed_against_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('evidence_images', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='open'),
        sa.Column('resolution', sa.String(length=20), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('response_description', sa.Text(), nullable=True),
        sa.Column('response_images', sa.JSON(), nullable=True),
        sa.Column('responded_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['filed_against_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['filed_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['task_id'], ['task_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for common queries
    op.create_index(op.f('ix_disputes_task_id'), 'disputes', ['task_id'], unique=False)
    op.create_index(op.f('ix_disputes_filed_by_id'), 'disputes', ['filed_by_id'], unique=False)
    op.create_index(op.f('ix_disputes_filed_against_id'), 'disputes', ['filed_against_id'], unique=False)
    op.create_index(op.f('ix_disputes_status'), 'disputes', ['status'], unique=False)
    op.create_index(op.f('ix_disputes_created_at'), 'disputes', ['created_at'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index(op.f('ix_disputes_created_at'), table_name='disputes')
    op.drop_index(op.f('ix_disputes_status'), table_name='disputes')
    op.drop_index(op.f('ix_disputes_filed_against_id'), table_name='disputes')
    op.drop_index(op.f('ix_disputes_filed_by_id'), table_name='disputes')
    op.drop_index(op.f('ix_disputes_task_id'), table_name='disputes')
    
    # Drop table
    op.drop_table('disputes')
