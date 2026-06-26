"""Add voucher post status fields to accounting_entries

Revision ID: 0012_entry_post_status
Revises: 0011_audit_workflow
Create Date: 2026-06-25 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0012_entry_post_status"
down_revision = "0011_audit_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "accounting_entries",
        sa.Column("post_status", sa.String(length=20), nullable=False, server_default="draft"),
    )
    op.add_column(
        "accounting_entries",
        sa.Column("posted_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "accounting_entries",
        sa.Column("posted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("accounting_entries", "posted_by")
    op.drop_column("accounting_entries", "posted_at")
    op.drop_column("accounting_entries", "post_status")
