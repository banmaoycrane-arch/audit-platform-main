"""会计科目（CoA）服务：CRUD + 默认种子。"""
from typing import Iterable

from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, ChartOfAccounts


ACCOUNT_CATEGORY_MAP = {
    "资产": {"流动资产", "非流动资产"},
    "负债": {"流动负债", "长期负债"},
    "所有者权益": set(),
}
EQUITY_SUBCATEGORIES = {"注册资本", "资本公积", "盈余公积", "未分配利润"}
NON_DIVIDEND_EQUITY_SUBCATEGORIES = {"注册资本", "资本公积", "盈余公积"}


# 《企业会计准则》一级 + 高频二级（精简集合）
DEFAULT_ACCOUNTS: list[dict] = [
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


INDUSTRY_ACCOUNT_TEMPLATES: dict[str, dict] = {
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


def _normalize_template_account(item: dict) -> dict:
    account = dict(item)
    account.setdefault("parent_code", None)
    account.setdefault("level", 1)
    account.setdefault("is_terminal", True)
    return account


def list_industry_templates() -> list[dict]:
    return [
        {"code": code, "name": template["name"], "description": template["description"]}
        for code, template in INDUSTRY_ACCOUNT_TEMPLATES.items()
    ]


def get_industry_template(template_code: str) -> dict:
    template = INDUSTRY_ACCOUNT_TEMPLATES.get(template_code)
    if not template:
        raise LookupError("行业科目模板不存在")
    return {
        "code": template_code,
        "name": template["name"],
        "description": template["description"],
        "accounts": [_normalize_template_account(item) for item in template["accounts"]],
    }


def preview_industry_template(db: Session, template_code: str, ledger_id: int | None = None) -> dict:
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


def import_industry_template(db: Session, template_code: str, ledger_id: int | None = None) -> dict:
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
        db.add(
            ChartOfAccounts(
                ledger_id=ledger_id,
                code=item["code"],
                name=item["name"],
                parent_code=None,
                level=1,
                category=item["category"],
                direction=item["direction"],
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


def _validate_account_design_fields(payload: dict) -> None:
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


def _normalize_account_design_fields(payload: dict) -> dict:
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


def create_account(db: Session, payload: dict) -> ChartOfAccounts:
    payload = _normalize_account_design_fields(payload)
    ledger_id = payload.get("ledger_id")
    if get_by_code(db, payload["code"], ledger_id):
        raise ValueError("科目代码已存在")
    parent_code = payload.get("parent_code")
    if parent_code and not get_by_code(db, parent_code, ledger_id):
        raise ValueError("父级科目不存在")
    account = ChartOfAccounts(
        ledger_id=ledger_id,
        code=payload["code"],
        name=payload["name"],
        parent_code=parent_code,
        level=payload.get("level", 1),
        category=payload["category"],
        direction=payload["direction"],
        account_category=payload.get("account_category"),
        account_subcategory=payload.get("account_subcategory"),
        equity_subcategory=payload.get("equity_subcategory"),
        include_in_dividend_base=payload.get("include_in_dividend_base"),
        is_terminal=payload.get("is_terminal", True),
        status="active",
        is_system=False,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def update_account(db: Session, code: str, payload: dict, ledger_id: int | None = None) -> ChartOfAccounts:
    account = get_by_code(db, code, ledger_id)
    if not account:
        raise LookupError("科目不存在")
    payload = _normalize_account_design_fields(payload)
    # 系统科目允许改名，但禁改 code/category
    if "name" in payload:
        account.name = payload["name"]
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
