"""voucher signature chain: source preparer, cross reviewer, approver

Revision ID: 0024_voucher_signature_chain
Revises: 0023_structured_import_staging
Create Date: 2026-07-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0024_voucher_signature_chain"
down_revision = "0023_structured_import_staging"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name: str) -> bool:
    return table_name in set(sa.inspect(connection).get_table_names())


def _add_column_if_missing(connection, table: str, column: str, ddl: str) -> None:
    cols = {c["name"] for c in sa.inspect(connection).get_columns(table)}
    if column not in cols:
        op.execute(sa.text(ddl))


def upgrade() -> None:
    connection = op.get_bind()
    if not _table_exists(connection, "vouchers"):
        return

    _add_column_if_missing(
        connection,
        "vouchers",
        "source_preparer_name",
        "ALTER TABLE vouchers ADD COLUMN source_preparer_name VARCHAR(200)",
    )
    _add_column_if_missing(
        connection,
        "vouchers",
        "cross_reviewed_by_user_id",
        "ALTER TABLE vouchers ADD COLUMN cross_reviewed_by_user_id INTEGER REFERENCES users(id)",
    )
    _add_column_if_missing(
        connection,
        "vouchers",
        "cross_reviewed_at",
        "ALTER TABLE vouchers ADD COLUMN cross_reviewed_at DATETIME",
    )
    _add_column_if_missing(
        connection,
        "vouchers",
        "approved_by_user_id",
        "ALTER TABLE vouchers ADD COLUMN approved_by_user_id INTEGER REFERENCES users(id)",
    )
    _add_column_if_missing(
        connection,
        "vouchers",
        "approved_at",
        "ALTER TABLE vouchers ADD COLUMN approved_at DATETIME",
    )

    if _table_exists(connection, "staging_accounting_entries"):
        _add_column_if_missing(
            connection,
            "staging_accounting_entries",
            "source_preparer_name",
            "ALTER TABLE staging_accounting_entries ADD COLUMN source_preparer_name VARCHAR(200)",
        )
        _add_column_if_missing(
            connection,
            "staging_accounting_entries",
            "cross_reviewed_by_user_id",
            "ALTER TABLE staging_accounting_entries ADD COLUMN cross_reviewed_by_user_id INTEGER REFERENCES users(id)",
        )
        _add_column_if_missing(
            connection,
            "staging_accounting_entries",
            "cross_reviewed_at",
            "ALTER TABLE staging_accounting_entries ADD COLUMN cross_reviewed_at DATETIME",
        )


def downgrade() -> None:
    connection = op.get_bind()
    for table, cols in (
        ("vouchers", ["approved_at", "approved_by_user_id", "cross_reviewed_at", "cross_reviewed_by_user_id", "source_preparer_name"]),
        ("staging_accounting_entries", ["cross_reviewed_at", "cross_reviewed_by_user_id", "source_preparer_name"]),
    ):
        if not _table_exists(connection, table):
            continue
        existing = {c["name"] for c in sa.inspect(connection).get_columns(table)}
        for col in cols:
            if col in existing:
                op.drop_column(table, col)
