"""add parse quality metrics and summaries

Revision ID: 0022_add_parse_quality_metrics
Revises: 0021_enhanced_entry_tags
Create Date: 2026-07-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0022_add_parse_quality_metrics"
down_revision = "0021_enhanced_entry_tags"
branch_labels = None
depends_on = None


def _table_exists(connection, table_name):
    return table_name in set(sa.inspect(connection).get_table_names())


def _index_exists(connection, table_name, index_name):
    indexes = sa.inspect(connection).get_indexes(table_name)
    return index_name in {idx["name"] for idx in indexes}


def upgrade():
    """
    1. 创建 parse_quality_metric 表，记录每次解析的质量指标。
    2. 创建 parse_quality_summary 表，按天/文档类型聚合指标。
    """
    connection = op.get_bind()

    # 1. parse_quality_metric
    if not _table_exists(connection, "parse_quality_metric"):
        op.create_table(
            "parse_quality_metric",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_file_id", sa.Integer(), nullable=True),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("document_type", sa.String(50), nullable=False),
            sa.Column("rule_engine_used", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("llm_engine_used", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("field_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("matched_field_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("missed_field_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("consistency_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("stability_score", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("review_required", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("conflict_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("correction_applied_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("diagnosis_snapshot", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["source_file_id"], ["source_files.id"]),
        )
        op.create_index("ix_parse_quality_metric_source_file_id", "parse_quality_metric", ["source_file_id"])
        op.create_index("ix_parse_quality_metric_document_type", "parse_quality_metric", ["document_type"])
        op.create_index("ix_parse_quality_metric_created_at", "parse_quality_metric", ["created_at"])

    # 2. parse_quality_summary
    if not _table_exists(connection, "parse_quality_summary"):
        op.create_table(
            "parse_quality_summary",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("summary_date", sa.String(10), nullable=False),
            sa.Column("document_type", sa.String(50), nullable=False),
            sa.Column("parse_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("review_required_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("avg_consistency_rate", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("avg_stability_score", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("overall_field_accuracy", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("overall_document_completeness", sa.Float(), nullable=False, server_default=sa.text("0")),
            sa.Column("correction_applied_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.UniqueConstraint("summary_date", "document_type", name="uq_parse_quality_summary_date_type"),
        )
        op.create_index("ix_parse_quality_summary_date", "parse_quality_summary", ["summary_date"])
        op.create_index("ix_parse_quality_summary_document_type", "parse_quality_summary", ["document_type"])
        op.create_index(
            "ix_parse_quality_summary_date_type",
            "parse_quality_summary",
            ["summary_date", "document_type"],
        )


def downgrade():
    """回滚：删除 parse_quality_metric 和 parse_quality_summary 表。"""
    connection = op.get_bind()

    if _table_exists(connection, "parse_quality_summary"):
        op.drop_table("parse_quality_summary")

    if _table_exists(connection, "parse_quality_metric"):
        op.drop_table("parse_quality_metric")
