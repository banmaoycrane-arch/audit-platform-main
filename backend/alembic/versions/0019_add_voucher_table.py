"""add voucher table and voucher_id to accounting_entries

Revision ID: 0019_add_voucher_table
Revises: 0018_add_entity_legal_type
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0019_add_voucher_table"
down_revision = "0018_add_entity_legal_type"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return table_name in set(sa.inspect(connection).get_table_names())


def _column_exists(connection, table_name, column_name):
    columns = sa.inspect(connection).get_columns(table_name)
    return column_name in {col["name"] for col in columns}


def upgrade():
    """
    1. 创建 vouchers 表（凭证主表）。
    2. 在 accounting_entries 表中增加 voucher_id 外键（可空，兼容历史数据）。
    3. 将 import_job_id 改为可空（部分凭证不来自导入）。
    """
    connection = op.get_bind()

    # 1. 创建 vouchers 表
    if not _table_exists(connection, "vouchers"):
        op.create_table(
            "vouchers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ledger_id", sa.Integer(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=False),
            sa.Column("voucher_no", sa.String(100), nullable=False),
            sa.Column("voucher_date", sa.Date(), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("source_type", sa.String(40), nullable=False, default="manual"),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("import_job_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, default="draft"),
            sa.Column("total_debit", sa.Numeric(14, 2), nullable=False, default=0),
            sa.Column("total_credit", sa.Numeric(14, 2), nullable=False, default=0),
            sa.Column("posted_at", sa.DateTime(), nullable=True),
            sa.Column("posted_by", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("ledger_id", "voucher_no", name="uq_voucher_ledger_no"),
            sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
            sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"]),
            sa.ForeignKeyConstraint(["posted_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        )

    # 2. accounting_entries 增加 voucher_id
    if not _column_exists(connection, "accounting_entries", "voucher_id"):
        with op.batch_alter_table("accounting_entries") as batch_op:
            batch_op.add_column(
                sa.Column("voucher_id", sa.Integer(), nullable=True),
            )
            batch_op.create_foreign_key(
                "fk_accounting_entries_voucher_id",
                "vouchers",
                ["voucher_id"],
                ["id"],
            )

    # 3. accounting_entries.import_job_id 改为可空
    if _column_exists(connection, "accounting_entries", "import_job_id"):
        # SQLite 不支持直接 ALTER COLUMN，需要先临时创建新表，但此处业务上仅允许 NULL。
        # 如果旧列已经是 nullable=False，可以通过 batch_alter_table 修改。
        with op.batch_alter_table("accounting_entries") as batch_op:
            batch_op.alter_column(
                "import_job_id",
                existing_type=sa.Integer(),
                nullable=True,
            )


def downgrade():
    """回滚：删除 vouchers 表和 voucher_id 列。"""
    connection = op.get_bind()

    if _column_exists(connection, "accounting_entries", "voucher_id"):
        with op.batch_alter_table("accounting_entries") as batch_op:
            batch_op.drop_constraint("fk_accounting_entries_voucher_id", type_="foreignkey")
            batch_op.drop_column("voucher_id")

    if _table_exists(connection, "vouchers"):
        op.drop_table("vouchers")
