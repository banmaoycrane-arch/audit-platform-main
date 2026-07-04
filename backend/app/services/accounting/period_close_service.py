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
        # 无损益需要结转，直接标记期间状态
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
