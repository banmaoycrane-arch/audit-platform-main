"""add entity legal_type for concept alignment

Revision ID: 0018_add_entity_legal_type
Revises: 0017_ledger_primary_boundary_refactor
Create Date: 2026-07-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0018_add_entity_legal_type"
down_revision = "0017_ledger_primary_boundary_refactor"
branch_labels = None
depends_on = None


def _column_exists(connection, table_name, column_name):
    """检查指定表中是否已存在目标列。"""
    columns = {col["name"] for col in sa.inspect(connection).get_columns(table_name)}
    return column_name in columns


def upgrade():
    """
    在 entities 表中增加可选字段 legal_type。

    业务目标：
    - 保留现有 is_accounting_entity / is_tax_entity / is_legal_entity / is_management_entity 标志不变。
    - 增加 legal_type 语义标签，便于在新方案中更清晰地区分：
        primary_legal（完整法人）
        sub_legal（分公司/次级法律载体）
        reporting_entity（报表主体/会计主体）
        accounting_unit（内部核算单位）
        management_entity（管理主体）
    - 该字段默认为 NULL，与现有数据完全兼容，不影响已有业务逻辑。
    """
    connection = op.get_bind()
    if not _column_exists(connection, "entities", "legal_type"):
        op.add_column(
            "entities",
            sa.Column("legal_type", sa.String(20), nullable=True, default=None),
        )


def downgrade():
    """回滚：删除 entities.legal_type 列。"""
    connection = op.get_bind()
    if _column_exists(connection, "entities", "legal_type"):
        op.drop_column("entities", "legal_type")
