"""损益结转健康检查：导入结转识别、期间状态与资产负债表一致性校验。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod, Voucher
import app.services.accounting.financial_statements_service as financial_statements_service

PL_TRANSFER_VOUCHER_PREFIX = "转-期末-"
IMPORT_PL_SUMMARY_KEYWORDS = ("结转", "本年利润", "损益结转")
IMPORT_PL_ACCOUNT_PREFIXES = ("4103", "3103", "4104", "4101")


def _period_bounds(period: AccountingPeriod) -> tuple:
    return period.start_date, period.end_date


def has_system_pl_voucher(db: Session, ledger_id: int, period_code: str) -> bool:
    voucher_no = f"{PL_TRANSFER_VOUCHER_PREFIX}{period_code}"
    return (
        db.query(Voucher.id)
        .filter(
            Voucher.ledger_id == ledger_id,
            Voucher.voucher_no == voucher_no,
            Voucher.source_type == "period_close",
        )
        .first()
        is not None
    )


def detect_imported_pl_vouchers(
    db: Session,
    ledger_id: int,
    period_id: int,
) -> list[dict[str, Any]]:
    """识别期间内来源为 import、摘要或科目暗示为损益结转的凭证。"""
    period = db.get(AccountingPeriod, period_id)
    if not period:
        return []
    start, end = _period_bounds(period)

    summary_filters = [Voucher.summary.like(f"%{kw}%") for kw in IMPORT_PL_SUMMARY_KEYWORDS]
    vouchers = (
        db.query(Voucher)
        .filter(
            Voucher.ledger_id == ledger_id,
            Voucher.source_type == "import",
            Voucher.voucher_date >= start,
            Voucher.voucher_date <= end,
            or_(*summary_filters),
        )
        .order_by(Voucher.voucher_date, Voucher.voucher_no)
        .all()
    )

    results: list[dict[str, Any]] = []
    seen: set[int] = set()
    for voucher in vouchers:
        if voucher.id in seen:
            continue
        seen.add(voucher.id)
        pl_accounts = (
            db.query(AccountingEntry.account_code)
            .filter(
                AccountingEntry.voucher_id == voucher.id,
                or_(
                    *[
                        AccountingEntry.account_code.like(f"{prefix}%")
                        for prefix in IMPORT_PL_ACCOUNT_PREFIXES
                    ]
                ),
            )
            .distinct()
            .all()
        )
        results.append(
            {
                "voucher_id": voucher.id,
                "voucher_no": voucher.voucher_no,
                "voucher_date": str(voucher.voucher_date),
                "summary": voucher.summary,
                "pl_accounts": [row[0] for row in pl_accounts],
            }
        )
    return results


def profit_accounts_closing_cleared(
    db: Session,
    ledger_id: int,
    period_id: int,
) -> tuple[bool, list[dict[str, Any]]]:
    """损益类科目期末借贷是否均已清零。"""
    rows = financial_statements_service.compute_account_balances(db, ledger_id, period_id)
    non_zero: list[dict[str, Any]] = []
    for row in rows:
        if row.get("_rollup_meta") or row.get("category") != "profit":
            continue
        closing_debit = Decimal(str(row.get("closing_debit", "0")))
        closing_credit = Decimal(str(row.get("closing_credit", "0")))
        if closing_debit != 0 or closing_credit != 0:
            non_zero.append(
                {
                    "account_code": row["account_code"],
                    "account_name": row["account_name"],
                    "closing_debit": str(closing_debit.quantize(Decimal("0.01"))),
                    "closing_credit": str(closing_credit.quantize(Decimal("0.01"))),
                }
            )
    return len(non_zero) == 0, non_zero


def assess_pl_transfer_readiness(db: Session, ledger_id: int, period_id: int) -> dict[str, Any]:
    """
    评估期间是否已满足损益结转条件（过账/结账前校验）。

    若导入凭证已使损益科目清零且资产负债表平衡，则 ready=True，无需单独点击损益结转。
    """
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")

    profit_cleared, non_zero_profit = profit_accounts_closing_cleared(db, ledger_id, period_id)
    bs = financial_statements_service._build_balance_sheet_payload(db, ledger_id, period_id)
    imported = detect_imported_pl_vouchers(db, ledger_id, period_id)
    system_pl = has_system_pl_voucher(db, ledger_id, period.period_code)
    is_balanced = bool(bs.get("is_balanced"))

    base = {
        "period_id": period_id,
        "period_code": period.period_code,
        "period_status": period.status,
        "profit_accounts_cleared": profit_cleared,
        "non_zero_profit_accounts": non_zero_profit[:10],
        "is_balanced": is_balanced,
        "has_system_pl_voucher": system_pl,
        "imported_pl_voucher_count": len(imported),
        "imported_pl_vouchers": imported[:5],
    }

    if period.status in {"pl_transferred", "closed"}:
        return {
            **base,
            "ready": True,
            "mode": "already_transferred",
            "can_close_without_manual_transfer": True,
            "message": "期间已满足损益结转条件",
        }

    if profit_cleared and is_balanced:
        if imported:
            mode = "imported_satisfied"
            message = (
                f"导入凭证已使损益科目清零且资产负债表平衡，可直接过账/结账"
                f"（检测到 {len(imported)} 张导入结转凭证）"
            )
        elif system_pl:
            mode = "system_satisfied"
            message = "系统结转凭证已存在，损益科目已清零，可直接结账"
        else:
            mode = "no_profit_balance"
            message = "本期无损益科目余额且资产负债表平衡，可直接结账"
        return {
            **base,
            "ready": True,
            "mode": mode,
            "can_close_without_manual_transfer": True,
            "message": message,
        }

    if not profit_cleared:
        return {
            **base,
            "ready": False,
            "mode": "transfer_required",
            "can_close_without_manual_transfer": False,
            "message": (
                f"尚有 {len(non_zero_profit)} 个损益类科目未清零；"
                "结账时将自动尝试生成结转凭证，或请补录导入结转凭证"
            ),
        }

    return {
        **base,
        "ready": False,
        "mode": "balance_sheet_unbalanced",
        "can_close_without_manual_transfer": False,
        "message": (
            "损益科目已清零但资产负债表仍不平衡，请检查凭证、期初余额与科目映射后再结账"
        ),
    }


def try_sync_pl_status_after_post(db: Session, ledger_id: int, voucher_id: int) -> dict[str, Any] | None:
    """凭证过账后：若导入结转已使损益清零且报表平衡，自动将期间标记为可结账。"""
    from datetime import datetime, timezone

    voucher = db.get(Voucher, voucher_id)
    if not voucher or voucher.ledger_id != ledger_id:
        return None

    period = (
        db.query(AccountingPeriod)
        .filter(
            AccountingPeriod.ledger_id == ledger_id,
            AccountingPeriod.start_date <= voucher.voucher_date,
            AccountingPeriod.end_date >= voucher.voucher_date,
            AccountingPeriod.status.in_(["open", "reopened"]),
        )
        .order_by(AccountingPeriod.start_date.desc())
        .first()
    )
    if not period:
        return None

    assessment = assess_pl_transfer_readiness(db, ledger_id, period.id)
    if not assessment.get("ready"):
        return None
    if assessment.get("mode") not in {"imported_satisfied", "no_profit_balance", "system_satisfied"}:
        return None

    period.status = "pl_transferred"
    period.updated_at = datetime.now(timezone.utc)
    db.commit()
    assessment["synced_after_post"] = True
    assessment["period_status"] = period.status
    return assessment


def audit_period_pl_status(db: Session, ledger_id: int, period_id: int) -> dict[str, Any]:
    """校验期间损益结转状态是否与凭证、资产负债表一致。"""
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")

    bs = financial_statements_service._build_balance_sheet_payload(db, ledger_id, period_id)
    imported = detect_imported_pl_vouchers(db, ledger_id, period_id)
    system_pl = has_system_pl_voucher(db, ledger_id, period.period_code)
    is_balanced = bool(bs.get("is_balanced"))

    profit_cleared, _ = profit_accounts_closing_cleared(db, ledger_id, period_id)

    warnings: list[str] = []
    if (
        period.status in {"pl_transferred", "closed"}
        and not system_pl
        and not imported
        and not profit_cleared
    ):
        warnings.append(
            f"期间已标记为 {period.status}，但损益科目未清零，且未检测到系统或导入结转凭证"
        )

    if period.status in {"pl_transferred", "closed"} and not is_balanced:
        gap = Decimal(str(bs.get("assets_total", 0))) - (
            Decimal(str(bs.get("liabilities_total", 0))) + Decimal(str(bs.get("equity_total", 0)))
        )
        warnings.append(
            f"期间已标记为 {period.status}，但资产负债表不平衡，差额 {gap.quantize(Decimal('0.01'))}"
        )

    if imported and any(
        not any(acc.startswith("4103") for acc in item.get("pl_accounts", []))
        for item in imported
    ):
        warnings.append("导入结转凭证使用了非 4103（本年利润）科目（如 3103 利润分配），与系统结转口径不一致")

    status_consistent = (
        period.status not in {"pl_transferred", "closed"}
        or (is_balanced and (system_pl or bool(imported) or profit_cleared))
    )

    readiness = assess_pl_transfer_readiness(db, ledger_id, period_id)

    return {
        **readiness,
        "period_status_consistent": status_consistent,
        "warnings": warnings,
    }


def reconcile_period_pl_status(db: Session, ledger_id: int, period_id: int, *, auto_fix: bool = False) -> dict[str, Any]:
    """
    校验并在允许时修复错误的 pl_transferred 标记。
    已结账期间仅报告，不自动降级。
    """
    audit = audit_period_pl_status(db, ledger_id, period_id)
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")

    fixed = False
    if (
        auto_fix
        and period.status == "pl_transferred"
        and not audit["period_status_consistent"]
    ):
        period.status = "open"
        db.commit()
        fixed = True
        audit["warnings"].append("已自动将期间状态从 pl_transferred 恢复为 open，请重新执行损益结转或修正科目映射")

    audit["fixed"] = fixed
    return audit
