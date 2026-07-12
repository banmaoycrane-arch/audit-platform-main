# -*- coding: utf-8 -*-
"""
模块功能：财务审计文档字段别名目录
业务场景：统一维护不同文档类型的字段别名映射，供解析引擎双引擎对比、
        字段标准化、动态规则加载等模块共享使用。
政策依据：财务数据标准化与跨引擎字段对齐需求。
输入数据：原始字段名、文档类型。
输出结果：标准化后的字段名或字段映射关系。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建，聚合合同、发票、银行流水、会计分录等字段别名。
"""
from typing import Any


# =============================================================================
# 通用字段别名（适用于所有文档类型）
# =============================================================================
_COMMON_FIELD_ALIASES: dict[str, list[str]] = {
    "document_no": ["doc_no", "voucher_no", "voucher_number", "凭证号", "凭证编号", "单据号", "单据编号"],
    "date": ["doc_date", "voucher_date", "document_date", "凭证日期", "日期", "发生日期"],
    "summary": ["abstract", "description", "remark", "摘要", "备注", "用途"],
}


# =============================================================================
# 合同类文档字段别名
# =============================================================================
_CONTRACT_FIELD_ALIASES: dict[str, list[str]] = {
    "contract_no": ["contract_number", "contract_id", "agreement_no", "合同编号", "合同号", "协议编号"],
    "contract_name": ["contract_title", "agreement_name", "项目名称", "合同名称", "协议名称"],
    "party_a_name": ["甲方", "甲方名称", "委托方", "发包方", "买方", "采购方", "甲方（买方）"],
    "party_b_name": ["乙方", "乙方名称", "受托方", "承包方", "卖方", "供应方", "乙方（卖方）"],
    "party_a_tax_id": ["甲方税号", "甲方统一社会信用代码", "甲方纳税人识别号"],
    "party_b_tax_id": ["乙方税号", "乙方统一社会信用代码", "乙方纳税人识别号"],
    "sign_date": ["contract_date", "签订日期", "签署日期", "签约日期", "日期"],
    "contract_amount": ["contract_value", "total_amount", "amount", "合同金额", "合同总价", "合同价款", "合同总额", "标的额", "总金额", "总价款"],
    "contract_term": ["term", "duration", "合同期限", "合同有效期", "履行期限"],
    "payment_terms": ["payment_method", "payment_schedule", "付款方式", "付款条件", "结算方式"],
    "project_name": ["project", "工程名称", "项目名"],
    "contract_subject_matter": ["标的物", "标的", "合同标的", "服务内容", "货物名称"],
    "key_clauses": ["主要条款", "关键条款", "合同条款"],
    "tax_clause": ["涉税条款", "税务条款", "发票约定", "税率约定", "开票约定"],
}


# =============================================================================
# 发票类文档字段别名
# =============================================================================
_INVOICE_FIELD_ALIASES: dict[str, list[str]] = {
    "invoice_no": ["invoice_number", "发票号码", "发票编号"],
    "invoice_code": ["发票代码"],
    "invoice_date": ["开票日期", "发票日期"],
    "buyer_name": ["购买方", "购方", "买方名称", "采购方名称"],
    "seller_name": ["销售方", "销方", "卖方名称", "供应方名称"],
    "total_amount": ["价税合计", "合计金额", "总金额"],
    "amount_excl_tax": ["不含税金额", "金额", "货款"],
    "tax_amount": ["税额", "税金"],
    "tax_rate": ["税率"],
    "tax_item": ["税目", "税收分类", "税收分类编码", "货物或应税劳务名称"],
    "specification": ["规格型号", "规格", "型号"],
    "unit": ["单位", "计量单位"],
    "quantity": ["数量"],
    "unit_price": ["单价", "不含税单价"],
}


# =============================================================================
# 银行流水/对账单字段别名
# =============================================================================
_BANK_FIELD_ALIASES: dict[str, list[str]] = {
    "transaction_date": ["交易日期", "日期", "入账日期"],
    "transaction_amount": ["交易金额", "发生额", "金额"],
    "counterparty_name": ["对方户名", "对方名称", "对方单位", "交易对手", "往来单位", "客户名称", "供应商名称"],
    "counterparty_bank": ["对方银行", "对方开户行", "对方行名", "收款行行名", "付款行行名"],
    "counterparty_account_no": ["对方账号", "对方账户", "收款人账号", "付款人账号"],
    "bank_name": ["银行名称", "开户行"],
    "account_no": ["账号", "银行账号"],
    "debit_amount": ["debit", "借方金额", "借方"],
    "credit_amount": ["credit", "贷方金额", "贷方"],
    "balance": ["余额"],
}


# =============================================================================
# 会计分录/记账凭证字段别名
# =============================================================================
_ENTRY_FIELD_ALIASES: dict[str, list[str]] = {
    "subject_code": ["account_code", "account_subject", "科目代码", "科目编号"],
    "subject_name": ["account_name", "科目名称", "科目"],
    "debit_amount": ["debit", "借方金额", "借方"],
    "credit_amount": ["credit", "贷方金额", "贷方"],
    "amount": ["total_amount", "money", "sum", "金额", "发生额", "交易金额"],
}


# =============================================================================
# 按文档类型聚合的别名目录
# =============================================================================
DOCUMENT_TYPE_FIELD_ALIASES: dict[str, dict[str, list[str]]] = {
    "contract": _CONTRACT_FIELD_ALIASES,
    "invoice": _INVOICE_FIELD_ALIASES,
    "bank_statement": _BANK_FIELD_ALIASES,
    "accounting_entry": _ENTRY_FIELD_ALIASES,
}


# =============================================================================
# 全量别名表（向后兼容，供不区分文档类型的场景使用）
# =============================================================================
ALL_FIELD_ALIASES: dict[str, list[str]] = {}
for _aliases in [_COMMON_FIELD_ALIASES, _CONTRACT_FIELD_ALIASES, _INVOICE_FIELD_ALIASES, _BANK_FIELD_ALIASES, _ENTRY_FIELD_ALIASES]:
    for standard_name, alias_list in _aliases.items():
        ALL_FIELD_ALIASES.setdefault(standard_name, []).extend(alias_list)


# 去重并保持顺序
for _standard_name in ALL_FIELD_ALIASES:
    _seen: set[str] = set()
    _deduped: list[str] = []
    for _alias in ALL_FIELD_ALIASES[_standard_name]:
        if _alias not in _seen:
            _seen.add(_alias)
            _deduped.append(_alias)
    ALL_FIELD_ALIASES[_standard_name] = _deduped


def get_field_aliases(document_type: str | None = None) -> dict[str, list[str]]:
    """
    获取指定文档类型的字段别名映射表。

    业务逻辑：
        1. 如果传入 document_type 且目录中存在，返回该类型的别名表叠加通用别名。
        2. 否则返回全量别名表。

    Args:
        document_type: 文档类型，如 contract/invoice/bank_statement/accounting_entry。

    Returns:
        dict[str, list[str]]: 标准字段名到别名列表的映射。
    """
    type_aliases = DOCUMENT_TYPE_FIELD_ALIASES.get(document_type, {}) if document_type else {}

    combined: dict[str, list[str]] = {}
    for standard_name, alias_list in _COMMON_FIELD_ALIASES.items():
        combined[standard_name] = list(alias_list)

    for standard_name, alias_list in type_aliases.items():
        if standard_name in combined:
            # 合并并去重
            seen = set(combined[standard_name])
            for alias in alias_list:
                if alias not in seen:
                    seen.add(alias)
                    combined[standard_name].append(alias)
        else:
            combined[standard_name] = list(alias_list)

    return combined


def normalize_field_name(field_name: str, document_type: str | None = None) -> str:
    """
    将字段名标准化为统一的业务字段名。

    业务逻辑：
        1. 对输入字段名做简单标准化（小写、空格/连字符转下划线）。
        2. 先在目标文档类型的别名表中查找。
        3. 未命中则在全量别名表中查找。
        4. 仍未命中返回原始标准化后的字段名。

    Args:
        field_name: 原始字段名。
        document_type: 文档类型（可选）。

    Returns:
        str: 标准化后的字段名。
    """
    if not field_name:
        return ""

    text = str(field_name).strip().lower()
    text = text.replace(" ", "_").replace("-", "_")

    # 1. 按文档类型查找
    type_aliases = get_field_aliases(document_type)
    if text in type_aliases:
        return text

    for standard_name, aliases in type_aliases.items():
        normalized_aliases = [a.strip().lower().replace(" ", "_").replace("-", "_") for a in aliases]
        if text in normalized_aliases:
            return standard_name

    # 2. 在全量别名表中查找
    if text in ALL_FIELD_ALIASES:
        return text

    for standard_name, aliases in ALL_FIELD_ALIASES.items():
        normalized_aliases = [a.strip().lower().replace(" ", "_").replace("-", "_") for a in aliases]
        if text in normalized_aliases:
            return standard_name

    return text


def build_field_mapping(
    data: dict[str, Any],
    document_type: str | None = None,
) -> dict[str, list[str]]:
    """
    建立标准化字段名到原始字段名的映射。

    Args:
        data: 原始解析结果数据。
        document_type: 文档类型（可选）。

    Returns:
        dict[str, list[str]]: 标准化字段名到原始字段名列表的映射。
    """
    mapping: dict[str, list[str]] = {}
    for field_name in data.keys():
        normalized = normalize_field_name(field_name, document_type)
        if normalized:
            mapping.setdefault(normalized, []).append(field_name)
    return mapping
