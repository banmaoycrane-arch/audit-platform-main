"""资产负债表标准列报：按报表项目聚合科目余额（含净值、合计、兜底桶）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

# 报表项目编码 → 可在科目表 balance_sheet_item 字段中引用
BS_ITEM_OPTIONS: dict[str, str] = {
    "cash_equivalents": "货币资金",
    "trading_financial_assets": "交易性金融资产",
    "notes_receivable": "应收票据",
    "accounts_receivable": "应收账款",
    "accounts_receivable_gross": "应收账款",
    "bad_debt_provision": "坏账准备",
    "prepayments": "预付款项",
    "other_receivables": "其他应收款",
    "inventory": "存货",
    "other_current_assets": "其他流动资产",
    "long_term_equity_investment": "长期股权投资",
    "fixed_assets_net": "固定资产净值",
    "fixed_assets_gross": "固定资产原价",
    "accumulated_depreciation": "累计折旧",
    "fixed_assets_disposal": "固定资产清理",
    "prepaid_expenses": "待摊费用",
    "intangible_assets_net": "无形资产",
    "long_term_prepaid": "长期待摊费用",
    "other_non_current_assets": "其他非流动资产",
    "short_term_borrowings": "短期借款",
    "notes_payable": "应付票据",
    "accounts_payable": "应付账款",
    "advances_from_customers": "预收款项",
    "employee_benefits_payable": "应付职工薪酬",
    "taxes_payable": "应交税费",
    "other_payables": "其他应付款",
    "dividends_payable": "应付股利",
    "other_levies_payable": "其他应交款",
    "accrued_expenses": "预提费用",
    "welfare_payable": "应付福利费",
    "bonds_payable": "应付债券",
    "other_current_liabilities": "其他流动负债",
    "long_term_borrowings": "长期借款",
    "other_non_current_liabilities": "其他非流动负债",
    "paid_in_capital": "实收资本",
    "capital_reserve": "资本公积",
    "surplus_reserve": "盈余公积",
    "retained_earnings": "未分配利润",
}


@dataclass
class BsLineDef:
    code: str
    line_no: int
    label: str
    section: str
    group: str  # current_asset / non_current_asset / current_liability / ...
    add_prefixes: tuple[str, ...] = ()
    add_codes: tuple[str, ...] = ()
    subtract_prefixes: tuple[str, ...] = ()
    subtract_codes: tuple[str, ...] = ()
    is_subtotal: bool = False
    is_catch_all: bool = False
    catch_group: str | None = None


BS_LINE_DEFINITIONS: list[BsLineDef] = [
    BsLineDef("cash_equivalents", 1, "货币资金", "流动资产", "current_asset", add_prefixes=("1001", "1002", "1012")),
    BsLineDef("trading_financial_assets", 2, "交易性金融资产", "流动资产", "current_asset", add_prefixes=("1101",)),
    BsLineDef("notes_receivable", 3, "应收票据", "流动资产", "current_asset", add_prefixes=("1121",)),
    BsLineDef("accounts_receivable_gross", 4, "应收账款", "流动资产", "current_asset", add_prefixes=("1122",)),
    BsLineDef("bad_debt_provision", 4, "坏账准备", "流动资产", "current_asset", add_prefixes=("1231",)),
    BsLineDef("accounts_receivable", 4, "应收账款净额", "流动资产", "current_asset", add_prefixes=("1122",), subtract_prefixes=("1231",)),
    BsLineDef("prepayments", 5, "预付款项", "流动资产", "current_asset", add_prefixes=("1123",)),
    BsLineDef("other_receivables", 6, "其他应收款", "流动资产", "current_asset", add_prefixes=("1221",)),
    BsLineDef("inventory", 7, "存货", "流动资产", "current_asset", add_prefixes=("1401", "1403", "1405", "1411")),
    BsLineDef("prepaid_expenses", 7, "待摊费用", "流动资产", "current_asset", add_prefixes=()),
    BsLineDef("other_current_assets", 8, "其他流动资产", "流动资产", "current_asset", is_catch_all=True, catch_group="current_asset"),
    BsLineDef("current_assets_subtotal", 9, "流动资产合计", "流动资产", "current_asset", is_subtotal=True),
    BsLineDef("long_term_equity_investment", 15, "长期股权投资", "非流动资产", "non_current_asset", add_prefixes=("1511", "1521")),
    BsLineDef("fixed_assets_gross", 16, "固定资产原价", "非流动资产", "non_current_asset", add_prefixes=("1601",)),
    BsLineDef("accumulated_depreciation", 16, "累计折旧", "非流动资产", "non_current_asset", add_prefixes=("1602", "1603")),
    BsLineDef("fixed_assets_net", 16, "固定资产净值", "非流动资产", "non_current_asset", add_prefixes=("1601",), subtract_prefixes=("1602", "1603")),
    BsLineDef("fixed_assets_disposal", 16, "固定资产清理", "非流动资产", "non_current_asset", add_prefixes=("1606",)),
    BsLineDef("intangible_assets_net", 17, "无形资产", "非流动资产", "non_current_asset", add_prefixes=("1701",), subtract_prefixes=("1702", "1703")),
    BsLineDef("long_term_prepaid", 18, "长期待摊费用", "非流动资产", "non_current_asset", add_prefixes=("1801",)),
    BsLineDef("other_non_current_assets", 19, "其他非流动资产", "非流动资产", "non_current_asset", is_catch_all=True, catch_group="non_current_asset"),
    BsLineDef("non_current_assets_subtotal", 20, "非流动资产合计", "非流动资产", "non_current_asset", is_subtotal=True),
    BsLineDef("assets_total", 21, "资产总计", "资产", "asset_total", is_subtotal=True),
    BsLineDef("short_term_borrowings", 31, "短期借款", "流动负债", "current_liability", add_prefixes=("2001",)),
    BsLineDef("notes_payable", 32, "应付票据", "流动负债", "current_liability", add_prefixes=("2201",)),
    BsLineDef("accounts_payable", 33, "应付账款", "流动负债", "current_liability", add_prefixes=("2202",)),
    BsLineDef("advances_from_customers", 34, "预收款项", "流动负债", "current_liability", add_prefixes=("2203",)),
    BsLineDef("employee_benefits_payable", 35, "应付职工薪酬", "流动负债", "current_liability", add_prefixes=("2211",)),
    BsLineDef("taxes_payable", 36, "应交税费", "流动负债", "current_liability", add_prefixes=("2221",)),
    BsLineDef("other_payables", 37, "其他应付款", "流动负债", "current_liability", add_prefixes=("2241",)),
    BsLineDef("dividends_payable", 37, "应付股利", "流动负债", "current_liability", add_prefixes=("2232",)),
    BsLineDef("other_levies_payable", 37, "其他应交款", "流动负债", "current_liability", add_prefixes=("2222",)),
    BsLineDef("accrued_expenses", 37, "预提费用", "流动负债", "current_liability", add_prefixes=("2233",)),
    BsLineDef("welfare_payable", 37, "应付福利费", "流动负债", "current_liability", add_prefixes=("2212",)),
    BsLineDef("other_current_liabilities", 38, "其他流动负债", "流动负债", "current_liability", is_catch_all=True, catch_group="current_liability"),
    BsLineDef("current_liabilities_subtotal", 39, "流动负债合计", "流动负债", "current_liability", is_subtotal=True),
    BsLineDef("long_term_borrowings", 45, "长期借款", "非流动负债", "non_current_liability", add_prefixes=("2501",)),
    BsLineDef("bonds_payable", 45, "应付债券", "非流动负债", "non_current_liability", add_prefixes=("2502",)),
    BsLineDef("other_non_current_liabilities", 46, "其他非流动负债", "非流动负债", "non_current_liability", is_catch_all=True, catch_group="non_current_liability"),
    BsLineDef("non_current_liabilities_subtotal", 47, "非流动负债合计", "非流动负债", "non_current_liability", is_subtotal=True),
    BsLineDef("liabilities_total", 48, "负债合计", "负债", "liability_total", is_subtotal=True),
    BsLineDef("paid_in_capital", 51, "实收资本", "所有者权益", "equity", add_prefixes=("4001",)),
    BsLineDef("capital_reserve", 52, "资本公积", "所有者权益", "equity", add_prefixes=("4002",)),
    BsLineDef("surplus_reserve", 53, "盈余公积", "所有者权益", "equity", add_prefixes=("4101",)),
    BsLineDef("retained_earnings", 54, "未分配利润", "所有者权益", "equity", add_prefixes=("4103", "4104")),
    BsLineDef("equity_total", 55, "所有者权益合计", "所有者权益", "equity_total", is_subtotal=True),
    BsLineDef("liabilities_and_equity_total", 56, "负债和所有者权益总计", "负债和所有者权益", "le_total", is_subtotal=True),
]

DEFAULT_CODE_TO_BS_ITEM: dict[str, str] = {}
for _line in BS_LINE_DEFINITIONS:
    for _pfx in _line.add_prefixes:
        if len(_pfx) == 4:
            DEFAULT_CODE_TO_BS_ITEM[_pfx] = _line.code


def _row_net_balance(row: dict[str, Any]) -> Decimal:
    category = str(row.get("category") or "")
    debit = Decimal(str(row.get("closing_debit") or 0))
    credit = Decimal(str(row.get("closing_credit") or 0))
    if category in {"liability", "equity"}:
        return credit - debit
    return debit - credit


def _row_opening_net(row: dict[str, Any]) -> Decimal:
    category = str(row.get("category") or "")
    debit = Decimal(str(row.get("opening_debit") or 0))
    credit = Decimal(str(row.get("opening_credit") or 0))
    if category in {"liability", "equity"}:
        return credit - debit
    return debit - credit


def _matches_prefix(code: str, prefixes: tuple[str, ...]) -> bool:
    return any(code == pfx or code.startswith(pfx) for pfx in prefixes)


def _resolve_bs_item_for_row(row: dict[str, Any], coa_bs_item: str | None) -> str | None:
    if coa_bs_item:
        return coa_bs_item
    code = str(row.get("account_code") or "")
    for pfx in sorted(DEFAULT_CODE_TO_BS_ITEM.keys(), key=len, reverse=True):
        if code == pfx or code.startswith(pfx):
            return DEFAULT_CODE_TO_BS_ITEM[pfx]
    sub = str(row.get("account_subcategory") or "")
    cat = str(row.get("category") or "")
    if cat == "asset":
        return "other_current_assets" if sub == "流动资产" else "other_non_current_assets"
    if cat == "liability":
        return "other_current_liabilities" if sub == "流动负债" else "other_non_current_liabilities"
    return None


def build_balance_sheet_statement_lines(
    account_rows: list[dict[str, Any]],
    *,
    coa_bs_items: dict[str, str | None] | None = None,
) -> list[dict[str, Any]]:
    """
    将科目余额行聚合为标准资产负债表报表项目。
    coa_bs_items: account_code -> balance_sheet_item（科目表属性覆盖）
    """
    coa_map = coa_bs_items or {}
    assigned: dict[str, set[str]] = {line.code: set() for line in BS_LINE_DEFINITIONS}
    line_closing: dict[str, Decimal] = {line.code: Decimal("0") for line in BS_LINE_DEFINITIONS}
    line_opening: dict[str, Decimal] = {line.code: Decimal("0") for line in BS_LINE_DEFINITIONS}

    catch_all_lines = {line.code: line for line in BS_LINE_DEFINITIONS if line.is_catch_all}

    for row in account_rows:
        code = str(row.get("account_code") or "")
        if not code:
            continue
        cat = str(row.get("category") or "")
        if cat not in {"asset", "liability", "equity"}:
            continue
        closing = _row_net_balance(row)
        opening = _row_opening_net(row)
        if closing == 0 and opening == 0:
            continue

        explicit_item = _resolve_bs_item_for_row(row, coa_map.get(code))
        matched_line: BsLineDef | None = None

        for line in BS_LINE_DEFINITIONS:
            if line.is_subtotal or line.is_catch_all:
                continue
            if explicit_item and line.code == explicit_item:
                matched_line = line
                break
            if _matches_prefix(code, line.add_prefixes) or code in line.add_codes:
                if not _matches_prefix(code, line.subtract_prefixes) and code not in line.subtract_codes:
                    matched_line = line
                    break
            if _matches_prefix(code, line.subtract_prefixes) or code in line.subtract_codes:
                matched_line = line
                closing = -closing
                opening = -opening
                break

        if matched_line is None and explicit_item and explicit_item in catch_all_lines:
            matched_line = catch_all_lines[explicit_item]

        if matched_line is None:
            sub = str(row.get("account_subcategory") or "")
            if cat == "asset":
                bucket = "other_current_assets" if sub == "流动资产" else "other_non_current_assets"
            elif cat == "liability":
                bucket = "other_current_liabilities" if sub == "流动负债" else "other_non_current_liabilities"
            else:
                bucket = None
            if bucket:
                matched_line = catch_all_lines.get(bucket)

        if matched_line is None:
            continue

        assigned[matched_line.code].add(code)
        line_closing[matched_line.code] += closing
        line_opening[matched_line.code] += opening

    # 小计
    line_closing["current_assets_subtotal"] = sum(
        line_closing[c] for c in (
            "cash_equivalents", "trading_financial_assets", "notes_receivable",
            "accounts_receivable_gross", "prepayments", "other_receivables",
            "inventory", "prepaid_expenses", "other_current_assets",
        )
    ) - line_closing.get("bad_debt_provision", Decimal("0"))
    line_opening["current_assets_subtotal"] = sum(
        line_opening[c] for c in (
            "cash_equivalents", "trading_financial_assets", "notes_receivable",
            "accounts_receivable_gross", "prepayments", "other_receivables",
            "inventory", "prepaid_expenses", "other_current_assets",
        )
    ) - line_opening.get("bad_debt_provision", Decimal("0"))
    line_closing["fixed_assets_net"] = (
        line_closing.get("fixed_assets_gross", Decimal("0"))
        - line_closing.get("accumulated_depreciation", Decimal("0"))
    )
    line_opening["fixed_assets_net"] = (
        line_opening.get("fixed_assets_gross", Decimal("0"))
        - line_opening.get("accumulated_depreciation", Decimal("0"))
    )
    line_closing["non_current_assets_subtotal"] = sum(
        line_closing[c] for c in (
            "long_term_equity_investment", "fixed_assets_net", "fixed_assets_disposal",
            "intangible_assets_net", "long_term_prepaid", "other_non_current_assets",
        )
    )
    line_opening["non_current_assets_subtotal"] = sum(
        line_opening[c] for c in (
            "long_term_equity_investment", "fixed_assets_net", "fixed_assets_disposal",
            "intangible_assets_net", "long_term_prepaid", "other_non_current_assets",
        )
    )
    line_closing["assets_total"] = line_closing["current_assets_subtotal"] + line_closing["non_current_assets_subtotal"]
    line_opening["assets_total"] = line_opening["current_assets_subtotal"] + line_opening["non_current_assets_subtotal"]

    line_closing["current_liabilities_subtotal"] = sum(
        line_closing[c] for c in (
            "short_term_borrowings", "notes_payable", "accounts_payable", "advances_from_customers",
            "other_payables", "dividends_payable", "employee_benefits_payable", "taxes_payable",
            "other_levies_payable", "accrued_expenses", "welfare_payable", "other_current_liabilities",
        )
    )
    line_opening["current_liabilities_subtotal"] = sum(
        line_opening[c] for c in (
            "short_term_borrowings", "notes_payable", "accounts_payable", "advances_from_customers",
            "other_payables", "dividends_payable", "employee_benefits_payable", "taxes_payable",
            "other_levies_payable", "accrued_expenses", "welfare_payable", "other_current_liabilities",
        )
    )
    line_closing["non_current_liabilities_subtotal"] = sum(
        line_closing[c] for c in ("long_term_borrowings", "bonds_payable", "other_non_current_liabilities")
    )
    line_opening["non_current_liabilities_subtotal"] = sum(
        line_opening[c] for c in ("long_term_borrowings", "bonds_payable", "other_non_current_liabilities")
    )
    line_closing["liabilities_total"] = line_closing["current_liabilities_subtotal"] + line_closing["non_current_liabilities_subtotal"]
    line_opening["liabilities_total"] = line_opening["current_liabilities_subtotal"] + line_opening["non_current_liabilities_subtotal"]

    line_closing["equity_total"] = sum(line_closing[c] for c in ("paid_in_capital", "capital_reserve", "surplus_reserve", "retained_earnings"))
    line_opening["equity_total"] = sum(line_opening[c] for c in ("paid_in_capital", "capital_reserve", "surplus_reserve", "retained_earnings"))
    line_closing["liabilities_and_equity_total"] = line_closing["liabilities_total"] + line_closing["equity_total"]
    line_opening["liabilities_and_equity_total"] = line_opening["liabilities_total"] + line_opening["equity_total"]

    result: list[dict[str, Any]] = []
    for line in BS_LINE_DEFINITIONS:
        closing = line_closing[line.code]
        opening = line_opening[line.code]
        if not line.is_subtotal and closing == 0 and opening == 0:
            continue
        result.append({
            "line_no": line.line_no,
            "line_code": line.code,
            "label": line.label,
            "section": line.section,
            "group": line.group,
            "is_subtotal": line.is_subtotal,
            "opening_balance": str(opening.quantize(Decimal("0.00"))),
            "closing_balance": str(closing.quantize(Decimal("0.00"))),
            "account_codes": sorted(assigned.get(line.code, set())),
        })
    return result
