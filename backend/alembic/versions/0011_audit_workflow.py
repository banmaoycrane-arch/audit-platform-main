"""Add audit workflow orchestration tables

Revision ID: 0011_audit_workflow
Revises: 0010_workpaper_version
Create Date: 2026-06-23 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0011_audit_workflow"
down_revision = "0010_workpaper_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_workflow_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("granularity", sa.String(length=20), nullable=False, server_default="standard"),
        sa.Column("enabled_procedures", sa.JSON(), nullable=True),
        sa.Column("auto_link_workpaper", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id"),
    )
    op.create_index("ix_project_workflow_configs_project_id", "project_workflow_configs", ["project_id"])

    op.create_table(
        "audit_procedure_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("ledger_id", sa.Integer(), nullable=False),
        sa.Column("procedure_key", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="planned"),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("related_entity_type", sa.String(length=50), nullable=True),
        sa.Column("related_entity_id", sa.Integer(), nullable=True),
        sa.Column("workpaper_index_id", sa.Integer(), nullable=True),
        sa.Column("source_file_id", sa.Integer(), nullable=True),
        sa.Column("recommended_by", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("concluded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"]),
        sa.ForeignKeyConstraint(["workpaper_index_id"], ["workpaper_indexes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_procedure_runs_ledger_id", "audit_procedure_runs", ["ledger_id"])
    op.create_index("ix_audit_procedure_runs_project_id", "audit_procedure_runs", ["project_id"])
    op.create_index("ix_audit_procedure_runs_procedure_key", "audit_procedure_runs", ["procedure_key"])
    op.create_index("ix_audit_procedure_runs_status", "audit_procedure_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_audit_procedure_runs_status", table_name="audit_procedure_runs")
    op.drop_index("ix_audit_procedure_runs_procedure_key", table_name="audit_procedure_runs")
    op.drop_index("ix_audit_procedure_runs_project_id", table_name="audit_procedure_runs")
    op.drop_index("ix_audit_procedure_runs_ledger_id", table_name="audit_procedure_runs")
    op.drop_table("audit_procedure_runs")
    op.drop_index("ix_project_workflow_configs_project_id", table_name="project_workflow_configs")
    op.drop_table("project_workflow_configs")
