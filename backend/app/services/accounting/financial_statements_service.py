"""三大财务报表计算服务：科目余额表、资产负债表、利润表。"""
from __future__ import annotations

from datetime import date
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
from app.services.accounting.reclassification_service import (
    build_reclassification_summary,
    classify_counterparty_balance,
)
from app.services.basic_data import coa_service

CLOSED_PERIOD_STATUSES = frozenset({"closed"})
PRESENTATION_MODE_BALANCE = "balance"
PRESENTATION_MODE_NET_MOVEMENT = "net_movement"
PRESENTATION_MODES = frozenset({PRESENTATION_MODE_BALANCE, PRESENTATION_MODE_NET_MOVEMENT})
CURRENT_YEAR_PROFIT_CODE = "4103"
CURRENT_YEAR_PROFIT_NAME = "本年利润"


def normalize_presentation_mode(mode: str | None) -> str:
    normalized = (mode or PRESENTATION_MODE_BALANCE).strip().lower()
    if normalized not in PRESENTATION_MODES:
        raise ValueError("presentation_mode 仅支持 balance 或 net_movement")
    return normalized


def resolve_as_of_date(period: AccountingPeriod, as_of_date: date | str | None = None) -> date:
    """解析报表截止日：开放期间默认到今天，已结账期间固定到期间末日。"""
    if period.status in CLOSED_PERIOD_STATUSES:
        return period.end_date
    if as_of_date is None:
        return min(date.today(), period.end_date)
    if isinstance(as_of_date, str):
        as_of_date = date.fromisoformat(as_of_date)
    if as_of_date < period.start_date:
        return period.start_date
    return min(as_of_date, period.end_date)


def _fiscal_year_start(period: AccountingPeriod) -> date:
    """自然年度口径：以期间截止日所在公历年 1 月 1 日为年初。"""
    return date(period.end_date.year, 1, 1)


def _trial_balance_row_keys() -> tuple[str, ...]:
    return (
        "account_code",
        "account_name",
        "category",
        "direction",
        "opening_debit",
        "opening_credit",
        "period_debit",
        "period_credit",
        "ytd_debit",
        "ytd_credit",
        "closing_debit",
        "closing_credit",
    )


def _trial_balance_row_has_activity(row: dict[str, Any]) -> bool:
    return any(
        Decimal(str(row.get(col, "0"))) != 0
        for col in (
            "opening_debit",
            "opening_credit",
            "period_debit",
            "period_credit",
            "ytd_debit",
            "ytd_credit",
            "closing_debit",
            "closing_credit",
        )
    )


def _sum_trial_balance_totals(rows: list[dict[str, Any]]) -> dict[str, str]:
    totals = {
        "opening_debit": Decimal("0.00"),
        "opening_credit": Decimal("0.00"),
        "period_debit": Decimal("0.00"),
        "period_credit": Decimal("0.00"),
        "ytd_debit": Decimal("0.00"),
        "ytd_credit": Decimal("0.00"),
        "closing_debit": Decimal("0.00"),
        "closing_credit": Decimal("0.00"),
    }
    for row in rows:
        for key in totals:
            totals[key] += Decimal(str(row.get(key, "0")))
    return {key: str(value.quantize(Decimal("0.00"))) for key, value in totals.items()}


def trial_balance_from_frozen_snapshots(
    db: Session,
    ledger_id: int,
    period_id: int,
) -> dict[str, Any]:
    """已结账期间：读取结账时固化的唯一科目余额表快照。"""
    from app.db.models import PeriodSnapshot

    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    if period.status not in CLOSED_PERIOD_STATUSES:
        raise ValueError("仅已结账期间可读取冻结科目余额表")

    snapshots = (
        db.query(PeriodSnapshot)
        .filter(
            PeriodSnapshot.period_id == period_id,
            PeriodSnapshot.dimension_type == "account",
            PeriodSnapshot.snapshot_status == "valid",
            PeriodSnapshot.snapshot_version == 1,
        )
        .order_by(PeriodSnapshot.dimension_code, PeriodSnapshot.id)
        .all()
    )
    if not snapshots:
        raise LookupError("该期间尚未固化科目余额表快照，请重新结账")

    rows: list[dict[str, Any]] = []
    for snapshot in snapshots:
        trial_row = (snapshot.source_scope or {}).get("trial_balance_row") or {}
        if not trial_row:
            continue
        rows.append({key: trial_row.get(key, "0.00") for key in _trial_balance_row_keys()})

    totals = _sum_trial_balance_totals(rows)
    return {
        "rows": rows,
        "totals": totals,
        "is_balanced": totals["closing_debit"] == totals["closing_credit"],
        "snapshot_frozen": True,
        "snapshot_version": 1,
        **_report_meta(period, period.end_date),
    }


def _report_meta(period: AccountingPeriod, as_of: date) -> dict[str, Any]:
    return {
        "period_id": period.id,
        "period_code": period.period_code,
        "period_status": period.status,
        "period_start_date": str(period.start_date),
        "period_end_date": str(period.end_date),
        "as_of_date": str(as_of),
        "balance_source": "snapshot" if period.status in CLOSED_PERIOD_STATUSES else "live",
    }


INCOME_ACCOUNTS = {
    "main_business_revenue": ["6001"],
    "other_business_revenue": ["6051"],
    "investment_income": ["6111"],
    "subsidy_income": ["6302"],
    "non_operating_income": ["6301"],
}
EXPENSE_ACCOUNTS = {
    "main_business_cost": ["6401"],
    "main_business_tax_surcharge": ["6403"],
    "other_business_cost": ["6402"],
    "selling_expenses": ["6601"],
    "admin_expenses": ["6602"],
    "financial_expenses": ["6603"],
    "asset_impairment_loss": ["6701"],
    "non_operating_expense": ["6711"],
    "income_tax_expense": ["6801"],
}


from app.services.accounting.coa_gap_mapping_service import rollup_amount_map_with_gap_mapping


def _rollup_amount_map(
    raw_map: dict[str, tuple[Decimal, Decimal]],
    coa_codes: set[str],
) -> tuple[dict[str, tuple[Decimal, Decimal]], Decimal, dict[str, Any]]:
    """按 COA 汇总借贷发生额，返回 rollup 结果、未能映射净额与映射元数据。"""
    rolled, orphan_net, meta = rollup_amount_map_with_gap_mapping(raw_map, coa_codes)
    return rolled, orphan_net, meta


def compute_account_balances(
    db: Session,
    ledger_id: int | None,
    period_id: int,
    as_of_date: date | str | None = None,
) -> list[dict[str, Any]]:
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    effective_ledger_id = ledger_id if ledger_id is not None else period.ledger_id
    if effective_ledger_id is not None and period.ledger_id is not None and period.ledger_id != effective_ledger_id:
        raise ValueError("会计期间不属于指定账簿")

    as_of = resolve_as_of_date(period, as_of_date)

    query = db.query(ChartOfAccounts)
    if effective_ledger_id is not None:
        query = query.filter(ChartOfAccounts.ledger_id == effective_ledger_id)
    else:
        query = query.filter(ChartOfAccounts.ledger_id.is_(None))
    accounts = query.order_by(ChartOfAccounts.code).all()
    coa_codes = {account.code for account in accounts}

    raw_opening_map = {
        ob.account_code: ob
        for ob in db.query(OpeningBalance)
        .filter(
            OpeningBalance.ledger_id == effective_ledger_id,
            OpeningBalance.period_id == period_id,
        )
        .all()
    }
    opening_rollup_input: dict[str, tuple[Decimal, Decimal]] = {}
    for code, ob in raw_opening_map.items():
        opening_rollup_input[code] = (
            Decimal(str(ob.debit_balance or 0)),
            Decimal(str(ob.credit_balance or 0)),
        )
    opening_map, _opening_orphan, _opening_meta = _rollup_amount_map(opening_rollup_input, coa_codes)
    rollup_meta: dict[str, Any] = {}

    effective_code_expr = func.coalesce(
        func.nullif(AccountingEntry.resolved_account_code, ""),
        AccountingEntry.account_code,
    )
    period_query = (
        db.query(
            effective_code_expr.label("effective_code"),
            func.sum(AccountingEntry.debit_amount).label("debit"),
            func.sum(AccountingEntry.credit_amount).label("credit"),
        )
        .filter(
            AccountingEntry.ledger_id == effective_ledger_id,
            AccountingEntry.voucher_date >= period.start_date,
            AccountingEntry.voucher_date <= as_of,
        )
        .group_by(effective_code_expr)
        .all()
    )
    raw_period_map = {
        str(row.effective_code): (Decimal(str(row.debit or 0)), Decimal(str(row.credit or 0)))
        for row in period_query
    }
    period_map, orphan_net, period_meta = _rollup_amount_map(raw_period_map, coa_codes)
    rollup_meta.update(period_meta)

    fiscal_year_start = _fiscal_year_start(period)
    ytd_query = (
        db.query(
            effective_code_expr.label("effective_code"),
            func.sum(AccountingEntry.debit_amount).label("debit"),
            func.sum(AccountingEntry.credit_amount).label("credit"),
        )
        .filter(
            AccountingEntry.ledger_id == effective_ledger_id,
            AccountingEntry.voucher_date >= fiscal_year_start,
            AccountingEntry.voucher_date <= as_of,
        )
        .group_by(effective_code_expr)
        .all()
    )
    raw_ytd_map = {
        str(row.effective_code): (Decimal(str(row.debit or 0)), Decimal(str(row.credit or 0)))
        for row in ytd_query
    }
    ytd_map, ytd_orphan_net, ytd_meta = _rollup_amount_map(raw_ytd_map, coa_codes)
    rollup_meta.update(ytd_meta)

    rows: list[dict[str, Any]] = []
    for account in accounts:
        opening_debit, opening_credit = opening_map.get(account.code, (Decimal("0"), Decimal("0")))
        period_debit, period_credit = period_map.get(account.code, (Decimal("0"), Decimal("0")))
        ytd_debit, ytd_credit = ytd_map.get(account.code, (Decimal("0"), Decimal("0")))

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
                "account_subcategory": account.account_subcategory,
                "balance_sheet_item": account.balance_sheet_item,
                "cash_flow_item": account.cash_flow_item,
                "opening_debit": str(opening_debit.quantize(Decimal("0.00"))),
                "opening_credit": str(opening_credit.quantize(Decimal("0.00"))),
                "period_debit": str(period_debit.quantize(Decimal("0.00"))),
                "period_credit": str(period_credit.quantize(Decimal("0.00"))),
                "ytd_debit": str(ytd_debit.quantize(Decimal("0.00"))),
                "ytd_credit": str(ytd_credit.quantize(Decimal("0.00"))),
                "closing_debit": str(closing_debit.quantize(Decimal("0.00"))),
                "closing_credit": str(closing_credit.quantize(Decimal("0.00"))),
            }
        )
    if rows:
        rows[0]["_rollup_meta"] = {
            "uses_resolved_account_code": True,
            "unmapped_entry_net": str(orphan_net.quantize(Decimal("0.00"))),
            "unmapped_ytd_entry_net": str(ytd_orphan_net.quantize(Decimal("0.00"))),
            "fiscal_year_start": str(fiscal_year_start),
            **rollup_meta,
        }
    return rows


def _code_matches_prefix(code: str, prefix: str) -> bool:
    """判断科目编码是否属于某汇总科目下级（含异构编码翻译后匹配）。"""
    from app.services.accounting.coa_gap_mapping_service import translate_legacy_code

    normalized = (code or "").strip().replace(".", "")
    root = (prefix or "").strip().replace(".", "")
    if not normalized or not root:
        return False
    if normalized == root or normalized.startswith(root):
        return True
    translated = translate_legacy_code(normalized)
    return translated == root or translated.startswith(root)


def _resolve_breakdown_direction(
    db: Session,
    ledger_id: int,
    account_prefix: str,
    category: str | None = None,
) -> tuple[str, str]:
    account = (
        db.query(ChartOfAccounts)
        .filter(ChartOfAccounts.ledger_id == ledger_id, ChartOfAccounts.code == account_prefix)
        .first()
    )
    if account:
        return account.category, account.direction
    if category:
        direction = "debit" if category == "asset" else "credit"
        return category, direction
    first = account_prefix[:1]
    if first == "1":
        return "asset", "debit"
    if first == "2":
        return "liability", "credit"
    if first in {"3", "4"}:
        return "equity", "credit"
    return "asset", "debit"


def account_balance_breakdown(
    db: Session,
    ledger_id: int,
    period_id: int,
    account_prefix: str,
    *,
    category: str | None = None,
    as_of_date: date | str | None = None,
    presentation_mode: str = PRESENTATION_MODE_BALANCE,
) -> dict[str, Any]:
    """按分录/期初明细编码汇总下级科目余额，供资产负债表 Treemap 下钻。"""
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    as_of = resolve_as_of_date(period, as_of_date)
    mode = normalize_presentation_mode(presentation_mode)
    prefix = (account_prefix or "").strip()
    if not prefix:
        raise ValueError("account_prefix 不能为空")

    resolved_category, direction = _resolve_breakdown_direction(db, ledger_id, prefix, category)

    if mode == PRESENTATION_MODE_NET_MOVEMENT and prefix == CURRENT_YEAR_PROFIT_CODE:
        ledger_rows = compute_account_balances(db, ledger_id, period_id, as_of_date=as_of)
        profit_rows: list[dict[str, Any]] = []
        for row in ledger_rows:
            if row.get("category") != "profit" or row.get("_rollup_meta"):
                continue
            net = _normal_period_net(row)
            if net == 0:
                continue
            closing_debit, closing_credit = _net_to_closing_sides(net, row["direction"])
            profit_rows.append(
                {
                    "account_code": row["account_code"],
                    "account_name": row["account_name"],
                    "category": "profit",
                    "direction": row["direction"],
                    "opening_debit": "0.00",
                    "opening_credit": "0.00",
                    "period_debit": row["period_debit"],
                    "period_credit": row["period_credit"],
                    "closing_debit": str(closing_debit.quantize(Decimal("0.00"))),
                    "closing_credit": str(closing_credit.quantize(Decimal("0.00"))),
                }
            )
        return {
            "account_prefix": prefix,
            "category": "equity",
            "presentation_mode": mode,
            "rows": sorted(profit_rows, key=lambda item: item["account_code"]),
            **_report_meta(period, as_of),
        }

    opening_rows = (
        db.query(OpeningBalance)
        .filter(
            OpeningBalance.ledger_id == ledger_id,
            OpeningBalance.period_id == period_id,
        )
        .all()
    )
    opening_map: dict[str, tuple[Decimal, Decimal]] = {}
    for ob in opening_rows:
        code = str(ob.account_code or "")
        if not _code_matches_prefix(code, prefix):
            continue
        prev = opening_map.get(code, (Decimal("0"), Decimal("0")))
        opening_map[code] = (
            prev[0] + Decimal(str(ob.debit_balance or 0)),
            prev[1] + Decimal(str(ob.credit_balance or 0)),
        )

    effective_code_expr = func.coalesce(
        func.nullif(AccountingEntry.resolved_account_code, ""),
        AccountingEntry.account_code,
    )
    entry_rows = (
        db.query(
            effective_code_expr.label("effective_code"),
            func.max(AccountingEntry.account_name).label("account_name"),
            func.sum(AccountingEntry.debit_amount).label("debit"),
            func.sum(AccountingEntry.credit_amount).label("credit"),
        )
        .filter(
            AccountingEntry.ledger_id == ledger_id,
            AccountingEntry.voucher_date >= period.start_date,
            AccountingEntry.voucher_date <= as_of,
        )
        .group_by(effective_code_expr)
        .all()
    )
    period_map: dict[str, tuple[Decimal, Decimal, str]] = {}
    for row in entry_rows:
        code = str(row.effective_code or "")
        if not _code_matches_prefix(code, prefix):
            continue
        prev = period_map.get(code, (Decimal("0"), Decimal("0"), ""))
        period_map[code] = (
            prev[0] + Decimal(str(row.debit or 0)),
            prev[1] + Decimal(str(row.credit or 0)),
            str(row.account_name or prev[2]),
        )

    all_codes = sorted(set(opening_map.keys()) | set(period_map.keys()))
    if not all_codes:
        all_codes = [prefix]

    rows: list[dict[str, Any]] = []
    for code in all_codes:
        opening_debit, opening_credit = opening_map.get(code, (Decimal("0"), Decimal("0")))
        period_debit, period_credit, account_name = period_map.get(
            code, (Decimal("0"), Decimal("0"), "")
        )
        row_direction = direction
        row_category = resolved_category
        account = coa_service.get_by_code(db, code, ledger_id=ledger_id)
        if account:
            row_direction = account.direction
            row_category = account.category

        if mode == PRESENTATION_MODE_NET_MOVEMENT:
            opening_debit = Decimal("0")
            opening_credit = Decimal("0")
            net = (
                period_debit - period_credit
                if row_direction == "debit"
                else period_credit - period_debit
            )
            closing_debit, closing_credit = _net_to_closing_sides(net, row_direction)
        else:
            if row_direction == "debit":
                net = (opening_debit - opening_credit) + (period_debit - period_credit)
                closing_debit = max(net, Decimal("0"))
                closing_credit = max(-net, Decimal("0"))
            else:
                net = (opening_credit - opening_debit) + (period_credit - period_debit)
                closing_credit = max(net, Decimal("0"))
                closing_debit = max(-net, Decimal("0"))

        rows.append(
            {
                "account_code": code,
                "account_name": account_name or code,
                "category": row_category,
                "direction": row_direction,
                "opening_debit": str(opening_debit.quantize(Decimal("0.00"))),
                "opening_credit": str(opening_credit.quantize(Decimal("0.00"))),
                "period_debit": str(period_debit.quantize(Decimal("0.00"))),
                "period_credit": str(period_credit.quantize(Decimal("0.00"))),
                "closing_debit": str(closing_debit.quantize(Decimal("0.00"))),
                "closing_credit": str(closing_credit.quantize(Decimal("0.00"))),
            }
        )

    return {
        "account_prefix": prefix,
        "category": resolved_category,
        "presentation_mode": mode,
        "rows": rows,
        **_report_meta(period, as_of),
    }


def _strip_rollup_meta(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if rows and "_rollup_meta" in rows[0]:
        return rows[0].pop("_rollup_meta", {})
    return {}


def trial_balance_report(
    db: Session,
    ledger_id: int,
    period_id: int,
    as_of_date: date | str | None = None,
) -> dict[str, Any]:
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    if period.status in CLOSED_PERIOD_STATUSES:
        return trial_balance_from_frozen_snapshots(db, ledger_id, period_id)

    as_of = resolve_as_of_date(period, as_of_date)
    rows = compute_account_balances(db, ledger_id, period_id, as_of_date=as_of)
    rollup_meta = _strip_rollup_meta(rows)
    totals = _sum_trial_balance_totals(rows)
    return {
        "rows": rows,
        "totals": totals,
        "is_balanced": totals["closing_debit"] == totals["closing_credit"],
        **rollup_meta,
        **_report_meta(period, as_of),
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


def _normal_period_net(row: dict[str, Any]) -> Decimal:
    """本期净发生额：借贷同有发生时按科目余额方向取净额。"""
    if row["direction"] == "debit":
        return Decimal(str(row["period_debit"])) - Decimal(str(row["period_credit"]))
    return Decimal(str(row["period_credit"])) - Decimal(str(row["period_debit"]))


def _net_to_closing_sides(net: Decimal, direction: str) -> tuple[Decimal, Decimal]:
    if direction == "debit":
        return max(net, Decimal("0")), max(-net, Decimal("0"))
    return max(-net, Decimal("0")), max(net, Decimal("0"))


def _apply_net_movement_presentation(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    净发生额视图：
    - 资产负债权益按本期净发生额展示（期初清零）；
    - 损益类科目发生额汇总进 4103 本年利润，不在图中单独列示。
    """
    profit_rollup = Decimal("0")
    presented: list[dict[str, Any]] = []
    profit_row: dict[str, Any] | None = None

    for row in rows:
        if row["category"] == "profit":
            profit_rollup += Decimal(str(row["period_credit"])) - Decimal(str(row["period_debit"]))
            continue
        if row["category"] not in ("asset", "liability", "equity"):
            continue

        net = _normal_period_net(row)
        closing_debit, closing_credit = _net_to_closing_sides(net, row["direction"])
        item = dict(row)
        item["opening_debit"] = "0.00"
        item["opening_credit"] = "0.00"
        item["closing_debit"] = str(closing_debit.quantize(Decimal("0.00")))
        item["closing_credit"] = str(closing_credit.quantize(Decimal("0.00")))

        if row["account_code"] == CURRENT_YEAR_PROFIT_CODE:
            profit_row = item
        else:
            presented.append(item)

    if profit_row is not None:
        total_net = _normal_period_net(profit_row) + profit_rollup
        cd, cc = _net_to_closing_sides(total_net, profit_row["direction"])
        profit_row["closing_debit"] = str(cd.quantize(Decimal("0.00")))
        profit_row["closing_credit"] = str(cc.quantize(Decimal("0.00")))
        presented.append(profit_row)
    elif profit_rollup != 0:
        cd, cc = _net_to_closing_sides(profit_rollup, "credit")
        presented.append(
            {
                "account_code": CURRENT_YEAR_PROFIT_CODE,
                "account_name": CURRENT_YEAR_PROFIT_NAME,
                "category": "equity",
                "direction": "credit",
                "opening_debit": "0.00",
                "opening_credit": "0.00",
                "period_debit": "0.00",
                "period_credit": str(profit_rollup.quantize(Decimal("0.00"))) if profit_rollup > 0 else "0.00",
                "closing_debit": str(cd.quantize(Decimal("0.00"))),
                "closing_credit": str(cc.quantize(Decimal("0.00"))),
            }
        )

    presented.sort(key=lambda item: item["account_code"])
    return presented


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
                "standard_basis": result.get("standard_basis"),
                "standard_reference": result.get("standard_reference"),
                "audit_assertion_risks": result.get("audit_assertion_risks", []),
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


def _build_balance_sheet_payload(
    db: Session,
    ledger_id: int,
    period_id: int,
    as_of_date: date | str | None = None,
    presentation_mode: str = PRESENTATION_MODE_BALANCE,
) -> dict[str, Any]:
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    as_of = resolve_as_of_date(period, as_of_date)
    mode = normalize_presentation_mode(presentation_mode)
    rows = compute_account_balances(db, ledger_id, period_id, as_of_date=as_of)
    rollup_meta = _strip_rollup_meta(rows)
    presentation_rows, reclassification_adjustments = _apply_counterparty_reclassification(rows)
    if mode == PRESENTATION_MODE_NET_MOVEMENT:
        presentation_rows = _apply_net_movement_presentation(presentation_rows)
        presentation_rows, movement_reclass = _apply_counterparty_reclassification(presentation_rows)
        reclassification_adjustments.extend(movement_reclass)
    assets_total = _category_total(presentation_rows, "asset")
    liabilities_total = _category_total(presentation_rows, "liability")
    equity_total = _category_total(presentation_rows, "equity")

    coa_bs_items = {
        str(r.get("account_code")): r.get("balance_sheet_item")
        for r in presentation_rows
        if r.get("balance_sheet_item")
    }
    from app.services.accounting.balance_sheet_presentation_service import build_balance_sheet_statement_lines

    statement_lines = build_balance_sheet_statement_lines(presentation_rows, coa_bs_items=coa_bs_items)
    from app.services.accounting.classic_report_layout_service import build_classic_dual_column_balance_sheet

    classic_layout = build_classic_dual_column_balance_sheet(statement_lines)
    assets_line_total = next((l for l in statement_lines if l["line_code"] == "assets_total"), None)
    le_line_total = next((l for l in statement_lines if l["line_code"] == "liabilities_and_equity_total"), None)

    return {
        "statement_lines": statement_lines,
        "classic_dual_column": classic_layout,
        "format": "classic_dual_column",
        "statement_balanced": (
            assets_line_total is not None
            and le_line_total is not None
            and assets_line_total["closing_balance"] == le_line_total["closing_balance"]
        ) if assets_line_total and le_line_total else False,
        "assets": [r for r in presentation_rows if r["category"] == "asset"],
        "liabilities": [r for r in presentation_rows if r["category"] == "liability"],
        "equity": [r for r in presentation_rows if r["category"] == "equity"],
        "assets_total": str(assets_total.quantize(Decimal("0.00"))),
        "liabilities_total": str(liabilities_total.quantize(Decimal("0.00"))),
        "equity_total": str(equity_total.quantize(Decimal("0.00"))),
        "reclassification_adjustments": reclassification_adjustments,
        "reclassification_summary": build_reclassification_summary(reclassification_adjustments),
        "presentation_mode": mode,
        "is_balanced": assets_total == liabilities_total + equity_total,
        **rollup_meta,
        **_report_meta(period, as_of),
    }


def balance_sheet(
    db: Session,
    ledger_id: int,
    period_id: int,
    as_of_date: date | str | None = None,
    presentation_mode: str = PRESENTATION_MODE_BALANCE,
) -> dict[str, Any]:
    from app.services.accounting.period_pl_health_service import audit_period_pl_status

    payload = _build_balance_sheet_payload(
        db, ledger_id, period_id, as_of_date=as_of_date, presentation_mode=presentation_mode
    )
    payload["pl_transfer_health"] = audit_period_pl_status(db, ledger_id, period_id)
    return payload


def _compute_profit_account_amounts(
    db: Session,
    ledger_id: int,
    period_id: int,
    *,
    date_from: date,
    date_to: date,
) -> dict[str, tuple[Decimal, Decimal]]:
    """统计利润表科目在指定日期区间内的借贷发生额（排除损益结转凭证）。"""
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
            AccountingEntry.voucher_date >= date_from,
            AccountingEntry.voucher_date <= date_to,
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


def _compute_profit_account_period_amounts(
    db: Session, ledger_id: int, period_id: int
) -> dict[str, tuple[Decimal, Decimal]]:
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")
    return _compute_profit_account_amounts(
        db, ledger_id, period_id, date_from=period.start_date, date_to=period.end_date
    )


def income_statement(
    db: Session,
    ledger_id: int,
    period_id: int,
    as_of_date: date | str | None = None,
) -> dict[str, Any]:
    """
    生成利润表。

    业务逻辑：
        利润表反映本期经营成果，统计口径为“本期真实发生额”，需排除
        损益结转凭证（source_type=period_close）对收入、成本费用的冲抵。
    """
    profit_amounts = _compute_profit_account_period_amounts(db, ledger_id, period_id)
    period = db.get(AccountingPeriod, period_id)
    as_of = resolve_as_of_date(period, as_of_date) if period else period.end_date
    ytd_amounts = _compute_profit_account_amounts(
        db, ledger_id, period_id, date_from=_fiscal_year_start(period), date_to=as_of
    ) if period else {}

    def _profit_sum(amounts: dict[str, tuple[Decimal, Decimal]], codes: list[str], side: str) -> Decimal:
        total = Decimal("0")
        for code in codes:
            debit, credit = amounts.get(code, (Decimal("0"), Decimal("0")))
            if side == "credit":
                total += credit - debit
            else:
                total += debit - credit
        return total

    def _profit_sum_period(codes: list[str], side: str) -> Decimal:
        return _profit_sum(profit_amounts, codes, side)

    def _profit_sum_ytd(codes: list[str], side: str) -> Decimal:
        return _profit_sum(ytd_amounts, codes, side)

    revenue = {k: str(_profit_sum_period(codes, "credit").quantize(Decimal("0.00"))) for k, codes in INCOME_ACCOUNTS.items()}
    expense = {k: str(_profit_sum_period(codes, "debit").quantize(Decimal("0.00"))) for k, codes in EXPENSE_ACCOUNTS.items()}
    ytd_revenue = {k: str(_profit_sum_ytd(codes, "credit").quantize(Decimal("0.00"))) for k, codes in INCOME_ACCOUNTS.items()}
    ytd_expense = {k: str(_profit_sum_ytd(codes, "debit").quantize(Decimal("0.00"))) for k, codes in EXPENSE_ACCOUNTS.items()}

    operating_revenue = _profit_sum_period(
        INCOME_ACCOUNTS["main_business_revenue"] + INCOME_ACCOUNTS["other_business_revenue"], "credit"
    )
    operating_cost = _profit_sum_period(
        EXPENSE_ACCOUNTS["main_business_cost"] + EXPENSE_ACCOUNTS["other_business_cost"], "debit"
    )
    period_expenses = (
        _profit_sum_period(EXPENSE_ACCOUNTS["selling_expenses"], "debit")
        + _profit_sum_period(EXPENSE_ACCOUNTS["admin_expenses"], "debit")
        + _profit_sum_period(EXPENSE_ACCOUNTS["financial_expenses"], "debit")
        + _profit_sum_period(EXPENSE_ACCOUNTS["asset_impairment_loss"], "debit")
    )
    investment_income = _profit_sum_period(INCOME_ACCOUNTS["investment_income"], "credit")
    non_operating_income = _profit_sum_period(INCOME_ACCOUNTS["non_operating_income"], "credit")
    non_operating_expense = _profit_sum_period(EXPENSE_ACCOUNTS["non_operating_expense"], "debit")
    income_tax_expense = _profit_sum_period(EXPENSE_ACCOUNTS["income_tax_expense"], "debit")

    operating_profit = operating_revenue - operating_cost - period_expenses + investment_income
    total_profit = operating_profit + non_operating_income - non_operating_expense
    net_profit = total_profit - income_tax_expense

    ytd_operating_revenue = _profit_sum_ytd(
        INCOME_ACCOUNTS["main_business_revenue"] + INCOME_ACCOUNTS["other_business_revenue"], "credit"
    )
    ytd_operating_cost = _profit_sum_ytd(
        EXPENSE_ACCOUNTS["main_business_cost"] + EXPENSE_ACCOUNTS["other_business_cost"], "debit"
    )
    ytd_period_expenses = (
        _profit_sum_ytd(EXPENSE_ACCOUNTS["selling_expenses"], "debit")
        + _profit_sum_ytd(EXPENSE_ACCOUNTS["admin_expenses"], "debit")
        + _profit_sum_ytd(EXPENSE_ACCOUNTS["financial_expenses"], "debit")
        + _profit_sum_ytd(EXPENSE_ACCOUNTS["asset_impairment_loss"], "debit")
    )
    ytd_investment_income = _profit_sum_ytd(INCOME_ACCOUNTS["investment_income"], "credit")
    ytd_non_operating_income = _profit_sum_ytd(INCOME_ACCOUNTS["non_operating_income"], "credit")
    ytd_non_operating_expense = _profit_sum_ytd(EXPENSE_ACCOUNTS["non_operating_expense"], "debit")
    ytd_income_tax = _profit_sum_ytd(EXPENSE_ACCOUNTS["income_tax_expense"], "debit")
    ytd_operating_profit = ytd_operating_revenue - ytd_operating_cost - ytd_period_expenses + ytd_investment_income
    ytd_total_profit = ytd_operating_profit + ytd_non_operating_income - ytd_non_operating_expense
    ytd_net_profit = ytd_total_profit - ytd_income_tax

    from app.services.accounting.classic_report_layout_service import build_classic_income_statement_lines

    classic_lines = build_classic_income_statement_lines(
        profit_amounts,
        ytd_amounts,
        income_accounts=INCOME_ACCOUNTS,
        expense_accounts=EXPENSE_ACCOUNTS,
    )

    period_meta = _report_meta(period, as_of) if period else {}
    return {
        **period_meta,
        "format": "classic_income_statement",
        "report_title": "损益表",
        "revenue": revenue,
        "expense": expense,
        "ytd_revenue": ytd_revenue,
        "ytd_expense": ytd_expense,
        "statement_lines": classic_lines,
        "operating_revenue": str(operating_revenue.quantize(Decimal("0.00"))),
        "operating_cost": str(operating_cost.quantize(Decimal("0.00"))),
        "period_expenses": str(period_expenses.quantize(Decimal("0.00"))),
        "operating_profit": str(operating_profit.quantize(Decimal("0.00"))),
        "total_profit": str(total_profit.quantize(Decimal("0.00"))),
        "income_tax": str(income_tax_expense.quantize(Decimal("0.00"))),
        "net_profit": str(net_profit.quantize(Decimal("0.00"))),
        "ytd_operating_profit": str(ytd_operating_profit.quantize(Decimal("0.00"))),
        "ytd_total_profit": str(ytd_total_profit.quantize(Decimal("0.00"))),
        "ytd_income_tax": str(ytd_income_tax.quantize(Decimal("0.00"))),
        "ytd_net_profit": str(ytd_net_profit.quantize(Decimal("0.00"))),
    }


# 现金流量表：列报规则见 cash_flow_presentation_service
CASH_EQUIVALENT_ACCOUNT_PREFIXES = ("1001", "1002", "1012", "1003")


def _is_cash_equivalent_code(code: str) -> bool:
    return any(code == p or code.startswith(p) for p in CASH_EQUIVALENT_ACCOUNT_PREFIXES)


def cash_flow_statement(
    db: Session,
    ledger_id: int,
    period_id: int,
    as_of_date: date | str | None = None,
) -> dict[str, Any]:
    """
    现金流量表：直接法分项列报 + 间接法净利润调节。

    编制规则：
        1. 直接法：解析现金科目（1001/1002/1012）收付，按对方科目/ cash_flow_item 归入分项。
        2. 收入直接进银行（借银行贷收入）与应收后回款（借银行贷应收）均归入「销售收现」。
        3. 内部现金划转（现金↔银行）剔除，不计入三大活动。
        4. 间接法：净利润 + 折旧摊销 + 存货/经营性应收应付变动，与直接法经营活动净额勾稽。
    """
    from app.services.accounting.cash_flow_presentation_service import (
        build_compilation_notes,
        build_direct_method_lines,
        build_indirect_method_lines,
    )

    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise LookupError("会计期间不存在")

    effective_ledger_id = ledger_id if ledger_id is not None else period.ledger_id
    if effective_ledger_id is not None and period.ledger_id is not None and period.ledger_id != effective_ledger_id:
        raise ValueError("会计期间不属于指定账簿")

    as_of = resolve_as_of_date(period, as_of_date)

    coa_rows = (
        db.query(ChartOfAccounts)
        .filter(ChartOfAccounts.ledger_id == effective_ledger_id)
        .all()
    )
    coa_cf_items = {str(a.code): getattr(a, "cash_flow_item", None) for a in coa_rows}

    entries = (
        db.query(AccountingEntry)
        .filter(
            AccountingEntry.ledger_id == effective_ledger_id,
            AccountingEntry.voucher_date >= period.start_date,
            AccountingEntry.voucher_date <= as_of,
            AccountingEntry.post_status == "posted",
        )
        .all()
    )

    entries_by_voucher: dict[int, list[Any]] = {}
    for entry in entries:
        if entry.voucher_id:
            entries_by_voucher.setdefault(entry.voucher_id, []).append(entry)

    statement_lines, totals, flags = build_direct_method_lines(
        entries_by_voucher,
        coa_cf_items=coa_cf_items,
    )

    prior_period = (
        db.query(AccountingPeriod)
        .filter(
            AccountingPeriod.ledger_id == effective_ledger_id,
            AccountingPeriod.end_date < period.start_date,
        )
        .order_by(AccountingPeriod.end_date.desc())
        .first()
    )
    prior_statement_lines: list[dict[str, Any]] = []
    if prior_period:
        prior_entries = (
            db.query(AccountingEntry)
            .filter(
                AccountingEntry.ledger_id == effective_ledger_id,
                AccountingEntry.voucher_date >= prior_period.start_date,
                AccountingEntry.voucher_date <= prior_period.end_date,
                AccountingEntry.post_status == "posted",
            )
            .all()
        )
        prior_groups: dict[int, list[Any]] = {}
        for entry in prior_entries:
            if entry.voucher_id:
                prior_groups.setdefault(entry.voucher_id, []).append(entry)
        prior_statement_lines, _, _ = build_direct_method_lines(prior_groups, coa_cf_items=coa_cf_items)

    from app.services.accounting.classic_report_layout_service import build_classic_cash_flow_lines

    classic_statement_lines = build_classic_cash_flow_lines(statement_lines, prior_statement_lines)

    balance_rows = compute_account_balances(db, effective_ledger_id, period_id, as_of_date=as_of)
    is_report = income_statement(db, effective_ledger_id, period_id, as_of_date=as_of)
    net_profit = Decimal(str(is_report.get("net_profit") or 0))

    indirect_lines = build_indirect_method_lines(
        net_profit,
        balance_rows,
        totals.get("operating_net", Decimal("0")),
    )
    indirect_operating = next(
        (l for l in indirect_lines if l.get("line_code") == "operating_net_indirect"),
        {},
    )
    direct_indirect_reconciled = bool(indirect_operating.get("reconciled_with_direct", False))

    operating_net = totals.get("operating_net", Decimal("0"))
    investing_net = totals.get("investing_net", Decimal("0"))
    financing_net = totals.get("financing_net", Decimal("0"))
    total_net = totals.get("net_increase_in_cash", operating_net + investing_net + financing_net)

    op_in = totals.get("operating_inflow_subtotal", Decimal("0"))
    op_out = totals.get("operating_outflow_subtotal", Decimal("0"))
    inv_in = totals.get("investing_inflow_subtotal", Decimal("0"))
    inv_out = totals.get("investing_outflow_subtotal", Decimal("0"))
    fin_in = totals.get("financing_inflow_subtotal", Decimal("0"))
    fin_out = totals.get("financing_outflow_subtotal", Decimal("0"))

    return {
        "method": "direct",
        "format": "classic_cash_flow",
        "report_title": "现金流量表",
        "statement_lines": classic_statement_lines,
        "direct_statement_lines": statement_lines,
        "indirect_lines": indirect_lines,
        "direct_indirect_reconciled": direct_indirect_reconciled,
        "compilation_notes": build_compilation_notes(flags),
        "pattern_flags": {
            "direct_revenue_to_bank": flags.get("direct_revenue_to_bank", False),
            "receivable_collection": flags.get("receivable_collection", False),
        },
        "operating_activities": {
            "inflow": str(op_in.quantize(Decimal("0.00"))),
            "outflow": str(op_out.quantize(Decimal("0.00"))),
            "net": str(operating_net.quantize(Decimal("0.00"))),
        },
        "investing_activities": {
            "inflow": str(inv_in.quantize(Decimal("0.00"))),
            "outflow": str(inv_out.quantize(Decimal("0.00"))),
            "net": str(investing_net.quantize(Decimal("0.00"))),
        },
        "financing_activities": {
            "inflow": str(fin_in.quantize(Decimal("0.00"))),
            "outflow": str(fin_out.quantize(Decimal("0.00"))),
            "net": str(financing_net.quantize(Decimal("0.00"))),
        },
        "net_increase_in_cash": str(total_net.quantize(Decimal("0.00"))),
        **_report_meta(period, as_of),
    }
