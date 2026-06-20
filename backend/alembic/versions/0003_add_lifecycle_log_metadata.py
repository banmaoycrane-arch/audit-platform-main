"""Add metadata to lifecycle logs

Revision ID: 0003_add_lifecycle_log_metadata
Revises: 0002_add_ledger_id_to_import_jobs
Create Date: 2026-06-19 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_add_lifecycle_log_metadata'
down_revision = '0002_add_ledger_id_to_import_jobs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('lifecycle_logs', sa.Column('log_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('lifecycle_logs', 'log_metadata')
