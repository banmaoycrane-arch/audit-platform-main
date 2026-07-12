"""add cash_flow_item to chart_of_accounts"""
from alembic import op
import sqlalchemy as sa

revision = "0027_cash_flow_item"
down_revision = "0026_balance_sheet_item"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("chart_of_accounts") as batch_op:
        batch_op.add_column(sa.Column("cash_flow_item", sa.String(60), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chart_of_accounts") as batch_op:
        batch_op.drop_column("cash_flow_item")
