"""Add entity_id to accounting_units for direct entity traceability

Revision ID: 0006_add_entity_id_to_accounting_units
Revises: 0005_add_parent_team_id
Create Date: 2026-06-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0006_add_entity_id_to_accounting_units'
down_revision = '0005_add_parent_team_id'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('accounting_units', sa.Column('entity_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=True))


def downgrade() -> None:
    op.drop_column('accounting_units', 'entity_id')
