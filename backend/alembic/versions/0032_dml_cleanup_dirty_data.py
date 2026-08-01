"""DML 数据修复：清理历史脏数据

Revision ID: 0032_dml_cleanup_dirty_data
Revises: 0031_data_integrity_constraints
Create Date: 2026-07-30 16:00:00.000000

与 0031_data_integrity_constraints 配套：
- 清理 vouchers.voucher_no / accounting_entries.account_code / account_name 前后空格
- 规范化已过账凭证的 voucher_no（确保非空）
- 对 voucher 合计与分录汇总不一致的，以分录为准重算 voucher.total_debit / total_credit

幂等模式：每次 WHERE 条件都只处理「仍然脏」的记录，重复执行安全。
WARNING: 0032 为 DML 迁移，不修改表结构。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "0032_dml_cleanup_dirty_data"
down_revision = "0031_data_integrity_constraints"
branch_labels = None
depends_on = None


def _dialect_is_sqlite() -> bool:
    bind = op.get_bind()
    return bind.dialect.name.lower() == "sqlite"


def _is_postgres() -> bool:
    bind = op.get_bind()
    return bind.dialect.name.lower() == "postgresql"


def upgrade() -> None:
    # 说明：Alembic 的 connection 方式对 DML 各数据库通用。
    # 所有 UPDATE 均带 WHERE 条件，保证幂等。

    # --- 1. voucher_no 前后空格清理 ---
    op.execute(text("""
        UPDATE vouchers
        SET voucher_no = TRIM(voucher_no)
        WHERE (voucher_no LIKE ' %' OR voucher_no LIKE '% ')
    """))

    # --- 2. 分录 account_code 前后空格清理 ---
    op.execute(text("""
        UPDATE accounting_entries
        SET account_code = TRIM(account_code)
        WHERE (account_code LIKE ' %' OR account_code LIKE '% ')
    """))

    # --- 3. 分录 account_name 前后空格清理 ---
    op.execute(text("""
        UPDATE accounting_entries
        SET account_name = TRIM(account_name)
        WHERE (account_name LIKE ' %' OR account_name LIKE '% ')
    """))

    # --- 4. 已过账凭证 voucher_no 不可空：填 "已过账-未编号-{id}" ---
    op.execute(text("""
        UPDATE vouchers
        SET voucher_no = '已过账-未编号-' || CAST(id AS VARCHAR)
        WHERE status = 'posted'
          AND (voucher_no IS NULL OR TRIM(voucher_no) = '')
    """))

    # --- 5. voucher 合计与分录汇总不一致，以分录为准重算 ---
    # SQLite/PG 都支持这种语法
    if _is_postgres():
        op.execute(text("""
            UPDATE vouchers v
            SET total_debit = COALESCE(e.debits, 0),
                total_credit = COALESCE(e.credits, 0)
            FROM (
                SELECT voucher_id,
                       SUM(debit_amount) AS debits,
                       SUM(credit_amount) AS credits
                FROM accounting_entries
                WHERE voucher_id IS NOT NULL
                GROUP BY voucher_id
            ) e
            WHERE v.id = e.voucher_id
              AND (v.total_debit <> e.debits OR v.total_credit <> e.credits)
        """))
    else:
        # SQLite 3.33+ 支持 UPDATE-FROM；更早版本用子查询。下面写双路子查询兜底写法。
        op.execute(text("""
            UPDATE vouchers
            SET total_debit = COALESCE((
                    SELECT SUM(debit_amount)
                    FROM accounting_entries
                    WHERE accounting_entries.voucher_id = vouchers.id
                ), 0),
                total_credit = COALESCE((
                    SELECT SUM(credit_amount)
                    FROM accounting_entries
                    WHERE accounting_entries.voucher_id = vouchers.id
                ), 0)
            WHERE EXISTS (
                SELECT 1 FROM accounting_entries e
                WHERE e.voucher_id = vouchers.id
            ) AND (
                total_debit <> COALESCE((
                    SELECT SUM(debit_amount)
                    FROM accounting_entries
                    WHERE accounting_entries.voucher_id = vouchers.id
                ), 0)
                OR
                total_credit <> COALESCE((
                    SELECT SUM(credit_amount)
                    FROM accounting_entries
                    WHERE accounting_entries.voucher_id = vouchers.id
                ), 0)
            )
        """))


def downgrade() -> None:
    """0032 为 DML 数据清理，无法回滚（无法还原已被清理的空格）。

    downgrade 留空：保证 `alembic downgrade` 可执行，但不修改任何数据。
    理由：trim 操作是「有损压缩」，原空格不可复原；voucher 合计重算也是最终一致性。
    """
    pass
