# -*- coding: utf-8 -*-
from __future__ import annotations

"""期末损益结转服务。

将本期所有 `category=profit` 科目余额结转到 `4103 本年利润`，
使资产负债表恒等式成立。

结转规则：
- 收入类（direction=credit，期末贷方有余）：借 6XXX / 贷 4103
- 成本费用类（direction=debit，期末借方有余）：借 4103 / 贷 6XXX

结转分录的凭证字为 `转-期末-{period_code}`。
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod, ChartOfAccounts, Voucher
import app.services.accounting.financial_statements_service as financial_statements_service
import app.services.accounting.voucher_service as voucher_service
from app.services.accounting.voucher_service import VoucherValidationError


PL_ACCOUNT_CODE = "4103"  # 本年利润
PL_TRANSFER_VOUCHER_PREFIX = "转-期末-"


def _ensure_pl_account(db: Session, ledger_id: int | None = None) -> ChartOfAccounts:
    query = db.query(ChartOfAccounts).filter(ChartOfAccounts.code == PL_ACCOUNT_CODE)
    if ledger_id is not None:
        query = query.filter(ChartOfAccounts.ledger_id == ledger_id)
    account = query.first()
    if not account:
        account = ChartOfAccounts(
            ledger_id=ledger_id,
            code=PL_ACCOUNT_CODE,
            name="本年利润",
            parent_code=None,
            level=1,
            category="equity",
            direction="credit",
            is_terminal=True,
            status="active",
            is_system=True,
        )
        db.add(account)
        db.flush()
    return account


def auto_pl_transfer(db: Session, ledger_id: int | None, period_id: int) -> dict[str, Any]:
    """对指定账簿和期间执行损益结转。"""
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    if ledger_id is not None and period.ledger_id is not None and period.ledger_id != ledger_id:
        raise ValueError("会计期间不属于指定账簿")
    if period.status == "pl_transferred":
        raise PermissionError("该期间已结转损益，请先反结转再重做")
    if period.status == "closed":
        raise PermissionError("该期间已结账，无法结转损益")

    effective_ledger_id = ledger_id or period.ledger_id
    if effective_ledger_id is None:
        raise ValueError("无法确定账簿ID")

    _ensure_pl_account(db, effective_ledger_id)

    rows = financial_statements_service.compute_account_balances(db, effective_ledger_id, period_id)
    voucher_no = f"{PL_TRANSFER_VOUCHER_PREFIX}{period.period_code}"

    # 删除旧的结转凭证（如果存在），避免重复
    _delete_pl_transfer_voucher(db, effective_ledger_id, voucher_no)

    lines: list[voucher_service.VoucherEntryLine] = []
    pl_total = Decimal("0")  # 净利润累加：贷方为 + ，借方为 -

    for row in rows:
        if row["category"] != "profit":
            continue
        period_debit = Decimal(str(row["period_debit"]))
        period_credit = Decimal(str(row["period_credit"]))
        if row["direction"] == "credit":
            # 收入类：贷方为正
            net = period_credit - period_debit
            if net == 0:
                continue
            # 借 收入科目 / 贷 4103
            lines.append(
                voucher_service.VoucherEntryLine(
                    account_code=row["account_code"],
                    account_name=row["account_name"],
                    summary=f"结转{row['account_name']}至本年利润",
                    debit_amount=Decimal(net) if net > 0 else Decimal("0"),
                    credit_amount=Decimal(-net) if net < 0 else Decimal("0"),
                    normalized_text=f"结转 {row['account_name']}",
                )
            )
            lines.append(
                voucher_service.VoucherEntryLine(
                    account_code=PL_ACCOUNT_CODE,
                    account_name="本年利润",
                    summary=f"结转{row['account_name']}至本年利润",
                    debit_amount=Decimal("0") if net > 0 else Decimal(-net),
                    credit_amount=Decimal(net) if net > 0 else Decimal("0"),
                    normalized_text="结转 本年利润",
                )
            )
            pl_total += net
        else:
            # 成本费用类：借方为正
            net = period_debit - period_credit
            if net == 0:
                continue
            # 借 4103 / 贷 费用科目
            lines.append(
                voucher_service.VoucherEntryLine(
                    account_code=PL_ACCOUNT_CODE,
                    account_name="本年利润",
                    summary=f"结转{row['account_name']}至本年利润",
                    debit_amount=Decimal(net) if net > 0 else Decimal("0"),
                    credit_amount=Decimal(-net) if net < 0 else Decimal("0"),
                    normalized_text="结转 本年利润",
                )
            )
            lines.append(
                voucher_service.VoucherEntryLine(
                    account_code=row["account_code"],
                    account_name=row["account_name"],
                    summary=f"结转{row['account_name']}至本年利润",
                    debit_amount=Decimal("0") if net > 0 else Decimal(-net),
                    credit_amount=Decimal(net) if net > 0 else Decimal("0"),
                    normalized_text=f"结转 {row['account_name']}",
                )
            )
            pl_total -= net

    if not lines:
        balance_sheet = financial_statements_service._build_balance_sheet_payload(
            db, effective_ledger_id, period_id
        )
        unmapped_net = Decimal(str(balance_sheet.get("unmapped_entry_net") or 0))

        if not balance_sheet.get("is_balanced"):
            hint = (
                "无损益科目可结转，但资产负债表仍不平衡，请检查明细科目映射、导入结转凭证或期初余额。"
                f" 资产 {balance_sheet.get('assets_total')} ≠ 负债 {balance_sheet.get('liabilities_total')}"
                f" + 权益 {balance_sheet.get('equity_total')}"
            )
            if unmapped_net != 0:
                unmapped_codes = balance_sheet.get("unmapped_codes") or []
                codes_text = "、".join(unmapped_codes[:8]) if unmapped_codes else "见科目余额表"
                hint += (
                    f"。未映射分录净额 {unmapped_net.quantize(Decimal('0.01'))}，"
                    f"建议在「损益结转与结账」页执行「补全 COA 缺口」（涉及科目：{codes_text}）"
                )
            raise ValueError(hint)

        period.status = "pl_transferred"
        period.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {
            "period_id": period_id,
            "voucher_no": voucher_no,
            "lines": 0,
            "net_profit": float(pl_total),
            "status": period.status,
        }

    voucher = voucher_service.create_voucher(
        db,
        ledger_id=effective_ledger_id,
        organization_id=period.organization_id,
        voucher_no=voucher_no,
        voucher_date=period.end_date,
        summary=f"损益结转 {period.period_code}",
        lines=lines,
        source_type=voucher_service.VoucherSourceType.PERIOD_CLOSE,
        source_id=period.id,
        status=voucher_service.VoucherStatus.POSTED,
        auto_commit=False,
    )

    # 损益结转后必须校验资产负债表平衡，这是会计准则的硬性要求。
    # 若不平衡，说明凭证、期初或期间处理存在错误，必须回滚并排查。
    balance_sheet = financial_statements_service.balance_sheet(db, effective_ledger_id, period_id)
    if not balance_sheet.get("is_balanced"):
        db.rollback()
        raise ValueError(
            f"损益结转后资产负债表不平衡：资产总计 {balance_sheet.get('assets_total')} "
            f"不等于负债及权益总计 {balance_sheet.get('liabilities_total')} + {balance_sheet.get('equity_total')}，"
            f"请检查凭证、期初余额及结转分录"
        )

    period.status = "pl_transferred"
    period.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "period_id": period_id,
        "voucher_no": voucher_no,
        "lines": len(lines),
        "net_profit": float(pl_total),
        "status": period.status,
        "voucher_id": voucher.id,
        "balance_sheet_balanced": True,
    }


def ensure_pl_transfer_ready(
    db: Session,
    ledger_id: int | None,
    period_id: int,
    *,
    auto_apply: bool = True,
) -> dict[str, Any]:
    """
    结账/过账前确保损益结转条件成立。

    - 导入凭证已清零损益且报表平衡：仅更新期间状态，不生成系统结转凭证
    - 仍有损益余额：自动调用 auto_pl_transfer 生成结转凭证
    """
    from app.services.accounting.period_pl_health_service import assess_pl_transfer_readiness

    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    if period.status == "closed":
        raise PermissionError("该期间已结账")
    effective_ledger_id = ledger_id or period.ledger_id
    if effective_ledger_id is None:
        raise ValueError("无法确定账簿ID")

    assessment = assess_pl_transfer_readiness(db, effective_ledger_id, period_id)
    if period.status == "pl_transferred":
        return {**assessment, "applied": False, "status": period.status}

    if assessment.get("ready"):
        if auto_apply and period.status in {"open", "reopened"}:
            period.status = "pl_transferred"
            period.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(period)
        return {
            **assessment,
            "applied": auto_apply,
            "status": period.status,
            "voucher_no": None,
            "lines": 0,
        }

    if assessment.get("mode") == "transfer_required" and auto_apply:
        return auto_pl_transfer(db, effective_ledger_id, period_id)

    raise ValueError(assessment.get("message") or "损益结转条件未满足，无法继续")


def _delete_pl_transfer_voucher(db: Session, ledger_id: int, voucher_no: str) -> int:
    """删除指定账簿和凭证号的损益结转凭证及其分录。"""
    voucher = (
        db.query(Voucher)
        .filter(Voucher.ledger_id == ledger_id, Voucher.voucher_no == voucher_no)
        .first()
    )
    deleted_lines = 0
    if voucher:
        deleted_lines = db.query(AccountingEntry).filter(AccountingEntry.voucher_id == voucher.id).delete()
        db.delete(voucher)
        db.flush()
    return deleted_lines


def reverse_pl_transfer(db: Session, ledger_id: int, period_id: int) -> dict[str, Any]:
    """反结转：删除该账簿期间的损益结转凭证，并把状态恢复为 open。"""
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    if period.ledger_id != ledger_id:
        raise ValueError("会计期间不属于指定账簿")
    if period.status == "closed":
        raise PermissionError("该期间已结账，无法反结转")

    voucher_no = f"{PL_TRANSFER_VOUCHER_PREFIX}{period.period_code}"
    deleted_lines = _delete_pl_transfer_voucher(db, ledger_id, voucher_no)

    period.status = "open"
    period.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {
        "period_id": period_id,
        "voucher_no": voucher_no,
        "deleted_lines": deleted_lines,
        "status": period.status,
    }


TRANSFERABLE_PERIOD_STATUSES = frozenset({"open", "reopened"})


def _resolve_batch_pl_transfer_periods(
    db: Session,
    ledger_id: int,
    *,
    period_ids: list[int] | None = None,
    from_period_id: int | None = None,
    to_period_id: int | None = None,
) -> list[AccountingPeriod]:
    """解析批量结转目标期间，按 start_date 升序返回。"""
    if period_ids:
        seen: set[int] = set()
        periods: list[AccountingPeriod] = []
        for period_id in period_ids:
            if period_id in seen:
                continue
            seen.add(period_id)
            period = db.get(AccountingPeriod, period_id)
            if not period:
                raise LookupError(f"会计期间不存在: {period_id}")
            if period.ledger_id != ledger_id:
                raise ValueError(f"期间 {period.period_code} 不属于指定账簿")
            periods.append(period)
        return sorted(periods, key=lambda item: (item.start_date, item.id))

    if from_period_id is not None and to_period_id is not None:
        period_from = db.get(AccountingPeriod, from_period_id)
        period_to = db.get(AccountingPeriod, to_period_id)
        if not period_from or not period_to:
            raise LookupError("起始或结束会计期间不存在")
        if period_from.ledger_id != ledger_id or period_to.ledger_id != ledger_id:
            raise ValueError("跨期间结转的起止期间必须属于同一账簿")
        range_start = min(period_from.start_date, period_to.start_date)
        range_end = max(period_from.end_date, period_to.end_date)
        return (
            db.query(AccountingPeriod)
            .filter(
                AccountingPeriod.ledger_id == ledger_id,
                AccountingPeriod.start_date >= range_start,
                AccountingPeriod.start_date <= range_end,
            )
            .order_by(AccountingPeriod.start_date, AccountingPeriod.id)
            .all()
        )

    raise ValueError("请指定 period_ids，或同时指定 from_period_id 与 to_period_id")


def batch_pl_transfer(
    db: Session,
    ledger_id: int,
    *,
    period_ids: list[int] | None = None,
    from_period_id: int | None = None,
    to_period_id: int | None = None,
    stop_on_error: bool = True,
    skip_transferred: bool = True,
) -> dict[str, Any]:
    """按期间顺序批量执行损益结转，支持勾选多期或起止跨期间连续结转。"""
    periods = _resolve_batch_pl_transfer_periods(
        db,
        ledger_id,
        period_ids=period_ids,
        from_period_id=from_period_id,
        to_period_id=to_period_id,
    )
    if not periods:
        raise ValueError("未找到可结转的会计期间")

    succeeded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for period in periods:
        if period.status == "closed":
            skipped.append(
                {
                    "period_id": period.id,
                    "period_code": period.period_code,
                    "status": period.status,
                    "reason": "已结账，跳过",
                }
            )
            continue
        if skip_transferred and period.status == "pl_transferred":
            skipped.append(
                {
                    "period_id": period.id,
                    "period_code": period.period_code,
                    "status": period.status,
                    "reason": "已结转损益，跳过",
                }
            )
            continue
        if period.status not in TRANSFERABLE_PERIOD_STATUSES:
            skipped.append(
                {
                    "period_id": period.id,
                    "period_code": period.period_code,
                    "status": period.status,
                    "reason": f"状态 {period.status} 不可结转，跳过",
                }
            )
            continue

        try:
            result = auto_pl_transfer(db, ledger_id, period.id)
            succeeded.append(
                {
                    "period_id": period.id,
                    "period_code": period.period_code,
                    "status": result.get("status", period.status),
                    "voucher_no": result.get("voucher_no"),
                    "lines": result.get("lines"),
                    "net_profit": result.get("net_profit"),
                }
            )
        except (LookupError, PermissionError, ValueError, VoucherValidationError) as exc:
            failed.append(
                {
                    "period_id": period.id,
                    "period_code": period.period_code,
                    "status": period.status,
                    "error": str(exc),
                }
            )
            if stop_on_error:
                break

    return {
        "ledger_id": ledger_id,
        "total": len(periods),
        "succeeded_count": len(succeeded),
        "failed_count": len(failed),
        "skipped_count": len(skipped),
        "stopped_early": bool(stop_on_error and failed),
        "succeeded": succeeded,
        "failed": failed,
        "skipped": skipped,
    }
