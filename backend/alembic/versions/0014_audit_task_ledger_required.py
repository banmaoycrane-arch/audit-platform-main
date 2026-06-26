"""Make audit_tasks ledger_id non-nullable.

Revision ID: 0014_audit_task_ledger_required
Revises: 0013_audit_collaboration_workflow
Create Date: 2026-06-26 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0014_audit_task_ledger_required'
down_revision = '0013_audit_collaboration_workflow'
branch_labels = None
depends_on = None


def upgrade():
    """将 audit_tasks 的 ledger_id 改为非空，确保审计任务必须绑定账套。"""
    op.alter_column('audit_tasks', 'ledger_id', nullable=False)


def downgrade():
    """将 audit_tasks 的 ledger_id 改回可空。"""
    op.alter_column('audit_tasks', 'ledger_id', nullable=True)
