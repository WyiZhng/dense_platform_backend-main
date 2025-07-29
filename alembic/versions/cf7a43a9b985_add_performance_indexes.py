"""add_performance_indexes

Revision ID: cf7a43a9b985
Revises: c5dbe4057398
Create Date: 2025-07-19 10:30:51.749820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf7a43a9b985'
down_revision: Union[str, None] = 'c5dbe4057398'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add performance indexes for User table
    op.create_index('idx_user_type_active', 'user', ['type', 'is_active'])
    op.create_index('idx_user_last_login', 'user', ['last_login'])
    op.create_index('idx_user_created_at', 'user', ['created_at'])
    
    # Add performance indexes for DenseReport table
    op.create_index('idx_report_user_status', 'dense_report', ['user', 'current_status'])
    op.create_index('idx_report_doctor_status', 'dense_report', ['doctor', 'current_status'])
    op.create_index('idx_report_submit_time', 'dense_report', ['submitTime'])
    op.create_index('idx_report_status_time', 'dense_report', ['current_status', 'submitTime'])


def downgrade() -> None:
    # Remove performance indexes for DenseReport table
    op.drop_index('idx_report_status_time', 'dense_report')
    op.drop_index('idx_report_submit_time', 'dense_report')
    op.drop_index('idx_report_doctor_status', 'dense_report')
    op.drop_index('idx_report_user_status', 'dense_report')
    
    # Remove performance indexes for User table
    op.drop_index('idx_user_created_at', 'user')
    op.drop_index('idx_user_last_login', 'user')
    op.drop_index('idx_user_type_active', 'user')
