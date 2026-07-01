"""ledger_primary_boundary_refactor

Revision ID: 0017_ledger_primary_boundary_refactor
Revises: 0016_add_user_platform_role
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0017_ledger_primary_boundary_refactor"
down_revision = "0016_add_user_platform_role"
branch_labels = None
depends_on = None


# 业务目标：将系统主边界从 organization_id 迁移到 ledger_id，
# 同时保留 organization_id 作为上层会计主体汇总维度。


def _column_exists(connection, table_name, column_name):
    """检查指定表中是否已存在目标列。"""
    columns = {col["name"] for col in sa.inspect(connection).get_columns(table_name)}
    return column_name in columns


def _constraint_exists(connection, table_name, constraint_name):
    """检查指定表中是否已存在目标唯一约束。"""
    constraints = {c["name"] for c in sa.inspect(connection).get_unique_constraints(table_name)}
    return constraint_name in constraints


def _index_exists(connection, table_name, index_name):
    """检查指定表中是否已存在目标索引。"""
    indexes = {idx["name"] for idx in sa.inspect(connection).get_indexes(table_name)}
    return index_name in indexes


def _get_or_create_default_team_id(connection):
    """返回一个可用的 team_id；teams 表为空时自动创建一条默认团队记录。"""
    team_id = connection.execute(
        sa.text("SELECT MIN(id) FROM teams")
    ).scalar()
    if team_id is not None:
        return team_id

    result = connection.execute(
        sa.text("INSERT INTO teams (name, status) VALUES ('默认团队', 'active')")
    )
    return result.lastrowid


def _ensure_ledger_organization_id(connection):
    """确保 ledgers 表存在 organization_id 列（可空）。"""
    if _column_exists(connection, "ledgers", "organization_id"):
        return

    dialect = connection.dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("ledgers") as batch_op:
            batch_op.add_column(
                sa.Column("organization_id", sa.Integer(), nullable=True)
            )
            batch_op.create_foreign_key(
                "fk_ledgers_organizations_id",
                "organizations",
                ["organization_id"],
                ["id"],
            )
    else:
        op.add_column(
            "ledgers",
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id"),
                nullable=True,
            ),
        )


def _get_organization_to_default_ledger_map(connection):
    """返回每个 organization_id 对应的默认 ledger_id 映射。

    映射策略：
    1. 先确保 ledgers 表存在 organization_id 列。
    2. 如果已有 ledger 的 organization_id 非空，则复用该 ledger。
    3. 对于尚无默认 ledger 的 organization，按默认 team 创建一条新 ledger，
       并将该 ledger 与 organization 关联。
    """
    _ensure_ledger_organization_id(connection)

    rows = connection.execute(
        sa.text(
            """
            SELECT organization_id, MIN(id) AS ledger_id
            FROM ledgers
            WHERE organization_id IS NOT NULL
            GROUP BY organization_id
            """
        )
    ).fetchall()
    org_to_ledger = {row.organization_id: row.ledger_id for row in rows}

    all_orgs = connection.execute(
        sa.text("SELECT id FROM organizations ORDER BY id")
    ).fetchall()

    default_team_id = _get_or_create_default_team_id(connection)

    for org in all_orgs:
        org_id = org.id
        if org_id in org_to_ledger:
            continue

        result = connection.execute(
            sa.text(
                """
                INSERT INTO ledgers (name, team_id, status, organization_id)
                VALUES ('默认账簿', :team_id, 'active', :org_id)
                """
            ),
            {"team_id": default_team_id, "org_id": org_id},
        )
        ledger_id = result.lastrowid
        org_to_ledger[org_id] = ledger_id

    return org_to_ledger


def _deduplicate_by_columns(connection, table_name, columns):
    """按指定列组合去重，保留 id 最小的记录。"""
    if not columns:
        return

    column_list = ", ".join(columns)
    connection.execute(
        sa.text(
            f"""
            DELETE FROM {table_name}
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM {table_name}
                GROUP BY {column_list}
            )
            """
        )
    )


def _fill_null_ledger_ids(connection, table_name, org_to_ledger):
    """将指定表中 ledger_id 为空的记录按 organization_id 填充默认 ledger_id。"""
    if not _column_exists(connection, table_name, "ledger_id"):
        return
    if not _column_exists(connection, table_name, "organization_id"):
        # 没有 organization_id 时无法按 org 映射，直接跳过
        return

    for org_id, ledger_id in org_to_ledger.items():
        connection.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET ledger_id = :ledger_id
                WHERE ledger_id IS NULL AND organization_id = :org_id
                """
            ),
            {"ledger_id": ledger_id, "org_id": org_id},
        )


def _add_column_with_fk(table_name, column_name, column_type, fk_target, nullable=True):
    """为表增加列，并在支持的数据库上添加外键约束；SQLite 使用 batch 模式。"""
    dialect = op.get_bind().dialect.name
    fk_name = f"fk_{table_name}_{fk_target.replace('.', '_')}"
    if dialect == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.add_column(
                sa.Column(column_name, column_type, nullable=nullable)
            )
            if fk_target:
                batch_op.create_foreign_key(fk_name, fk_target.split(".")[0], [column_name], [fk_target.split(".")[1]])
    else:
        fk_kwargs = {}
        if fk_target:
            fk_kwargs["foreign_key"] = sa.ForeignKey(fk_target)
        op.add_column(
            table_name,
            sa.Column(column_name, column_type, nullable=nullable, **fk_kwargs),
        )


def _drop_column_with_fk(table_name, column_name, fk_target):
    """移除列及其外键约束，兼容 SQLite batch 模式；约束不存在时忽略。"""
    dialect = op.get_bind().dialect.name
    fk_name = f"fk_{table_name}_{fk_target.replace('.', '_')}"
    if dialect == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_column(column_name)
    else:
        try:
            op.drop_constraint(fk_name, table_name, type_="foreignkey")
        except Exception:
            pass
        op.drop_column(table_name, column_name)


def _create_unique_constraint(table_name, constraint_name, columns):
    """创建唯一约束，兼容 SQLite batch 模式。"""
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_unique_constraint(constraint_name, columns)
    else:
        op.create_unique_constraint(constraint_name, table_name, columns)


def _drop_constraint_safe(table_name, constraint_name, constraint_type):
    """删除约束，兼容 SQLite batch 模式；约束不存在时忽略。"""
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            try:
                batch_op.drop_constraint(constraint_name, type_=constraint_type)
            except Exception:
                pass
    else:
        try:
            op.drop_constraint(constraint_name, table_name, type_=constraint_type)
        except Exception:
            pass


def _alter_column_nullable(table_name, column_name, nullable):
    """修改列的可空性，兼容 SQLite batch 模式。"""
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column(column_name, nullable=nullable)
    else:
        op.alter_column(table_name, column_name, nullable=nullable)


def _create_index_safe(index_name, table_name, columns):
    """创建索引，兼容 SQLite batch 模式。"""
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_index(op.f(index_name), columns)
    else:
        op.create_index(index_name, table_name, columns)


def _drop_index_safe(index_name, table_name):
    """删除索引；索引不存在时忽略。"""
    try:
        op.drop_index(index_name, table_name=table_name)
    except Exception:
        pass


def _is_column_nullable(connection, table_name, column_name):
    """返回指定列当前是否可空。"""
    for col in sa.inspect(connection).get_columns(table_name):
        if col["name"] == column_name:
            return col["nullable"]
    return True


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ============================================================
    # 1. ledgers 表增加 organization_id 列
    # ============================================================
    if not _column_exists(bind, "ledgers", "organization_id"):
        _add_column_with_fk(
            "ledgers", "organization_id", sa.Integer(), "organizations.id", nullable=True
        )

    # 预先生成 organization_id -> 默认 ledger_id 映射，后续填充复用
    org_to_ledger = _get_organization_to_default_ledger_map(bind)

    # ============================================================
    # 2. accounting_periods 表：ledger_id 非空 + 唯一约束
    # ============================================================
    if _constraint_exists(bind, "accounting_periods", "uq_accounting_period_org_code"):
        _drop_constraint_safe(
            "accounting_periods", "uq_accounting_period_org_code", "unique"
        )

    if _column_exists(bind, "accounting_periods", "ledger_id"):
        if _is_column_nullable(bind, "accounting_periods", "ledger_id"):
            _fill_null_ledger_ids(bind, "accounting_periods", org_to_ledger)
            _deduplicate_by_columns(bind, "accounting_periods", ["ledger_id", "period_code"])
            _alter_column_nullable("accounting_periods", "ledger_id", False)

    if not _constraint_exists(bind, "accounting_periods", "uq_accounting_period_ledger_code"):
        _create_unique_constraint(
            "accounting_periods", "uq_accounting_period_ledger_code", ["ledger_id", "period_code"]
        )

    # ============================================================
    # 3. opening_balances 表：ledger_id 非空 + 唯一约束 + 索引
    # ============================================================
    if _constraint_exists(bind, "opening_balances", "uq_opening_balance_org_period_account"):
        _drop_constraint_safe(
            "opening_balances", "uq_opening_balance_org_period_account", "unique"
        )

    if _column_exists(bind, "opening_balances", "ledger_id"):
        if _is_column_nullable(bind, "opening_balances", "ledger_id"):
            _fill_null_ledger_ids(bind, "opening_balances", org_to_ledger)
            _deduplicate_by_columns(
                bind, "opening_balances", ["ledger_id", "period_id", "account_code"]
            )
            _alter_column_nullable("opening_balances", "ledger_id", False)

    if not _constraint_exists(
        bind, "opening_balances", "uq_opening_balance_ledger_period_account"
    ):
        _create_unique_constraint(
            "opening_balances",
            "uq_opening_balance_ledger_period_account",
            ["ledger_id", "period_id", "account_code"],
        )

    if not _index_exists(bind, "opening_balances", "ix_opening_balances_ledger_id"):
        _create_index_safe("ix_opening_balances_ledger_id", "opening_balances", ["ledger_id"])

    # ============================================================
    # 4. accounting_entries 表：ledger_id 非空 + 新索引
    # ============================================================
    if _column_exists(bind, "accounting_entries", "ledger_id"):
        if _is_column_nullable(bind, "accounting_entries", "ledger_id"):
            _fill_null_ledger_ids(bind, "accounting_entries", org_to_ledger)
            _alter_column_nullable("accounting_entries", "ledger_id", False)

    # 删除原 organization_id 维度索引（如果存在），创建 ledger 维度索引
    _drop_index_safe("ix_entry_voucher_line", "accounting_entries")
    if not _index_exists(bind, "accounting_entries", "ix_entry_ledger_voucher_line"):
        _create_index_safe(
            "ix_entry_ledger_voucher_line",
            "accounting_entries",
            ["ledger_id", "voucher_no", "entry_line_no"],
        )

    # ============================================================
    # 5. chart_of_accounts 表：增加 ledger_id / organization_id 并改 ledger_id 非空
    # ============================================================
    if not _column_exists(bind, "chart_of_accounts", "organization_id"):
        _add_column_with_fk(
            "chart_of_accounts", "organization_id", sa.Integer(), "organizations.id", nullable=True
        )
    if not _column_exists(bind, "chart_of_accounts", "ledger_id"):
        _add_column_with_fk(
            "chart_of_accounts", "ledger_id", sa.Integer(), "ledgers.id", nullable=True
        )

    # 为 chart_of_accounts 填充默认 organization_id 与 ledger_id
    default_org = next(iter(org_to_ledger.keys()), None)
    if default_org is not None:
        default_ledger = org_to_ledger[default_org]
        connection = bind
        connection.execute(
            sa.text(
                """
                UPDATE chart_of_accounts
                SET organization_id = COALESCE(organization_id, :org_id),
                    ledger_id = COALESCE(ledger_id, :ledger_id)
                """
            ),
            {"org_id": default_org, "ledger_id": default_ledger},
        )
        _deduplicate_by_columns(bind, "chart_of_accounts", ["ledger_id", "code"])

    if not _constraint_exists(bind, "chart_of_accounts", "uq_chart_of_accounts_ledger_code"):
        _create_unique_constraint(
            "chart_of_accounts", "uq_chart_of_accounts_ledger_code", ["ledger_id", "code"]
        )
    if not _constraint_exists(bind, "chart_of_accounts", "uq_chart_of_accounts_org_code"):
        _create_unique_constraint(
            "chart_of_accounts", "uq_chart_of_accounts_org_code", ["organization_id", "code"]
        )

    if _column_exists(bind, "chart_of_accounts", "ledger_id"):
        if _is_column_nullable(bind, "chart_of_accounts", "ledger_id"):
            _alter_column_nullable("chart_of_accounts", "ledger_id", False)

    # ============================================================
    # 6. import_jobs 表：ledger_id 非空
    # ============================================================
    if _column_exists(bind, "import_jobs", "ledger_id"):
        if _is_column_nullable(bind, "import_jobs", "ledger_id"):
            _fill_null_ledger_ids(bind, "import_jobs", org_to_ledger)
            _alter_column_nullable("import_jobs", "ledger_id", False)

    # ============================================================
    # 7. source_files 表：ledger_id 非空
    # ============================================================
    if _column_exists(bind, "source_files", "ledger_id"):
        if _is_column_nullable(bind, "source_files", "ledger_id"):
            _fill_null_ledger_ids(bind, "source_files", org_to_ledger)
            _alter_column_nullable("source_files", "ledger_id", False)

    # ============================================================
    # 8. period_snapshots 表：ledger_id 非空
    # ============================================================
    if _column_exists(bind, "period_snapshots", "ledger_id"):
        if _is_column_nullable(bind, "period_snapshots", "ledger_id"):
            _fill_null_ledger_ids(bind, "period_snapshots", org_to_ledger)
            _alter_column_nullable("period_snapshots", "ledger_id", False)

    # ============================================================
    # 9. period_close_logs 表：增加 ledger_id 并改非空
    # ============================================================
    if not _column_exists(bind, "period_close_logs", "ledger_id"):
        _add_column_with_fk(
            "period_close_logs", "ledger_id", sa.Integer(), "ledgers.id", nullable=True
        )

    if _is_column_nullable(bind, "period_close_logs", "ledger_id"):
        _fill_null_ledger_ids(bind, "period_close_logs", org_to_ledger)
        _alter_column_nullable("period_close_logs", "ledger_id", False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 9. period_close_logs 表移除 ledger_id
    if _column_exists(bind, "period_close_logs", "ledger_id"):
        _drop_column_with_fk("period_close_logs", "ledger_id", "ledgers.id")

    # 8. period_snapshots 表 ledger_id 改回可空
    if _column_exists(bind, "period_snapshots", "ledger_id"):
        _alter_column_nullable("period_snapshots", "ledger_id", True)

    # 7. source_files 表 ledger_id 改回可空
    if _column_exists(bind, "source_files", "ledger_id"):
        _alter_column_nullable("source_files", "ledger_id", True)

    # 6. import_jobs 表 ledger_id 改回可空
    if _column_exists(bind, "import_jobs", "ledger_id"):
        _alter_column_nullable("import_jobs", "ledger_id", True)

    # 5. chart_of_accounts 表恢复为无 ledger_id / organization_id 的 0015 状态
    if _constraint_exists(bind, "chart_of_accounts", "uq_chart_of_accounts_ledger_code"):
        _drop_constraint_safe(
            "chart_of_accounts", "uq_chart_of_accounts_ledger_code", "unique"
        )
    if _constraint_exists(bind, "chart_of_accounts", "uq_chart_of_accounts_org_code"):
        _drop_constraint_safe(
            "chart_of_accounts", "uq_chart_of_accounts_org_code", "unique"
        )
    if _column_exists(bind, "chart_of_accounts", "ledger_id"):
        _drop_column_with_fk("chart_of_accounts", "ledger_id", "ledgers.id")
    if _column_exists(bind, "chart_of_accounts", "organization_id"):
        _drop_column_with_fk("chart_of_accounts", "organization_id", "organizations.id")

    # 4. accounting_entries 表恢复索引与可空
    _drop_index_safe("ix_entry_ledger_voucher_line", "accounting_entries")
    if not _index_exists(bind, "accounting_entries", "ix_entry_voucher_line"):
        _create_index_safe(
            "ix_entry_voucher_line",
            "accounting_entries",
            ["organization_id", "voucher_no", "entry_line_no"],
        )
    if _column_exists(bind, "accounting_entries", "ledger_id"):
        _alter_column_nullable("accounting_entries", "ledger_id", True)

    # 3. opening_balances 表恢复 org 维度唯一约束
    _drop_index_safe("ix_opening_balances_ledger_id", "opening_balances")
    if _constraint_exists(
        bind, "opening_balances", "uq_opening_balance_ledger_period_account"
    ):
        _drop_constraint_safe(
            "opening_balances", "uq_opening_balance_ledger_period_account", "unique"
        )
    if not _constraint_exists(
        bind, "opening_balances", "uq_opening_balance_org_period_account"
    ):
        _create_unique_constraint(
            "opening_balances",
            "uq_opening_balance_org_period_account",
            ["organization_id", "period_id", "account_code"],
        )
    if _column_exists(bind, "opening_balances", "ledger_id"):
        _alter_column_nullable("opening_balances", "ledger_id", True)

    # 2. accounting_periods 表恢复 org 维度唯一约束
    if _constraint_exists(bind, "accounting_periods", "uq_accounting_period_ledger_code"):
        _drop_constraint_safe(
            "accounting_periods", "uq_accounting_period_ledger_code", "unique"
        )
    if not _constraint_exists(bind, "accounting_periods", "uq_accounting_period_org_code"):
        _create_unique_constraint(
            "accounting_periods",
            "uq_accounting_period_org_code",
            ["organization_id", "period_code"],
        )
    if _column_exists(bind, "accounting_periods", "ledger_id"):
        _alter_column_nullable("accounting_periods", "ledger_id", True)

    # 1. ledgers 表移除 organization_id
    if _column_exists(bind, "ledgers", "organization_id"):
        _drop_column_with_fk("ledgers", "organization_id", "organizations.id")
