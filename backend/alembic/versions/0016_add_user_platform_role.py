"""add_user_platform_role

Revision ID: 0016_add_user_platform_role
Revises: 0015_add_draft_data_to_import_jobs
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0016_add_user_platform_role"
down_revision = "0015_add_draft_data_to_import_jobs"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "platform_role" not in user_columns:
        op.add_column(
            "users",
            sa.Column("platform_role", sa.String(length=40), nullable=False, server_default="user"),
        )
        op.alter_column("users", "platform_role", server_default=None)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "platform_role" in user_columns:
        op.drop_column("users", "platform_role")
