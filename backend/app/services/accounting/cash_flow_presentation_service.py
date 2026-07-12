"""现金流量表标准列报：直接法分项 + 间接法调节，支持科目 cash_flow_item 扩展。"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

# 可在科目表 cash_flow_item 字段中引用
CF_ITEM_OPTIONS: dict[str, str] = {
    "sales_cash_received": "销售商品、提供劳务收到的现金",
    "tax_refund_received": "收到的税费返还",
    "other_operating_inflow": "收到其他与经营活动有关的现金",
    "goods_services_cash_paid": "购买商品、接受劳务支付的现金",
    "employee_cash_paid": "支付给职工以及为职工支付的现金",
    "tax_cash_paid": "支付的各项税费",
    "other_operating_outflow": "支付其他与经营活动有关的现金",
    "investment_recovery_cash": "收回投资收到的现金",
    "investment_income_cash": "取得投资收益收到的现金",
    "asset_disposal_cash": "处置固定资产、无形资产和其他长期资产收回的现金净额",
    "asset_acquisition_cash": "购建固定资产、无形资产和其他长期资产支付的现金",
    "investment_cash_paid": "投资支付的现金",
    "other_investing_inflow": "收到其他与投资活动有关的现金",
    "other_investing_outflow": "支付其他与投资活动有关的现金",
    "equity_cash_received": "吸收投资收到的现金",
    "borrowing_cash_received": "取得借款收到的现金",
    "debt_repayment_cash": "偿还债务支付的现金",
    "dividend_interest_cash_paid": "分配股利、利润或偿付利息支付的现金",
    "other_financing_inflow": "收到其他与筹资活动有关的现金",
    "other_financing_outflow": "支付其他与筹资活动有关的现金",
}

CASH_ACCOUNT_PREFIXES = ("1001", "1002", "1012", "1003")

# 经营性应收 / 应付（间接法营运资本调节）
OPERATING_RECEIVABLE_PREFIXES = ("1121", "1122", "1123", "1221")
OPERATING_PAYABLE_PREFIXES = ("2201", "2202", "2203", "2211", "2221", "2241")
INVENTORY_PREFIXES = ("1401", "1403", "1405", "1411")
DEPRECIATION_PREFIXES = ("1602", "1702", "1801")

REVENUE_PREFIXES = ("60", "61", "62", "63")
COST_PREFIXES = ("64", "65")
EXPENSE_PREFIXES = ("66", "67", "68")


@dataclass
class CfLineDef:
    code: str
    line_no: int
    label: str
    activity: str  # operating | investing | financing | summary
    direction: str  # inflow | outflow | subtotal | header | net
    add_prefixes: tuple[str, ...] = ()
    subtract_prefixes: tuple[str, ...] = ()
    is_subtotal: bool = False
    is_header: bool = False
    is_catch_all: bool = False
    catch_activity: str | None = None
    catch_direction: str | None = None


DIRECT_LINE_DEFINITIONS: list[CfLineDef] = [
    CfLineDef("operating_header", 0, "一、经营活动产生的现金流量", "operating", "header", is_header=True),
    CfLineDef("sales_cash_received", 1, "销售商品、提供劳务收到的现金", "operating", "inflow",
              add_prefixes=REVENUE_PREFIXES + OPERATING_RECEIVABLE_PREFIXES),
    CfLineDef("tax_refund_received", 2, "收到的税费返还", "operating", "inflow", add_prefixes=("2221",)),
    CfLineDef("other_operating_inflow", 3, "收到其他与经营活动有关的现金", "operating", "inflow",
              is_catch_all=True, catch_activity="operating", catch_direction="inflow"),
    CfLineDef("operating_inflow_subtotal", 4, "经营活动现金流入小计", "operating", "subtotal", is_subtotal=True),
    CfLineDef("goods_services_cash_paid", 5, "购买商品、接受劳务支付的现金", "operating", "outflow",
              add_prefixes=COST_PREFIXES + INVENTORY_PREFIXES + ("2202",)),
    CfLineDef("employee_cash_paid", 6, "支付给职工以及为职工支付的现金", "operating", "outflow", add_prefixes=("2211",)),
    CfLineDef("tax_cash_paid", 7, "支付的各项税费", "operating", "outflow", add_prefixes=("2221",)),
    CfLineDef("other_operating_outflow", 8, "支付其他与经营活动有关的现金", "operating", "outflow",
              add_prefixes=EXPENSE_PREFIXES + ("2241",),
              is_catch_all=True, catch_activity="operating", catch_direction="outflow"),
    CfLineDef("operating_outflow_subtotal", 9, "经营活动现金流出小计", "operating", "subtotal", is_subtotal=True),
    CfLineDef("operating_net", 10, "经营活动产生的现金流量净额", "operating", "net", is_subtotal=True),
    CfLineDef("investing_header", 20, "二、投资活动产生的现金流量", "investing", "header", is_header=True),
    CfLineDef("investment_recovery_cash", 21, "收回投资收到的现金", "investing", "inflow", add_prefixes=("1511", "1521")),
    CfLineDef("investment_income_cash", 22, "取得投资收益收到的现金", "investing", "inflow", add_prefixes=("6111",)),
    CfLineDef("asset_disposal_cash", 23, "处置固定资产、无形资产和其他长期资产收回的现金净额", "investing", "inflow",
              add_prefixes=("1601", "1701", "1801")),
    CfLineDef("other_investing_inflow", 24, "收到其他与投资活动有关的现金", "investing", "inflow",
              is_catch_all=True, catch_activity="investing", catch_direction="inflow"),
    CfLineDef("investing_inflow_subtotal", 25, "投资活动现金流入小计", "investing", "subtotal", is_subtotal=True),
    CfLineDef("asset_acquisition_cash", 26, "购建固定资产、无形资产和其他长期资产支付的现金", "investing", "outflow",
              add_prefixes=("1601", "1701", "1801")),
    CfLineDef("investment_cash_paid", 27, "投资支付的现金", "investing", "outflow", add_prefixes=("1511", "1521")),
    CfLineDef("other_investing_outflow", 28, "支付其他与投资活动有关的现金", "investing", "outflow",
              is_catch_all=True, catch_activity="investing", catch_direction="outflow"),
    CfLineDef("investing_outflow_subtotal", 29, "投资活动现金流出小计", "investing", "subtotal", is_subtotal=True),
    CfLineDef("investing_net", 30, "投资活动产生的现金流量净额", "investing", "net", is_subtotal=True),
    CfLineDef("financing_header", 40, "三、筹资活动产生的现金流量", "financing", "header", is_header=True),
    CfLineDef("equity_cash_received", 41, "吸收投资收到的现金", "financing", "inflow", add_prefixes=("40",)),
    CfLineDef("borrowing_cash_received", 42, "取得借款收到的现金", "financing", "inflow", add_prefixes=("2001", "2501")),
    CfLineDef("other_financing_inflow", 43, "收到其他与筹资活动有关的现金", "financing", "inflow",
              is_catch_all=True, catch_activity="financing", catch_direction="inflow"),
    CfLineDef("financing_inflow_subtotal", 44, "筹资活动现金流入小计", "financing", "subtotal", is_subtotal=True),
    CfLineDef("debt_repayment_cash", 45, "偿还债务支付的现金", "financing", "outflow", add_prefixes=("2001", "2501")),
    CfLineDef("dividend_interest_cash_paid", 46, "分配股利、利润或偿付利息支付的现金", "financing", "outflow",
              add_prefixes=("4103", "4104", "2231")),
    CfLineDef("other_financing_outflow", 47, "支付其他与筹资活动有关的现金", "financing", "outflow",
              is_catch_all=True, catch_activity="financing", catch_direction="outflow"),
    CfLineDef("financing_outflow_subtotal", 48, "筹资活动现金流出小计", "financing", "subtotal", is_subtotal=True),
    CfLineDef("financing_net", 49, "筹资活动产生的现金流量净额", "financing", "net", is_subtotal=True),
    CfLineDef("net_increase_in_cash", 50, "四、现金及现金等价物净增加额", "summary", "net", is_subtotal=True),
]

DEFAULT_CODE_TO_CF_ITEM: dict[str, str] = {}
for _line in DIRECT_LINE_DEFINITIONS:
    if not _line.is_header and not _line.is_subtotal and not _line.is_catch_all:
        for _pfx in _line.add_prefixes:
            if _pfx not in DEFAULT_CODE_TO_CF_ITEM:
                DEFAULT_CODE_TO_CF_ITEM[_pfx] = _line.code


def _matches_prefix(code: str, prefixes: tuple[str, ...]) -> bool:
    return any(code == p or code.startswith(p) for p in prefixes)


def is_cash_account(code: str) -> bool:
    return _matches_prefix(code, CASH_ACCOUNT_PREFIXES)


def _resolve_cf_item(counterparty_code: str, explicit: str | None, cash_direction: str) -> str | None:
    """cash_direction: inflow | outflow"""
    if explicit and explicit in CF_ITEM_OPTIONS:
        line = next((l for l in DIRECT_LINE_DEFINITIONS if l.code == explicit), None)
        if line and not line.is_header and not line.is_subtotal:
            if line.direction == cash_direction or line.is_catch_all:
                return explicit
    code = counterparty_code or ""
    for line in DIRECT_LINE_DEFINITIONS:
        if line.is_header or line.is_subtotal or line.is_catch_all:
            continue
        if line.direction != cash_direction:
            continue
        if _matches_prefix(code, line.add_prefixes) and not _matches_prefix(code, line.subtract_prefixes):
            return line.code
    catch = next(
        (
            l
            for l in DIRECT_LINE_DEFINITIONS
            if l.is_catch_all and l.catch_activity and l.catch_direction == cash_direction
        ),
        None,
    )
    if catch:
        activity = _infer_activity(code)
        if activity == catch.catch_activity:
            return catch.code
    return None


def _infer_activity(code: str) -> str:
    if _matches_prefix(code, ("15", "16", "17", "18")):
        return "investing"
    if _matches_prefix(code, ("20", "21", "25", "40", "41", "42")):
        return "financing"
    return "operating"


def _row_net_balance(row: dict[str, Any]) -> Decimal:
    cat = str(row.get("category") or "")
    debit = Decimal(str(row.get("closing_debit") or 0))
    credit = Decimal(str(row.get("closing_credit") or 0))
    if cat in {"liability", "equity"}:
        return credit - debit
    return debit - credit


def _row_opening_net(row: dict[str, Any]) -> Decimal:
    cat = str(row.get("category") or "")
    debit = Decimal(str(row.get("opening_debit") or 0))
    credit = Decimal(str(row.get("opening_credit") or 0))
    if cat in {"liability", "equity"}:
        return credit - debit
    return debit - credit


def classify_voucher_cash_movements(
    voucher_entries: list[Any],
    *,
    coa_cf_items: dict[str, str | None] | None = None,
) -> tuple[dict[str, Decimal], dict[str, Any]]:
    """
    解析单张凭证中的现金收付，返回 line_code -> amount 及模式标记。
    支持：收入直接进银行、先挂应收后回款、经营性往来等常见路径。
    """
    coa_map = coa_cf_items or {}
    line_amounts: dict[str, Decimal] = {line.code: Decimal("0") for line in DIRECT_LINE_DEFINITIONS}
    flags: dict[str, Any] = {
        "direct_revenue_to_bank": False,
        "receivable_collection": False,
        "internal_transfer_skipped": Decimal("0"),
    }

    cash_entries = [e for e in voucher_entries if is_cash_account(str(e.account_code or ""))]
    non_cash = [e for e in voucher_entries if not is_cash_account(str(e.account_code or ""))]
    if not cash_entries:
        return line_amounts, flags

    if not non_cash and len(cash_entries) >= 2:
        flags["internal_transfer_skipped"] += sum(
            Decimal(str(e.debit_amount or 0)) + Decimal(str(e.credit_amount or 0))
            for e in cash_entries
        ) / 2
        return line_amounts, flags

    for cash_e in cash_entries:
        cash_in = Decimal(str(cash_e.debit_amount or 0))
        cash_out = Decimal(str(cash_e.credit_amount or 0))
        if cash_in > 0:
            counterparts = [
                e for e in non_cash
                if Decimal(str(e.credit_amount or 0)) > 0
            ]
            if not counterparts:
                if all(is_cash_account(str(e.account_code or "")) for e in voucher_entries):
                    flags["internal_transfer_skipped"] += cash_in
                continue
            total_cp = sum(Decimal(str(e.credit_amount or 0)) for e in counterparts)
            for cp in counterparts:
                cp_amt = Decimal(str(cp.credit_amount or 0))
                alloc = cash_in * cp_amt / total_cp if total_cp else Decimal("0")
                cp_code = str(cp.account_code or "")
                if _matches_prefix(cp_code, REVENUE_PREFIXES):
                    flags["direct_revenue_to_bank"] = True
                if _matches_prefix(cp_code, OPERATING_RECEIVABLE_PREFIXES):
                    flags["receivable_collection"] = True
                item = _resolve_cf_item(cp_code, coa_map.get(cp_code), "inflow")
                if item:
                    line_amounts[item] += alloc
        elif cash_out > 0:
            counterparts = [
                e for e in non_cash
                if Decimal(str(e.debit_amount or 0)) > 0
            ]
            if not counterparts:
                if all(is_cash_account(str(e.account_code or "")) for e in voucher_entries):
                    flags["internal_transfer_skipped"] += cash_out
                continue
            total_cp = sum(Decimal(str(e.debit_amount or 0)) for e in counterparts)
            for cp in counterparts:
                cp_amt = Decimal(str(cp.debit_amount or 0))
                alloc = cash_out * cp_amt / total_cp if total_cp else Decimal("0")
                cp_code = str(cp.account_code or "")
                item = _resolve_cf_item(cp_code, coa_map.get(cp_code), "outflow")
                if item:
                    line_amounts[item] += alloc

    return line_amounts, flags


def build_direct_method_lines(
    voucher_groups: dict[int, list[Any]],
    *,
    coa_cf_items: dict[str, str | None] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Decimal], dict[str, Any]]:
    totals: dict[str, Decimal] = {line.code: Decimal("0") for line in DIRECT_LINE_DEFINITIONS}
    agg_flags: dict[str, Any] = {
        "direct_revenue_to_bank": False,
        "receivable_collection": False,
        "internal_transfer_skipped": Decimal("0"),
    }

    for _vid, entries in voucher_groups.items():
        partial, flags = classify_voucher_cash_movements(entries, coa_cf_items=coa_cf_items)
        for code, amt in partial.items():
            totals[code] += amt
        if flags.get("direct_revenue_to_bank"):
            agg_flags["direct_revenue_to_bank"] = True
        if flags.get("receivable_collection"):
            agg_flags["receivable_collection"] = True
        agg_flags["internal_transfer_skipped"] += Decimal(str(flags.get("internal_transfer_skipped") or 0))

    # 小计与净额
    op_in = sum(totals[c] for c in ("sales_cash_received", "tax_refund_received", "other_operating_inflow"))
    op_out = sum(totals[c] for c in ("goods_services_cash_paid", "employee_cash_paid", "tax_cash_paid", "other_operating_outflow"))
    totals["operating_inflow_subtotal"] = op_in
    totals["operating_outflow_subtotal"] = op_out
    totals["operating_net"] = op_in - op_out

    inv_in = sum(totals[c] for c in ("investment_recovery_cash", "investment_income_cash", "asset_disposal_cash", "other_investing_inflow"))
    inv_out = sum(totals[c] for c in ("asset_acquisition_cash", "investment_cash_paid", "other_investing_outflow"))
    totals["investing_inflow_subtotal"] = inv_in
    totals["investing_outflow_subtotal"] = inv_out
    totals["investing_net"] = inv_in - inv_out

    fin_in = sum(totals[c] for c in ("equity_cash_received", "borrowing_cash_received", "other_financing_inflow"))
    fin_out = sum(totals[c] for c in ("debt_repayment_cash", "dividend_interest_cash_paid", "other_financing_outflow"))
    totals["financing_inflow_subtotal"] = fin_in
    totals["financing_outflow_subtotal"] = fin_out
    totals["financing_net"] = fin_in - fin_out
    totals["net_increase_in_cash"] = totals["operating_net"] + totals["investing_net"] + totals["financing_net"]

    lines: list[dict[str, Any]] = []
    for line in DIRECT_LINE_DEFINITIONS:
        amt = totals.get(line.code, Decimal("0"))
        if line.is_header:
            lines.append({
                "line_no": line.line_no,
                "line_code": line.code,
                "label": line.label,
                "section": line.activity,
                "is_header": True,
                "current_amount": "",
            })
            continue
        if not line.is_subtotal and amt == 0:
            continue
        display = amt if line.direction in {"inflow", "outflow"} else amt
        if line.direction == "outflow" and not line.is_subtotal and line.code not in {
            "operating_outflow_subtotal", "investing_outflow_subtotal", "financing_outflow_subtotal",
        }:
            display = amt  # 流出以正数列示金额，报表阅读更直观
        lines.append({
            "line_no": line.line_no,
            "line_code": line.code,
            "label": line.label,
            "section": line.activity,
            "direction": line.direction,
            "is_subtotal": line.is_subtotal,
            "current_amount": str(display.quantize(Decimal("0.00"))),
        })

    return lines, totals, agg_flags


def _sum_balance_change(
    balance_rows: list[dict[str, Any]],
    prefixes: tuple[str, ...],
    *,
    liability: bool = False,
) -> Decimal:
    """期末减期初；负债/权益类增加视为正数（应付增加 → 现金流入调节）。"""
    total = Decimal("0")
    for row in balance_rows:
        code = str(row.get("account_code") or "")
        if not _matches_prefix(code, prefixes):
            continue
        opening = _row_opening_net(row)
        closing = _row_net_balance(row)
        delta = closing - opening
        if liability:
            total += delta
        else:
            total -= delta  # 应收减少 → 正调节
    return total


def build_indirect_method_lines(
    net_profit: Decimal,
    balance_rows: list[dict[str, Any]],
    direct_operating_net: Decimal,
) -> list[dict[str, Any]]:
    """将净利润调节为经营活动现金流量净额（与直接法勾稽）。"""
    depreciation = Decimal("0")
    for row in balance_rows:
        code = str(row.get("account_code") or "")
        if not _matches_prefix(code, DEPRECIATION_PREFIXES):
            continue
        depreciation += Decimal(str(row.get("period_credit") or 0))

    inventory_change = _sum_balance_change(balance_rows, INVENTORY_PREFIXES, liability=False)
    receivable_change = _sum_balance_change(balance_rows, OPERATING_RECEIVABLE_PREFIXES, liability=False)
    payable_change = _sum_balance_change(balance_rows, OPERATING_PAYABLE_PREFIXES, liability=True)

    adjustments = [
        ("add_depreciation", "加：折旧与摊销", depreciation),
        ("inventory_decrease", "存货的减少（减：增加）", inventory_change),
        ("receivable_decrease", "经营性应收项目的减少（减：增加）", receivable_change),
        ("payable_increase", "经营性应付项目的增加（减：减少）", payable_change),
    ]
    adjusted = net_profit + sum(a[2] for a in adjustments)
    reconciled = abs(adjusted - direct_operating_net) <= Decimal("0.02")

    lines: list[dict[str, Any]] = [
        {"line_no": 1, "line_code": "net_profit", "label": "净利润", "current_amount": str(net_profit.quantize(Decimal("0.00")))},
    ]
    for i, (_code, label, amt) in enumerate(adjustments, start=2):
        if amt == 0:
            continue
        lines.append({
            "line_no": i,
            "line_code": _code,
            "label": label,
            "current_amount": str(amt.quantize(Decimal("0.00"))),
        })
    lines.append({
        "line_no": 20,
        "line_code": "operating_net_indirect",
        "label": "经营活动产生的现金流量净额",
        "current_amount": str(adjusted.quantize(Decimal("0.00"))),
        "is_subtotal": True,
        "reconciled_with_direct": reconciled,
        "direct_operating_net": str(direct_operating_net.quantize(Decimal("0.00"))),
    })
    return lines


def build_compilation_notes(flags: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if flags.get("direct_revenue_to_bank") and not flags.get("receivable_collection"):
        notes.append(
            "检测到部分收入直接记入银行存款（未经过应收科目）。"
            "直接法已按销售收现归集；间接法通过净利润与营运资本变动调节，不依赖应收回款分录。"
        )
    elif flags.get("direct_revenue_to_bank") and flags.get("receivable_collection"):
        notes.append(
            "本期同时存在「收入直接进银行」与「应收后回款」两种路径，系统已按凭证对方科目分别归集。"
        )
    skipped = Decimal(str(flags.get("internal_transfer_skipped") or 0))
    if skipped > 0:
        notes.append(f"已剔除现金科目间内部划转 {skipped.quantize(Decimal('0.00'))} 元，不计入三大活动现金流量。")
    notes.append(
        "直接法按现金科目（1001/1002/1012）收付对方科目分项列示；"
        "间接法以净利润加折旧摊销及经营性应收应付变动调节，可与直接法经营活动净额勾稽。"
    )
    notes.append("可在科目表设置「现金流量列报项目」进一步细分行次，便于非财务人员理解资金流向。")
    return notes
