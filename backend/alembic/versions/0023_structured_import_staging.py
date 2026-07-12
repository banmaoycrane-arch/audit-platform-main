"""structured import staging tables and working ledger flags

Revision ID: 0023_structured_import_staging
Revises: 0022_add_parse_quality_metrics
Create Date: 2026-07-07 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "0023_structured_import_staging"
down_revision = "0022_add_parse_quality_metrics"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name: str) -> bool:
    return table_name in set(sa.inspect(connection).get_table_names())


def upgrade() -> None:
    connection = op.get_bind()

    if not _table_exists(connection, "ledgers"):
        return

    ledger_cols = {col["name"] for col in sa.inspect(connection).get_columns("ledgers")}
    if "is_working" not in ledger_cols:
        op.add_column(
            "ledgers",
            sa.Column("is_working", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
    if "project_id" not in ledger_cols:
        op.add_column("ledgers", sa.Column("project_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_ledgers_project_id",
            "ledgers",
            "projects",
            ["project_id"],
            ["id"],
        )

    staging_tables = [
        (
            "staging_accounting_entries",
            [
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("import_job_id", sa.Integer(), sa.ForeignKey("import_jobs.id"), nullable=False),
                sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
                sa.Column("ledger_id", sa.Integer(), sa.ForeignKey("ledgers.id"), nullable=True),
                sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id"), nullable=True),
                sa.Column("entity_org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=True),
                sa.Column("import_mode", sa.String(8), nullable=False, server_default="A"),
                sa.Column("source_type", sa.String(40), nullable=False, server_default="ledger_day_book"),
                sa.Column("voucher_no", sa.String(100), nullable=True),
                sa.Column("voucher_date", sa.Date(), nullable=True),
                sa.Column("summary", sa.Text(), nullable=True),
                sa.Column("account_code", sa.String(100), nullable=True),
                sa.Column("account_name", sa.String(200), nullable=True),
                sa.Column("resolved_account_code", sa.String(100), nullable=True),
                sa.Column("resolved_account_name", sa.String(200), nullable=True),
                sa.Column("debit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
                sa.Column("credit_amount", sa.Numeric(14, 2), nullable=False, server_default="0"),
                sa.Column("counterparty", sa.String(200), nullable=True),
                sa.Column("counterparty_id", sa.Integer(), sa.ForeignKey("counterparties.id"), nullable=True),
                sa.Column("entry_line_no", sa.Integer(), nullable=False, server_default="1"),
                sa.Column("source_file_id", sa.Integer(), sa.ForeignKey("source_files.id"), nullable=True),
                sa.Column("original_row", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
                sa.Column("normalized_text", sa.Text(), nullable=False, server_default=""),
                sa.Column("entry_tags_payload", sa.JSON(), nullable=True),
                sa.Column("review_status", sa.String(20), nullable=False, server_default="draft"),
                sa.Column("compliance_hint", sa.Text(), nullable=True),
                sa.Column("compliance_severity", sa.String(16), nullable=False, server_default="info"),
                sa.Column("spot_check_flag", sa.Boolean(), nullable=False, server_default=sa.text("0")),
                sa.Column("vector_id", sa.String(128), nullable=True),
                sa.Column("parse_diagnostics", sa.JSON(), nullable=True),
                sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            ],
        ),
    ]

    for table_name, columns in staging_tables:
        if not _table_exists(connection, table_name):
            op.create_table(table_name, *columns)
            op.create_index(f"ix_{table_name}_import_job_id", table_name, ["import_job_id"])


def downgrade() -> None:
    connection = op.get_bind()
    if _table_exists(connection, "staging_accounting_entries"):
        op.drop_table("staging_accounting_entries")
    if _table_exists(connection, "ledgers"):
        ledger_cols = {col["name"] for col in sa.inspect(connection).get_columns("ledgers")}
        if "project_id" in ledger_cols:
            op.drop_constraint("fk_ledgers_project_id", "ledgers", type_="foreignkey")
            op.drop_column("ledgers", "project_id")
        if "is_working" in ledger_cols:
            op.drop_column("ledgers", "is_working")
