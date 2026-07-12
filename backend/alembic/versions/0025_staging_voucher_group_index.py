"""staging voucher group composite index for preview-vouchers SQL pagination

Revision ID: 0025_staging_voucher_group_index
Revises: 0024_voucher_signature_chain
Create Date: 2026-07-09 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0025_staging_voucher_group_index"
down_revision = "0024_voucher_signature_chain"
branch_labels = None
depends_on = None

INDEX_NAME = "ix_staging_accounting_entries_job_voucher"
TABLE_NAME = "staging_accounting_entries"
INDEX_COLUMNS = ("import_job_id", "voucher_no", "voucher_date")


def _table_exists(connection, table_name: str) -> bool:
    return table_name in set(sa.inspect(connection).get_table_names())


def _index_exists(connection, table_name: str, index_name: str) -> bool:
    return index_name in {idx["name"] for idx in sa.inspect(connection).get_indexes(table_name)}


def upgrade() -> None:
    connection = op.get_bind()
    if not _table_exists(connection, TABLE_NAME):
        return
    if _index_exists(connection, TABLE_NAME, INDEX_NAME):
        return
    op.create_index(INDEX_NAME, TABLE_NAME, list(INDEX_COLUMNS))


def downgrade() -> None:
    connection = op.get_bind()
    if not _table_exists(connection, TABLE_NAME):
        return
    if not _index_exists(connection, TABLE_NAME, INDEX_NAME):
        return
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
