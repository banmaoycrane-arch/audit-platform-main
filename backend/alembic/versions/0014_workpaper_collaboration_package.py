"""Add workpaper collaboration package fields

Revision ID: 0014_workpaper_collaboration_package
Revises: 0014_audit_task_ledger_required
Create Date: 2026-06-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0014_workpaper_collaboration_package"
down_revision = "0014_audit_task_ledger_required"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workpaper_versions", sa.Column("file_name", sa.String(length=300), nullable=True))
    op.add_column("workpaper_versions", sa.Column("file_ext", sa.String(length=20), nullable=True))
    op.add_column("workpaper_versions", sa.Column("mime_type", sa.String(length=120), nullable=True))
    op.add_column("workpaper_versions", sa.Column("storage_path", sa.String(length=500), nullable=True))
    op.add_column("workpaper_versions", sa.Column("file_hash", sa.String(length=128), nullable=True))
    op.add_column("workpaper_versions", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("workpaper_versions", sa.Column("template_code", sa.String(length=80), nullable=True))
    op.add_column("workpaper_versions", sa.Column("sheet_count", sa.Integer(), nullable=True))
    op.add_column("workpaper_versions", sa.Column("workbook_metadata", sa.JSON(), nullable=True))
    op.add_column("workpaper_versions", sa.Column("generated_from", sa.String(length=80), nullable=True))

    op.add_column("audit_review_requests", sa.Column("submitted_version_id", sa.Integer(), nullable=True))
    op.add_column("audit_review_requests", sa.Column("approved_version_id", sa.Integer(), nullable=True))
    op.add_column("audit_review_requests", sa.Column("merged_version_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_audit_review_requests_submitted_version_id",
        "audit_review_requests",
        "workpaper_versions",
        ["submitted_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_audit_review_requests_approved_version_id",
        "audit_review_requests",
        "workpaper_versions",
        ["approved_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_audit_review_requests_merged_version_id",
        "audit_review_requests",
        "workpaper_versions",
        ["merged_version_id"],
        ["id"],
    )
    op.create_index("ix_audit_review_requests_submitted_version_id", "audit_review_requests", ["submitted_version_id"])
    op.create_index("ix_audit_review_requests_approved_version_id", "audit_review_requests", ["approved_version_id"])
    op.create_index("ix_audit_review_requests_merged_version_id", "audit_review_requests", ["merged_version_id"])

    op.add_column("audit_comments", sa.Column("marker_type", sa.String(length=50), nullable=True))
    op.add_column("audit_comments", sa.Column("sheet_name", sa.String(length=120), nullable=True))
    op.add_column("audit_comments", sa.Column("cell_ref", sa.String(length=40), nullable=True))
    op.add_column("audit_comments", sa.Column("range_ref", sa.String(length=80), nullable=True))
    op.add_column("audit_comments", sa.Column("severity", sa.String(length=30), nullable=True))
    op.add_column("audit_comments", sa.Column("resolved_at", sa.DateTime(), nullable=True))
    op.add_column("audit_comments", sa.Column("resolved_by", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_audit_comments_resolved_by",
        "audit_comments",
        "users",
        ["resolved_by"],
        ["id"],
    )

    op.create_table(
        "audit_notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("recipient_user_id", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("ledger_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_notifications_event_type", "audit_notifications", ["event_type"])
    op.create_index("ix_audit_notifications_is_read", "audit_notifications", ["is_read"])
    op.create_index("ix_audit_notifications_ledger_id", "audit_notifications", ["ledger_id"])
    op.create_index("ix_audit_notifications_project_id", "audit_notifications", ["project_id"])
    op.create_index("ix_audit_notifications_recipient_user_id", "audit_notifications", ["recipient_user_id"])
    op.create_index("ix_audit_notifications_target_id", "audit_notifications", ["target_id"])
    op.create_index("ix_audit_notifications_target_type", "audit_notifications", ["target_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_notifications_target_type", table_name="audit_notifications")
    op.drop_index("ix_audit_notifications_target_id", table_name="audit_notifications")
    op.drop_index("ix_audit_notifications_recipient_user_id", table_name="audit_notifications")
    op.drop_index("ix_audit_notifications_project_id", table_name="audit_notifications")
    op.drop_index("ix_audit_notifications_ledger_id", table_name="audit_notifications")
    op.drop_index("ix_audit_notifications_is_read", table_name="audit_notifications")
    op.drop_index("ix_audit_notifications_event_type", table_name="audit_notifications")
    op.drop_table("audit_notifications")

    op.drop_constraint("fk_audit_comments_resolved_by", "audit_comments", type_="foreignkey")
    op.drop_column("audit_comments", "resolved_by")
    op.drop_column("audit_comments", "resolved_at")
    op.drop_column("audit_comments", "severity")
    op.drop_column("audit_comments", "range_ref")
    op.drop_column("audit_comments", "cell_ref")
    op.drop_column("audit_comments", "sheet_name")
    op.drop_column("audit_comments", "marker_type")

    op.drop_index("ix_audit_review_requests_merged_version_id", table_name="audit_review_requests")
    op.drop_index("ix_audit_review_requests_approved_version_id", table_name="audit_review_requests")
    op.drop_index("ix_audit_review_requests_submitted_version_id", table_name="audit_review_requests")
    op.drop_constraint("fk_audit_review_requests_merged_version_id", "audit_review_requests", type_="foreignkey")
    op.drop_constraint("fk_audit_review_requests_approved_version_id", "audit_review_requests", type_="foreignkey")
    op.drop_constraint("fk_audit_review_requests_submitted_version_id", "audit_review_requests", type_="foreignkey")
    op.drop_column("audit_review_requests", "merged_version_id")
    op.drop_column("audit_review_requests", "approved_version_id")
    op.drop_column("audit_review_requests", "submitted_version_id")

    op.drop_column("workpaper_versions", "generated_from")
    op.drop_column("workpaper_versions", "workbook_metadata")
    op.drop_column("workpaper_versions", "sheet_count")
    op.drop_column("workpaper_versions", "template_code")
    op.drop_column("workpaper_versions", "file_size")
    op.drop_column("workpaper_versions", "file_hash")
    op.drop_column("workpaper_versions", "storage_path")
    op.drop_column("workpaper_versions", "mime_type")
    op.drop_column("workpaper_versions", "file_ext")
    op.drop_column("workpaper_versions", "file_name")
