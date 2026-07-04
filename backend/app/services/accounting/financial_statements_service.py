"""三大财务报表计算服务：科目余额表、资产负债表、利润表。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    ChartOfAccounts,
    OpeningBalance,
    Voucher,
)
from app.services.accounting.reclassification_service import classify_counterparty_balance


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
                "opening_debit": str(opening_debit.quantize(Decimal("0.00"))),
                "opening_credit": str(opening_credit.quantize(Decimal("0.00"))),
                "period_debit": str(period_debit.quantize(Decimal("0.00"))),
                "period_credit": str(period_credit.quantize(Decimal("0.00"))),
                "closing_debit": str(closing_debit.quantize(Decimal("0.00"))),
                "closing_credit": str(closing_credit.quantize(Decimal("0.00"))),
            }
        )
    return rows


def trial_balance_report(db: Session, ledger_id: int, period_id: int) -> dict[str, Any]:
    rows = compute_account_balances(db, ledger_id, period_id)
    
    opening_debit_total = Decimal("0.00")
    opening_credit_total = Decimal("0.00")
    period_debit_total = Decimal("0.00")
    period_credit_total = Decimal("0.00")
    closing_debit_total = Decimal("0.00")
    closing_credit_total = Decimal("0.00")
    
    for r in rows:
        opening_debit_total += Decimal(str(r["opening_debit"]))
        opening_credit_total += Decimal(str(r["opening_credit"]))
        period_debit_total += Decimal(str(r["period_debit"]))
        period_credit_total += Decimal(str(r["period_credit"]))
        closing_debit_total += Decimal(str(r["closing_debit"]))
        closing_credit_total += Decimal(str(r["closing_credit"]))
    
    totals: dict[str, Decimal] = {
        "opening_debit": opening_debit_total,
        "opening_credit": opening_credit_total,
        "period_debit": period_debit_total,
        "period_credit": period_credit_total,
        "closing_debit": closing_debit_total,
        "closing_credit": closing_credit_total,
    }
    return {
        "rows": rows,
        "totals": {
            "opening_debit": str(totals["opening_debit"].quantize(Decimal("0.00"))),
            "opening_credit": str(totals["opening_credit"].quantize(Decimal("0.00"))),
            "period_debit": str(totals["period_debit"].quantize(Decimal("0.00"))),
            "period_credit": str(totals["period_credit"].quantize(Decimal("0.00"))),
            "closing_debit": str(totals["closing_debit"].quantize(Decimal("0.00"))),
            "closing_credit": str(totals["closing_credit"].quantize(Decimal("0.00"))),
        },
        "is_balanced": totals["closing_debit"] == totals["closing_credit"],
    }


def _category_total(rows: list[dict[str, Any]], category: str) -> Decimal:
    """按类别汇总：以方向决定取借/贷净额。"""
    total = Decimal("0")
    for r in rows:
        if r["category"] != category:
            continue
        if r["direction"] == "debit":
            total += Decimal(str(r["closing_debit"])) - Decimal(str(r["closing_credit"]))
        else:
            total += Decimal(str(r["closing_credit"])) - Decimal(str(r["closing_debit"]))
    return total


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
        source_row["closing_debit"] = "0.00"
        source_row["closing_credit"] = "0.00"
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
                    "opening_debit": "0.00",
                    "opening_credit": "0.00",
                    "period_debit": "0.00",
                    "period_credit": "0.00",
                    "closing_debit": "0.00",
                    "closing_credit": "0.00",
                }
            )
            presentation_rows_by_code[target_code] = target_row
            adjusted_rows.append(target_row)

        if target_row["direction"] == "debit":
            target_row["closing_debit"] = str((Decimal(str(target_row["closing_debit"])) + amount).quantize(Decimal("0.00")))
        else:
            target_row["closing_credit"] = str((Decimal(str(target_row["closing_credit"])) + amount).quantize(Decimal("0.00")))
        target_row["reclassified_from_account_code"] = row["account_code"]

        adjustments.append(
            {
                "from_account_code": row["account_code"],
                "from_account_name": row["account_name"],
                "to_account_code": target_code,
                "to_account_name": result["presentation_account_name"],
                "amount": str(amount.quantize(Decimal("0.00"))),
                "balance_direction": result["balance_direction"],
                "reason": result["reason"],
                "counterparty_semantic_note": result["counterparty_semantic_note"],
            }
        )

    return adjusted_rows, adjustments


def _sum_codes(rows_by_code: dict[str, dict[str, Any]], codes: list[str], side: str) -> Decimal:
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
        "assets_total": str(assets_total.quantize(Decimal("0.00"))),
        "liabilities_total": str(liabilities_total.quantize(Decimal("0.00"))),
        "equity_total": str(equity_total.quantize(Decimal("0.00"))),
        "reclassification_adjustments": reclassification_adjustments,
        "is_balanced": assets_total == liabilities_total + equity_total,
    }


def _compute_profit_account_period_amounts(
    db: Session, ledger_id: int, period_id: int
) -> dict[str, tuple[Decimal, Decimal]]:
    """
    计算利润表科目在指定期间内的本期发生额，并排除损益结转凭证的影响。

    业务逻辑：
        利润表反映的是本期真实经营成果，不应包含为期末结账而生成的
        损益结转分录（source_type=period_close）。本函数仅统计已过账、
        来源非 period_close 的分录发生额。
    """
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")

    effective_ledger_id = ledger_id if ledger_id is not None else period.ledger_id
    if effective_ledger_id is not None and period.ledger_id is not None and period.ledger_id != effective_ledger_id:
        raise ValueError("会计期间不属于指定账簿")

    profit_account_codes = set()
    for codes in INCOME_ACCOUNTS.values():
        profit_account_codes.update(codes)
    for codes in EXPENSE_ACCOUNTS.values():
        profit_account_codes.update(codes)

    query = (
        db.query(
            AccountingEntry.account_code,
            func.sum(AccountingEntry.debit_amount).label("debit"),
            func.sum(AccountingEntry.credit_amount).label("credit"),
        )
        .outerjoin(Voucher, AccountingEntry.voucher_id == Voucher.id)
        .filter(
            AccountingEntry.ledger_id == effective_ledger_id,
            AccountingEntry.voucher_date >= period.start_date,
            AccountingEntry.voucher_date <= period.end_date,
            AccountingEntry.post_status == "posted",
            AccountingEntry.account_code.in_(profit_account_codes),
            or_(
                AccountingEntry.voucher_id.is_(None),
                Voucher.source_type != "period_close",
            ),
        )
        .group_by(AccountingEntry.account_code)
    )
    return {
        row.account_code: (Decimal(str(row.debit or 0)), Decimal(str(row.credit or 0)))
        for row in query.all()
    }


def income_statement(db: Session, ledger_id: int, period_id: int) -> dict[str, Any]:
    """
    生成利润表。

    业务逻辑：
        利润表反映本期经营成果，统计口径为“本期真实发生额”，需排除
        损益结转凭证（source_type=period_close）对收入、成本费用的冲抵。
    """
    profit_amounts = _compute_profit_account_period_amounts(db, ledger_id, period_id)

    def _profit_sum(codes: list[str], side: str) -> Decimal:
        total = Decimal("0")
        for code in codes:
            debit, credit = profit_amounts.get(code, (Decimal("0"), Decimal("0")))
            if side == "credit":
                total += credit - debit
            else:
                total += debit - credit
        return total

    revenue = {k: str(_profit_sum(codes, "credit").quantize(Decimal("0.00"))) for k, codes in INCOME_ACCOUNTS.items()}
    expense = {k: str(_profit_sum(codes, "debit").quantize(Decimal("0.00"))) for k, codes in EXPENSE_ACCOUNTS.items()}

    operating_revenue = _profit_sum(
        INCOME_ACCOUNTS["main_business_revenue"] + INCOME_ACCOUNTS["other_business_revenue"], "credit"
    )
    operating_cost = _profit_sum(
        EXPENSE_ACCOUNTS["main_business_cost"] + EXPENSE_ACCOUNTS["other_business_cost"], "debit"
    )
    period_expenses = (
        _profit_sum(EXPENSE_ACCOUNTS["selling_expenses"], "debit")
        + _profit_sum(EXPENSE_ACCOUNTS["admin_expenses"], "debit")
        + _profit_sum(EXPENSE_ACCOUNTS["financial_expenses"], "debit")
        + _profit_sum(EXPENSE_ACCOUNTS["asset_impairment_loss"], "debit")
    )
    investment_income = _profit_sum(INCOME_ACCOUNTS["investment_income"], "credit")
    non_operating_income = _profit_sum(INCOME_ACCOUNTS["non_operating_income"], "credit")
    non_operating_expense = _profit_sum(EXPENSE_ACCOUNTS["non_operating_expense"], "debit")
    income_tax_expense = _profit_sum(EXPENSE_ACCOUNTS["income_tax_expense"], "debit")

    operating_profit = operating_revenue - operating_cost - period_expenses + investment_income
    total_profit = operating_profit + non_operating_income - non_operating_expense
    net_profit = total_profit - income_tax_expense

    return {
        "revenue": revenue,
        "expense": expense,
        "operating_revenue": str(operating_revenue.quantize(Decimal("0.00"))),
        "operating_cost": str(operating_cost.quantize(Decimal("0.00"))),
        "period_expenses": str(period_expenses.quantize(Decimal("0.00"))),
        "operating_profit": str(operating_profit.quantize(Decimal("0.00"))),
        "total_profit": str(total_profit.quantize(Decimal("0.00"))),
        "income_tax": str(income_tax_expense.quantize(Decimal("0.00"))),
        "net_profit": str(net_profit.quantize(Decimal("0.00"))),
    }


# 现金流量表科目分类规则
# 现金及现金等价物科目：库存现金、银行存款、其他货币资金
CASH_EQUIVALENT_ACCOUNT_PREFIXES = ("1001", "1002", "1003")

# 经营活动对方科目前缀：收入、成本、费用、往来等
OPERATING_COUNTERPARTY_PREFIXES = (
    "60", "61", "63",  # 收入
    "64", "66", "67", "68",  # 成本费用
    "11", "12", "22",  # 应收、预付、应付等往来
    "14",  # 其他应收
    "22",  # 应付职工薪酬等
)

# 投资活动对方科目前缀：长期股权投资、固定资产、无形资产等
INVESTING_COUNTERPARTY_PREFIXES = (
    "15", "16", "17",  # 长期股权投资、固定资产、无形资产
)

# 筹资活动对方科目前缀：借款、实收资本、资本公积等
FINANCING_COUNTERPARTY_PREFIXES = (
    "20", "21",  # 短期/长期借款
    "40", "41",  # 实收资本、资本公积
    "42",  # 盈余公积
)


def _classify_cash_flow_by_counterparty(account_code: str) -> str:
    """根据对方科目代码推断现金流量类别。"""
    code = account_code or ""
    for prefix in INVESTING_COUNTERPARTY_PREFIXES:
        if code.startswith(prefix):
            return "investing"
    for prefix in FINANCING_COUNTERPARTY_PREFIXES:
        if code.startswith(prefix):
            return "financing"
    return "operating"


def cash_flow_statement(db: Session, ledger_id: int, period_id: int) -> dict[str, Any]:
    """
    现金流量表（直接法简化版）。

    业务逻辑：
        1. 选取现金及现金等价物科目（1001/1002/1003）的发生额。
        2. 按对方科目类别将现金流划分为经营、投资、筹资活动。
        3. 计算各类活动的现金流入、流出及净额。

    注意事项：
        1. 本版本为简化直接法，未按凭证逐笔解析完整业务实质。
        2. 内部转账（现金与银行存款互转）不纳入现金流量。
    """
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")

    effective_ledger_id = ledger_id if ledger_id is not None else period.ledger_id
    if effective_ledger_id is not None and period.ledger_id is not None and period.ledger_id != effective_ledger_id:
        raise ValueError("会计期间不属于指定账簿")

    # 获取现金及现金等价物科目
    cash_accounts = (
        db.query(ChartOfAccounts)
        .filter(
            ChartOfAccounts.ledger_id == effective_ledger_id,
            ChartOfAccounts.code.in_(CASH_EQUIVALENT_ACCOUNT_PREFIXES),
        )
        .all()
    )
    cash_account_codes = {a.code for a in cash_accounts}

    # 查询期间内所有分录
    entries = (
        db.query(AccountingEntry)
        .filter(
            AccountingEntry.ledger_id == effective_ledger_id,
            AccountingEntry.voucher_date >= period.start_date,
            AccountingEntry.voucher_date <= period.end_date,
            AccountingEntry.post_status == "posted",
        )
        .all()
    )

    operating_inflow = Decimal("0")
    operating_outflow = Decimal("0")
    investing_inflow = Decimal("0")
    investing_outflow = Decimal("0")
    financing_inflow = Decimal("0")
    financing_outflow = Decimal("0")

    # 按 voucher_id 分组，识别同一凭证中的对方科目
    entries_by_voucher: dict[int, list[Any]] = {}
    for entry in entries:
        entries_by_voucher.setdefault(entry.voucher_id or 0, []).append(entry)

    for voucher_id, voucher_entries in entries_by_voucher.items():
        if not voucher_id:
            continue

        for entry in voucher_entries:
            if entry.account_code not in cash_account_codes:
                continue

            # 现金科目借方 = 现金流入；贷方 = 现金流出
            if entry.debit_amount and entry.debit_amount > 0:
                # 找到对方科目（贷方金额最大的非现金科目）
                counterparties = [
                    e for e in voucher_entries
                    if e.id != entry.id and e.account_code not in cash_account_codes and e.credit_amount and e.credit_amount > 0
                ]
                if not counterparties:
                    continue
                counterparty = max(counterparties, key=lambda e: e.credit_amount or Decimal("0"))
                flow_type = _classify_cash_flow_by_counterparty(counterparty.account_code)
                if flow_type == "operating":
                    operating_inflow += entry.debit_amount
                elif flow_type == "investing":
                    investing_inflow += entry.debit_amount
                else:
                    financing_inflow += entry.debit_amount

            elif entry.credit_amount and entry.credit_amount > 0:
                # 找到对方科目（借方金额最大的非现金科目）
                counterparties = [
                    e for e in voucher_entries
                    if e.id != entry.id and e.account_code not in cash_account_codes and e.debit_amount and e.debit_amount > 0
                ]
                if not counterparties:
                    continue
                counterparty = max(counterparties, key=lambda e: e.debit_amount or Decimal("0"))
                flow_type = _classify_cash_flow_by_counterparty(counterparty.account_code)
                if flow_type == "operating":
                    operating_outflow += entry.credit_amount
                elif flow_type == "investing":
                    investing_outflow += entry.credit_amount
                else:
                    financing_outflow += entry.credit_amount

    operating_net = operating_inflow - operating_outflow
    investing_net = investing_inflow - investing_outflow
    financing_net = financing_inflow - financing_outflow
    total_net = operating_net + investing_net + financing_net

    return {
        "operating_activities": {
            "inflow": str(operating_inflow.quantize(Decimal("0.00"))),
            "outflow": str(operating_outflow.quantize(Decimal("0.00"))),
            "net": str(operating_net.quantize(Decimal("0.00"))),
        },
        "investing_activities": {
            "inflow": str(investing_inflow.quantize(Decimal("0.00"))),
            "outflow": str(investing_outflow.quantize(Decimal("0.00"))),
            "net": str(investing_net.quantize(Decimal("0.00"))),
        },
        "financing_activities": {
            "inflow": str(financing_inflow.quantize(Decimal("0.00"))),
            "outflow": str(financing_outflow.quantize(Decimal("0.00"))),
            "net": str(financing_net.quantize(Decimal("0.00"))),
        },
        "net_increase_in_cash": str(total_net.quantize(Decimal("0.00"))),
    }
