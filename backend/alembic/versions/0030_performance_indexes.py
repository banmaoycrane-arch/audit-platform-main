"""performance indexes for accounting_entries and audit_findings

Revision ID: 0030_performance_indexes
Revises: 0029_add_contract_deep_analysis
Create Date: 2026-07-30 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0030_performance_indexes"
down_revision = "0029_add_contract_deep_analysis"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name: str) -> bool:
    return table_name in set(sa.inspect(connection).get_table_names())


def _index_exists(connection, table_name: str, index_name: str) -> bool:
    return index_name in {idx["name"] for idx in sa.inspect(connection).get_indexes(table_name)}


_INDEXES = [
    ("ix_entry_ledger_date", "accounting_entries", ["ledger_id", "voucher_date"]),
    ("ix_entry_import_job", "accounting_entries", ["import_job_id"]),
    ("ix_entry_org_account_date", "accounting_entries", ["organization_id", "account_code", "voucher_date"]),
    ("ix_entry_voucher_id", "accounting_entries", ["voucher_id"]),
    ("ix_audit_finding_ledger", "audit_findings", ["ledger_id"]),
    ("ix_audit_finding_job", "audit_findings", ["job_id"]),
    ("ix_audit_finding_status", "audit_findings", ["status"]),
]


def upgrade() -> None:
    connection = op.get_bind()
    for index_name, table_name, columns in _INDEXES:
        if not _table_exists(connection, table_name):
            continue
        if _index_exists(connection, table_name, index_name):
            continue
        op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    connection = op.get_bind()
    for index_name, table_name, columns in reversed(_INDEXES):
        if not _table_exists(connection, table_name):
            continue
        if not _index_exists(connection, table_name, index_name):
            continue
        op.drop_index(index_name, table_name=table_name)
