# -*- coding: utf-8 -*-
"""
模块功能：规则引擎解析器（各文档类型专用）
业务场景：使用规则和正则表达式解析各类财务文档的结构化数据
政策依据：各类会计准则（CAS 1/9/14/22等）、发票管理办法、银行结算办法
输入数据：文件路径、提取的文本内容、文档类型
输出结果：结构化数据字典
创建日期：2026-06-26
更新记录：
    2026-06-26  初始创建，实现发票、银行流水、合同、入库单等规则解析
"""

import logging
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# =============================================================================
# 通用工具函数
# =============================================================================

def _extract_date(text: str, patterns: list[str]) -> Optional[str]:
    """
    从文本中提取日期
    
    Args:
        text: 文本内容
        patterns: 日期正则表达式列表
        
    Returns:
        str: 格式化的日期字符串 YYYY-MM-DD，或 None
    """
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            date_str = date_str.replace('/', '-').replace('.', '-')
            try:
                if len(date_str) == 8 and date_str.isdigit():
                    return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                parts = date_str.split('-')
                if len(parts) == 3:
                    year, month, day = parts
                    if len(year) == 2:
                        year = f"20{year}"
                    return f"{year.zfill(4)}-{month.zfill(2)}-{day.zfill(2)}"
            except Exception:
                pass
    return None


def _extract_amount(text: str, patterns: list[str]) -> Optional[Decimal]:
    """
    从文本中提取金额
    
    Args:
        text: 文本内容
        patterns: 金额正则表达式列表
        
    Returns:
        Decimal: 金额（保留2位小数），或 None
    """
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            amount_str = match.group(1).replace(',', '').replace(' ', '')
            try:
                return Decimal(amount_str).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            except Exception:
                pass
    return None


def _extract_number(text: str, patterns: list[str]) -> Optional[str]:
    """
    从文本中提取编号
    
    Args:
        text: 文本内容
        patterns: 编号正则表达式列表
        
    Returns:
        str: 编号字符串，或 None
    """
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


# =============================================================================
# 发票规则解析器
# =============================================================================

def parse_invoice_rules(text: str, file_path: str = "") -> dict[str, Any]:
    """
    发票规则解析器
    
    功能描述：使用规则和正则表达式解析发票的结构化数据
    业务逻辑：
        1. 提取发票号码、代码
        2. 提取开票日期
        3. 提取购买方和销售方信息
        4. 提取金额信息（不含税金额、税额、价税合计）
        5. 提取货物/服务名称
        6. 提取税率
    
    会计口径：符合《发票管理办法》和增值税发票规范
    
    Args:
        text: 提取的文本内容
        file_path: 文件路径
        
    Returns:
        dict: 结构化发票数据
    """
    data: dict[str, Any] = {
        "document_type": "invoice",
        "invoice_no": None,
        "invoice_code": None,
        "invoice_date": None,
        "seller_name": None,
        "seller_tax_id": None,
        "seller_address": None,
        "seller_phone": None,
        "buyer_name": None,
        "buyer_tax_id": None,
        "buyer_address": None,
        "buyer_phone": None,
        "goods_name": None,
        "quantity": None,
        "unit_price": None,
        "amount_excl_tax": None,
        "tax_rate": None,
        "tax_amount": None,
        "total_amount": None,
    }

    # 发票号码
    invoice_no_patterns = [
        r'发票号码[：:]\s*(\d+)',
        r'发票号[：:]\s*(\d+)',
        r'No[：:]\s*(\d+)',
        r'票号[：:]\s*(\d+)',
    ]
    data["invoice_no"] = _extract_number(text, invoice_no_patterns)

    # 发票代码
    invoice_code_patterns = [
        r'发票代码[：:]\s*(\d+)',
        r'发票代码\s*(\d+)',
    ]
    data["invoice_code"] = _extract_number(text, invoice_code_patterns)

    # 开票日期
    date_patterns = [
        r'开票日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'开票日期[：:]\s*(\d{8})',
        r'日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'日期[：:]\s*(\d{8})',
    ]
    data["invoice_date"] = _extract_date(text, date_patterns)

    # 销售方名称
    seller_name_patterns = [
        r'销售方名称[：:]\s*(.*?)(\n|购买方|纳税人识别号)',
        r'销货方名称[：:]\s*(.*?)(\n|购买方|纳税人识别号)',
        r'卖方[：:]\s*(.*?)(\n|购买方|纳税人)',
    ]
    for pattern in seller_name_patterns:
        match = re.search(pattern, text)
        if match:
            data["seller_name"] = match.group(1).strip()
            break

    # 销售方税号
    seller_tax_id_patterns = [
        r'销售方纳税人识别号[：:]\s*(\d+)',
        r'卖方税号[：:]\s*(\d+)',
    ]
    data["seller_tax_id"] = _extract_number(text, seller_tax_id_patterns)

    # 购买方名称
    buyer_name_patterns = [
        r'购买方名称[：:]\s*(.*?)(\n|销售方|纳税人识别号)',
        r'购货方名称[：:]\s*(.*?)(\n|销售方|纳税人识别号)',
        r'买方[：:]\s*(.*?)(\n|销售方|纳税人)',
    ]
    for pattern in buyer_name_patterns:
        match = re.search(pattern, text)
        if match:
            data["buyer_name"] = match.group(1).strip()
            break

    # 购买方税号
    buyer_tax_id_patterns = [
        r'购买方纳税人识别号[：:]\s*(\d+)',
        r'买方税号[：:]\s*(\d+)',
    ]
    data["buyer_tax_id"] = _extract_number(text, buyer_tax_id_patterns)

    # 价税合计（大写和小写）
    total_amount_patterns = [
        r'价税合计.*?([\d,]+\.\d{2})',
        r'合计.*?([\d,]+\.\d{2})',
        r'￥\s*([\d,]+\.\d{2})',
        r'¥\s*([\d,]+\.\d{2})',
    ]
    data["total_amount"] = _extract_amount(text, total_amount_patterns)

    # 不含税金额
    amount_excl_tax_patterns = [
        r'金额.*?([\d,]+\.\d{2})',
        r'不含税.*?([\d,]+\.\d{2})',
        r'小计.*?([\d,]+\.\d{2})',
    ]
    if data["total_amount"] is None:
        data["amount_excl_tax"] = _extract_amount(text, amount_excl_tax_patterns)

    # 税额
    tax_amount_patterns = [
        r'税额.*?([\d,]+\.\d{2})',
        r'税合计.*?([\d,]+\.\d{2})',
    ]
    data["tax_amount"] = _extract_amount(text, tax_amount_patterns)

    # 税率
    tax_rate_patterns = [
        r'税率[：:]\s*([\d.]+)',
        r'(\d+\.?\d*)%',
    ]
    for pattern in tax_rate_patterns:
        match = re.search(pattern, text)
        if match:
            data["tax_rate"] = match.group(1).strip()
            break

    # 货物/服务名称
    goods_patterns = [
        r'货物或应税劳务、服务名称[：:]\s*(.*?)(\n|规格|单位)',
        r'名称[：:]\s*(.*?)(\n|规格|单位|数量)',
    ]
    for pattern in goods_patterns:
        match = re.search(pattern, text)
        if match:
            data["goods_name"] = match.group(1).strip()
            break

    # 货物数量
    quantity_patterns = [
        r'数量[：:]\s*(\d+(\.\d+)?)',
        r'Qty[：:]\s*(\d+(\.\d+)?)',
        r'(\d+(\.\d+)?)\s*[个件台套]',
    ]
    for pattern in quantity_patterns:
        match = re.search(pattern, text)
        if match:
            data["quantity"] = match.group(1).strip()
            break

    return data


# =============================================================================
# 银行流水规则解析器
# =============================================================================

def parse_bank_statement_rules(text: str, file_path: str = "") -> dict[str, Any]:
    """
    银行流水规则解析器
    
    功能描述：使用规则和正则表达式解析银行流水的结构化数据
    业务逻辑：
        1. 提取账户信息（户名、账号、开户行）
        2. 提取交易日期范围
        3. 提取期初余额、期末余额
        4. 提取交易记录列表
        5. 提取收入合计、支出合计
        6. 电子回单专用：提取回单号、交易时间、金额、业务种类等
    
    会计口径：符合银行结算办法和企业银行对账规范
    
    Args:
        text: 提取的文本内容
        file_path: 文件路径
        
    Returns:
        dict: 结构化银行流水数据
    """
    data: dict[str, Any] = {
        "document_type": "bank_statement",
        "account_name": None,
        "account_no": None,
        "bank_name": None,
        "statement_period_start": None,
        "statement_period_end": None,
        "opening_balance": None,
        "closing_balance": None,
        "total_inflow": None,
        "total_outflow": None,
        "transactions": [],
        "receipt_no": None,
        "transaction_time": None,
        "transaction_amount": None,
        "transaction_amount_text": None,
        "business_type": None,
        "transaction_status": None,
        "counterparty_name": None,
        "counterparty_account_no": None,
        "counterparty_bank": None,
        "purpose": None,
        "transaction_serial_no": None,
    }

    # 电子回单号
    receipt_no_patterns = [
        r'电子回单号[：:]\s*(.*?)(\n|\s)',
        r'回单号[：:]\s*(.*?)(\n|\s)',
        r'回单编号[：:]\s*(.*?)(\n|\s)',
    ]
    for pattern in receipt_no_patterns:
        match = re.search(pattern, text)
        if match:
            data["receipt_no"] = match.group(1).strip()
            break

    # 交易时间
    transaction_time_patterns = [
        r'交易时间[：:]\s*(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2})',
        r'交易时间[：:]\s*(\d{4}-\d{2}-\d{2}\d{2}:\d{2}:\d{2})',
        r'时间[：:]\s*(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2}:\d{2})',
    ]
    for pattern in transaction_time_patterns:
        match = re.search(pattern, text)
        if match:
            data["transaction_time"] = match.group(1).strip()
            break

    # 业务种类
    business_type_patterns = [
        r'业务种类[：:]\s*(.*?)(\n|\s)',
        r'业务类型[：:]\s*(.*?)(\n|\s)',
        r'种类[：:]\s*(.*?)(\n|\s)',
    ]
    for pattern in business_type_patterns:
        match = re.search(pattern, text)
        if match:
            data["business_type"] = match.group(1).strip()
            break

    # 交易状态
    status_patterns = [
        r'交易状态[：:]\s*(.*?)(\n|\s)',
        r'状态[：:]\s*(.*?)(\n|\s)',
    ]
    for pattern in status_patterns:
        match = re.search(pattern, text)
        if match:
            data["transaction_status"] = match.group(1).strip()
            break

    # 交易流水号
    serial_no_patterns = [
        r'交易流水号[：:]\s*(\d+)',
        r'流水号[：:]\s*(\d+)',
    ]
    data["transaction_serial_no"] = _extract_number(text, serial_no_patterns)

    # 用途/附言
    purpose_patterns = [
        r'用途[：:]\s*(.*?)(\n|\s)',
        r'附言[：:]\s*(.*?)(\n|\s)',
    ]
    for pattern in purpose_patterns:
        match = re.search(pattern, text)
        if match:
            data["purpose"] = match.group(1).strip()
            break

    # 金额（小写）
    amount_patterns = [
        r'人民币.*?([\d,]+\.\d{2})元',
        r'(\d{1,3}(?:,\d{3})*\.\d{2})元',
        r'\*([\d,]+\.\d{2})元',
        r'金额.*?([\d,]+\.\d{2})',
        r'￥\s*([\d,]+\.\d{2})',
        r'¥\s*([\d,]+\.\d{2})',
    ]
    data["transaction_amount"] = _extract_amount(text, amount_patterns)

    # 金额（大写）
    text_parts = text.split('\n')
    for part in text_parts:
        part = part.strip()
        if any(kw in part for kw in ["万", "仟", "佰", "拾", "元", "角", "分", "肆", "伍", "拾"]):
            if "人民币" in part or "大写" in part or "整" in part:
                data["transaction_amount_text"] = part
                break

    # 提取户名（支持多个户名，取第一个作为本方）
    account_name_patterns = [
        r'户名[：:]\s*(.*?)(\n|账号|账户)',
        r'账户名称[：:]\s*(.*?)(\n|账号)',
        r'名称[：:]\s*(.*?)(\n|账号)',
    ]
    
    all_names = []
    for pattern in account_name_patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1).strip()
            if name and name not in all_names:
                all_names.append(name)
    
    if len(all_names) >= 2:
        data["account_name"] = all_names[0]
        data["counterparty_name"] = all_names[1]
    elif len(all_names) == 1:
        data["account_name"] = all_names[0]

    # 提取账号（支持多个账号）
    account_no_patterns = [
        r'账号[：:]\s*(\d+)',
        r'账户号[：:]\s*(\d+)',
        r'卡号[：:]\s*(\d+)',
    ]
    
    all_accounts = []
    for pattern in account_no_patterns:
        for match in re.finditer(pattern, text):
            acct = match.group(1).strip()
            if acct and acct not in all_accounts:
                all_accounts.append(acct)
    
    if len(all_accounts) >= 2:
        data["account_no"] = all_accounts[0]
        data["counterparty_account_no"] = all_accounts[1]
    elif len(all_accounts) == 1:
        data["account_no"] = all_accounts[0]

    # 提取开户行（支持多个开户行）
    bank_name_patterns = [
        r'开户行[：:]\s*(.*?)(\n|户名|账号)',
        r'开户银行[：:]\s*(.*?)(\n|户名|账号)',
        r'银行[：:]\s*(.*?)(\n|户名|账号)',
    ]
    
    all_banks = []
    for pattern in bank_name_patterns:
        for match in re.finditer(pattern, text):
            bank = match.group(1).strip()
            if bank and bank not in all_banks:
                all_banks.append(bank)
    
    if len(all_banks) >= 2:
        data["bank_name"] = all_banks[0]
        data["counterparty_bank"] = all_banks[1]
    elif len(all_banks) == 1:
        data["bank_name"] = all_banks[0]

    # 交易日期范围
    period_patterns = [
        r'日期范围[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})\s*至\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'起止日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})\s*[-~]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
    ]
    for pattern in period_patterns:
        match = re.search(pattern, text)
        if match:
            data["statement_period_start"] = match.group(1)
            data["statement_period_end"] = match.group(2)
            break

    # 期初余额
    opening_balance_patterns = [
        r'期初余额[：:]\s*([\d,]+\.\d{2})',
        r'上期余额[：:]\s*([\d,]+\.\d{2})',
        r'起始余额[：:]\s*([\d,]+\.\d{2})',
    ]
    data["opening_balance"] = _extract_amount(text, opening_balance_patterns)

    # 期末余额
    closing_balance_patterns = [
        r'期末余额[：:]\s*([\d,]+\.\d{2})',
        r'当前余额[：:]\s*([\d,]+\.\d{2})',
        r'结余[：:]\s*([\d,]+\.\d{2})',
    ]
    data["closing_balance"] = _extract_amount(text, closing_balance_patterns)

    # 收入合计
    inflow_patterns = [
        r'收入合计[：:]\s*([\d,]+\.\d{2})',
        r'总收入[：:]\s*([\d,]+\.\d{2})',
        r'存入合计[：:]\s*([\d,]+\.\d{2})',
    ]
    data["total_inflow"] = _extract_amount(text, inflow_patterns)

    # 支出合计
    outflow_patterns = [
        r'支出合计[：:]\s*([\d,]+\.\d{2})',
        r'总支出[：:]\s*([\d,]+\.\d{2})',
        r'支取合计[：:]\s*([\d,]+\.\d{2})',
    ]
    data["total_outflow"] = _extract_amount(text, outflow_patterns)

    # 提取交易记录（简单模式匹配）
    lines = text.split('\n')
    transactions = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        transaction_pattern = r'(\d{4}-\d{2}-\d{2})\s+(.+?)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})?'
        match = re.search(transaction_pattern, line)
        if match:
            transactions.append({
                "transaction_date": match.group(1),
                "description": match.group(2).strip(),
                "amount": match.group(3).replace(',', ''),
                "counterparty_name": None,
                "summary": match.group(2).strip(),
            })
    
    if transactions:
        data["transactions"] = transactions[:50]

    # 提取对方户名（从交易记录中）
    for trans in transactions:
        desc = trans["description"]
        if len(desc) > 2:
            trans["counterparty_name"] = desc[:20]
            trans["summary"] = desc

    return data


# =============================================================================
# 合同规则解析器
# =============================================================================

def parse_contract_rules(text: str, file_path: str = "") -> dict[str, Any]:
    """
    合同规则解析器
    
    功能描述：使用规则和正则表达式解析合同的结构化数据
    业务逻辑：
        1. 提取合同编号
        2. 提取合同名称
        3. 提取甲方和乙方信息
        4. 提取合同金额
        5. 提取签订日期
        6. 提取合同期限
    
    会计口径：符合合同法和企业合同管理规范
    
    Args:
        text: 提取的文本内容
        file_path: 文件路径
        
    Returns:
        dict: 结构化合同数据
    """
    data: dict[str, Any] = {
        "document_type": "contract",
        "contract_no": None,
        "contract_name": None,
        "contract_subject": None,
        "party_a_name": None,
        "party_a_tax_id": None,
        "party_b_name": None,
        "party_b_tax_id": None,
        "contract_amount": None,
        "sign_date": None,
        "effective_date": None,
        "expiry_date": None,
        "execution_status": None,
    }

    # 合同编号
    contract_no_patterns = [
        r'合同编号[：:]\s*(\S+)',
        r'合同号[：:]\s*(\S+)',
        r'编号[：:]\s*(\S+)',
    ]
    data["contract_no"] = _extract_number(text, contract_no_patterns)

    # 合同名称（通常在开头）
    lines = text.split('\n')[:5]
    for line in lines:
        line = line.strip()
        if line and len(line) > 5 and len(line) < 100:
            if not any(kw in line for kw in ["编号", "甲方", "乙方", "签订"]):
                data["contract_name"] = line
                break

    # 合同标的
    subject_patterns = [
        r'标的[：:]\s*(.*?)(\n|数量|金额|价款)',
        r'合同标的[：:]\s*(.*?)(\n|数量|金额)',
        r'标的内容[：:]\s*(.*?)(\n|数量|金额)',
        r'服务内容[：:]\s*(.*?)(\n|数量|金额)',
        r'货物名称[：:]\s*(.*?)(\n|规格|数量)',
    ]
    for pattern in subject_patterns:
        match = re.search(pattern, text)
        if match:
            data["contract_subject"] = match.group(1).strip()
            break

    # 甲方名称
    party_a_patterns = [
        r'甲方[：:]\s*(.*?)(\n|乙方|地址)',
        r'甲方全称[：:]\s*(.*?)(\n|乙方)',
        r'委托方[：:]\s*(.*?)(\n|受托方)',
    ]
    for pattern in party_a_patterns:
        match = re.search(pattern, text)
        if match:
            data["party_a_name"] = match.group(1).strip()
            break

    # 乙方名称
    party_b_patterns = [
        r'乙方[：:]\s*(.*?)(\n|甲方|地址)',
        r'乙方全称[：:]\s*(.*?)(\n|甲方)',
        r'受托方[：:]\s*(.*?)(\n|委托方)',
    ]
    for pattern in party_b_patterns:
        match = re.search(pattern, text)
        if match:
            data["party_b_name"] = match.group(1).strip()
            break

    # 合同金额
    contract_amount_patterns = [
        r'合同金额[：:]\s*([\d,]+\.\d{2})',
        r'金额[：:]\s*([\d,]+\.\d{2})',
        r'价款[：:]\s*([\d,]+\.\d{2})',
        r'总金额[：:]\s*([\d,]+\.\d{2})',
    ]
    data["contract_amount"] = _extract_amount(text, contract_amount_patterns)

    # 签订日期
    sign_date_patterns = [
        r'签订日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'签订时间[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'签署日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
    ]
    data["sign_date"] = _extract_date(text, sign_date_patterns)

    # 合同期限
    term_patterns = [
        r'期限.*?(\d{4}[-/]\d{2}[-/]\d{2})\s*至\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'有效期.*?(\d{4}[-/]\d{2}[-/]\d{2})\s*[-~]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
    ]
    for pattern in term_patterns:
        match = re.search(pattern, text)
        if match:
            data["effective_date"] = match.group(1)
            data["expiry_date"] = match.group(2)
            break

    return data


# =============================================================================
# 入库单规则解析器
# =============================================================================

def parse_inventory_receipt_rules(text: str, file_path: str = "") -> dict[str, Any]:
    """
    入库单规则解析器
    
    功能描述：使用规则和正则表达式解析入库单的结构化数据
    业务逻辑：
        1. 提取入库单号
        2. 提取入库日期
        3. 提取供应商信息
        4. 提取物料/商品信息
        5. 提取数量、单价、金额
        6. 提取合计金额
    
    会计口径：符合存货核算规范和采购入库流程
    
    Args:
        text: 提取的文本内容
        file_path: 文件路径
        
    Returns:
        dict: 结构化入库单数据
    """
    data: dict[str, Any] = {
        "document_type": "inventory_receipt",
        "receipt_no": None,
        "receipt_date": None,
        "supplier_name": None,
        "supplier_code": None,
        "warehouse_name": None,
        "items": [],
        "total_quantity": None,
        "total_amount": None,
        "received_by": None,
    }

    # 入库单号
    receipt_no_patterns = [
        r'入库单号[：:]\s*(\S+)',
        r'单号[：:]\s*(\S+)',
        r'编号[：:]\s*(\S+)',
    ]
    data["receipt_no"] = _extract_number(text, receipt_no_patterns)

    # 入库日期
    receipt_date_patterns = [
        r'入库日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
    ]
    data["receipt_date"] = _extract_date(text, receipt_date_patterns)

    # 供应商名称
    supplier_patterns = [
        r'供应商[：:]\s*(.*?)(\n|入库|仓库)',
        r'供货单位[：:]\s*(.*?)(\n|入库|仓库)',
        r'供方[：:]\s*(.*?)(\n|入库|仓库)',
    ]
    for pattern in supplier_patterns:
        match = re.search(pattern, text)
        if match:
            data["supplier_name"] = match.group(1).strip()
            break

    # 仓库名称
    warehouse_patterns = [
        r'仓库[：:]\s*(.*?)(\n|供应商|物料)',
        r'入库仓库[：:]\s*(.*?)(\n|供应商)',
    ]
    for pattern in warehouse_patterns:
        match = re.search(pattern, text)
        if match:
            data["warehouse_name"] = match.group(1).strip()
            break

    # 合计金额
    total_amount_patterns = [
        r'合计金额[：:]\s*([\d,]+\.\d{2})',
        r'总金额[：:]\s*([\d,]+\.\d{2})',
        r'金额合计[：:]\s*([\d,]+\.\d{2})',
    ]
    data["total_amount"] = _extract_amount(text, total_amount_patterns)

    # 总数量
    total_quantity_patterns = [
        r'合计数量[：:]\s*(\d+)',
        r'总数量[：:]\s*(\d+)',
        r'数量合计[：:]\s*(\d+)',
    ]
    for pattern in total_quantity_patterns:
        match = re.search(pattern, text)
        if match:
            data["total_quantity"] = int(match.group(1))
            break

    # 提取物料明细（简单模式）
    lines = text.split('\n')
    items = []
    
    for line in lines:
        line = line.strip()
        item_pattern = r'(\S+)\s+(\S+)\s+(\d+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})'
        match = re.search(item_pattern, line)
        if match:
            items.append({
                "item_code": match.group(1),
                "item_name": match.group(2),
                "quantity": int(match.group(3)),
                "unit_price": match.group(4).replace(',', ''),
                "amount": match.group(5).replace(',', ''),
            })
    
    if items:
        data["items"] = items[:20]

    return data


# =============================================================================
# 工资表规则解析器
# =============================================================================

def parse_salary_table_rules(text: str, file_path: str = "") -> dict[str, Any]:
    """
    工资表规则解析器
    
    功能描述：使用规则和正则表达式解析工资表的结构化数据
    业务逻辑：
        1. 提取工资期间
        2. 提取部门信息
        3. 提取员工列表（姓名、工号）
        4. 提取工资项目（应发工资、扣款、实发工资）
        5. 提取合计金额
    
    会计口径：符合企业薪酬核算规范和个人所得税法
    
    Args:
        text: 提取的文本内容
        file_path: 文件路径
        
    Returns:
        dict: 结构化工资表数据
    """
    data: dict[str, Any] = {
        "document_type": "salary_table",
        "salary_period": None,
        "department": None,
        "employee_count": None,
        "gross_total": None,
        "deduction_total": None,
        "net_total": None,
        "employees": [],
    }

    # 工资期间
    period_patterns = [
        r'工资期间[：:]\s*(.*?)(\n|部门)',
        r'所属月份[：:]\s*(.*?)(\n|部门)',
        r'(\d{4}年\d{1,2}月)',
    ]
    for pattern in period_patterns:
        match = re.search(pattern, text)
        if match:
            data["salary_period"] = match.group(1).strip()
            break

    # 部门
    department_patterns = [
        r'部门[：:]\s*(.*?)(\n|姓名|工号)',
        r'所属部门[：:]\s*(.*?)(\n|姓名)',
    ]
    for pattern in department_patterns:
        match = re.search(pattern, text)
        if match:
            data["department"] = match.group(1).strip()
            break

    # 合计金额（应发、扣款、实发）
    gross_patterns = [
        r'应发合计[：:]\s*([\d,]+\.\d{2})',
        r'工资合计[：:]\s*([\d,]+\.\d{2})',
        r'应发工资[：:]\s*([\d,]+\.\d{2})',
    ]
    data["gross_total"] = _extract_amount(text, gross_patterns)

    deduction_patterns = [
        r'扣款合计[：:]\s*([\d,]+\.\d{2})',
        r'代扣合计[：:]\s*([\d,]+\.\d{2})',
        r'扣除合计[：:]\s*([\d,]+\.\d{2})',
    ]
    data["deduction_total"] = _extract_amount(text, deduction_patterns)

    net_patterns = [
        r'实发合计[：:]\s*([\d,]+\.\d{2})',
        r'实发工资[：:]\s*([\d,]+\.\d{2})',
        r'发放合计[：:]\s*([\d,]+\.\d{2})',
    ]
    data["net_total"] = _extract_amount(text, net_patterns)

    # 提取员工记录（简单模式）
    lines = text.split('\n')
    employees = []
    
    for line in lines:
        line = line.strip()
        emp_pattern = r'(\d+)\s+(\S+)\s+.*?([\d,]+\.\d{2})\s+.*?([\d,]+\.\d{2})'
        match = re.search(emp_pattern, line)
        if match and len(match.group(2)) < 20:
            employees.append({
                "employee_id": match.group(1),
                "employee_name": match.group(2),
                "gross_amount": match.group(3).replace(',', ''),
                "net_amount": match.group(4).replace(',', ''),
            })
    
    if employees:
        data["employees"] = employees[:30]
        data["employee_count"] = len(employees)

    return data


# =============================================================================
# 费用单据规则解析器
# =============================================================================

def parse_expense_document_rules(text: str, file_path: str = "") -> dict[str, Any]:
    """
    费用单据规则解析器
    
    功能描述：使用规则和正则表达式解析费用单据的结构化数据
    业务逻辑：
        1. 提取单据编号
        2. 提取日期
        3. 提取报销人信息
        4. 提取费用项目明细
        5. 提取金额信息
        6. 提取审批状态
    
    会计口径：符合企业费用报销制度和会计准则
    
    Args:
        text: 提取的文本内容
        file_path: 文件路径
        
    Returns:
        dict: 结构化费用单据数据
    """
    data: dict[str, Any] = {
        "document_type": "expense_document",
        "document_no": None,
        "expense_date": None,
        "reimbursement_date": None,
        "applicant_name": None,
        "applicant_department": None,
        "expense_items": [],
        "total_amount": None,
        "approved_amount": None,
        "approval_status": None,
    }

    # 单据编号
    doc_no_patterns = [
        r'单据编号[：:]\s*(\S+)',
        r'编号[：:]\s*(\S+)',
        r'单号[：:]\s*(\S+)',
    ]
    data["document_no"] = _extract_number(text, doc_no_patterns)

    # 费用日期
    expense_date_patterns = [
        r'费用日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'发生日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
    ]
    data["expense_date"] = _extract_date(text, expense_date_patterns)

    # 报销日期
    reimbursement_date_patterns = [
        r'报销日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'申请日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
    ]
    data["reimbursement_date"] = _extract_date(text, reimbursement_date_patterns)

    # 报销人
    applicant_patterns = [
        r'报销人[：:]\s*(.*?)(\n|部门|日期)',
        r'申请人[：:]\s*(.*?)(\n|部门|日期)',
        r'姓名[：:]\s*(.*?)(\n|部门|日期)',
    ]
    for pattern in applicant_patterns:
        match = re.search(pattern, text)
        if match:
            data["applicant_name"] = match.group(1).strip()
            break

    # 部门
    department_patterns = [
        r'部门[：:]\s*(.*?)(\n|姓名|日期)',
        r'所属部门[：:]\s*(.*?)(\n|姓名)',
    ]
    for pattern in department_patterns:
        match = re.search(pattern, text)
        if match:
            data["applicant_department"] = match.group(1).strip()
            break

    # 合计金额
    total_amount_patterns = [
        r'合计金额[：:]\s*([\d,]+\.\d{2})',
        r'总金额[：:]\s*([\d,]+\.\d{2})',
        r'报销金额[：:]\s*([\d,]+\.\d{2})',
    ]
    data["total_amount"] = _extract_amount(text, total_amount_patterns)

    # 审批金额
    approved_amount_patterns = [
        r'审批金额[：:]\s*([\d,]+\.\d{2})',
        r'同意金额[：:]\s*([\d,]+\.\d{2})',
    ]
    data["approved_amount"] = _extract_amount(text, approved_amount_patterns)

    # 审批状态
    if "已批准" in text or "已通过" in text:
        data["approval_status"] = "approved"
    elif "审批中" in text or "待审批" in text:
        data["approval_status"] = "pending"
    elif "已拒绝" in text or "已退回" in text:
        data["approval_status"] = "rejected"

    # 提取费用明细（简单模式）
    lines = text.split('\n')
    items = []
    
    for line in lines:
        line = line.strip()
        item_pattern = r'(\S+)\s+(\S+)\s+(\d+)\s+([\d,]+\.\d{2})'
        match = re.search(item_pattern, line)
        if match:
            items.append({
                "item_name": match.group(1),
                "item_type": match.group(2),
                "quantity": int(match.group(3)),
                "amount": match.group(4).replace(',', ''),
            })
    
    if items:
        data["expense_items"] = items[:20]

    return data


# =============================================================================
# 收据规则解析器
# =============================================================================

def parse_receipt_rules(text: str, file_path: str = "") -> dict[str, Any]:
    """
    收据规则解析器
    
    功能描述：使用规则和正则表达式解析收据的结构化数据
    业务逻辑：
        1. 提取收据编号
        2. 提取日期
        3. 提取付款人/收款人信息
        4. 提取金额（大写和小写）
        5. 提取收款事由
        6. 提取盖章信息
    
    会计口径：符合收据管理规范和现金管理规定
    
    Args:
        text: 提取的文本内容
        file_path: 文件路径
        
    Returns:
        dict: 结构化收据数据
    """
    data: dict[str, Any] = {
        "document_type": "receipt",
        "receipt_no": None,
        "receipt_date": None,
        "payer_name": None,
        "payee_name": None,
        "amount": None,
        "amount_text": None,
        "reason": None,
        "received_by": None,
    }

    # 收据编号
    receipt_no_patterns = [
        r'收据编号[：:]\s*(\S+)',
        r'编号[：:]\s*(\S+)',
        r'票号[：:]\s*(\S+)',
    ]
    data["receipt_no"] = _extract_number(text, receipt_no_patterns)

    # 日期
    receipt_date_patterns = [
        r'日期[：:]\s*(\d{4}[-/]\d{2}[-/]\d{2})',
        r'(\d{4}年\d{1,2}月\d{1,2}日)',
    ]
    data["receipt_date"] = _extract_date(text, receipt_date_patterns)

    # 付款人
    payer_patterns = [
        r'今收到[：:]\s*(.*?)(\n|交来|金额)',
        r'付款人[：:]\s*(.*?)(\n|收款人)',
        r'交款人[：:]\s*(.*?)(\n|金额)',
    ]
    for pattern in payer_patterns:
        match = re.search(pattern, text)
        if match:
            data["payer_name"] = match.group(1).strip()
            break

    # 收款人
    payee_patterns = [
        r'收款人[：:]\s*(.*?)(\n|盖章)',
        r'单位[：:]\s*(.*?)(\n|盖章)',
    ]
    for pattern in payee_patterns:
        match = re.search(pattern, text)
        if match:
            data["payee_name"] = match.group(1).strip()
            break

    # 金额（小写）
    amount_patterns = [
        r'金额.*?([\d,]+\.\d{2})',
        r'￥\s*([\d,]+\.\d{2})',
        r'¥\s*([\d,]+\.\d{2})',
    ]
    data["amount"] = _extract_amount(text, amount_patterns)

    # 金额（大写）
    text_parts = text.split('\n')
    for part in text_parts:
        part = part.strip()
        if any(kw in part for kw in ["万", "仟", "佰", "拾", "元", "角", "分"]):
            data["amount_text"] = part
            break

    # 收款事由
    reason_patterns = [
        r'事由[：:]\s*(.*?)(\n|金额)',
        r'用途[：:]\s*(.*?)(\n|金额)',
        r'交来[：:]\s*(.*?)(\n|金额)',
    ]
    for pattern in reason_patterns:
        match = re.search(pattern, text)
        if match:
            data["reason"] = match.group(1).strip()
            break

    return data


def _detect_header_row(df: "pd.DataFrame") -> int:
    """
    检测 Excel/CSV 数据表中的真正表头行位置。

    业务含义：
        财务类表格常见习惯是前 4-5 行为标题、企业名称、制表时间、
        货币单位等说明信息，真正字段名在下方。本函数通过统计每行
        的字段名特征来定位表头。
    """
    import pandas as pd

    if df.empty:
        return 0

    candidate_keywords = [
        "凭证", "日期", "摘要", "科目", "借方", "贷方", "余额", "金额",
        "序号", "年", "月", "日", "对方科目", "经办人", "审核人", "过账",
        "voucher", "date", "summary", "subject", "debit", "credit", "balance",
        "amount", "no", "serial",
    ]
    best_score = -1
    best_index = 0

    for idx in range(min(len(df), 15)):
        row = df.iloc[idx]
        text = " ".join(str(x).strip().lower() for x in row.values if pd.notna(x))
        if not text:
            continue
        score = 0
        for keyword in candidate_keywords:
            if keyword in text:
                score += 1
        # 如果一行中包含大量非空单元格且看起来像字段名，给予更高权重
        non_empty_count = sum(1 for x in row.values if pd.notna(x) and str(x).strip())
        if non_empty_count >= 4:
            score += non_empty_count * 0.5
        if score > best_score:
            best_score = score
            best_index = idx

    return best_index


def _normalize_header_name(header: str) -> str:
    """将表头字段名标准化为统一口径。"""
    import re

    text = str(header).strip().lower()
    text = re.sub(r"[\s_:：-]+", "_", text)
    text = text.replace("（", "(").replace("）", ")")
    text = text.strip("_")

    aliases = {
        "document_no": ["凭证号", "凭证编号", "单据号", "单据编号", "记字号", "凭证字号", "voucher_no", "voucher_number", "doc_no", "no"],
        "date": ["日期", "凭证日期", "记账日期", "业务日期", "voucher_date", "doc_date"],
        "summary": ["摘要", "业务说明", "摘要说明", "abstract", "description", "summary"],
        "subject_code": ["科目代码", "科目编号", "科目编码", "account_code", "subject_code"],
        "subject_name": ["科目名称", "科目", "会计科目", "account_name", "subject_name"],
        "debit_amount": ["借方", "借方金额", "借方发生额", "debit", "debit_amount"],
        "credit_amount": ["贷方", "贷方金额", "贷方发生额", "credit", "credit_amount"],
        "balance": ["余额", "账面余额", "balance", "balance_amount"],
        "counterparty_subject": ["对方科目", "对应科目", "对方科目名称", "counterparty_subject"],
        "direction": ["方向", "借贷方向", "direction"],
    }

    for standard, variants in aliases.items():
        if text in [v.lower() for v in variants] or text == standard:
            return standard
    return text


def _is_summary_row(row: "pd.Series") -> bool:
    """判断一行是否为小计/合计/汇总行。"""
    import pandas as pd

    text = " ".join(str(x).strip() for x in row.values if pd.notna(x)).lower()
    summary_keywords = ["合计", "小计", "总计", "汇总", "sum", "total", "subtotal"]
    if any(keyword in text for keyword in summary_keywords):
        return True
    # 如果整行只有一个有效单元格且包含关键词，也视为汇总行
    non_empty = [x for x in row.values if pd.notna(x) and str(x).strip()]
    if len(non_empty) == 1 and any(k in str(non_empty[0]).lower() for k in summary_keywords):
        return True
    return False


def _parse_amount_value(value: Any) -> float | None:
    """从单元格中解析金额数值。"""
    import pandas as pd

    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().replace(",", "").replace("，", "").replace("¥", "").replace("￥", "").replace("元", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def parse_accounting_entry_rules(text: str, file_path: str = "") -> dict[str, Any]:
    """
    会计凭证/序时簿规则解析器（支持 Excel/CSV 结构化表格）。

    业务含义：
        财务序时簿通常首行为标题、企业名称、制表时间、货币单位等，
        真正数据表头在下方 4-5 行，且数据中间可能夹杂小计/合计行。
        本解析器会自动定位表头、过滤汇总行并提取关键字段。
    """
    import pandas as pd

    data: dict[str, Any] = {
        "document_type": "accounting_entry",
        "company_name": None,
        "report_period": None,
        "currency_unit": "元",
        "columns": [],
        "entries": [],
        "entry_count": 0,
        "total_debit": None,
        "total_credit": None,
    }

    if not file_path or not Path(file_path).exists():
        return data

    suffix = Path(file_path).suffix.lower()
    try:
        if suffix == ".csv":
            df = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        else:
            df = pd.read_excel(file_path, dtype=str, keep_default_na=False)
    except Exception as e:
        logger.warning(f"读取序时簿文件失败 {file_path}: {e}")
        return data

    if df.empty:
        return data

    # 1. 尝试提取表头说明信息（企业名称、期间、货币单位）
    for idx in range(min(len(df), 5)):
        row_text = " ".join(str(x).strip() for x in df.iloc[idx].values if str(x).strip())
        if not row_text:
            continue
        if "公司" in row_text or "企业" in row_text or "单位" in row_text:
            data["company_name"] = row_text.strip()
        if any(kw in row_text for kw in ["202", "期间", "年度", "月份", "会计期间"]):
            data["report_period"] = row_text.strip()
        if any(kw in row_text for kw in ["货币单位", "本位币", "币种", "单位："]):
            data["currency_unit"] = row_text.strip()

    # 2. 定位真正表头行
    header_row_index = _detect_header_row(df)
    raw_headers = df.iloc[header_row_index].values
    headers = [_normalize_header_name(h) for h in raw_headers]

    # 清理表头，确保不重复且非空
    seen: set[str] = set()
    clean_headers: list[str] = []
    for h in headers:
        if h and h not in seen:
            seen.add(h)
            clean_headers.append(h)
        else:
            clean_headers.append("")
    data["columns"] = [h for h in clean_headers if h]

    # 3. 读取数据行
    entries: list[dict[str, Any]] = []
    total_debit = 0.0
    total_credit = 0.0

    for idx in range(header_row_index + 1, len(df)):
        row = df.iloc[idx]
        if _is_summary_row(row):
            # 对于汇总行，尝试累计借方/贷方合计
            row_dict = {}
            for col_idx, raw_header in enumerate(raw_headers):
                if col_idx >= len(row):
                    break
                normalized = _normalize_header_name(raw_header)
                row_dict[normalized] = row.iloc[col_idx]
            d_val = _parse_amount_value(row_dict.get("debit_amount"))
            c_val = _parse_amount_value(row_dict.get("credit_amount"))
            if d_val is not None and d_val > 0:
                total_debit += d_val
            if c_val is not None and c_val > 0:
                total_credit += c_val
            continue

        # 跳过空行
        non_empty_values = [str(x).strip() for x in row.values if str(x).strip()]
        if not non_empty_values:
            continue

        row_dict: dict[str, Any] = {}
        for col_idx, raw_header in enumerate(raw_headers):
            if col_idx >= len(row):
                break
            normalized = _normalize_header_name(raw_header)
            if not normalized:
                continue
            row_dict[normalized] = row.iloc[col_idx]

        # 只保留至少包含一个关键字段的行
        key_fields = ["document_no", "date", "summary", "subject_code", "subject_name", "debit_amount", "credit_amount"]
        if not any(row_dict.get(f) for f in key_fields):
            continue

        entry = {
            "document_no": row_dict.get("document_no") or None,
            "date": row_dict.get("date") or None,
            "summary": row_dict.get("summary") or None,
            "subject_code": row_dict.get("subject_code") or None,
            "subject_name": row_dict.get("subject_name") or None,
            "debit_amount": _parse_amount_value(row_dict.get("debit_amount")),
            "credit_amount": _parse_amount_value(row_dict.get("credit_amount")),
            "balance": _parse_amount_value(row_dict.get("balance")),
            "counterparty_subject": row_dict.get("counterparty_subject") or None,
            "direction": row_dict.get("direction") or None,
        }

        # 如果金额列可以转为 Decimal，则保留 2 位小数
        from decimal import Decimal, ROUND_HALF_UP
        for key in ("debit_amount", "credit_amount", "balance"):
            val = entry[key]
            if val is not None:
                try:
                    entry[key] = str(Decimal(str(val)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))
                except Exception:
                    pass

        entries.append(entry)

    # 4. 汇总
    data["entries"] = entries
    data["entry_count"] = len(entries)
    if total_debit > 0:
        data["total_debit"] = str(Decimal(str(total_debit)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))
    if total_credit > 0:
        data["total_credit"] = str(Decimal(str(total_credit)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))

    return data


# =============================================================================
# 规则引擎调度函数
# =============================================================================

def parse_with_rules(
    document_type: str,
    text: str,
    file_path: str = "",
) -> dict[str, Any]:
    """
    根据文档类型调用对应的规则解析器
    
    功能描述：统一入口，根据文档类型分发到对应的规则解析器
    业务逻辑：
        1. 根据document_type选择解析器
        2. 调用对应解析器获取结构化数据
        3. 返回统一格式的结果
    
    Args:
        document_type: 文档类型字符串
        text: 提取的文本内容
        file_path: 文件路径
        
    Returns:
        dict: 结构化数据
    """
    parser_map = {
        "invoice": parse_invoice_rules,
        "bank_statement": parse_bank_statement_rules,
        "contract": parse_contract_rules,
        "inventory_receipt": parse_inventory_receipt_rules,
        "salary_table": parse_salary_table_rules,
        "expense_document": parse_expense_document_rules,
        "receipt": parse_receipt_rules,
        "accounting_entry": parse_accounting_entry_rules,
    }

    parser = parser_map.get(document_type)
    if parser:
        try:
            return parser(text, file_path)
        except Exception as e:
            logger.error(f"规则解析失败 {document_type}: {e}")
            return {"document_type": document_type}
    
    return {"document_type": document_type}
