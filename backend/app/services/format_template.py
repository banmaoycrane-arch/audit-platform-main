"""
会计凭证格式模板系统

支持多种格式的字段别名映射，实现智能模板匹配
"""

from typing import Any

# 标准会计分录字段定义
STANDARD_FIELDS = {
    "voucher_no": "凭证号",
    "voucher_date": "凭证日期",
    "summary": "摘要",
    "account_code": "科目编码",
    "account_name": "科目名称",
    "debit_amount": "借方金额",
    "credit_amount": "贷方金额",
    "counterparty": "往来单位",
}

# 预定义格式模板
ACCOUNTING_TEMPLATES: dict[str, dict[str, Any]] = {
    "标准中文": {
        "priority": 100,
        "fields": {
            "voucher_no": ["凭证号", "凭证编号", "编号", "单据号"],
            "voucher_date": ["凭证日期", "记账日期", "日期", "业务日期", "制单日期"],
            "summary": ["摘要", "说明", "描述", "交易描述", "事由"],
            "account_code": ["科目编码", "科目代码", "科目号", "会计科目编码"],
            "account_name": ["科目名称", "会计科目", "科目", "账户名称", "会计科目名称"],
            "debit_amount": ["借方金额", "借方", "借发生额", "借方发生额", " debit"],
            "credit_amount": ["贷方金额", "贷方", "贷发生额", "贷方发生额", "credit"],
            "counterparty": ["往来单位", "供应商", "客户", "对方单位", "交易对方", "单位"],
        },
        "required": ["summary", "account_name"],
        "optional": ["voucher_no", "voucher_date", "account_code", "debit_amount", "credit_amount", "counterparty"],
    },
    "标准英文": {
        "priority": 90,
        "fields": {
            "voucher_no": ["voucher_no", "voucher", "doc_no", "document_no", "reference"],
            "voucher_date": ["voucher_date", "date", "trans_date", "transaction_date", "posting_date"],
            "summary": ["summary", "description", "memo", "narration", "details"],
            "account_code": ["account_code", "account_id", "gl_account", "account_number"],
            "account_name": ["account_name", "account_title", "account", "gl_account_name", "description"],
            "debit_amount": ["debit_amount", "debit", "dr", "debit_amt"],
            "credit_amount": ["credit_amount", "credit", "cr", "credit_amt"],
            "counterparty": ["counterparty", "supplier", "customer", "vendor", "payee", "party"],
        },
        "required": ["summary", "account_name"],
        "optional": ["voucher_no", "voucher_date", "account_code", "debit_amount", "credit_amount", "counterparty"],
    },
    "金蝶K3标准": {
        "priority": 80,
        "fields": {
            "voucher_no": ["凭证字", "凭证号", "编号", "凭证编号"],
            "voucher_date": ["日期", "记账日期", "凭证日期"],
            "summary": ["科目", "科目名称", "摘要"],
            "account_code": ["科目代码", "科目编码"],
            "account_name": ["科目全称", "科目名称"],
            "debit_amount": ["借方", "借方金额", "借方本位币"],
            "credit_amount": ["贷方", "贷方金额", "贷方本位币"],
            "counterparty": ["往来单位", "供应商", "客户"],
        },
        "required": ["summary", "account_name", "debit_amount", "credit_amount"],
        "optional": ["voucher_no", "voucher_date", "account_code", "counterparty"],
    },
    "用友U8标准": {
        "priority": 80,
        "fields": {
            "voucher_no": ["凭证编号", "凭证号", "编号"],
            "voucher_date": ["制单日期", "凭证日期", "日期"],
            "summary": ["摘要", "科目摘要", "分录摘要"],
            "account_code": ["科目编码", "科目代码"],
            "account_name": ["科目名称", "会计科目"],
            "debit_amount": ["借方金额", "借方"],
            "credit_amount": ["贷方金额", "贷方"],
            "counterparty": ["往来单位", "部门", "个人"],
        },
        "required": ["summary", "account_name"],
        "optional": ["voucher_no", "voucher_date", "account_code", "debit_amount", "credit_amount", "counterparty"],
    },
    "SAP格式": {
        "priority": 75,
        "fields": {
            "voucher_no": ["Document No", "Doc No", "Reference"],
            "voucher_date": ["Posting Date", "Document Date"],
            "summary": ["Item Text", "Description", "Explanation"],
            "account_code": ["G/L Account", "Account", "GL Account"],
            "account_name": ["Short Text", "Account Text", "Item Text"],
            "debit_amount": ["Debit Amount", "Debit", "DR"],
            "credit_amount": ["Credit Amount", "Credit", "CR"],
            "counterparty": ["Business Partner", "Vendor", "Customer"],
        },
        "required": ["account_code", "account_name"],
        "optional": ["voucher_no", "voucher_date", "summary", "debit_amount", "credit_amount", "counterparty"],
    },
    "Oracle EBS格式": {
        "priority": 75,
        "fields": {
            "voucher_no": ["VOUCHER_NUM", "DOC_SEQUENCE_VALUE"],
            "voucher_date": ["VOUCHER_DATE", "GL_DATE"],
            "summary": ["DESCRIPTION", "LINE_DESCRIPTION", "REMARKS"],
            "account_code": ["CODE_COMBINATION_ID", "ACCOUNT", "SEGMENT1"],
            "account_name": ["ACCOUNT_DESCRIPTION", "ACCOUNT_NAME"],
            "debit_amount": ["DEBIT", "ENTERED_DR", "ACCOUNTED_DR"],
            "credit_amount": ["CREDIT", "ENTERED_CR", "ACCOUNTED_CR"],
            "counterparty": ["VENDOR_NAME", "CUSTOMER_NAME", "SUPPLIER_NAME"],
        },
        "required": ["account_code", "account_name"],
        "optional": ["voucher_no", "voucher_date", "summary", "debit_amount", "credit_amount", "counterparty"],
    },
}


def normalize_header(header: str) -> str:
    """标准化表头名称"""
    return str(header).strip().lower()


def build_alias_index() -> dict[str, dict[str, str]]:
    """构建别名索引（别名 -> 标准字段名）"""
    index: dict[str, dict[str, str]] = {}
    for template_name, template in ACCOUNTING_TEMPLATES.items():
        for field_name, aliases in template["fields"].items():
            if field_name not in index:
                index[field_name] = {}
            for alias in aliases:
                key = normalize_header(alias)
                index[key] = field_name
    return index


# 全局别名索引（延迟初始化）
_alias_index: dict[str, dict[str, str]] | None = None


def get_alias_index() -> dict[str, dict[str, str]]:
    """获取别名索引（单例）"""
    global _alias_index
    if _alias_index is None:
        _alias_index = build_alias_index()
    return _alias_index


def match_header(header: str, template: dict[str, Any] | None = None) -> str | None:
    """
    匹配表头到标准字段

    Args:
        header: 表头名称
        template: 可选的模板（用于优先匹配特定模板）

    Returns:
        标准字段名或 None
    """
    normalized = normalize_header(header)
    index = get_alias_index()

    # 精确匹配
    if normalized in index:
        return index[normalized]

    # 模糊匹配（包含）
    for alias, field in index.items():
        if normalized in alias or alias in normalized:
            return field

    return None


def detect_template(headers: list[str]) -> tuple[str | None, dict[str, str]]:
    """
    检测最适合的模板

    Args:
        headers: 表头列表

    Returns:
        (模板名, 映射表) 或 (None, {})
    """
    if not headers:
        return None, {}

    header_set = {normalize_header(h) for h in headers}
    best_template: str | None = None
    best_score = 0
    best_mapping: dict[str, str] = {}

    for template_name, template in sorted(ACCOUNTING_TEMPLATES.items(), key=lambda x: x[1].get("priority", 0), reverse=True):
        mapping: dict[str, str] = {}
        score = 0

        for header in headers:
            matched_field = match_header(header, template)
            if matched_field:
                mapping[normalize_header(header)] = matched_field
                score += 1

        if score > best_score:
            best_score = score
            best_template = template_name
            best_mapping = mapping

    # 计算匹配率
    match_rate = best_score / len(headers) if headers else 0

    if match_rate < 0.3:  # 匹配率低于 30% 认为不匹配
        return None, best_mapping

    return best_template, best_mapping


def get_template_fields(template_name: str) -> dict[str, list[str]]:
    """获取模板的字段定义"""
    template = ACCOUNTING_TEMPLATES.get(template_name, {})
    return template.get("fields", {})


def get_required_fields(template_name: str) -> list[str]:
    """获取模板的必填字段"""
    template = ACCOUNTING_TEMPLATES.get(template_name, {})
    return template.get("required", [])


def is_valid_template(template_name: str) -> bool:
    """检查模板是否有效"""
    return template_name in ACCOUNTING_TEMPLATES


def add_custom_template(name: str, fields: dict[str, list[str]], required: list[str] | None = None, priority: int = 50) -> None:
    """
    添加自定义模板

    Args:
        name: 模板名称
        fields: 字段映射 {标准字段名: [别名列表]}
        required: 必填字段列表
        priority: 优先级（越高越先匹配）
    """
    ACCOUNTING_TEMPLATES[name] = {
        "priority": priority,
        "fields": fields,
        "required": required or [],
        "optional": [f for f in STANDARD_FIELDS if f not in (required or [])],
    }
    # 清除缓存
    global _alias_index
    _alias_index = None
