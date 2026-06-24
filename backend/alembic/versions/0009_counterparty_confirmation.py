"""Add counterparty confirmation control table

Revision ID: 0009_counterparty_confirmation
Revises: 0008_bank_reconciliation
Create Date: 2026-06-23 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0009_counterparty_confirmation"
down_revision = "0008_bank_reconciliation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "counterparty_confirmations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=False),
        sa.Column("counterparty_id", sa.Integer(), nullable=True),
        sa.Column("counterparty_name", sa.String(length=200), nullable=True),
        sa.Column("balance_type", sa.String(length=40), nullable=False),
        sa.Column("book_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("confirmation_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reply_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("difference", sa.Numeric(18, 2), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("replied_at", sa.DateTime(), nullable=True),
        sa.Column("source_file_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["counterparty_id"], ["counterparties.id"]),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_counterparty_confirmations_ledger_id", "counterparty_confirmations", ["ledger_id"])
    op.create_index(
        "ix_counterparty_confirmations_counterparty_id",
        "counterparty_confirmations",
        ["counterparty_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_counterparty_confirmations_counterparty_id", table_name="counterparty_confirmations")
    op.drop_index("ix_counterparty_confirmations_ledger_id", table_name="counterparty_confirmations")
    op.drop_table("counterparty_confirmations")
