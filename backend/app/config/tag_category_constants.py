# -*- coding: utf-8 -*-
"""Tag 分类编码常量与别名（避免 account_detail 与往来/科目明细语义混淆）。"""

from __future__ import annotations

# 货币资金（1001/1002）专用维度：银行账户主数据
BANK_ACCOUNT_CATEGORY_CODE = "bank_account"

# 历史编码：与 bank_account 等价，导入/展示时逐步迁移
LEGACY_BANK_ACCOUNT_CATEGORY_CODES: frozenset[str] = frozenset(
    {"account_detail", BANK_ACCOUNT_CATEGORY_CODE}
)

# 系统内置、可在维度分类页扩展的常用分析类维度
STANDARD_VECTOR_CATEGORY_CODES: frozenset[str] = frozenset(
    {
        "fixed_asset_class",
        "fixed_asset_item",
        "cip_category",
        "cip_project",
        "loan_channel",
        "expense_type",
        "department",
        "project",
        "region",
        "product",
        "service",
        "material",
        "cost_element",
        "tax_type",
    }
)

DEFAULT_CATEGORY_META: dict[str, dict[str, str | None]] = {
    BANK_ACCOUNT_CATEGORY_CODE: {
        "name": "银行账户",
        "value_type": "entity",
        "source_table": "bank_accounts",
        "description": "仅用于货币资金科目(1001/1002)的户名/账号主数据",
    },
    # 兼容旧账簿已创建的分类
    "account_detail": {
        "name": "银行账户（旧编码 account_detail）",
        "value_type": "entity",
        "source_table": "bank_accounts",
        "description": "已弃用编码，请改用 bank_account；1122 等往来请用 customer/supplier",
    },
    "customer": {
        "name": "客户",
        "value_type": "entity",
        "source_table": "counterparties",
        "description": "1122 应收等；对应原辅助核算「客户」，主数据含名称/角色/信用代码/关联方等",
    },
    "supplier": {
        "name": "供应商",
        "value_type": "entity",
        "source_table": "counterparties",
        "description": "2202 应付等；对应原辅助核算「供应商」",
    },
    "counterparty_object": {
        "name": "往来对象",
        "value_type": "entity",
        "source_table": "counterparties",
        "description": "1221/2241 等其他应收应付；对应原辅助核算往来档案",
    },
    "product": {"name": "产品", "value_type": "text", "source_table": None, "description": "商品/存货；共享 EntryTag，跨模块复用"},
    "service": {"name": "服务", "value_type": "text", "source_table": None, "description": "劳务/服务型收入；共享 EntryTag"},
    "material": {"name": "材料", "value_type": "text", "source_table": None},
    "cost_element": {"name": "成本要素", "value_type": "text", "source_table": None},
    "expense_type": {"name": "费用类型", "value_type": "text", "source_table": None, "description": "替代费用类辅助核算；存 EntryTag"},
    "department": {"name": "部门", "value_type": "text", "source_table": None, "description": "替代部门辅助核算；存 EntryTag"},
    "project": {"name": "项目", "value_type": "text", "source_table": None, "description": "替代项目辅助核算；存 EntryTag"},
    "region": {"name": "区域", "value_type": "text", "source_table": None},
    "tax_type": {"name": "税费类型", "value_type": "text", "source_table": None},
    "fixed_asset_class": {"name": "固定资产类别", "value_type": "text", "source_table": None},
    "fixed_asset_item": {"name": "固定资产项目", "value_type": "text", "source_table": None},
    "cip_category": {"name": "在建工程类别", "value_type": "text", "source_table": None},
    "cip_project": {"name": "在建工程项目", "value_type": "text", "source_table": None},
    "loan_channel": {"name": "借款渠道", "value_type": "text", "source_table": None},
}


def normalize_tag_category_code(category_code: str | None) -> str:
    """将旧编码 account_detail 规范为 bank_account。"""
    code = (category_code or "").strip()
    if code == "account_detail":
        return BANK_ACCOUNT_CATEGORY_CODE
    return code


def is_bank_account_category(category_code: str | None) -> bool:
    return (category_code or "").strip() in LEGACY_BANK_ACCOUNT_CATEGORY_CODES
