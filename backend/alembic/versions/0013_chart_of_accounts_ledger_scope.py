"""Scope chart of accounts by ledger

Revision ID: 0013_chart_of_accounts_ledger_scope
Revises: 0012_entry_post_status
Create Date: 2026-06-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0013_chart_of_accounts_ledger_scope"
down_revision = "0012_entry_post_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("chart_of_accounts")}
    if "ledger_id" not in columns:
        op.add_column("chart_of_accounts", sa.Column("ledger_id", sa.Integer(), nullable=True))

    for constraint in inspector.get_unique_constraints("chart_of_accounts"):
        if constraint.get("column_names") == ["code"] and constraint.get("name"):
            op.drop_constraint(constraint["name"], "chart_of_accounts", type_="unique")

    index_names = {index["name"] for index in inspector.get_indexes("chart_of_accounts")}
    if "ix_chart_of_accounts_ledger_id" not in index_names:
        op.create_index("ix_chart_of_accounts_ledger_id", "chart_of_accounts", ["ledger_id"])

    unique_constraints = {
        tuple(constraint.get("column_names") or [])
        for constraint in inspector.get_unique_constraints("chart_of_accounts")
    }
    if ("ledger_id", "code") not in unique_constraints:
        op.create_unique_constraint(
            "uq_chart_of_accounts_ledger_code",
            "chart_of_accounts",
            ["ledger_id", "code"],
        )
    op.create_foreign_key(
        "fk_chart_of_accounts_ledger_id_ledgers",
        "chart_of_accounts",
        "ledgers",
        ["ledger_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_chart_of_accounts_ledger_id_ledgers", "chart_of_accounts", type_="foreignkey")
    op.drop_constraint("uq_chart_of_accounts_ledger_code", "chart_of_accounts", type_="unique")
    op.drop_index("ix_chart_of_accounts_ledger_id", table_name="chart_of_accounts")
    op.drop_column("chart_of_accounts", "ledger_id")
