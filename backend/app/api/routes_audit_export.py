"""审计报告导出路由

提供 GET /api/audit-tests/{job_id}/export?format=xlsx|json
- xlsx：openpyxl 生成两个 Sheet（概览 + 审计发现）
- json：直接序列化最近一次审计报告或基于持久化发现拼装的最小报告
"""
from __future__ import annotations

import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.models import ImportJob
from app.db.session import get_db
from app.services.audit.audit_report_service import (
    SUPPORTED_FORMATS,
    build_report_payload,
    report_to_json,
    report_to_xlsx,
)

router = APIRouter(prefix="/api/audit-tests", tags=["audit-export"])


@router.get("/{job_id}/export")
def export_audit_report(job_id: int, format: str = "xlsx", db: Session = Depends(get_db)) -> StreamingResponse:
    fmt = format.lower()
    if fmt not in SUPPORTED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的导出格式：{format}，仅支持 xlsx/json",
        )

    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    report = build_report_payload(db, job_id)

    if fmt == "xlsx":
        body = report_to_xlsx(report)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"audit_report_{job_id}.xlsx"
    else:
        body = report_to_json(report)
        media = "application/json; charset=utf-8"
        filename = f"audit_report_{job_id}.json"

    return StreamingResponse(
        io.BytesIO(body),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
