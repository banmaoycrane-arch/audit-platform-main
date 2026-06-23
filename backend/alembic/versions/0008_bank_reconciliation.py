"""Add bank reconciliation draft tables

Revision ID: 0008_bank_reconciliation
Revises: 0007_add_register_ledger_scope
Create Date: 2026-06-23 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0008_bank_reconciliation"
down_revision = "0007_add_register_ledger_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_reconciliations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=False),
        sa.Column("bank_account_id", sa.Integer(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("statement_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("book_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("adjusted_statement_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("adjusted_book_balance", sa.Numeric(18, 2), nullable=False),
        sa.Column("difference", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["bank_account_id"], ["bank_accounts.id"]),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bank_reconciliations_ledger_id", "bank_reconciliations", ["ledger_id"])
    op.create_index("ix_bank_reconciliations_bank_account_id", "bank_reconciliations", ["bank_account_id"])

    op.create_table(
        "bank_reconciliation_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("reconciliation_id", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=40), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("direction", sa.String(length=10), nullable=True),
        sa.Column("bank_transaction_id", sa.Integer(), nullable=True),
        sa.Column("entry_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(length=500), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["bank_transaction_id"], ["bank_transactions.id"]),
        sa.ForeignKeyConstraint(["entry_id"], ["accounting_entries.id"]),
        sa.ForeignKeyConstraint(["reconciliation_id"], ["bank_reconciliations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bank_reconciliation_items_reconciliation_id",
        "bank_reconciliation_items",
        ["reconciliation_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_reconciliation_items_reconciliation_id", table_name="bank_reconciliation_items")
    op.drop_table("bank_reconciliation_items")
    op.drop_index("ix_bank_reconciliations_bank_account_id", table_name="bank_reconciliations")
    op.drop_index("ix_bank_reconciliations_ledger_id", table_name="bank_reconciliations")
    op.drop_table("bank_reconciliations")
