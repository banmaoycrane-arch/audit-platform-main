"""三大报表经典通用格式布局（与纸质表样完全一致：固定行次、表头页脚、左右合计对齐）。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

# ---------- 资产负债表：左右双栏行次模板（固定显示，零也列示） ----------

CLASSIC_BS_LEFT_TEMPLATE: list[dict[str, Any]] = [
    {"label": "流动资产", "is_section": True},
    {"line_code": "cash_equivalents", "label": "  货币资金"},
    {"line_code": "trading_financial_assets", "label": "  短期投资"},
    {"line_code": "notes_receivable", "label": "  应收票据"},
    {"line_code": "accounts_receivable_gross", "label": "  应收账款"},
    {"line_code": "bad_debt_provision", "label": "  坏账准备", "display_as_contra": True},
    {"line_code": "net_accounts_receivable", "label": "  净应收账款", "is_computed": True},
    {"line_code": "prepayments", "label": "  预付账款"},
    {"line_code": "other_receivables", "label": "  其他应收款"},
    {"line_code": "inventory", "label": "  存货"},
    {"line_code": "prepaid_expenses", "label": "  待摊费用"},
    {"line_code": "other_current_assets", "label": "  待处理流动资产损失"},
    {"line_code": "current_assets_subtotal", "label": "  流动资产合计", "is_subtotal": True},
    {"label": "长期投资", "is_section": True},
    {"line_code": "long_term_equity_investment", "label": "  长期投资"},
    {"label": "固定资产", "is_section": True},
    {"line_code": "fixed_assets_gross", "label": "  固定资产原价"},
    {"line_code": "accumulated_depreciation", "label": "  减：累计折旧", "display_as_contra": True},
    {"line_code": "fixed_assets_net", "label": "  固定资产净值", "is_computed": True},
    {"line_code": "fixed_assets_disposal", "label": "  固定资产清理"},
    {"label": "无形资产及递延资产", "is_section": True},
    {"line_code": "long_term_prepaid", "label": "  递延资产"},
    {"line_code": "intangible_assets_net", "label": "  无形资产"},
    {"line_code": "intangible_deferred_subtotal", "label": "  无形资产及递延资产合计", "is_computed": True},
    {"label": "其他长期资产", "is_section": True},
    {"line_code": "other_non_current_assets", "label": "  其他长期资产"},
    {"line_code": "deferred_tax_asset", "label": "  递延税项"},
    {"line_code": "deferred_tax_debit", "label": "  递延税款借项"},
    {"line_code": "assets_total", "label": "资产总计", "is_subtotal": True, "is_grand_total": True},
]

CLASSIC_BS_RIGHT_TEMPLATE: list[dict[str, Any]] = [
    {"label": "流动负债", "is_section": True},
    {"line_code": "short_term_borrowings", "label": "  短期借款"},
    {"line_code": "notes_payable", "label": "  应付票据"},
    {"line_code": "accounts_payable", "label": "  应付账款"},
    {"line_code": "advances_from_customers", "label": "  预收账款"},
    {"line_code": "other_payables", "label": "  其他应付款"},
    {"line_code": "dividends_payable", "label": "  应付股利"},
    {"line_code": "employee_benefits_payable", "label": "  应付工资"},
    {"line_code": "taxes_payable", "label": "  未交税金"},
    {"line_code": "other_levies_payable", "label": "  其他应交款"},
    {"line_code": "accrued_expenses", "label": "  预提费用"},
    {"line_code": "welfare_payable", "label": "  应付福利费"},
    {"line_code": "other_current_liabilities", "label": "  其他流动负债"},
    {"line_code": "current_liabilities_subtotal", "label": "  流动负债合计", "is_subtotal": True},
    {"label": "长期负债", "is_section": True},
    {"line_code": "long_term_borrowings", "label": "  长期借款"},
    {"line_code": "bonds_payable", "label": "  应付债券"},
    {"line_code": "other_non_current_liabilities", "label": "  其他长期负债"},
    {"line_code": "non_current_liabilities_subtotal", "label": "  长期负债合计", "is_subtotal": True},
    {"label": "所有者权益", "is_section": True},
    {"line_code": "paid_in_capital", "label": "  实收资本"},
    {"line_code": "capital_reserve", "label": "  资本公积"},
    {"line_code": "surplus_reserve", "label": "  盈余公积"},
    {"line_code": "retained_earnings", "label": "  未分配利润"},
    {"line_code": "equity_total", "label": "  所有者权益合计", "is_subtotal": True},
    {"line_code": "liabilities_and_equity_total", "label": "负债及所有者权益合计", "is_subtotal": True, "is_grand_total": True},
]

# ---------- 损益表：16行（固定） ----------

CLASSIC_IS_TEMPLATE: list[dict[str, Any]] = [
    {"line_no": 1, "label": "一、主营业务收入", "key": "main_business_revenue"},
    {"line_no": 2, "label": "减：主营业务成本", "key": "main_business_cost"},
    {"line_no": 3, "label": "主营业务税金及附加", "key": "main_business_tax_surcharge"},
    {"line_no": 4, "label": "二、主营业务利润", "key": "main_business_profit", "is_calc": True},
    {"line_no": 5, "label": "加：其他业务利润", "key": "other_business_profit", "is_calc": True},
    {"line_no": 6, "label": "减：营业费用", "key": "selling_expenses"},
    {"line_no": 7, "label": "管理费用", "key": "admin_expenses"},
    {"line_no": 8, "label": "财务费用", "key": "financial_expenses"},
    {"line_no": 9, "label": "三、营业利润", "key": "operating_profit", "is_calc": True},
    {"line_no": 10, "label": "加：投资收益", "key": "investment_income"},
    {"line_no": 11, "label": "补贴收入", "key": "subsidy_income"},
    {"line_no": 12, "label": "营业外收入", "key": "non_operating_income"},
    {"line_no": 13, "label": "减：营业外支出", "key": "non_operating_expense"},
    {"line_no": 14, "label": "四、利润总额", "key": "total_profit", "is_calc": True},
    {"line_no": 15, "label": "减：所得税", "key": "income_tax_expense"},
    {"line_no": 16, "label": "五、净利润", "key": "net_profit", "is_calc": True},
]

# ---------- 现金流量表：固定行次 1-33 ----------

CLASSIC_CF_SPECS: list[dict[str, Any]] = [
    {"line_no": "", "line_code": "operating_header", "label": "一、经营活动产生的现金流量", "is_header": True},
    {"line_no": 1, "line_code": "sales_cash_received", "label": "销售商品、提供劳务收到的现金"},
    {"line_no": 2, "line_code": "tax_refund_received", "label": "收到的税费返还"},
    {"line_no": 3, "line_code": "other_operating_inflow", "label": "收到的其他与经营活动有关的现金"},
    {"line_no": 4, "line_code": "operating_inflow_subtotal", "label": "现金流入小计", "is_subtotal": True},
    {"line_no": 5, "line_code": "goods_services_cash_paid", "label": "购买商品、接受劳务支付的现金"},
    {"line_no": 6, "line_code": "employee_cash_paid", "label": "支付给职工以及为职工支付的现金"},
    {"line_no": 7, "line_code": "tax_cash_paid", "label": "支付的各项税费"},
    {"line_no": 8, "line_code": "other_operating_outflow", "label": "支付的其他与经营活动有关的现金"},
    {"line_no": 9, "line_code": "operating_outflow_subtotal", "label": "现金流出小计", "is_subtotal": True},
    {"line_no": 10, "line_code": "operating_net", "label": "经营活动产生的现金流量净额", "is_subtotal": True},
    {"line_no": "", "line_code": "investing_header", "label": "二、投资活动产生的现金流量", "is_header": True},
    {"line_no": 12, "line_code": "investment_recovery_cash", "label": "收回投资收到的现金"},
    {"line_no": 13, "line_code": "investment_income_cash", "label": "取得投资收益收到的现金"},
    {"line_no": 14, "line_code": "asset_disposal_cash", "label": "处置固定资产、无形资产和其他长期资产收回的现金净额"},
    {"line_no": 15, "line_code": "other_investing_inflow", "label": "收到的其他与投资活动有关的现金"},
    {"line_no": 16, "line_code": "investing_inflow_subtotal", "label": "现金流入小计", "is_subtotal": True},
    {"line_no": 17, "line_code": "asset_acquisition_cash", "label": "购建固定资产、无形资产和其他长期资产支付的现金"},
    {"line_no": 18, "line_code": "investment_cash_paid", "label": "投资支付的现金"},
    {"line_no": 19, "line_code": "other_investing_outflow", "label": "支付的其他与投资活动有关的现金"},
    {"line_no": 20, "line_code": "investing_outflow_subtotal", "label": "现金流出小计", "is_subtotal": True},
    {"line_no": 21, "line_code": "investing_net", "label": "投资活动产生的现金流量净额", "is_subtotal": True},
    {"line_no": "", "line_code": "financing_header", "label": "三、筹资活动产生的现金流量", "is_header": True},
    {"line_no": 23, "line_code": "equity_cash_received", "label": "吸收投资收到的现金"},
    {"line_no": 24, "line_code": "borrowing_cash_received", "label": "借款收到的现金"},
    {"line_no": 25, "line_code": "other_financing_inflow", "label": "收到的其他与筹资活动有关的现金"},
    {"line_no": 26, "line_code": "financing_inflow_subtotal", "label": "现金流入小计", "is_subtotal": True},
    {"line_no": 27, "line_code": "debt_repayment_cash", "label": "偿还债务支付的现金"},
    {"line_no": 28, "line_code": "dividend_interest_cash_paid", "label": "分配股利、利润或偿付利息支付的现金"},
    {"line_no": 29, "line_code": "other_financing_outflow", "label": "支付的其他与筹资活动有关的现金"},
    {"line_no": 30, "line_code": "financing_outflow_subtotal", "label": "现金流出小计", "is_subtotal": True},
    {"line_no": 31, "line_code": "financing_net", "label": "筹资活动产生的现金流量净额", "is_subtotal": True},
    {"line_no": 32, "line_code": "fx_effect_on_cash", "label": "四、汇率变动对现金的影响"},
    {"line_no": 33, "line_code": "net_increase_in_cash", "label": "五、现金及现金等价物净增加额", "is_grand_total": True},
]

CLASSIC_REPORT_FOOTER_LABELS = ("制表人", "负责人", "复核")


def _fmt(amount: Decimal | None) -> str:
    if amount is None:
        return "0.00"
    return str(amount.quantize(Decimal("0.00")))


def _lookup_amounts(statement_lines: list[dict[str, Any]]) -> dict[str, dict[str, Decimal]]:
    out: dict[str, dict[str, Decimal]] = {}
    for line in statement_lines:
        code = str(line.get("line_code") or "")
        if not code:
            continue
        out[code] = {
            "opening": Decimal(str(line.get("opening_balance") or 0)),
            "closing": Decimal(str(line.get("closing_balance") or 0)),
        }
    return out


def _resolve_bs_amount(
    amounts: dict[str, dict[str, Decimal]],
    item: dict[str, Any],
    field: str,
) -> Decimal:
    code = item.get("line_code")
    if not code:
        return Decimal("0")
    if item.get("is_computed"):
        if code == "net_accounts_receivable":
            gross = amounts.get("accounts_receivable_gross", {}).get(field, Decimal("0"))
            prov = amounts.get("bad_debt_provision", {}).get(field, Decimal("0"))
            return gross - prov
        if code == "fixed_assets_net":
            gross = amounts.get("fixed_assets_gross", {}).get(field, Decimal("0"))
            dep = amounts.get("accumulated_depreciation", {}).get(field, Decimal("0"))
            return gross - dep
        if code == "intangible_deferred_subtotal":
            return (
                amounts.get("long_term_prepaid", {}).get(field, Decimal("0"))
                + amounts.get("intangible_assets_net", {}).get(field, Decimal("0"))
            )
        return Decimal("0")
    raw = amounts.get(code, {}).get(field, Decimal("0"))
    if item.get("display_as_contra"):
        return abs(raw)
    return raw


def _build_side_rows(
    template: list[dict[str, Any]],
    amounts: dict[str, dict[str, Decimal]],
) -> list[dict[str, Any]]:
    """固定行次：分区标题留空，金额行零也显示 0.00。"""
    rows: list[dict[str, Any]] = []
    for item in template:
        if item.get("is_section"):
            rows.append({
                "label": item["label"],
                "is_section": True,
                "opening_balance": "",
                "closing_balance": "",
            })
            continue
        opening = _resolve_bs_amount(amounts, item, "opening")
        closing = _resolve_bs_amount(amounts, item, "closing")
        rows.append({
            "line_code": item.get("line_code"),
            "label": item["label"],
            "is_subtotal": item.get("is_subtotal", False),
            "is_grand_total": item.get("is_grand_total", False),
            "opening_balance": _fmt(opening),
            "closing_balance": _fmt(closing),
        })
    return rows


def _pair_balance_sheet_sides(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """左右配对；资产总计与负债及所有者权益合计强制同一末行对齐。"""
    left_body = [r for r in left if not r.get("is_grand_total")]
    left_total = next((r for r in left if r.get("is_grand_total")), None)
    right_body = [r for r in right if not r.get("is_grand_total")]
    right_total = next((r for r in right if r.get("is_grand_total")), None)

    max_body = max(len(left_body), len(right_body))
    while len(left_body) < max_body:
        left_body.append({"label": "", "opening_balance": "", "closing_balance": ""})
    while len(right_body) < max_body:
        right_body.append({"label": "", "opening_balance": "", "closing_balance": ""})

    paired: list[dict[str, Any]] = []
    for i in range(max_body):
        l, r = left_body[i], right_body[i]
        paired.append(_pair_row(i + 1, l, r))
    if left_total or right_total:
        paired.append(_pair_row(max_body + 1, left_total or {}, right_total or {}))
    return paired


def _pair_row(index: int, left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_index": index,
        "asset_label": left.get("label", ""),
        "asset_opening": left.get("opening_balance", ""),
        "asset_closing": left.get("closing_balance", ""),
        "asset_is_section": left.get("is_section", False),
        "asset_is_subtotal": left.get("is_subtotal", False) or left.get("is_grand_total", False),
        "liability_label": right.get("label", ""),
        "liability_opening": right.get("opening_balance", ""),
        "liability_closing": right.get("closing_balance", ""),
        "liability_is_section": right.get("is_section", False),
        "liability_is_subtotal": right.get("is_subtotal", False) or right.get("is_grand_total", False),
    }


def build_classic_dual_column_balance_sheet(statement_lines: list[dict[str, Any]]) -> dict[str, Any]:
    amounts = _lookup_amounts(statement_lines)
    left = _build_side_rows(CLASSIC_BS_LEFT_TEMPLATE, amounts)
    right = _build_side_rows(CLASSIC_BS_RIGHT_TEMPLATE, amounts)
    paired_rows = _pair_balance_sheet_sides(left, right)
    return {
        "format": "classic_dual_column",
        "left_rows": left,
        "right_rows": right,
        "paired_rows": paired_rows,
        "column_headers": ["资产", "年初数", "年末数", "负债及所有者权益", "年初数", "年末数"],
    }


def _sum_credit(amounts: dict[str, tuple[Decimal, Decimal]], codes: list[str]) -> Decimal:
    total = Decimal("0")
    for code in codes:
        debit, credit = amounts.get(code, (Decimal("0"), Decimal("0")))
        total += credit - debit
    return total


def _sum_debit(amounts: dict[str, tuple[Decimal, Decimal]], codes: list[str]) -> Decimal:
    total = Decimal("0")
    for code in codes:
        debit, credit = amounts.get(code, (Decimal("0"), Decimal("0")))
        total += debit - credit
    return total


def build_classic_income_statement_lines(
    period_amounts: dict[str, tuple[Decimal, Decimal]],
    ytd_amounts: dict[str, tuple[Decimal, Decimal]],
    *,
    income_accounts: dict[str, list[str]],
    expense_accounts: dict[str, list[str]],
) -> list[dict[str, Any]]:
    def period_credit(key: str) -> Decimal:
        return _sum_credit(period_amounts, income_accounts.get(key, []))

    def period_debit(key: str) -> Decimal:
        return _sum_debit(period_amounts, expense_accounts.get(key, []))

    def ytd_credit(key: str) -> Decimal:
        return _sum_credit(ytd_amounts, income_accounts.get(key, []))

    def ytd_debit(key: str) -> Decimal:
        return _sum_debit(ytd_amounts, expense_accounts.get(key, []))

    main_rev_p, main_rev_y = period_credit("main_business_revenue"), ytd_credit("main_business_revenue")
    main_cost_p, main_cost_y = period_debit("main_business_cost"), ytd_debit("main_business_cost")
    tax_sur_p = _sum_debit(period_amounts, expense_accounts.get("main_business_tax_surcharge", []))
    tax_sur_y = _sum_debit(ytd_amounts, expense_accounts.get("main_business_tax_surcharge", []))
    other_rev_p, other_rev_y = period_credit("other_business_revenue"), ytd_credit("other_business_revenue")
    other_cost_p, other_cost_y = period_debit("other_business_cost"), ytd_debit("other_business_cost")

    values: dict[str, tuple[Decimal, Decimal]] = {
        "main_business_revenue": (main_rev_p, main_rev_y),
        "main_business_cost": (main_cost_p, main_cost_y),
        "main_business_tax_surcharge": (tax_sur_p, tax_sur_y),
        "main_business_profit": (main_rev_p - main_cost_p - tax_sur_p, main_rev_y - main_cost_y - tax_sur_y),
        "other_business_profit": (other_rev_p - other_cost_p, other_rev_y - other_cost_y),
        "selling_expenses": (period_debit("selling_expenses"), ytd_debit("selling_expenses")),
        "admin_expenses": (period_debit("admin_expenses"), ytd_debit("admin_expenses")),
        "financial_expenses": (period_debit("financial_expenses"), ytd_debit("financial_expenses")),
        "investment_income": (period_credit("investment_income"), ytd_credit("investment_income")),
        "subsidy_income": (period_credit("subsidy_income"), ytd_credit("subsidy_income")),
        "non_operating_income": (period_credit("non_operating_income"), ytd_credit("non_operating_income")),
        "non_operating_expense": (period_debit("non_operating_expense"), ytd_debit("non_operating_expense")),
        "income_tax_expense": (period_debit("income_tax_expense"), ytd_debit("income_tax_expense")),
    }
    mp, op = values["main_business_profit"], values["other_business_profit"]
    se, ae, fe = values["selling_expenses"], values["admin_expenses"], values["financial_expenses"]
    values["operating_profit"] = (mp[0] + op[0] - se[0] - ae[0] - fe[0], mp[1] + op[1] - se[1] - ae[1] - fe[1])
    oper = values["operating_profit"]
    inv, sub, noi, noe = values["investment_income"], values["subsidy_income"], values["non_operating_income"], values["non_operating_expense"]
    values["total_profit"] = (oper[0] + inv[0] + sub[0] + noi[0] - noe[0], oper[1] + inv[1] + sub[1] + noi[1] - noe[1])
    tp, tax = values["total_profit"], values["income_tax_expense"]
    values["net_profit"] = (tp[0] - tax[0], tp[1] - tax[1])

    lines: list[dict[str, Any]] = []
    for item in CLASSIC_IS_TEMPLATE:
        key = item["key"]
        cur, ytd = values.get(key, (Decimal("0"), Decimal("0")))
        lines.append({
            "line_no": item["line_no"],
            "line_code": key,
            "label": item["label"],
            "is_subtotal": item.get("is_calc", False),
            "current_amount": _fmt(cur),
            "ytd_amount": _fmt(ytd),
            "month_amount": _fmt(cur),
            "year_to_date_amount": _fmt(ytd),
        })
    return lines


def build_classic_cash_flow_lines(
    current_lines: list[dict[str, Any]],
    prior_lines: list[dict[str, Any]] | None = None,
    *,
    fx_effect: Decimal = Decimal("0"),
    prior_fx_effect: Decimal = Decimal("0"),
) -> list[dict[str, Any]]:
    """固定 33 行表样，全部行次均输出（零显示 0.00）。"""
    cur_map = {str(l.get("line_code")): l for l in current_lines if l.get("line_code")}
    pri_map = {str(l.get("line_code")): l for l in (prior_lines or []) if l.get("line_code")}

    result: list[dict[str, Any]] = []
    for spec in CLASSIC_CF_SPECS:
        code = spec["line_code"]
        if spec.get("is_header"):
            result.append({
                "line_no": spec.get("line_no", ""),
                "line_code": code,
                "label": spec["label"],
                "is_header": True,
                "prior_amount": "",
                "current_amount": "",
            })
            continue
        if code == "fx_effect_on_cash":
            result.append({
                **spec,
                "prior_amount": _fmt(prior_fx_effect),
                "current_amount": _fmt(fx_effect),
            })
            continue
        if code == "net_increase_in_cash":
            pri_amt = Decimal(str(pri_map.get("net_increase_in_cash", {}).get("current_amount") or 0))
            cur_amt = Decimal(str(cur_map.get("net_increase_in_cash", {}).get("current_amount") or 0))
            result.append({
                **spec,
                "prior_amount": _fmt(pri_amt),
                "current_amount": _fmt(cur_amt),
                "is_subtotal": True,
            })
            continue
        cur = cur_map.get(code, {})
        pri = pri_map.get(code, {})
        cur_amt = Decimal(str(cur.get("current_amount") or 0))
        pri_amt = Decimal(str(pri.get("current_amount") or 0))
        result.append({
            "line_no": spec.get("line_no", ""),
            "line_code": code,
            "label": spec["label"],
            "is_subtotal": spec.get("is_subtotal", False),
            "prior_amount": _fmt(pri_amt),
            "current_amount": _fmt(cur_amt),
        })
    return result


def classic_report_header_rows(report_kind: str, report: dict[str, Any]) -> list[list[str]]:
    """纸质表样表头（标题 + 编制单位 + 日期 + 单位）。"""
    title = {
        "balance_sheet": "资产负债表",
        "income_statement": "损益表",
        "cash_flow": "现金流量表",
    }.get(report_kind, report.get("report_title") or "财务报表")
    ledger = report.get("ledger_name") or "—"
    as_of = report.get("as_of_date") or "—"
    period = report.get("period_code") or ""
    year = period[:4] if period else str(as_of)[:4]

    rows: list[list[str]] = [[title]]
    if report_kind == "balance_sheet":
        rows.append([f"编制单位：{ledger}", f"编制日期：{as_of}", "单位：元"])
    elif report_kind == "income_statement":
        rows.append([f"编制单位：{ledger}", f"填表日期：{as_of}", "单位：元"])
    elif report_kind == "cash_flow":
        rows.append([f"编制单位：{ledger}", f"{year}年", "单位：元"])
    else:
        rows.append([f"编制单位：{ledger}", f"会计期间：{period}", "单位：元"])
    rows.append([])
    return rows


def classic_report_footer_rows(report: dict[str, Any]) -> list[list[str]]:
    """纸质表样页脚：制表人 / 负责人 / 复核。"""
    sig = report.get("signature") or {}
    preparer = sig.get("preparer_name") or report.get("preparer_name") or ""
    approver = sig.get("approver_name") or report.get("approver_name") or ""
    reviewer = sig.get("reviewer_name") or report.get("reviewer_name") or ""
    return [
        [],
        [
            f"制表人：{preparer or '____________'}",
            f"负责人：{approver or '____________'}",
            f"复核：{reviewer or '____________'}",
        ],
    ]
