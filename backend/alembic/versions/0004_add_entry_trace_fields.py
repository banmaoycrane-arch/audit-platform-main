"""Add entry trace fields to accounting_entries

Revision ID: 0004_add_entry_trace_fields
Revises: 0003_add_lifecycle_log_metadata
Create Date: 2026-06-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_add_entry_trace_fields'
down_revision = '0003_add_lifecycle_log_metadata'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 新增 source_file_id 字段：关联到源文件，实现分录到原始资料的直接追溯
    op.add_column(
        'accounting_entries',
        sa.Column('source_file_id', sa.Integer(), sa.ForeignKey('source_files.id'), nullable=True)
    )
    # 新增 entry_source 字段：区分自动生成与手工录入
    op.add_column(
        'accounting_entries',
        sa.Column('entry_source', sa.String(20), nullable=False, server_default='auto')
    )


def downgrade() -> None:
    op.drop_column('accounting_entries', 'entry_source')
    op.drop_column('accounting_entries', 'source_file_id')
