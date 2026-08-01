"""add contract deep analysis field

Revision ID: 0029_add_contract_deep_analysis
Revises: 0028_tax_city_egress_pool
Create Date: 2026-07-21

Add deep_analysis JSON field to contracts table for storing ContractDeepAnalyzer results.
"""
from alembic import op
import sqlalchemy as sa

revision = "0029_add_contract_deep_analysis"
down_revision = "0028_tax_city_egress_pool"
branch_labels = None
depends_on = None


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(connection)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    connection = op.get_bind()
    if _column_exists(connection, "contracts", "deep_analysis"):
        return
    op.add_column("contracts", sa.Column("deep_analysis", sa.JSON(), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    if _column_exists(connection, "contracts", "deep_analysis"):
        op.drop_column("contracts", "deep_analysis")