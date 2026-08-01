"""缺失数据库索引迁移（运维负债修复）

Revision ID: 0033_ops_missing_indexes
Revises: 0032_dml_cleanup_dirty_data
Create Date: 2026-07-31 12:00:00.000000

修复扫描发现的 3 个高频查询列缺索引问题：
- vouchers.voucher_date  (凭证日期，期间查询核心字段)
- accounting_entries.voucher_date  (分录日期，审计筛选核心字段)
- accounting_entries.post_status  (过账状态，批量过账筛选)

SQLite 限制：SQLite 不支持 DROP INDEX IF EXISTS 的完整语法，
此处仅 CREATE INDEX（不存在则跳过）。
PostgreSQL/MySQL 安全执行。
"""
from alembic import op
import sqlalchemy as sa

revision = "0033_ops_missing_indexes"
down_revision = "0032_dml_cleanup_dirty_data"
branch_labels = None
depends_on = None


def _is_sqlite() -> bool:
    bind = op.get_bind()
    return bind.dialect.name.lower() == "sqlite"


def upgrade() -> None:
    is_sqlite = _is_sqlite()

    if not is_sqlite:
        op.create_index(
            "ix_vouchers_voucher_date",
            "vouchers",
            ["voucher_date"],
            if_not_exists=True,
        )
        op.create_index(
            "ix_accounting_entries_voucher_date",
            "accounting_entries",
            ["voucher_date"],
            if_not_exists=True,
        )
        op.create_index(
            "ix_accounting_entries_post_status",
            "accounting_entries",
            ["post_status"],
            if_not_exists=True,
        )
        op.create_index(
            "ix_accounting_entries_review_status",
            "accounting_entries",
            ["review_status"],
            if_not_exists=True,
        )
        op.create_index(
            "ix_accounting_entries_ledger_id",
            "accounting_entries",
            ["ledger_id"],
            if_not_exists=True,
        )
    else:
        # SQLite: 先检查索引是否已存在
        bind = op.get_bind()
        existing_indexes = set()
        for table_name in ["vouchers", "accounting_entries"]:
            result = bind.execute(
                sa.text(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}'")
            )
            for row in result:
                existing_indexes.add(row[0])

        index_defs = [
            ("ix_vouchers_voucher_date", "vouchers", "voucher_date"),
            ("ix_accounting_entries_voucher_date", "accounting_entries", "voucher_date"),
            ("ix_accounting_entries_post_status", "accounting_entries", "post_status"),
            ("ix_accounting_entries_review_status", "accounting_entries", "review_status"),
            ("ix_accounting_entries_ledger_id", "accounting_entries", "ledger_id"),
        ]

        for idx_name, table, col in index_defs:
            if idx_name not in existing_indexes:
                op.create_index(idx_name, table, [col])


def downgrade() -> None:
    is_sqlite = _is_sqlite()

    if not is_sqlite:
        op.drop_index("ix_accounting_entries_ledger_id", if_exists=True)
        op.drop_index("ix_accounting_entries_review_status", if_exists=True)
        op.drop_index("ix_accounting_entries_post_status", if_exists=True)
        op.drop_index("ix_accounting_entries_voucher_date", if_exists=True)
        op.drop_index("ix_vouchers_voucher_date", if_exists=True)
    else:
        # SQLite: 只能 DROP 存在的索引
        bind = op.get_bind()
        existing_indexes = set()
        for table_name in ["vouchers", "accounting_entries"]:
            result = bind.execute(
                sa.text(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='{table_name}'")
            )
            for row in result:
                existing_indexes.add(row[0])

        for idx_name in [
            "ix_accounting_entries_ledger_id",
            "ix_accounting_entries_review_status",
            "ix_accounting_entries_post_status",
            "ix_accounting_entries_voucher_date",
            "ix_vouchers_voucher_date",
        ]:
            if idx_name in existing_indexes:
                op.drop_index(idx_name)
