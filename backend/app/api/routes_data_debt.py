"""数据负债扫描 API 路由。

业务场景：系统管理员/审计人员触发全库数据负债扫描，查看孤儿记录、约束完整性、
数据一致性、脏数据 4 类问题报告，并可对白名单低风险项执行自动修复。

政策依据：会计信息系统内部控制规范——数据完整性必须可审计、可追溯。
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.db.session import get_db
from app.models.user import User
from app.services.shared.data_debt_scan_service import (
    apply_auto_fixes,
    scan_data_debt,
)

router = APIRouter(prefix="/api/data-debt", tags=["data-debt"])


class FixActionResponse(BaseModel):
    rule_id: str
    action: str
    count: int
    sql_preview: str = ""


class ScanReportResponse(BaseModel):
    generated_at: str
    scopes: dict[str, Any]
    summary: dict[str, Any]
    findings: list[dict[str, Any]]


@router.get("/scan", response_model=ScanReportResponse)
def scan_data_debt_api(
    organization_id: int | None = Query(None, description="可选，仅扫描指定组织"),
    ledger_id: int | None = Query(None, description="可选，仅扫描指定账簿"),
    categories: str | None = Query(
        None,
        description="可选，逗号分隔的类别：orphan,constraint_integrity,consistency,dirty",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ScanReportResponse:
    """执行数据负债扫描，返回结构化报告（只读，不修改数据）。"""
    cat_list = (
        [c.strip() for c in categories.split(",") if c.strip()]
        if categories
        else None
    )
    report = scan_data_debt(
        db,
        organization_id=organization_id,
        ledger_id=ledger_id,
        categories=cat_list,
    )
    return ScanReportResponse(**report.to_dict())


@router.post("/fix", response_model=list[FixActionResponse])
def apply_auto_fixes_api(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> list[FixActionResponse]:
    """对白名单低风险脏数据（空格 trim）执行自动修复。

    安全策略：
    - 仅修复 FIXABLE_RULES 白名单中的规则（当前仅 TRIM 空格）
    - 不处理 critical/high 级别问题（需人工核查）
    - 修复后提交事务
    """
    report = scan_data_debt(db, categories=["dirty"])
    try:
        actions = apply_auto_fixes(db, report, approved=True)
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"修复执行失败: {exc}",
        ) from exc
    return [FixActionResponse(**a.__dict__) for a in actions]
