from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    AuditFinding,
    AuditRisk,
)
from app.db.session import get_db
from app.core.dependencies import get_current_user, get_current_ledger
from app.models.user import User
from app.services import ledger_management_service

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_dashboard_summary(
    organization_id: int | None = None,
    ledger_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_ledger_id: int | None = Depends(get_current_ledger),
) -> dict:
    """首页 KPI 仪表盘聚合接口（团队级）。

    返回：
    - user: 当前用户信息（含 team）
    - voucher_count：凭证张数
    - unclosed_periods：未结账期间数量（status == "open"）
    - unaudited_periods：未审计期间数量（占位，取未结账期间数）
    - pending_risks：待复核风险数量
    - notifications：通知数量（占位 0）
    - module_status：各模块状态概览
    """
    # 优先使用显式传入的 ledger_id，其次使用依赖注入的 current_ledger_id。
    # 当用户没有账簿时返回空仪表盘；当用户显式请求无权账簿时仍按权限规则拒绝。
    effective_ledger_id = ledger_id or current_ledger_id
    if ledger_id and not ledger_management_service.user_has_ledger_access(
        db,
        current_user.id,
        ledger_id,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"用户无权访问账簿 {ledger_id}",
        )

    # 凭证数
    voucher_q = db.query(func.count(func.distinct(AccountingEntry.voucher_no))).filter(
        AccountingEntry.voucher_no.isnot(None)
    )
    if organization_id:
        voucher_q = voucher_q.filter(AccountingEntry.organization_id == organization_id)
    if effective_ledger_id:
        voucher_q = voucher_q.filter(AccountingEntry.ledger_id == effective_ledger_id)
    voucher_count = voucher_q.scalar() or 0

    pending_voucher_q = db.query(func.count(AccountingEntry.id)).filter(
        AccountingEntry.review_status.in_(["draft", "pending"])
    )
    if organization_id:
        pending_voucher_q = pending_voucher_q.filter(AccountingEntry.organization_id == organization_id)
    if effective_ledger_id:
        pending_voucher_q = pending_voucher_q.filter(AccountingEntry.ledger_id == effective_ledger_id)
    pending_vouchers = pending_voucher_q.scalar() or 0

    # 未结账期间
    period_q = db.query(func.count(AccountingPeriod.id)).filter(
        AccountingPeriod.status == "open"
    )
    if organization_id:
        period_q = period_q.filter(AccountingPeriod.organization_id == organization_id)
    if effective_ledger_id:
        period_q = period_q.filter(AccountingPeriod.ledger_id == effective_ledger_id)
    unclosed_periods = period_q.scalar() or 0

    # 待复核风险
    risk_q = db.query(func.count(AuditRisk.id)).filter(
        AuditRisk.status == "pending_review"
    )
    if organization_id:
        risk_q = risk_q.filter(AuditRisk.organization_id == organization_id)
    if effective_ledger_id:
        risk_q = risk_q.filter(AuditRisk.ledger_id == effective_ledger_id)
    pending_risks = risk_q.scalar() or 0

    # 审计发现总数
    finding_q = db.query(func.count(AuditFinding.id))
    if effective_ledger_id:
        finding_q = finding_q.filter(AuditFinding.ledger_id == effective_ledger_id)
    recent_findings = finding_q.scalar() or 0

    user_info = {
        "id": current_user.id,
        "username": current_user.username or "",
        "team": None,
    }
    teams = ledger_management_service.get_teams_by_user(db, current_user.id)
    if teams:
        user_info["team"] = {
            "id": teams[0].id,
            "name": teams[0].name,
        }
    elif current_user.team:
        user_info["team"] = {
            "id": current_user.team.id,
            "name": current_user.team.name,
        }

    return {
        "user": user_info,
        "voucher_count": int(voucher_count),
        "unclosed_periods": int(unclosed_periods),
        "unaudited_periods": int(unclosed_periods),
        "pending_risks": int(pending_risks),
        "recent_findings": int(recent_findings),
        "unposted_periods": int(unclosed_periods),
        "notifications": 0,
        "module_status": {
            "ledger": {
                "pending_vouchers": int(pending_vouchers),
                "unclosed_periods": int(unclosed_periods),
            },
            "audit": {
                "active_projects": int(recent_findings),
                "pending_tests": int(pending_risks),
            },
            "bank": {
                "unreconciled": 0,
            },
            "tax": {
                "pending_invoices": 0,
            },
            "basic": {
                "incomplete_accounts": 0,
            },
        },
    }
