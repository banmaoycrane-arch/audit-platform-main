"""data integrity constraints: CheckConstraint, UniqueConstraint, ondelete policies

Revision ID: 0031_data_integrity_constraints
Revises: 0030_performance_indexes
Create Date: 2026-07-30 12:00:00.000000

应用 TD-014 数据完整性修复：
1. CheckConstraint：
   - vouchers.status ∈ (draft/pending/verified/posted/cancelled)
   - accounting_entries.review_status ∈ (draft/pending/auto_reviewed/ready/verified/posted)
   - accounting_entries.post_status ∈ (draft/verified/posted)
   - accounting_periods.status ∈ (open/reopened/pl_transferred/closed)
2. UniqueConstraint:
   - accounting_entries (voucher_id, entry_line_no) 名称 uq_entry_voucher_line_no
3. ondelete 策略：
   - Voucher/Entry/Period 三表核心外键
   - 外围表（EntryTag/Counterparty/OpeningBalance/PeriodSnapshot/PeriodCloseLog/
     SourceFile/BankAccount/BankTransaction/BankReconciliation/BankReconciliationItem/
     CounterpartyConfirmation）外键

幂等模式：所有约束/外键创建前先检查是否已存在。
SQLite 兼容：使用 batch_alter_table 重建表以应用 ondelete。
"""
from alembic import op
import sqlalchemy as sa

revision = "0031_data_integrity_constraints"
down_revision = "0030_performance_indexes"
branch_labels = None
depends_on = None


# ==================== 幂等辅助函数 ====================

def _table_exists(connection, table_name: str) -> bool:
    return table_name in set(sa.inspect(connection).get_table_names())


def _index_exists(connection, table_name: str, index_name: str) -> bool:
    if not _table_exists(connection, table_name):
        return False
    return index_name in {idx["name"] for idx in sa.inspect(connection).get_indexes(table_name)}


def _fk_exists(connection, table_name: str, fk_name: str) -> bool:
    if not _table_exists(connection, table_name):
        return False
    return fk_name in {fk["name"] for fk in sa.inspect(connection).get_foreign_keys(table_name) if fk.get("name")}


def _check_constraint_exists(connection, table_name: str, constraint_name: str) -> bool:
    if not _table_exists(connection, table_name):
        return False
    return constraint_name in {
        ck["name"] for ck in sa.inspect(connection).get_check_constraints(table_name) if ck.get("name")
    }


def _unique_constraint_exists(connection, table_name: str, constraint_name: str) -> bool:
    if not _table_exists(connection, table_name):
        return False
    return constraint_name in {
        uq["name"] for uq in sa.inspect(connection).get_unique_constraints(table_name) if uq.get("name")
    }


# ==================== 约束定义 ====================

# (table, constraint_name, condition)
_CHECK_CONSTRAINTS = [
    ("vouchers", "ck_voucher_status_valid",
     "status IN ('draft', 'pending', 'verified', 'posted', 'cancelled')"),
    ("accounting_entries", "ck_entry_review_status_valid",
     "review_status IN ('draft', 'pending', 'auto_reviewed', 'ready', 'verified', 'posted')"),
    ("accounting_entries", "ck_entry_post_status_valid",
     "post_status IN ('draft', 'verified', 'posted')"),
    ("accounting_periods", "ck_accounting_period_status_valid",
     "status IN ('open', 'reopened', 'pl_transferred', 'closed')"),
]

# (table, constraint_name, columns, index_name)
_UNIQUE_CONSTRAINTS = [
    ("accounting_entries", "uq_entry_voucher_line_no", ["voucher_id", "entry_line_no"]),
]

# (table, fk_name, referenced_table, local_cols, remote_cols, ondelete)
# 仅列核心与外围财务表的关键外键；其余外键由 ORM/数据库默认行为兜底。
_ONDELETE_FKS = [
    # ---- Voucher 表 ----
    ("vouchers", "fk_vouchers_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "RESTRICT"),
    ("vouchers", "fk_vouchers_organization_id_organizations", "organizations",
     ["organization_id"], ["id"], "RESTRICT"),
    ("vouchers", "fk_vouchers_import_job_id_import_jobs", "import_jobs",
     ["import_job_id"], ["id"], "SET NULL"),
    ("vouchers", "fk_vouchers_period_id_accounting_periods", "accounting_periods",
     ["period_id"], ["id"], "SET NULL"),
    # ---- AccountingEntry 表 ----
    ("accounting_entries", "fk_accounting_entries_organization_id_organizations", "organizations",
     ["organization_id"], ["id"], "RESTRICT"),
    ("accounting_entries", "fk_accounting_entries_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "SET NULL"),
    ("accounting_entries", "fk_accounting_entries_import_job_id_import_jobs", "import_jobs",
     ["import_job_id"], ["id"], "SET NULL"),
    ("accounting_entries", "fk_accounting_entries_voucher_id_vouchers", "vouchers",
     ["voucher_id"], ["id"], "CASCADE"),
    ("accounting_entries", "fk_accounting_entries_entity_id_entities", "entities",
     ["entity_id"], ["id"], "SET NULL"),
    ("accounting_entries", "fk_accounting_entries_source_file_id_source_files", "source_files",
     ["source_file_id"], ["id"], "SET NULL"),
    ("accounting_entries", "fk_accounting_entries_counterparty_id_counterparties", "counterparties",
     ["counterparty_id"], ["id"], "SET NULL"),
    ("accounting_entries", "fk_accounting_entries_posted_by_users", "users",
     ["posted_by"], ["id"], "SET NULL"),
    # ---- AccountingPeriod 表 ----
    ("accounting_periods", "fk_accounting_periods_organization_id_organizations", "organizations",
     ["organization_id"], ["id"], "RESTRICT"),
    ("accounting_periods", "fk_accounting_periods_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "SET NULL"),
    # ---- EntryTag 表 ----
    ("entry_tags", "fk_entry_tags_entry_id_accounting_entries", "accounting_entries",
     ["entry_id"], ["id"], "CASCADE"),
    ("entry_tags", "fk_entry_tags_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "SET NULL"),
    ("entry_tags", "fk_entry_tags_category_id_tag_categories", "tag_categories",
     ["category_id"], ["id"], "SET NULL"),
    # ---- OpeningBalance 表 ----
    ("opening_balances", "fk_opening_balances_organization_id_organizations", "organizations",
     ["organization_id"], ["id"], "RESTRICT"),
    ("opening_balances", "fk_opening_balances_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "SET NULL"),
    ("opening_balances", "fk_opening_balances_period_id_accounting_periods", "accounting_periods",
     ["period_id"], ["id"], "CASCADE"),
    # ---- PeriodSnapshot 表 ----
    ("period_snapshots", "fk_period_snapshots_organization_id_organizations", "organizations",
     ["organization_id"], ["id"], "RESTRICT"),
    ("period_snapshots", "fk_period_snapshots_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "SET NULL"),
    ("period_snapshots", "fk_period_snapshots_period_id_accounting_periods", "accounting_periods",
     ["period_id"], ["id"], "CASCADE"),
    # ---- PeriodCloseLog 表 ----
    ("period_close_logs", "fk_period_close_logs_organization_id_organizations", "organizations",
     ["organization_id"], ["id"], "RESTRICT"),
    ("period_close_logs", "fk_period_close_logs_period_id_accounting_periods", "accounting_periods",
     ["period_id"], ["id"], "SET NULL"),
    # ---- SourceFile 表 ----
    ("source_files", "fk_source_files_organization_id_organizations", "organizations",
     ["organization_id"], ["id"], "RESTRICT"),
    ("source_files", "fk_source_files_import_job_id_import_jobs", "import_jobs",
     ["import_job_id"], ["id"], "CASCADE"),
    ("source_files", "fk_source_files_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "SET NULL"),
    ("source_files", "fk_source_files_counterparty_id_counterparties", "counterparties",
     ["counterparty_id"], ["id"], "SET NULL"),
    # ---- BankAccount 表 ----
    ("bank_accounts", "fk_bank_accounts_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "RESTRICT"),
    # ---- BankTransaction 表 ----
    ("bank_transactions", "fk_bank_transactions_bank_account_id_bank_accounts", "bank_accounts",
     ["bank_account_id"], ["id"], "CASCADE"),
    ("bank_transactions", "fk_bank_transactions_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "RESTRICT"),
    ("bank_transactions", "fk_bank_transactions_matched_entry_id_accounting_entries", "accounting_entries",
     ["matched_entry_id"], ["id"], "SET NULL"),
    # ---- BankReconciliation 表 ----
    ("bank_reconciliations", "fk_bank_reconciliations_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "RESTRICT"),
    ("bank_reconciliations", "fk_bank_reconciliations_bank_account_id_bank_accounts", "bank_accounts",
     ["bank_account_id"], ["id"], "CASCADE"),
    # ---- BankReconciliationItem 表 ----
    ("bank_reconciliation_items", "fk_bank_reconciliation_items_reconciliation_id_bank_reconciliations",
     "bank_reconciliations", ["reconciliation_id"], ["id"], "CASCADE"),
    ("bank_reconciliation_items", "fk_bank_reconciliation_items_bank_transaction_id_bank_transactions",
     "bank_transactions", ["bank_transaction_id"], ["id"], "SET NULL"),
    ("bank_reconciliation_items", "fk_bank_reconciliation_items_entry_id_accounting_entries",
     "accounting_entries", ["entry_id"], ["id"], "SET NULL"),
    # ---- CounterpartyConfirmation 表 ----
    ("counterparty_confirmations", "fk_counterparty_confirmations_ledger_id_ledgers", "ledgers",
     ["ledger_id"], ["id"], "RESTRICT"),
    ("counterparty_confirmations", "fk_counterparty_confirmations_counterparty_id_counterparties",
     "counterparties", ["counterparty_id"], ["id"], "SET NULL"),
    ("counterparty_confirmations", "fk_counterparty_confirmations_source_file_id_source_files",
     "source_files", ["source_file_id"], ["id"], "SET NULL"),
]


def upgrade() -> None:
    connection = op.get_bind()

    # ---------- 1. 应用 CheckConstraint ----------
    for table_name, ck_name, condition in _CHECK_CONSTRAINTS:
        if not _table_exists(connection, table_name):
            continue
        if _check_constraint_exists(connection, table_name, ck_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_check_constraint(ck_name, condition)

    # ---------- 2. 应用 UniqueConstraint ----------
    for table_name, uq_name, columns in _UNIQUE_CONSTRAINTS:
        if not _table_exists(connection, table_name):
            continue
        if _unique_constraint_exists(connection, table_name, uq_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_unique_constraint(uq_name, columns)

    # ---------- 3. 应用 ondelete 策略（drop 旧 fk + create 新 fk） ----------
    for table_name, fk_name, ref_table, local_cols, remote_cols, ondelete in _ONDELETE_FKS:
        if not _table_exists(connection, table_name):
            continue
        if not _table_exists(connection, ref_table):
            continue
        # 若新外键已存在，跳过
        if _fk_exists(connection, table_name, fk_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            # 不显式 drop 旧 fk：SQLite 下 drop_constraint 会在 batch_alter_table
            # 退出时触发 ValueError（约束名不匹配），而 batch_alter_table 重建
            # 表时旧约束会自动丢失，无需显式 drop。
            batch_op.create_foreign_key(
                fk_name,
                ref_table,
                local_cols,
                remote_cols,
                ondelete=ondelete,
            )


def downgrade() -> None:
    """回滚：仅删除本迁移新增的 CheckConstraint / UniqueConstraint。

    ondelete 外键不回滚（ondelete 策略对现有数据无破坏性，回滚反而会丢失完整性保护）。
    """
    connection = op.get_bind()

    # 删除 UniqueConstraint
    for table_name, uq_name, columns in reversed(_UNIQUE_CONSTRAINTS):
        if not _table_exists(connection, table_name):
            continue
        if not _unique_constraint_exists(connection, table_name, uq_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(uq_name, type_="unique")

    # 删除 CheckConstraint
    for table_name, ck_name, condition in reversed(_CHECK_CONSTRAINTS):
        if not _table_exists(connection, table_name):
            continue
        if not _check_constraint_exists(connection, table_name, ck_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(ck_name, type_="check")
