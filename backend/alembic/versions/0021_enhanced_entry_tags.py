"""enhanced entry tags: category, history, mapping rules

Revision ID: 0021_enhanced_entry_tags
Revises: 0020_add_period_id_and_attachment_count_to_vouchers
Create Date: 2026-07-01 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0021_enhanced_entry_tags"
down_revision = "0020_add_period_id_and_attachment_count_to_vouchers"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return table_name in set(sa.inspect(connection).get_table_names())


def _column_exists(connection, table_name, column_name):
    columns = sa.inspect(connection).get_columns(table_name)
    return column_name in {col["name"] for col in columns}


def _index_exists(connection, table_name, index_name):
    indexes = sa.inspect(connection).get_indexes(table_name)
    return index_name in {idx["name"] for idx in indexes}


def _fk_exists(connection, table_name, fk_name):
    fks = sa.inspect(connection).get_foreign_keys(table_name)
    return fk_name in {fk["name"] for fk in fks}


def upgrade():
    """
    1. 创建 tag_categories 表（标签维度分类，支持多级层级）。
    2. 创建 tag_histories 表（标签变更历史）。
    3. 创建 tag_mapping_rules 表（外部标签/二级科目映射规则）。
    4. 改造 entry_tags 表：增加 category_id、ledger_id、weight、value_id、display_name。
    """
    connection = op.get_bind()

    # 1. tag_categories
    if not _table_exists(connection, "tag_categories"):
        op.create_table(
            "tag_categories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ledger_id", sa.Integer(), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("code", sa.String(60), nullable=False),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("level", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("value_type", sa.String(40), nullable=False, server_default=sa.text("'text'")),
            sa.Column("source_table", sa.String(60), nullable=True),
            sa.Column("is_mandatory", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("status", sa.String(20), nullable=False, server_default=sa.text("'active'")),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint("ledger_id", "code", name="uq_tag_category_ledger_code"),
            sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
            sa.ForeignKeyConstraint(["parent_id"], ["tag_categories.id"]),
        )
        op.create_index("ix_tag_categories_ledger_id", "tag_categories", ["ledger_id"])
        op.create_index("ix_tag_categories_parent_id", "tag_categories", ["parent_id"])
        op.create_index("ix_tag_categories_ledger_level", "tag_categories", ["ledger_id", "level"])

    # 2. tag_histories
    if not _table_exists(connection, "tag_histories"):
        op.create_table(
            "tag_histories",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("entry_tag_id", sa.Integer(), nullable=False),
            sa.Column("entry_id", sa.Integer(), nullable=False),
            sa.Column("ledger_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=True),
            sa.Column("change_type", sa.String(40), nullable=False),
            sa.Column("old_value", sa.String(255), nullable=True),
            sa.Column("new_value", sa.String(255), nullable=True),
            sa.Column("old_weight", sa.Float(), nullable=True),
            sa.Column("new_weight", sa.Float(), nullable=True),
            sa.Column("changed_by", sa.Integer(), nullable=True),
            sa.Column("change_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
            sa.ForeignKeyConstraint(["entry_tag_id"], ["entry_tags.id"]),
            sa.ForeignKeyConstraint(["entry_id"], ["accounting_entries.id"]),
            sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
            sa.ForeignKeyConstraint(["category_id"], ["tag_categories.id"]),
            sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        )
        op.create_index("ix_tag_histories_entry_tag_id", "tag_histories", ["entry_tag_id"])
        op.create_index("ix_tag_histories_entry_id", "tag_histories", ["entry_id"])
        op.create_index("ix_tag_histories_created_at", "tag_histories", ["created_at"])

    # 3. tag_mapping_rules
    if not _table_exists(connection, "tag_mapping_rules"):
        op.create_table(
            "tag_mapping_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("ledger_id", sa.Integer(), nullable=False),
            sa.Column("source_pattern", sa.String(255), nullable=False),
            sa.Column("source_type", sa.String(40), nullable=False, server_default=sa.text("'account_code'")),
            sa.Column("target_category_code", sa.String(60), nullable=False),
            sa.Column("target_value", sa.String(255), nullable=True),
            sa.Column("target_value_id", sa.Integer(), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_regex", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
            sa.UniqueConstraint(
                "ledger_id", "source_pattern", "source_type", "target_category_code",
                name="uq_tag_mapping_rule_ledger_source_target",
            ),
            sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        )
        op.create_index("ix_tag_mapping_rules_ledger_id", "tag_mapping_rules", ["ledger_id"])
        op.create_index(
            "ix_tag_mapping_rules_ledger_priority",
            "tag_mapping_rules",
            ["ledger_id", "priority"],
        )

    # 4. 改造 entry_tags
    if _table_exists(connection, "entry_tags"):
        with op.batch_alter_table("entry_tags") as batch_op:
            if not _column_exists(connection, "entry_tags", "ledger_id"):
                batch_op.add_column(sa.Column("ledger_id", sa.Integer(), nullable=True))
                if not _fk_exists(connection, "entry_tags", "fk_entry_tags_ledger_id"):
                    batch_op.create_foreign_key(
                        "fk_entry_tags_ledger_id", "ledgers.id", ["ledger_id"], ["id"]
                    )

            if not _column_exists(connection, "entry_tags", "category_id"):
                batch_op.add_column(sa.Column("category_id", sa.Integer(), nullable=True))
                if not _fk_exists(connection, "entry_tags", "fk_entry_tags_category_id"):
                    batch_op.create_foreign_key(
                        "fk_entry_tags_category_id", "tag_categories.id", ["category_id"], ["id"]
                    )

            if not _column_exists(connection, "entry_tags", "value_id"):
                batch_op.add_column(sa.Column("value_id", sa.Integer(), nullable=True))

            if not _column_exists(connection, "entry_tags", "display_name"):
                batch_op.add_column(sa.Column("display_name", sa.String(255), nullable=True))

            if not _column_exists(connection, "entry_tags", "weight"):
                batch_op.add_column(
                    sa.Column("weight", sa.Float(), nullable=False, server_default=sa.text("1.0"))
                )

        # SQLite 下索引需在 batch_alter_table 外创建
        if not _index_exists(connection, "entry_tags", "ix_entry_tags_entry_category"):
            op.create_index(
                "ix_entry_tags_entry_category", "entry_tags", ["entry_id", "category_id"]
            )
        if not _index_exists(connection, "entry_tags", "ix_entry_tags_ledger_category_value"):
            op.create_index(
                "ix_entry_tags_ledger_category_value",
                "entry_tags",
                ["ledger_id", "category_id", "tag_value"],
            )


def downgrade():
    """回滚：删除新增表和 entry_tags 新增字段。"""
    connection = op.get_bind()

    if _table_exists(connection, "tag_mapping_rules"):
        op.drop_table("tag_mapping_rules")

    if _table_exists(connection, "tag_histories"):
        op.drop_table("tag_histories")

    if _table_exists(connection, "tag_categories"):
        op.drop_table("tag_categories")

    if _table_exists(connection, "entry_tags"):
        with op.batch_alter_table("entry_tags") as batch_op:
            if _column_exists(connection, "entry_tags", "weight"):
                batch_op.drop_column("weight")
            if _column_exists(connection, "entry_tags", "display_name"):
                batch_op.drop_column("display_name")
            if _column_exists(connection, "entry_tags", "value_id"):
                batch_op.drop_column("value_id")
            if _column_exists(connection, "entry_tags", "category_id"):
                if _fk_exists(connection, "entry_tags", "fk_entry_tags_category_id"):
                    batch_op.drop_constraint("fk_entry_tags_category_id", type_="foreignkey")
                batch_op.drop_column("category_id")
            if _column_exists(connection, "entry_tags", "ledger_id"):
                if _fk_exists(connection, "entry_tags", "fk_entry_tags_ledger_id"):
                    batch_op.drop_constraint("fk_entry_tags_ledger_id", type_="foreignkey")
                batch_op.drop_column("ledger_id")

        if _index_exists(connection, "entry_tags", "ix_entry_tags_entry_category"):
            op.drop_index("ix_entry_tags_entry_category", "entry_tags")
        if _index_exists(connection, "entry_tags", "ix_entry_tags_ledger_category_value"):
            op.drop_index("ix_entry_tags_ledger_category_value", "entry_tags")
