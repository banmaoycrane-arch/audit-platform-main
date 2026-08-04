"""document_tags.ledger_id for vector isolation

Revision ID: 0035
Revises: 0034_add_economic_event_workorder
Create Date: 2026-08-02

TD-032: DocumentTag 按账簿隔离向量检索，从 source_files / import_jobs 回填 ledger_id。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0035_document_tag_ledger_id"
down_revision: Union[str, None] = "0034_add_economic_event_workorder"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(connection, table_name: str, column_name: str) -> bool:
    inspector = sa.inspect(connection)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    connection = op.get_bind()
    if not _column_exists(connection, "document_tags", "ledger_id"):
        op.add_column(
            "document_tags",
            sa.Column("ledger_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            op.f("ix_document_tags_ledger_id"),
            "document_tags",
            ["ledger_id"],
            unique=False,
        )
        op.create_foreign_key(
            "fk_document_tags_ledger_id",
            "document_tags",
            "ledgers",
            ["ledger_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # 优先从 source_files.ledger_id 回填
    op.execute(
        """
        UPDATE document_tags
        SET ledger_id = (
            SELECT sf.ledger_id FROM source_files sf
            WHERE sf.id = document_tags.document_id
        )
        WHERE ledger_id IS NULL
          AND EXISTS (
            SELECT 1 FROM source_files sf
            WHERE sf.id = document_tags.document_id AND sf.ledger_id IS NOT NULL
          )
        """
    )
    # 兜底：source_files.ledger_id 为空时，从 import_jobs 取
    op.execute(
        """
        UPDATE document_tags
        SET ledger_id = (
            SELECT ij.ledger_id
            FROM source_files sf
            JOIN import_jobs ij ON ij.id = sf.import_job_id
            WHERE sf.id = document_tags.document_id
        )
        WHERE ledger_id IS NULL
          AND EXISTS (
            SELECT 1
            FROM source_files sf
            JOIN import_jobs ij ON ij.id = sf.import_job_id
            WHERE sf.id = document_tags.document_id AND ij.ledger_id IS NOT NULL
          )
        """
    )
    # 已同步向量需重同步以写入真实 ledger_id payload
    op.execute(
        """
        UPDATE document_tags
        SET vector_stored = 0
        WHERE ledger_id IS NOT NULL AND vector_stored = 1
        """
    )


def downgrade() -> None:
    connection = op.get_bind()
    if _column_exists(connection, "document_tags", "ledger_id"):
        op.drop_constraint("fk_document_tags_ledger_id", "document_tags", type_="foreignkey")
        op.drop_index(op.f("ix_document_tags_ledger_id"), table_name="document_tags")
        op.drop_column("document_tags", "ledger_id")
