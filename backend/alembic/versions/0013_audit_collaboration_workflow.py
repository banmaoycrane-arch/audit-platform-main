"""Add audit collaboration workflow tables (task, branch, review, comment, milestone)

Revision ID: 0013_audit_collaboration_workflow
Revises: 0012_entry_post_status
Create Date: 2026-06-26 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0013_audit_collaboration_workflow"
down_revision = "0012_entry_post_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_milestones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=True),
        sa.Column("milestone_no", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("milestone_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="planned"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("snapshot_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_milestones_ledger_id", "audit_milestones", ["ledger_id"])
    op.create_index("ix_audit_milestones_milestone_no", "audit_milestones", ["milestone_no"])
    op.create_index("ix_audit_milestones_project_id", "audit_milestones", ["project_id"])
    op.create_index("ix_audit_milestones_status", "audit_milestones", ["status"])

    op.create_table(
        "audit_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=True),
        sa.Column("task_no", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("audit_area", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_ids", sa.JSON(), nullable=True),
        sa.Column("related_finding_id", sa.Integer(), nullable=True),
        sa.Column("related_procedure_key", sa.String(length=50), nullable=True),
        sa.Column("parent_task_id", sa.Integer(), nullable=True),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.ForeignKeyConstraint(["parent_task_id"], ["audit_tasks.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["related_finding_id"], ["audit_findings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_tasks_ledger_id", "audit_tasks", ["ledger_id"])
    op.create_index("ix_audit_tasks_project_id", "audit_tasks", ["project_id"])
    op.create_index("ix_audit_tasks_status", "audit_tasks", ["status"])
    op.create_index("ix_audit_tasks_task_no", "audit_tasks", ["task_no"])

    op.create_table(
        "audit_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mention_user_ids", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_comments_target_type_target_id", "audit_comments", ["target_type", "target_id"])

    op.create_table(
        "audit_work_branches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("branch_name", sa.String(length=200), nullable=False),
        sa.Column("base_branch", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("assignee_id", sa.Integer(), nullable=True),
        sa.Column("workpaper_index_id", sa.Integer(), nullable=True),
        sa.Column("procedure_run_id", sa.Integer(), nullable=True),
        sa.Column("latest_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("merged_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["latest_version_id"], ["workpaper_versions.id"]),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.ForeignKeyConstraint(["procedure_run_id"], ["audit_procedure_runs.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["audit_tasks.id"]),
        sa.ForeignKeyConstraint(["workpaper_index_id"], ["workpaper_indexes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_work_branches_ledger_id", "audit_work_branches", ["ledger_id"])
    op.create_index("ix_audit_work_branches_project_id", "audit_work_branches", ["project_id"])
    op.create_index("ix_audit_work_branches_status", "audit_work_branches", ["status"])
    op.create_index("ix_audit_work_branches_task_id", "audit_work_branches", ["task_id"])

    op.create_table(
        "audit_review_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("ledger_id", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("pr_no", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_branch", sa.String(length=200), nullable=False, server_default="main"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("current_review_level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("reviewer_level_1_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_level_2_id", sa.Integer(), nullable=True),
        sa.Column("reviewer_level_3_id", sa.Integer(), nullable=True),
        sa.Column("merged_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("merged_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["branch_id"], ["audit_work_branches.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["ledger_id"], ["ledgers.id"]),
        sa.ForeignKeyConstraint(["merged_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["reviewer_level_1_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewer_level_2_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["reviewer_level_3_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["audit_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_review_requests_branch_id", "audit_review_requests", ["branch_id"])
    op.create_index("ix_audit_review_requests_ledger_id", "audit_review_requests", ["ledger_id"])
    op.create_index("ix_audit_review_requests_pr_no", "audit_review_requests", ["pr_no"])
    op.create_index("ix_audit_review_requests_project_id", "audit_review_requests", ["project_id"])
    op.create_index("ix_audit_review_requests_status", "audit_review_requests", ["status"])
    op.create_index("ix_audit_review_requests_task_id", "audit_review_requests", ["task_id"])

    op.create_table(
        "audit_review_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("review_request_id", sa.Integer(), nullable=False),
        sa.Column("review_level", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("signature_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["review_request_id"], ["audit_review_requests.id"]),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_review_actions_review_request_id", "audit_review_actions", ["review_request_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_review_actions_review_request_id", table_name="audit_review_actions")
    op.drop_table("audit_review_actions")

    op.drop_index("ix_audit_review_requests_task_id", table_name="audit_review_requests")
    op.drop_index("ix_audit_review_requests_status", table_name="audit_review_requests")
    op.drop_index("ix_audit_review_requests_project_id", table_name="audit_review_requests")
    op.drop_index("ix_audit_review_requests_pr_no", table_name="audit_review_requests")
    op.drop_index("ix_audit_review_requests_ledger_id", table_name="audit_review_requests")
    op.drop_index("ix_audit_review_requests_branch_id", table_name="audit_review_requests")
    op.drop_table("audit_review_requests")

    op.drop_index("ix_audit_work_branches_task_id", table_name="audit_work_branches")
    op.drop_index("ix_audit_work_branches_status", table_name="audit_work_branches")
    op.drop_index("ix_audit_work_branches_project_id", table_name="audit_work_branches")
    op.drop_index("ix_audit_work_branches_ledger_id", table_name="audit_work_branches")
    op.drop_table("audit_work_branches")

    op.drop_index("ix_audit_comments_target_type_target_id", table_name="audit_comments")
    op.drop_table("audit_comments")

    op.drop_index("ix_audit_tasks_task_no", table_name="audit_tasks")
    op.drop_index("ix_audit_tasks_status", table_name="audit_tasks")
    op.drop_index("ix_audit_tasks_project_id", table_name="audit_tasks")
    op.drop_index("ix_audit_tasks_ledger_id", table_name="audit_tasks")
    op.drop_table("audit_tasks")

    op.drop_index("ix_audit_milestones_status", table_name="audit_milestones")
    op.drop_index("ix_audit_milestones_project_id", table_name="audit_milestones")
    op.drop_index("ix_audit_milestones_milestone_no", table_name="audit_milestones")
    op.drop_index("ix_audit_milestones_ledger_id", table_name="audit_milestones")
    op.drop_table("audit_milestones")
