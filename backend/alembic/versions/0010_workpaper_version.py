"""Add workpaper index and version tables

Revision ID: 0010_workpaper_version
Revises: 0009_counterparty_confirmation
Create Date: 2026-06-23 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0010_workpaper_version"
down_revision = "0009_counterparty_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workpaper_indexes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("index_no", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("audit_area", sa.String(length=100), nullable=True),
        sa.Column("archive_path", sa.String(length=1000), nullable=True),
        sa.Column("source_module_key", sa.String(length=50), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["workpaper_indexes.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workpaper_indexes_ledger_id", "workpaper_indexes", ["ledger_id"])
    op.create_index("ix_workpaper_indexes_project_id", "workpaper_indexes", ["project_id"])
    op.create_index("ix_workpaper_indexes_parent_id", "workpaper_indexes", ["parent_id"])
    op.create_index("ix_workpaper_indexes_index_no", "workpaper_indexes", ["index_no"])

    op.create_table(
        "workpaper_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workpaper_index_id", sa.Integer(), nullable=False),
        sa.Column("source_file_id", sa.Integer(), nullable=False),
        sa.Column("version_no", sa.String(length=20), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("prepared_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("supersedes_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["prepared_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"]),
        sa.ForeignKeyConstraint(["supersedes_id"], ["workpaper_versions.id"]),
        sa.ForeignKeyConstraint(["workpaper_index_id"], ["workpaper_indexes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workpaper_versions_workpaper_index_id", "workpaper_versions", ["workpaper_index_id"])
    op.create_index("ix_workpaper_versions_source_file_id", "workpaper_versions", ["source_file_id"])


def downgrade() -> None:
    op.drop_index("ix_workpaper_versions_source_file_id", table_name="workpaper_versions")
    op.drop_index("ix_workpaper_versions_workpaper_index_id", table_name="workpaper_versions")
    op.drop_table("workpaper_versions")
    op.drop_index("ix_workpaper_indexes_index_no", table_name="workpaper_indexes")
    op.drop_index("ix_workpaper_indexes_parent_id", table_name="workpaper_indexes")
    op.drop_index("ix_workpaper_indexes_project_id", table_name="workpaper_indexes")
    op.drop_index("ix_workpaper_indexes_ledger_id", table_name="workpaper_indexes")
    op.drop_table("workpaper_indexes")
