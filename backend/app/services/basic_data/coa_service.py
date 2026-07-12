# -*- coding: utf-8 -*-
"""
模块功能：会计科目（CoA）服务，支持 CRUD、默认种子、编码自动生成与校验。
业务场景：维护账簿的会计科目体系，确保科目编码符合配置化规则。
政策依据：《企业会计准则》科目编号惯例。
输入数据：科目基础信息、父级科目编码、编码规则配置。
输出结果：ChartOfAccounts 记录、编码校验结果、自动生成的子科目编码。
创建日期：2026-07-02
更新记录：
    2026-07-02  增加配置化编码规则、自动生成与校验逻辑。
"""

import re
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.config.coa_code_config import CoaCodeRuleConfig, load_coa_code_config
from app.db.models import ChartOfAccounts
from app.services.accounting.balance_sheet_presentation_service import BS_ITEM_OPTIONS, DEFAULT_CODE_TO_BS_ITEM
from app.services.accounting.cash_flow_presentation_service import DEFAULT_CODE_TO_CF_ITEM


ACCOUNT_CATEGORY_MAP = {
    "资产": {"流动资产", "非流动资产"},
    "负债": {"流动负债", "长期负债"},
    "所有者权益": set(),
}
EQUITY_SUBCATEGORIES = {"注册资本", "资本公积", "盈余公积", "未分配利润"}
NON_DIVIDEND_EQUITY_SUBCATEGORIES = {"注册资本", "资本公积", "盈余公积"}


# 《企业会计准则》一级 + 高频二级（精简集合）
DEFAULT_ACCOUNTS: list[dict[str, Any]] = [
    # 资产类
    {"code": "1001", "name": "库存现金", "category": "asset", "direction": "debit"},
    {"code": "1002", "name": "银行存款", "category": "asset", "direction": "debit"},
    {"code": "1012", "name": "其他货币资金", "category": "asset", "direction": "debit"},
    {"code": "1101", "name": "交易性金融资产", "category": "asset", "direction": "debit"},
    {"code": "1122", "name": "应收账款", "category": "asset", "direction": "debit"},
    {"code": "1123", "name": "预付账款", "category": "asset", "direction": "debit"},
    {"code": "1221", "name": "其他应收款", "category": "asset", "direction": "debit"},
    {"code": "1231", "name": "坏账准备", "category": "asset", "direction": "credit"},
    {"code": "1401", "name": "材料采购", "category": "asset", "direction": "debit"},
    {"code": "1403", "name": "原材料", "category": "asset", "direction": "debit"},
    {"code": "1405", "name": "库存商品", "category": "asset", "direction": "debit"},
    {"code": "1601", "name": "固定资产", "category": "asset", "direction": "debit"},
    {"code": "1602", "name": "累计折旧", "category": "asset", "direction": "credit"},
    {"code": "1701", "name": "无形资产", "category": "asset", "direction": "debit"},
    # 负债类
    {"code": "2001", "name": "短期借款", "category": "liability", "direction": "credit"},
    {"code": "2202", "name": "应付账款", "category": "liability", "direction": "credit"},
    {"code": "2203", "name": "预收账款", "category": "liability", "direction": "credit"},
    {"code": "2211", "name": "应付职工薪酬", "category": "liability", "direction": "credit"},
    {"code": "2221", "name": "应交税费", "category": "liability", "direction": "credit"},
    {"code": "2241", "name": "其他应付款", "category": "liability", "direction": "credit"},
    # 共同/权益
    {"code": "4001", "name": "实收资本", "category": "equity", "direction": "credit"},
    {"code": "4002", "name": "资本公积", "category": "equity", "direction": "credit"},
    {"code": "4101", "name": "盈余公积", "category": "equity", "direction": "credit"},
    {"code": "4103", "name": "本年利润", "category": "equity", "direction": "credit"},
    {"code": "4104", "name": "利润分配", "category": "equity", "direction": "credit"},
    # 成本/损益
    {"code": "5001", "name": "生产成本", "category": "cost", "direction": "debit"},
    {"code": "5101", "name": "制造费用", "category": "cost", "direction": "debit"},
    {"code": "6001", "name": "主营业务收入", "category": "profit", "direction": "credit"},
    {"code": "6051", "name": "其他业务收入", "category": "profit", "direction": "credit"},
    {"code": "6111", "name": "投资收益", "category": "profit", "direction": "credit"},
    {"code": "6301", "name": "营业外收入", "category": "profit", "direction": "credit"},
    {"code": "6401", "name": "主营业务成本", "category": "profit", "direction": "debit"},
    {"code": "6402", "name": "其他业务成本", "category": "profit", "direction": "debit"},
    {"code": "6601", "name": "销售费用", "category": "profit", "direction": "debit"},
    {"code": "6602", "name": "管理费用", "category": "profit", "direction": "debit"},
    {"code": "6603", "name": "财务费用", "category": "profit", "direction": "debit"},
    {"code": "6701", "name": "资产减值损失", "category": "profit", "direction": "debit"},
    {"code": "6711", "name": "营业外支出", "category": "profit", "direction": "debit"},
    {"code": "6801", "name": "所得税费用", "category": "profit", "direction": "debit"},
]

# 默认科目 → 科目细类 / 资产负债表列报项目
COA_DEFAULT_DESIGN: dict[str, dict[str, str]] = {
    "1001": {"account_subcategory": "流动资产", "balance_sheet_item": "cash_equivalents"},
    "1002": {"account_subcategory": "流动资产", "balance_sheet_item": "cash_equivalents"},
    "1012": {"account_subcategory": "流动资产", "balance_sheet_item": "cash_equivalents"},
    "1101": {"account_subcategory": "流动资产", "balance_sheet_item": "trading_financial_assets"},
    "1122": {"account_subcategory": "流动资产", "balance_sheet_item": "accounts_receivable"},
    "1123": {"account_subcategory": "流动资产", "balance_sheet_item": "prepayments"},
    "1221": {"account_subcategory": "流动资产", "balance_sheet_item": "other_receivables"},
    "1231": {"account_subcategory": "流动资产", "balance_sheet_item": "accounts_receivable"},
    "1401": {"account_subcategory": "流动资产", "balance_sheet_item": "inventory"},
    "1403": {"account_subcategory": "流动资产", "balance_sheet_item": "inventory"},
    "1405": {"account_subcategory": "流动资产", "balance_sheet_item": "inventory"},
    "1601": {"account_subcategory": "非流动资产", "balance_sheet_item": "fixed_assets_net"},
    "1602": {"account_subcategory": "非流动资产", "balance_sheet_item": "fixed_assets_net"},
    "1701": {"account_subcategory": "非流动资产", "balance_sheet_item": "intangible_assets_net"},
    "2001": {"account_subcategory": "流动负债", "balance_sheet_item": "short_term_borrowings"},
    "2202": {"account_subcategory": "流动负债", "balance_sheet_item": "accounts_payable"},
    "2203": {"account_subcategory": "流动负债", "balance_sheet_item": "advances_from_customers"},
    "2211": {"account_subcategory": "流动负债", "balance_sheet_item": "employee_benefits_payable"},
    "2221": {"account_subcategory": "流动负债", "balance_sheet_item": "taxes_payable"},
    "2241": {"account_subcategory": "流动负债", "balance_sheet_item": "other_payables"},
    "4001": {"account_category": "所有者权益", "equity_subcategory": "注册资本", "balance_sheet_item": "paid_in_capital"},
    "4002": {"account_category": "所有者权益", "equity_subcategory": "资本公积", "balance_sheet_item": "capital_reserve"},
    "4101": {"account_category": "所有者权益", "equity_subcategory": "盈余公积", "balance_sheet_item": "surplus_reserve"},
    "4103": {"account_category": "所有者权益", "equity_subcategory": "未分配利润", "balance_sheet_item": "retained_earnings"},
    "4104": {"account_category": "所有者权益", "equity_subcategory": "未分配利润", "balance_sheet_item": "retained_earnings"},
    "6001": {"cash_flow_item": "sales_cash_received"},
    "6401": {"cash_flow_item": "goods_services_cash_paid"},
    "6601": {"cash_flow_item": "other_operating_outflow"},
    "6801": {"cash_flow_item": "other_operating_outflow"},
}


def _default_design_for_code(code: str) -> dict[str, str]:
    if code in COA_DEFAULT_DESIGN:
        return dict(COA_DEFAULT_DESIGN[code])
    design: dict[str, str] = {}
    for pfx, item in sorted(DEFAULT_CODE_TO_CF_ITEM.items(), key=lambda x: len(x[0]), reverse=True):
        if code == pfx or code.startswith(pfx):
            design["cash_flow_item"] = item
            break
    for pfx, item in sorted(DEFAULT_CODE_TO_BS_ITEM.items(), key=lambda x: len(x[0]), reverse=True):
        if code == pfx or code.startswith(pfx):
            design["balance_sheet_item"] = item
            if code.startswith(("1", "14")) and not code.startswith(("15", "16", "17", "18")):
                design["account_subcategory"] = "流动资产"
            elif code.startswith(("15", "16", "17", "18")):
                design["account_subcategory"] = "非流动资产"
            elif code.startswith(("2",)):
                design["account_subcategory"] = "流动负债"
            break
    return design


INDUSTRY_ACCOUNT_TEMPLATES: dict[str, dict[str, Any]] = {
    "general": {
        "name": "通用企业",
        "description": "适用于多数小微和一般企业的基础科目集合。",
        "accounts": DEFAULT_ACCOUNTS,
    },
    "trading": {
        "name": "商贸企业",
        "description": "突出采购、库存商品、销售收入和销售费用核算。",
        "accounts": DEFAULT_ACCOUNTS + [
            {"code": "140501", "name": "库存商品-外购商品", "category": "asset", "direction": "debit", "parent_code": "1405", "level": 2},
            {"code": "220201", "name": "应付账款-供应商", "category": "liability", "direction": "credit", "parent_code": "2202", "level": 2},
            {"code": "600101", "name": "主营业务收入-商品销售", "category": "profit", "direction": "credit", "parent_code": "6001", "level": 2},
            {"code": "640101", "name": "主营业务成本-商品销售成本", "category": "profit", "direction": "debit", "parent_code": "6401", "level": 2},
            {"code": "660101", "name": "销售费用-平台服务费", "category": "profit", "direction": "debit", "parent_code": "6601", "level": 2},
        ],
    },
    "manufacturing": {
        "name": "制造企业",
        "description": "突出原材料、在产品、产成品、生产成本和制造费用核算。",
        "accounts": DEFAULT_ACCOUNTS + [
            {"code": "140301", "name": "原材料-主要材料", "category": "asset", "direction": "debit", "parent_code": "1403", "level": 2},
            {"code": "1407", "name": "在产品", "category": "asset", "direction": "debit"},
            {"code": "1408", "name": "产成品", "category": "asset", "direction": "debit"},
            {"code": "500101", "name": "生产成本-直接材料", "category": "cost", "direction": "debit", "parent_code": "5001", "level": 2},
            {"code": "500102", "name": "生产成本-直接人工", "category": "cost", "direction": "debit", "parent_code": "5001", "level": 2},
            {"code": "510101", "name": "制造费用-折旧费", "category": "cost", "direction": "debit", "parent_code": "5101", "level": 2},
        ],
    },
    "service": {
        "name": "服务业",
        "description": "突出服务收入、人工成本和项目服务成本核算。",
        "accounts": DEFAULT_ACCOUNTS + [
            {"code": "112201", "name": "应收账款-服务客户", "category": "asset", "direction": "debit", "parent_code": "1122", "level": 2},
            {"code": "500101", "name": "合同履约成本-人工成本", "category": "cost", "direction": "debit", "parent_code": "5001", "level": 2},
            {"code": "600101", "name": "主营业务收入-服务收入", "category": "profit", "direction": "credit", "parent_code": "6001", "level": 2},
            {"code": "640101", "name": "主营业务成本-服务成本", "category": "profit", "direction": "debit", "parent_code": "6401", "level": 2},
            {"code": "660201", "name": "管理费用-专业服务费", "category": "profit", "direction": "debit", "parent_code": "6602", "level": 2},
        ],
    },
}


def _get_config(db: Session | None = None) -> CoaCodeRuleConfig:
    """加载科目编码规则配置。"""
    return load_coa_code_config(db=db)


def _code_level(code: str, config: CoaCodeRuleConfig) -> int:
    """根据编码长度判断科目层级。"""
    lengths = config.total_code_lengths
    for level in range(1, config.max_level + 1):
        if len(code) == lengths[level]:
            return level
    raise ValueError(f"科目编码长度 {len(code)} 不符合规则，当前规则长度为 {set(lengths.values())}")


def _parent_code_of(code: str, level: int, config: CoaCodeRuleConfig) -> str | None:
    """计算给定编码的父级编码。"""
    if level <= 1:
        return None
    lengths = config.total_code_lengths
    parent_length = lengths[level - 1]
    return code[:parent_length]


def validate_account_code(
    code: str,
    parent_code: str | None = None,
    *,
    db: Session | None = None,
    config: CoaCodeRuleConfig | None = None,
) -> dict[str, Any]:
    """
    校验科目编码是否符合配置化规则。

    Args:
        code: 待校验的科目编码。
        parent_code: 显式指定的父级编码，可选。
        db: 数据库会话，用于加载数据库配置和校验父级存在性。
        config: 外部传入的配置对象，优先使用。

    Returns:
        dict: 包含 is_valid、level、parent_code、message 的校验结果。
    """
    result: dict[str, bool | int | str | None] = {"is_valid": False, "level": None, "parent_code": None, "message": ""}
    if not code:
        result["message"] = "科目编码不能为空"
        return result

    cfg = config or _get_config(db)
    if not re.match(r"^\d+$", code):
        result["message"] = "科目编码只能包含数字"
        return result

    try:
        level = _code_level(code, cfg)
    except ValueError as exc:
        result["message"] = str(exc)
        return result

    result["level"] = level
    inferred_parent = _parent_code_of(code, level, cfg)
    result["parent_code"] = inferred_parent

    # 校验每一层序号范围
    lengths = cfg.total_code_lengths
    for lvl in range(1, level + 1):
        rule = cfg.get_level_rule(lvl)
        segment = code[lengths[lvl - 1] if lvl > 1 else 0 : lengths[lvl]]
        if not rule.compiled_pattern.match(segment):
            result["message"] = f"第 {lvl} 层编码段 '{segment}' 不符合规则 {rule.pattern}"
            return result
        segment_value = int(segment)
        if segment_value < rule.min_value or segment_value > rule.max_value:
            result["message"] = (
                f"第 {lvl} 层编码段 '{segment}' 超出范围 [{rule.min_code}, {rule.max_code}]"
            )
            return result

    # 校验显式父级与推断父级一致
    if parent_code is not None and parent_code != inferred_parent:
        result["message"] = (
            f"编码 {code} 推断的父级为 {inferred_parent}，与传入的父级 {parent_code} 不一致"
        )
        return result

    # 校验父级存在
    if cfg.validation.require_parent_exists and inferred_parent is not None and db is not None:
        parent = get_by_code(db, inferred_parent)
        if not parent:
            result["message"] = f"父级科目 {inferred_parent} 不存在"
            return result

    result["is_valid"] = True
    return result


def generate_account_code(
    db: Session,
    parent_code: str | None = None,
    *,
    ledger_id: int | None = None,
    config: CoaCodeRuleConfig | None = None,
) -> str:
    """
    根据父级科目自动生成下一个可用的子科目编码。

    Args:
        db: 数据库会话。
        parent_code: 父级科目编码，None 表示生成一级科目编码。
        ledger_id: 可选的账簿过滤条件。
        config: 外部传入的配置对象。

    Returns:
        str: 生成的科目编码。

    Raises:
        ValueError: 父级科目不存在、层级已达最大深度或无可用编码。
    """
    cfg = config or _get_config(db)

    if parent_code is None:
        level = 1
        parent_length = 0
        parent = None
    else:
        parent = get_by_code(db, parent_code, ledger_id)
        if not parent:
            raise ValueError(f"父级科目 {parent_code} 不存在")
        parent_level = _code_level(parent_code, cfg)
        level = parent_level + 1
        if level > cfg.max_level:
            raise ValueError(f"已超过最大科目层级深度 {cfg.max_level}")
        parent_length = cfg.total_code_lengths[parent_level]

    rule = cfg.get_level_rule(level)
    prefix = parent_code or ""

    query = db.query(ChartOfAccounts.code)
    if ledger_id is not None:
        query = query.filter(ChartOfAccounts.ledger_id == ledger_id)
    if parent_code is None:
        query = query.filter(ChartOfAccounts.parent_code.is_(None))
    else:
        query = query.filter(ChartOfAccounts.code.like(f"{parent_code}%"))
    existing_codes = {row.code for row in query.all()}

    start = rule.min_value
    for seq in range(start, rule.max_value + 1):
        segment = str(seq).zfill(rule.segment_length) if cfg.auto_generation.pad_with_zero else str(seq)
        candidate = f"{prefix}{segment}"
        if cfg.auto_generation.skip_zero_ending and segment.endswith("00"):
            continue
        if candidate not in existing_codes:
            return candidate

    raise ValueError(f"父级科目 {parent_code} 下无可用子科目编码")


def _normalize_template_account(item: dict[str, Any]) -> dict[str, Any]:
    """标准化模板科目数据，补全父级和层级字段。"""
    account = dict(item)
    account.setdefault("parent_code", None)
    account.setdefault("level", 1)
    account.setdefault("is_terminal", True)
    return account


def list_industry_templates() -> list[dict[str, Any]]:
    return [
        {"code": code, "name": template["name"], "description": template["description"]}
        for code, template in INDUSTRY_ACCOUNT_TEMPLATES.items()
    ]


def get_industry_template(template_code: str) -> dict[str, Any]:
    template = INDUSTRY_ACCOUNT_TEMPLATES.get(template_code)
    if not template:
        raise LookupError("行业科目模板不存在")
    return {
        "code": template_code,
        "name": template["name"],
        "description": template["description"],
        "accounts": [_normalize_template_account(item) for item in template["accounts"]],
    }


def preview_industry_template(db: Session, template_code: str, ledger_id: int | None = None) -> dict[str, Any]:
    template = get_industry_template(template_code)
    query = db.query(ChartOfAccounts)
    if ledger_id is not None:
        query = query.filter(ChartOfAccounts.ledger_id == ledger_id)
    existing_accounts = {row.code: row for row in query.all()}
    accounts = []
    summary = {"new": 0, "skipped": 0, "conflicts": 0}
    for item in template["accounts"]:
        existing = existing_accounts.get(item["code"])
        status = "new"
        if existing:
            if existing.name == item["name"] and existing.category == item["category"] and existing.direction == item["direction"]:
                status = "skipped"
            else:
                status = "conflict"
        summary["new" if status == "new" else "skipped" if status == "skipped" else "conflicts"] += 1
        accounts.append({**item, "import_status": status})
    return {**template, "accounts": accounts, "summary": summary}


def import_industry_template(db: Session, template_code: str, ledger_id: int | None = None) -> dict[str, Any]:
    preview = preview_industry_template(db, template_code, ledger_id)
    created_accounts = []
    for item in preview["accounts"]:
        if item["import_status"] != "new":
            continue
        account = ChartOfAccounts(
            ledger_id=ledger_id,
            code=item["code"],
            name=item["name"],
            parent_code=item.get("parent_code"),
            level=item.get("level", 1),
            category=item["category"],
            direction=item["direction"],
            is_terminal=item.get("is_terminal", True),
            status="active",
            is_system=True,
        )
        db.add(account)
        created_accounts.append(item)
    if created_accounts:
        db.commit()
    return {"template": {"code": preview["code"], "name": preview["name"]}, "summary": preview["summary"], "created_accounts": created_accounts}


def init_default_accounts(db: Session, ledger_id: int | None = None) -> int:
    """启动时初始化默认会计科目，返回新增条数。"""
    query = db.query(ChartOfAccounts)
    if ledger_id is not None:
        query = query.filter(ChartOfAccounts.ledger_id == ledger_id)
    existing_codes = {row.code for row in query.all()}
    created = 0
    for item in DEFAULT_ACCOUNTS:
        if item["code"] in existing_codes:
            continue
        design = _default_design_for_code(item["code"])
        db.add(
            ChartOfAccounts(
                ledger_id=ledger_id,
                code=item["code"],
                name=item["name"],
                parent_code=None,
                level=1,
                category=item["category"],
                direction=item["direction"],
                account_category=design.get("account_category"),
                account_subcategory=design.get("account_subcategory"),
                equity_subcategory=design.get("equity_subcategory"),
                balance_sheet_item=design.get("balance_sheet_item"),
                cash_flow_item=design.get("cash_flow_item"),
                is_terminal=True,
                status="active",
                is_system=True,
            )
        )
        created += 1
    if created:
        db.commit()
    return created


def list_accounts(db: Session, ledger_id: int | None = None) -> list[ChartOfAccounts]:
    query = db.query(ChartOfAccounts)
    if ledger_id is not None:
        query = query.filter(ChartOfAccounts.ledger_id == ledger_id)
    return query.order_by(ChartOfAccounts.code).all()


def get_by_code(db: Session, code: str, ledger_id: int | None = None) -> ChartOfAccounts | None:
    query = db.query(ChartOfAccounts).filter(ChartOfAccounts.code == code)
    if ledger_id is not None:
        query = query.filter(ChartOfAccounts.ledger_id == ledger_id)
    return query.first()


def _validate_account_design_fields(payload: dict[str, Any]) -> None:
    account_category = payload.get("account_category")
    account_subcategory = payload.get("account_subcategory")
    equity_subcategory = payload.get("equity_subcategory")

    if account_category is None:
        return
    if account_category not in ACCOUNT_CATEGORY_MAP:
        raise ValueError("科目大类仅支持资产、负债、所有者权益")
    if account_category in {"资产", "负债"}:
        if account_subcategory not in ACCOUNT_CATEGORY_MAP[account_category]:
            raise ValueError("科目细类与科目大类不匹配")
        if equity_subcategory is not None:
            raise ValueError("资产或负债科目不应设置权益细类")
    if account_category == "所有者权益":
        if account_subcategory is not None:
            raise ValueError("所有者权益科目不应设置资产或负债细类")
        if equity_subcategory not in EQUITY_SUBCATEGORIES:
            raise ValueError("权益细类仅支持注册资本、资本公积、盈余公积、未分配利润")


def _normalize_account_design_fields(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    _validate_account_design_fields(normalized)
    equity_subcategory = normalized.get("equity_subcategory")
    if equity_subcategory in NON_DIVIDEND_EQUITY_SUBCATEGORIES:
        normalized["include_in_dividend_base"] = False
    elif equity_subcategory == "未分配利润" and normalized.get("include_in_dividend_base") is None:
        normalized["include_in_dividend_base"] = True
    elif normalized.get("account_category") != "所有者权益":
        normalized["include_in_dividend_base"] = None
    return normalized


def create_account(db: Session, payload: dict[str, Any]) -> ChartOfAccounts:
    payload = _normalize_account_design_fields(payload)
    ledger_id = payload.get("ledger_id")
    code = payload.get("code")
    parent_code = payload.get("parent_code")
    level = payload.get("level")

    if not code and parent_code:
        code = generate_account_code(db, parent_code, ledger_id=ledger_id)

    if not code:
        raise ValueError("科目编码不能为空，或请提供父级科目编码以便自动生成")

    if get_by_code(db, code, ledger_id):
        raise ValueError("科目代码已存在")

    validation = validate_account_code(code, parent_code, db=db)
    if not validation["is_valid"]:
        raise ValueError(f"科目编码校验失败：{validation['message']}")

    inferred_level = validation["level"]
    inferred_parent = validation["parent_code"]

    if level is not None and level != inferred_level:
        raise ValueError(f"指定的层级 {level} 与编码推断的层级 {inferred_level} 不一致")

    if parent_code is not None and parent_code != inferred_parent:
        raise ValueError(f"指定的父级编码 {parent_code} 与编码推断的父级 {inferred_parent} 不一致")

    account = ChartOfAccounts(
        ledger_id=ledger_id,
        code=code,
        name=payload["name"],
        parent_code=inferred_parent,
        level=inferred_level,
        category=payload["category"],
        direction=payload["direction"],
        account_category=payload.get("account_category"),
        account_subcategory=payload.get("account_subcategory"),
        equity_subcategory=payload.get("equity_subcategory"),
        balance_sheet_item=payload.get("balance_sheet_item"),
        cash_flow_item=payload.get("cash_flow_item"),
        include_in_dividend_base=payload.get("include_in_dividend_base"),
        is_terminal=payload.get("is_terminal", True),
        status="active",
        is_system=False,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, code: str, payload: dict[str, Any], ledger_id: int | None = None) -> ChartOfAccounts:
    account = get_by_code(db, code, ledger_id)
    if not account:
        raise LookupError("科目不存在")
    payload = _normalize_account_design_fields(payload)
    # 系统科目允许改名，但禁改 code/category
    if "name" in payload:
        account.name = payload["name"]
    if "balance_sheet_item" in payload:
        account.balance_sheet_item = payload["balance_sheet_item"]
    if "cash_flow_item" in payload:
        account.cash_flow_item = payload["cash_flow_item"]
    if not account.is_system:
        if "category" in payload:
            account.category = payload["category"]
        if "direction" in payload:
            account.direction = payload["direction"]
        if "account_category" in payload:
            account.account_category = payload["account_category"]
        if "account_subcategory" in payload:
            account.account_subcategory = payload["account_subcategory"]
        if "equity_subcategory" in payload:
            account.equity_subcategory = payload["equity_subcategory"]
        if "include_in_dividend_base" in payload:
            account.include_in_dividend_base = payload["include_in_dividend_base"]
        if "parent_code" in payload:
            account.parent_code = payload["parent_code"]
        if "is_terminal" in payload:
            account.is_terminal = payload["is_terminal"]
    db.commit()
    db.refresh(account)
    return account


def set_status(db: Session, code: str, status: str, ledger_id: int | None = None) -> ChartOfAccounts:
    account = get_by_code(db, code, ledger_id)
    if not account:
        raise LookupError("科目不存在")
    if status not in {"active", "disabled", "archived"}:
        raise ValueError("非法状态")
    account.status = status
    db.commit()
    db.refresh(account)
    return account


def delete_account(db: Session, code: str, ledger_id: int | None = None) -> None:
    account = get_by_code(db, code, ledger_id)
    if not account:
        raise LookupError("科目不存在")
    if account.is_system:
        raise PermissionError("准则默认科目不可删除，可停用")
    in_use = (
        db.query(AccountingEntry)
        .filter(AccountingEntry.account_code == code)
        .first()
    )
    if in_use:
        raise PermissionError("该科目存在业务记录，不可删除")
    db.delete(account)
    db.commit()


def save_coa_code_rule(db: Session, rule_content: dict[str, Any], name: str = "默认规则") -> Any:
    """
    保存科目编码规则到数据库。

    业务场景：支持通过数据库动态调整科目编码规则，优先级高于配置文件。

    Args:
        db: 数据库会话。
        rule_content: 规则内容字典，格式与配置文件一致。
        name: 规则名称。

    Returns:
        CoaCodeRule: 保存后的规则记录。
    """
    from app.db.models import CoaCodeRule

    rule = CoaCodeRule(
        name=name,
        version=rule_content.get("version", "1.0.0"),
        rule_content=rule_content,
        is_active=True,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule
