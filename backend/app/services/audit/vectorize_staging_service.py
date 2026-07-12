"""Staging 向量化：科目映射 + 行嵌入 + 组嵌入（Phase1 最小实现）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import StagingAccountingEntry


def vectorize_staging_job(db: Session, job_id: int) -> dict[str, int]:
    """为 staging 分录写入 vector_id 占位，后续可接入真实向量库。"""
    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    updated = 0
    for row in rows:
        if row.vector_id:
            continue
        row.vector_id = f"staging-entry-{job_id}-{row.id}"
        updated += 1
    if updated:
        db.commit()
    return {"vectorized_rows": updated, "total_rows": len(rows)}
