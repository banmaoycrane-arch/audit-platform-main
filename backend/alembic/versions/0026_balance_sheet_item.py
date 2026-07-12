"""add balance_sheet_item to chart_of_accounts"""
from alembic import op
import sqlalchemy as sa

revision = "0026_balance_sheet_item"
down_revision = "0025_staging_voucher_group_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chart_of_accounts") as batch_op:
        batch_op.add_column(sa.Column("balance_sheet_item", sa.String(60), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chart_of_accounts") as batch_op:
        batch_op.drop_column("balance_sheet_item")
