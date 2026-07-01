"""add period_id and attachment_count to vouchers

Revision ID: 0020_add_period_id_and_attachment_count_to_vouchers
Revises: 0019_add_voucher_table
Create Date: 2026-07-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0020_add_period_id_and_attachment_count_to_vouchers"
down_revision = "0019_add_voucher_table"
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
    """在 vouchers 表增加 period_id 和 attachment_count 字段。"""
    connection = op.get_bind()

    if not _table_exists(connection, "vouchers"):
        raise RuntimeError("vouchers 表不存在，无法添加字段。请先应用 0019_add_voucher_table 迁移。")

    with op.batch_alter_table("vouchers") as batch_op:
        # 1. 添加会计期间外键（业务必填，但允许 NULL 兼容历史数据）
        if not _column_exists(connection, "vouchers", "period_id"):
            batch_op.add_column(
                sa.Column("period_id", sa.Integer(), nullable=True),
            )
            # 创建索引（SQLite 下 batch_alter_table 支持 create_index）
            if not _index_exists(connection, "vouchers", "ix_vouchers_period_id"):
                batch_op.create_index(
                    "ix_vouchers_period_id", ["period_id"]
                )
            # 创建外键约束
            if not _fk_exists(connection, "vouchers", "fk_vouchers_period_id"):
                batch_op.create_foreign_key(
                    "fk_vouchers_period_id",
                    "accounting_periods",
                    ["period_id"],
                    ["id"],
                )

        # 2. 添加附件数量字段
        if not _column_exists(connection, "vouchers", "attachment_count"):
            batch_op.add_column(
                sa.Column("attachment_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            )


def downgrade():
    """回滚：删除 vouchers 表的 period_id 和 attachment_count 字段。"""
    connection = op.get_bind()

    with op.batch_alter_table("vouchers") as batch_op:
        if _column_exists(connection, "vouchers", "attachment_count"):
            batch_op.drop_column("attachment_count")

        if _column_exists(connection, "vouchers", "period_id"):
            if _fk_exists(connection, "vouchers", "fk_vouchers_period_id"):
                batch_op.drop_constraint("fk_vouchers_period_id", type_="foreignkey")
            if _index_exists(connection, "vouchers", "ix_vouchers_period_id"):
                batch_op.drop_index("ix_vouchers_period_id")
            batch_op.drop_column("period_id")
