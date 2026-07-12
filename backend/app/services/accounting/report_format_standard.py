"""财务报表标准格式：表头、列名与军工/审计审查常用列报口径。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

CATEGORY_CN: dict[str, str] = {
    "asset": "资产",
    "liability": "负债",
    "common": "共同",
    "equity": "所有者权益",
    "cost": "成本",
    "profit": "损益",
}

TRIAL_BALANCE_HEADERS = [
    "科目编码",
    "科目名称",
    "科目类别",
    "期初借方余额",
    "期初贷方余额",
    "本期借方发生额",
    "本期贷方发生额",
    "本年借方累计",
    "本年贷方累计",
    "期末借方余额",
    "期末贷方余额",
]

BALANCE_SHEET_HEADERS = ["资产", "年初数", "年末数", "负债及所有者权益", "年初数", "年末数"]

INCOME_STATEMENT_HEADERS = ["财务项目", "行次", "本月数", "本年累计数"]

CASH_FLOW_HEADERS = ["项目", "行次", "上期数", "本期数"]

SUBSIDIARY_HEADERS_BASE = [
    "日期",
    "凭证字号",
    "摘要",
    "借方金额",
    "贷方金额",
    "方向",
    "余额",
]

_REVENUE_LINES = [
    ("1", "一、营业收入", "main_business_revenue"),
    ("2", "其他业务收入", "other_business_revenue"),
    ("3", "投资收益", "investment_income"),
    ("4", "营业外收入", "non_operating_income"),
]

_EXPENSE_LINES = [
    ("5", "减：营业成本", "main_business_cost"),
    ("6", "其他业务成本", "other_business_cost"),
    ("7", "销售费用", "selling_expenses"),
    ("8", "管理费用", "admin_expenses"),
    ("9", "财务费用", "financial_expenses"),
    ("10", "资产减值损失", "asset_impairment_loss"),
    ("11", "营业外支出", "non_operating_expense"),
]

_SUMMARY_LINES = [
    ("12", "营业利润", "operating_profit"),
    ("13", "利润总额", "total_profit"),
    ("14", "减：所得税费用", "income_tax"),
    ("15", "净利润", "net_profit"),
]

_CASH_FLOW_LINES = [
    ("1", "经营活动产生的现金流量净额", "operating_activities"),
    ("2", "投资活动产生的现金流量净额", "investing_activities"),
    ("3", "筹资活动产生的现金流量净额", "financing_activities"),
    ("4", "现金及现金等价物净增加额", "net_increase_in_cash"),
]


def category_label(value: str | None) -> str:
    if not value:
        return ""
    return CATEGORY_CN.get(str(value).lower(), str(value))


def format_money(value: Any) -> str:
    if value is None or value == "":
        return ""
    try:
        return f"{Decimal(str(value)):.2f}"
    except Exception:
        return str(value)


def format_money_num(value: Any) -> float | str:
    if value is None or value == "":
        return ""
    try:
        return float(Decimal(str(value)))
    except Exception:
        return str(value)


def closing_net_balance(row: dict[str, Any], section: str | None = None) -> str:
    debit = Decimal(str(row.get("closing_debit") or 0))
    credit = Decimal(str(row.get("closing_credit") or 0))
    category = str(row.get("category") or section or "").lower()
    if category in {"liability", "equity", "负债", "所有者权益", "权益"}:
        net = credit - debit
    else:
        net = debit - credit
    return format_money(net)


def balance_direction(balance: Decimal, account_direction: str = "debit") -> str:
    if balance == 0:
        return "平"
    if account_direction == "credit":
        return "贷" if balance > 0 else "借"
    return "借" if balance > 0 else "贷"


def report_meta_lines(
    *,
    report_title: str,
    ledger_name: str | None = None,
    period_code: str | None = None,
    as_of_date: date | str | None = None,
    account_label: str | None = None,
) -> list[list[str]]:
    """标准报表表头行（编制单位、期间、币种、金额单位）。"""
    period_text = period_code or ""
    if as_of_date:
        period_text = f"{period_text}（截止 {as_of_date}）" if period_text else f"截止 {as_of_date}"
    lines: list[list[str]] = [[report_title]]
    lines.append([f"编制单位：{ledger_name or '—'}"])
    if account_label:
        lines.append([f"科目：{account_label}"])
    lines.append([f"会计期间：{period_text or '—'}"])
    lines.append(["币种：人民币", "金额单位：元"])
    lines.append([])
    return lines


def append_trial_balance_body(
    rows_out: list[list[Any]],
    report: dict[str, Any],
    *,
    include_totals: bool = True,
) -> None:
    rows_out.append(TRIAL_BALANCE_HEADERS)
    for row in report.get("rows", []):
        rows_out.append([
            row.get("account_code", ""),
            row.get("account_name", ""),
            category_label(row.get("category")),
            format_money_num(row.get("opening_debit")),
            format_money_num(row.get("opening_credit")),
            format_money_num(row.get("period_debit")),
            format_money_num(row.get("period_credit")),
            format_money_num(row.get("ytd_debit")),
            format_money_num(row.get("ytd_credit")),
            format_money_num(row.get("closing_debit")),
            format_money_num(row.get("closing_credit")),
        ])
    if include_totals:
        totals = report.get("totals") or {}
        rows_out.append([
            "合计",
            "",
            "",
            format_money_num(totals.get("opening_debit")),
            format_money_num(totals.get("opening_credit")),
            format_money_num(totals.get("period_debit")),
            format_money_num(totals.get("period_credit")),
            format_money_num(totals.get("ytd_debit")),
            format_money_num(totals.get("ytd_credit")),
            format_money_num(totals.get("closing_debit")),
            format_money_num(totals.get("closing_credit")),
        ])


def build_income_statement_lines(
    revenue: dict[str, Any],
    expense: dict[str, Any],
    ytd_revenue: dict[str, Any],
    ytd_expense: dict[str, Any],
    operating_profit: Decimal,
    total_profit: Decimal,
    income_tax: Decimal,
    net_profit: Decimal,
    ytd_operating_profit: Decimal,
    ytd_total_profit: Decimal,
    ytd_income_tax: Decimal,
    ytd_net_profit: Decimal,
) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for line_no, label, key in _REVENUE_LINES:
        lines.append({
            "line_no": int(line_no),
            "label": label,
            "current_amount": format_money(revenue.get(key)),
            "ytd_amount": format_money(ytd_revenue.get(key)),
        })
    for line_no, label, key in _EXPENSE_LINES:
        lines.append({
            "line_no": int(line_no),
            "label": label,
            "current_amount": format_money(expense.get(key)),
            "ytd_amount": format_money(ytd_expense.get(key)),
        })
    for line_no, label, current, ytd in [
        ("12", "营业利润", operating_profit, ytd_operating_profit),
        ("13", "利润总额", total_profit, ytd_total_profit),
        ("14", "减：所得税费用", income_tax, ytd_income_tax),
        ("15", "净利润", net_profit, ytd_net_profit),
    ]:
        lines.append({
            "line_no": int(line_no),
            "label": label,
            "current_amount": format_money(current),
            "ytd_amount": format_money(ytd),
        })
    return lines


def append_balance_sheet_body(rows_out: list[list[Any]], report: dict[str, Any]) -> None:
    classic = report.get("classic_dual_column") or {}
    paired = classic.get("paired_rows") or []
    if paired:
        rows_out.append(BALANCE_SHEET_HEADERS)
        for row in paired:
            rows_out.append([
                row.get("asset_label", ""),
                format_money_num(row.get("asset_opening")),
                format_money_num(row.get("asset_closing")),
                row.get("liability_label", ""),
                format_money_num(row.get("liability_opening")),
                format_money_num(row.get("liability_closing")),
            ])
        if not str(report.get("format", "")).startswith("classic"):
            rows_out.append([
                "",
                "",
                "",
                "恒等式校验",
                "",
                "平衡" if report.get("statement_balanced", report.get("is_balanced")) else "不平衡",
            ])
        return
    rows_out.append(["行次", "报表项目", "年初余额", "期末余额"])
    statement_lines = report.get("statement_lines") or []
    if statement_lines:
        for line in statement_lines:
            rows_out.append([
                line.get("line_no", ""),
                line.get("label", ""),
                format_money_num(line.get("opening_balance")),
                format_money_num(line.get("closing_balance")),
            ])
        rows_out.append([
            "",
            "恒等式校验",
            "",
            "平衡" if report.get("statement_balanced", report.get("is_balanced")) else "不平衡",
        ])
        return
    line_no = 0
    for section, key, rows in [
        ("资产", "assets_total", report.get("assets", [])),
        ("负债", "liabilities_total", report.get("liabilities", [])),
        ("所有者权益", "equity_total", report.get("equity", [])),
    ]:
        for row in rows:
            line_no += 1
            rows_out.append([
                line_no,
                row.get("account_name", ""),
                "",
                closing_net_balance(row, section),
            ])
        line_no += 1
        rows_out.append([line_no, f"{section}合计", "", format_money_num(report.get(key))])
    line_no += 1
    rows_out.append([line_no, "恒等式校验", "", "平衡" if report.get("is_balanced") else "不平衡"])


def append_income_statement_body(rows_out: list[list[Any]], report: dict[str, Any]) -> None:
    rows_out.append(INCOME_STATEMENT_HEADERS)
    statement_lines = report.get("statement_lines") or []
    if statement_lines:
        for line in statement_lines:
            rows_out.append([
                line.get("label", ""),
                line.get("line_no", ""),
                format_money_num(line.get("month_amount", line.get("current_amount"))),
                format_money_num(line.get("year_to_date_amount", line.get("ytd_amount"))),
            ])
        return
    revenue = report.get("revenue") or {}
    expense = report.get("expense") or {}
    ytd_revenue = report.get("ytd_revenue") or {}
    ytd_expense = report.get("ytd_expense") or {}
    for line_no, label, key in _REVENUE_LINES:
        rows_out.append([line_no, label, format_money_num(revenue.get(key)), format_money_num(ytd_revenue.get(key))])
    for line_no, label, key in _EXPENSE_LINES:
        rows_out.append([line_no, label, format_money_num(expense.get(key)), format_money_num(ytd_expense.get(key))])
    for line_no, label, key in _SUMMARY_LINES:
        ytd_key = f"ytd_{key}" if key != "income_tax" else "ytd_income_tax"
        rows_out.append([line_no, label, format_money_num(report.get(key)), format_money_num(report.get(ytd_key))])


def append_cash_flow_body(rows_out: list[list[Any]], report: dict[str, Any]) -> None:
    rows_out.append(CASH_FLOW_HEADERS)
    statement_lines = report.get("statement_lines") or []
    if statement_lines:
        for line in statement_lines:
            if line.get("is_header"):
                rows_out.append([line.get("label", ""), "", "", ""])
                continue
            rows_out.append([
                line.get("label", ""),
                line.get("line_no", ""),
                format_money_num(line.get("prior_amount")),
                format_money_num(line.get("current_amount")),
            ])
        if report.get("indirect_lines"):
            rows_out.append([])
            rows_out.append(["", "附：将净利润调节为经营活动现金流量（间接法）", "", ""])
            rows_out.append(["行次", "调节项目", "金额", ""])
            for line in report.get("indirect_lines") or []:
                rows_out.append([
                    line.get("line_no", ""),
                    line.get("label", ""),
                    format_money_num(line.get("current_amount")),
                    "",
                ])
        if report.get("compilation_notes"):
            rows_out.append([])
            for note in report["compilation_notes"]:
                rows_out.append(["说明", note, "", ""])
        return
    for line_no, label, key in _CASH_FLOW_LINES[:3]:
        block = report.get(key) or {}
        rows_out.append([line_no, label, format_money_num(block.get("net"))])
    rows_out.append(["4", "现金及现金等价物净增加额", format_money_num(report.get("net_increase_in_cash"))])
