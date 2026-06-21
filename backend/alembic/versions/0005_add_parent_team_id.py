"""Add parent_team_id to teams for hierarchical organization

Revision ID: 0005_add_parent_team_id
Revises: 0004_add_entry_trace_fields
Create Date: 2026-06-21 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0005_add_parent_team_id'
down_revision = '0004_add_entry_trace_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('teams', sa.Column('parent_team_id', sa.Integer(), sa.ForeignKey('teams.id'), nullable=True))


def downgrade() -> None:
    op.drop_column('teams', 'parent_team_id')
