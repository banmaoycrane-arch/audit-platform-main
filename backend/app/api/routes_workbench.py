from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.audit.workbench_service import build_workbench_queue
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/workbench", tags=["workbench"])


@router.get("/items")
def list_workbench_items(
    status: str | None = Query(None, description="待办状态；默认 pending/open"),
    source: str | None = Query(None, description="来源筛选：internal_control | dimension | risk | all"),
    job_id: int | None = Query(None, description="限定导入任务"),
    limit: int = Query(300, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    ledger_id: int | None = Depends(get_current_ledger),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """内控待办工作台：合并内控缺陷、维度待办、风险提醒。"""
    del current_user
    if ledger_id is None:
        raise HTTPException(status_code=400, detail="请先选择账簿（X-Ledger-Id）")
    return build_workbench_queue(
        db,
        ledger_id=ledger_id,
        status=status,
        source=source,
        job_id=job_id,
        limit=limit,
    )
