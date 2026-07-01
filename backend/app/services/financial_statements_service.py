"""三大财务报表计算服务：科目余额表、资产负债表、利润表。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    ChartOfAccounts,
    OpeningBalance,
)
from app.services.reclassification_service import classify_counterparty_balance


# 利润表科目分组
INCOME_ACCOUNTS = {
    "main_business_revenue": ["6001"],
    "other_business_revenue": ["6051"],
    "investment_income": ["6111"],
    "non_operating_income": ["6301"],
}
EXPENSE_ACCOUNTS = {
    "main_business_cost": ["6401"],
    "other_business_cost": ["6402"],
    "selling_expenses": ["6601"],
    "admin_expenses": ["6602"],
    "financial_expenses": ["6603"],
    "asset_impairment_loss": ["6701"],
    "non_operating_expense": ["6711"],
    "income_tax_expense": ["6801"],
}


def compute_account_balances(db: Session, ledger_id: int | None, period_id: int) -> list[dict[str, Any]]:
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    effective_ledger_id = ledger_id if ledger_id is not None else period.ledger_id
    if effective_ledger_id is not None and period.ledger_id is not None and period.ledger_id != effective_ledger_id:
        raise ValueError("会计期间不属于指定账簿")

    query = db.query(ChartOfAccounts)
    if effective_ledger_id is not None:
        query = query.filter(ChartOfAccounts.ledger_id == effective_ledger_id)
    else:
        query = query.filter(ChartOfAccounts.ledger_id.is_(None))
    accounts = query.order_by(ChartOfAccounts.code).all()

    opening_map = {
        ob.account_code: ob
        for ob in db.query(OpeningBalance)
        .filter(
            OpeningBalance.ledger_id == ledger_id,
            OpeningBalance.period_id == period_id,
        )
        .all()
    }

    period_query = (
        db.query(
            AccountingEntry.account_code,
            func.sum(AccountingEntry.debit_amount).label("debit"),
            func.sum(AccountingEntry.credit_amount).label("credit"),
        )
        .filter(
            AccountingEntry.ledger_id == ledger_id,
            AccountingEntry.voucher_date >= period.start_date,
            AccountingEntry.voucher_date <= period.end_date,
        )
        .group_by(AccountingEntry.account_code)
        .all()
    )
    period_map = {row.account_code: (Decimal(str(row.debit or 0)), Decimal(str(row.credit or 0))) for row in period_query}

    rows: list[dict[str, Any]] = []
    for account in accounts:
        opening = opening_map.get(account.code)
        opening_debit = Decimal(str(opening.debit_balance)) if opening else Decimal("0")
        opening_credit = Decimal(str(opening.credit_balance)) if opening else Decimal("0")
        period_debit, period_credit = period_map.get(account.code, (Decimal("0"), Decimal("0")))

        # 期末余额（按方向收敛到一边）
        if account.direction == "debit":
            net = (opening_debit - opening_credit) + (period_debit - period_credit)
            closing_debit = max(net, Decimal("0"))
            closing_credit = max(-net, Decimal("0"))
        else:
            net = (opening_credit - opening_debit) + (period_credit - period_debit)
            closing_credit = max(net, Decimal("0"))
            closing_debit = max(-net, Decimal("0"))

        rows.append(
            {
                "account_code": account.code,
                "account_name": account.name,
                "category": account.category,
                "direction": account.direction,
                "opening_debit": float(opening_debit),
                "opening_credit": float(opening_credit),
                "period_debit": float(period_debit),
                "period_credit": float(period_credit),
                "closing_debit": float(closing_debit),
                "closing_credit": float(closing_credit),
            }
        )
    return rows


def trial_balance_report(db: Session, ledger_id: int, period_id: int) -> dict[str, Any]:
    rows = compute_account_balances(db, ledger_id, period_id)
    totals = {
        "opening_debit": sum(r["opening_debit"] for r in rows),
        "opening_credit": sum(r["opening_credit"] for r in rows),
        "period_debit": sum(r["period_debit"] for r in rows),
        "period_credit": sum(r["period_credit"] for r in rows),
        "closing_debit": sum(r["closing_debit"] for r in rows),
        "closing_credit": sum(r["closing_credit"] for r in rows),
    }
    return {
        "rows": rows,
        "totals": totals,
        "is_balanced": totals["closing_debit"] == totals["closing_credit"],
    }


def _category_total(rows: list[dict], category: str) -> float:
    """按类别汇总：以方向决定取借/贷净额。"""
    total = Decimal("0")
    for r in rows:
        if r["category"] != category:
            continue
        if r["direction"] == "debit":
            total += Decimal(str(r["closing_debit"])) - Decimal(str(r["closing_credit"]))
        else:
            total += Decimal(str(r["closing_credit"])) - Decimal(str(r["closing_debit"]))
    return float(total)


def _normal_balance_amount(row: dict[str, Any]) -> Decimal:
    if row["direction"] == "debit":
        return Decimal(str(row["closing_debit"])) - Decimal(str(row["closing_credit"]))
    return Decimal(str(row["closing_credit"])) - Decimal(str(row["closing_debit"]))


def _row_amount_for_presentation(row: dict[str, Any]) -> Decimal:
    amount = _normal_balance_amount(row)
    return abs(amount)


def _apply_counterparty_reclassification(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows_by_code = {row["account_code"]: row for row in rows}
    adjusted_rows = [dict(row) for row in rows]
    presentation_rows_by_code = {row["account_code"]: row for row in adjusted_rows}
    adjustments: list[dict[str, Any]] = []

    for row in rows:
        try:
            result = classify_counterparty_balance(row["account_code"], _normal_balance_amount(row))
        except ValueError:
            continue
        target_code = result["presentation_account_code"]
        if target_code == row["account_code"] or result["balance_direction"] == "zero":
            continue

        amount = _row_amount_for_presentation(row)
        source_row = presentation_rows_by_code[row["account_code"]]
        source_row["closing_debit"] = 0.0
        source_row["closing_credit"] = 0.0
        source_row["reclassified_to_account_code"] = target_code
        source_row["reclassification_reason"] = result["reason"]

        target_row = presentation_rows_by_code.get(target_code)
        if target_row is None:
            configured_target = rows_by_code.get(target_code)
            target_row = dict(configured_target or row)
            target_row.update(
                {
                    "account_code": target_code,
                    "account_name": result["presentation_account_name"],
                    "category": "asset" if target_code.startswith("1") else "liability",
                    "direction": "debit" if target_code.startswith("1") else "credit",
                    "opening_debit": 0.0,
                    "opening_credit": 0.0,
                    "period_debit": 0.0,
                    "period_credit": 0.0,
                    "closing_debit": 0.0,
                    "closing_credit": 0.0,
                }
            )
            presentation_rows_by_code[target_code] = target_row
            adjusted_rows.append(target_row)

        if target_row["direction"] == "debit":
            target_row["closing_debit"] = float(Decimal(str(target_row["closing_debit"])) + amount)
        else:
            target_row["closing_credit"] = float(Decimal(str(target_row["closing_credit"])) + amount)
        target_row["reclassified_from_account_code"] = row["account_code"]

        adjustments.append(
            {
                "from_account_code": row["account_code"],
                "from_account_name": row["account_name"],
                "to_account_code": target_code,
                "to_account_name": result["presentation_account_name"],
                "amount": float(amount),
                "balance_direction": result["balance_direction"],
                "reason": result["reason"],
                "counterparty_semantic_note": result["counterparty_semantic_note"],
            }
        )

    return adjusted_rows, adjustments


def _sum_codes(rows_by_code: dict[str, dict], codes: list[str], side: str) -> Decimal:
    total = Decimal("0")
    for code in codes:
        row = rows_by_code.get(code)
        if not row:
            continue
        if side == "credit":
            total += Decimal(str(row["period_credit"])) - Decimal(str(row["period_debit"]))
        else:
            total += Decimal(str(row["period_debit"])) - Decimal(str(row["period_credit"]))
    return total


def balance_sheet(db: Session, ledger_id: int, period_id: int) -> dict[str, Any]:
    rows = compute_account_balances(db, ledger_id, period_id)
    presentation_rows, reclassification_adjustments = _apply_counterparty_reclassification(rows)
    assets_total = _category_total(presentation_rows, "asset")
    liabilities_total = _category_total(presentation_rows, "liability")
    equity_total = _category_total(presentation_rows, "equity")
    return {
        "assets": [r for r in presentation_rows if r["category"] == "asset"],
        "liabilities": [r for r in presentation_rows if r["category"] == "liability"],
        "equity": [r for r in presentation_rows if r["category"] == "equity"],
        "assets_total": assets_total,
        "liabilities_total": liabilities_total,
        "equity_total": equity_total,
        "reclassification_adjustments": reclassification_adjustments,
        "is_balanced": round(assets_total - liabilities_total - equity_total, 2) == 0,
    }


def income_statement(db: Session, ledger_id: int, period_id: int) -> dict[str, Any]:
    rows = compute_account_balances(db, ledger_id, period_id)
    rows_by_code = {r["account_code"]: r for r in rows}

    revenue = {k: float(_sum_codes(rows_by_code, codes, "credit")) for k, codes in INCOME_ACCOUNTS.items()}
    expense = {k: float(_sum_codes(rows_by_code, codes, "debit")) for k, codes in EXPENSE_ACCOUNTS.items()}

    operating_revenue = revenue["main_business_revenue"] + revenue["other_business_revenue"]
    operating_cost = expense["main_business_cost"] + expense["other_business_cost"]
    period_expenses = (
        expense["selling_expenses"]
        + expense["admin_expenses"]
        + expense["financial_expenses"]
        + expense["asset_impairment_loss"]
    )
    operating_profit = operating_revenue - operating_cost - period_expenses + revenue["investment_income"]
    total_profit = operating_profit + revenue["non_operating_income"] - expense["non_operating_expense"]
    net_profit = total_profit - expense["income_tax_expense"]

    return {
        "revenue": revenue,
        "expense": expense,
        "operating_revenue": operating_revenue,
        "operating_cost": operating_cost,
        "period_expenses": period_expenses,
        "operating_profit": operating_profit,
        "total_profit": total_profit,
        "income_tax": expense["income_tax_expense"],
        "net_profit": net_profit,
    }
