"""运维负债扫描 + 健康检查 API 路由。

业务场景：系统管理员查看运维负债报告，检查服务健康状态。
政策依据：会计信息系统内部控制规范——系统可用性、可观测性必须保障。
"""
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.shared.ops_debt_scan_service import scan_ops_debt

router = APIRouter(prefix="/api/ops", tags=["ops"])


class OpsReportResponse(BaseModel):
    generated_at: str
    summary: dict[str, Any]
    findings: list[dict[str, Any]]


class HealthResponse(BaseModel):
    status: str
    database: str
    app_version: str


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: Session = Depends(get_db),
) -> HealthResponse:
    """健康检查端点：数据库连通性 + 应用版本。

    用于容器编排（k8s）的 livenessProbe / readinessProbe。
    """
    db_status = "unknown"
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "down"

    return HealthResponse(
        status="healthy" if db_status == "ok" else "degraded",
        database=db_status,
        app_version="0.1.0",
    )


@router.get("/debt-scan", response_model=OpsReportResponse)
def scan_ops_debt_api(
    categories: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OpsReportResponse:
    """执行运维负债扫描，返回结构化报告（只读）。"""
    cat_list = (
        [c.strip() for c in categories.split(",") if c.strip()]
        if categories
        else None
    )
    report = scan_ops_debt(categories=cat_list)
    return OpsReportResponse(
        generated_at=report.generated_at.isoformat(),
        summary=report.summary(),
        findings=[f.to_dict() for f in report.findings],
    )
