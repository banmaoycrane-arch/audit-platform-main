"""add_draft_data_to_import_jobs

Revision ID: 0015_add_draft_data_to_import_jobs
Revises: 0014_audit_task_ledger_required
Create Date: 2026-06-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '0015_add_draft_data_to_import_jobs'
down_revision = '0014_audit_task_ledger_required'
branch_labels = None
depends_on = None


def upgrade():
    # 为 import_jobs 表添加 draft_data 字段（JSON 类型，可空）
    # 用于保存解析失败时的原始数据，供草稿页面展示和重试
    op.add_column(
        'import_jobs',
        sa.Column('draft_data', sqlite.JSON, nullable=True)
    )
    # 添加 audit_cycles 字段（如果缺失）
    try:
        op.add_column(
            'import_jobs',
            sa.Column('audit_cycles', sqlite.JSON, nullable=True)
        )
    except Exception:
        pass  # 字段已存在


def downgrade():
    # 删除 draft_data 字段
    op.drop_column('import_jobs', 'draft_data')
    try:
        op.drop_column('import_jobs', 'audit_cycles')
    except Exception:
        pass  # 字段不存在
