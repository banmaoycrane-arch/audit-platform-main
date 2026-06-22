"""Add ledger scope and contract execution status to register tables

Revision ID: 0007_add_register_ledger_scope
Revises: 0006_add_entity_id_to_accounting_units
Create Date: 2026-06-21 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0007_add_register_ledger_scope"
down_revision = "0006_add_entity_id_to_accounting_units"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contracts", sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("ledgers.id"), nullable=True))
    op.add_column("contracts", sa.Column("counterparty_id", sa.Integer(), sa.ForeignKey("counterparties.id"), nullable=True))
    op.add_column(
        "contracts",
        sa.Column("execution_status", sa.String(length=30), nullable=False, server_default="pending"),
    )
    op.create_index("ix_contracts_ledger_id", "contracts", ["ledger_id"])

    op.add_column("invoices", sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("ledgers.id"), nullable=True))
    op.add_column("invoices", sa.Column("counterparty_id", sa.Integer(), sa.ForeignKey("counterparties.id"), nullable=True))
    op.create_index("ix_invoices_ledger_id", "invoices", ["ledger_id"])

    op.add_column("bank_statements", sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("ledgers.id"), nullable=True))
    op.add_column(
        "bank_statements",
        sa.Column("counterparty_id", sa.Integer(), sa.ForeignKey("counterparties.id"), nullable=True),
    )
    op.create_index("ix_bank_statements_ledger_id", "bank_statements", ["ledger_id"])

    op.add_column(
        "inventory_documents",
        sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("ledgers.id"), nullable=True),
    )
    op.add_column(
        "inventory_documents",
        sa.Column("counterparty_id", sa.Integer(), sa.ForeignKey("counterparties.id"), nullable=True),
    )
    op.create_index("ix_inventory_documents_ledger_id", "inventory_documents", ["ledger_id"])


def downgrade() -> None:
    op.drop_index("ix_inventory_documents_ledger_id", table_name="inventory_documents")
    op.drop_column("inventory_documents", "counterparty_id")
    op.drop_column("inventory_documents", "ledger_id")

    op.drop_index("ix_bank_statements_ledger_id", table_name="bank_statements")
    op.drop_column("bank_statements", "counterparty_id")
    op.drop_column("bank_statements", "ledger_id")

    op.drop_index("ix_invoices_ledger_id", table_name="invoices")
    op.drop_column("invoices", "counterparty_id")
    op.drop_column("invoices", "ledger_id")

    op.drop_index("ix_contracts_ledger_id", table_name="contracts")
    op.drop_column("contracts", "execution_status")
    op.drop_column("contracts", "counterparty_id")
    op.drop_column("contracts", "ledger_id")
