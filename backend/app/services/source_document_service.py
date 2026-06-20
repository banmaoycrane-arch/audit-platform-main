"""
原始资料解析服务

用于解析各类财务原始凭证：发票、银行流水、合同、入库单等

作为会计，你可能熟悉的场景：
- 发票：购买商品或服务时收到的增值税发票
- 银行流水：银行账户的交易记录明细
- 合同：与供应商或客户签订的采购/销售合同
- 入库单：仓库收到货物时的收货单据
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# =============================================================================
# 数据模型定义
# =============================================================================

class InvoiceData(BaseModel):
    """发票数据结构"""
    invoice_number: Optional[str] = None  # 发票号码
    invoice_date: Optional[str] = None  # 开票日期
    buyer_name: Optional[str] = None  # 购买方名称
    seller_name: Optional[str] = None  # 销售方名称
    items: list[dict] = []  # 商品明细
    total_amount: Optional[float] = None  # 价税合计金额
    tax_amount: Optional[float] = None  # 税额
    tax_rate: Optional[float] = None  # 税率


class BankTransaction(BaseModel):
    """银行流水数据结构"""
    transaction_date: str  # 交易日期
    amount: float  # 交易金额
    counterparty: Optional[str] = None  # 对方账户/户名
    summary: Optional[str] = None  # 摘要/用途
    transaction_type: Optional[str] = None  # 收入/支出


class ContractData(BaseModel):
    """合同数据结构"""
    contract_number: Optional[str] = None  # 合同编号
    sign_date: Optional[str] = None  # 签订日期
    amount: Optional[float] = None  # 合同金额
    party_a: Optional[str] = None  # 甲方
    party_b: Optional[str] = None  # 乙方
    content: Optional[str] = None  # 合同完整文本


class InventoryReceipt(BaseModel):
    """入库单数据结构"""
    receipt_number: Optional[str] = None  # 入库单号
    receipt_date: Optional[str] = None  # 入库日期
    supplier: Optional[str] = None  # 供应商
    items: list[dict] = []  # 商品明细
    total_amount: Optional[float] = None  # 总金额


class SourceDocumentResult(BaseModel):
    """原始文档解析结果"""
    document_type: str  # 文档类型：invoice/bank_statement/contract/inventory_receipt/general
    confidence: float  # 置信度 0-1
    data: dict  # 具体解析结果（对应类型的模型数据）
    raw_text: Optional[str] = None  # 原始文本（便于后续AI处理）
    file_name: str  # 文件名


# =============================================================================
# 工具函数
# =============================================================================

def _extract_amount(text: str, pattern: str) -> Optional[float]:
    """
    使用正则表达式从文本中提取金额

    财务数据中金额格式可能多种多样：
    - ¥1,234.56
    - RMB 1234.56
    - 1234.56元
    """
    match = re.search(pattern, text)
    if match:
        amount_str = match.group(1).replace(",", "").replace("¥", "").replace("元", "").replace(" ", "")
        try:
            return float(amount_str)
        except ValueError:
            return None
    return None


def _extract_date(text: str, patterns: list[str]) -> Optional[str]:
    """从文本中提取日期"""
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def _clean_text(text: str) -> str:
    """清理文本，去除多余空白"""
    return re.sub(r"\s+", " ", text).strip()


# =============================================================================
# PDF 文本提取
# =============================================================================

def _extract_text_from_pdf(path: str) -> str:
    """
    从 PDF 文件提取文本

    PDF 是财务文档常见的格式，但解析起来比较复杂。
    不同 PDF 的文本布局可能差异很大。
    """
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception as e:
        logger.warning(f"PDF 解析失败 {path}: {e}")
        return ""


# =============================================================================
# 发票解析
# =============================================================================

def parse_invoice(path: str, file_name: str = "") -> SourceDocumentResult:
    """
    解析发票文件

    支持格式：PDF、图片（JPG/PNG）

    发票上通常包含以下关键信息：
    - 发票号码：税务系统唯一编号
    - 开票日期：开具发票的日期
    - 购买方：买家的名称和税号
    - 销售方：卖家的名称和税号
    - 商品/服务明细：所购买的具体内容
    - 金额：单价、数量、金额
    - 税率和税额：增值税信息
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    # 1. 提取文本内容
    if suffix == ".pdf":
        raw_text = _extract_text_from_pdf(path)
    elif suffix == ".txt":
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_text = file_path.read_text(encoding="gbk")
    elif suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
        from app.services.ocr_service import extract_text_from_image
        raw_text = extract_text_from_image(path)
    else:
        raw_text = ""

    if not raw_text:
        return SourceDocumentResult(
            document_type="invoice",
            confidence=0.0,
            data={},
            raw_text="",
            file_name=file_name
        )

    # 2. 使用正则表达式提取发票关键信息
    # 发票号码通常是10位或12位数字
    invoice_number_match = re.search(r"发票号码[：:]\s*([A-Z0-9]{10,12})", raw_text)
    invoice_number = invoice_number_match.group(1) if invoice_number_match else None

    # 尝试多种日期格式
    invoice_date = _extract_date(raw_text, [
        r"\d{4}年\d{1,2}月\d{1,2}日",
        r"\d{4}-\d{2}-\d{2}",
        r"\d{4}/\d{2}/\d{2}"
    ])

    # 购买方和销售方
    buyer_match = re.search(r"购买方[：:]\s*([^\n]+)", raw_text)
    buyer_name = _clean_text(buyer_match.group(1)) if buyer_match else None

    seller_match = re.search(r"销售方[：:]\s*([^\n]+)", raw_text)
    seller_name = _clean_text(seller_match.group(1)) if seller_match else None

    # 金额提取 - 价税合计通常是最大的金额
    # 常见格式："价税合计（大写）叁万伍仟元整" 或 "¥35,000.00"
    total_amount = None
    tax_amount = None
    tax_rate = None

    # 提取税率
    tax_rate_match = re.search(r"税率[：:]\s*(\d+(?:\.\d+)?)%?", raw_text)
    if tax_rate_match:
        rate_str = tax_rate_match.group(1)
        tax_rate = float(rate_str) / 100 if "%" in tax_rate_match.group(0) else float(rate_str)

    # 提取金额
    total_match = re.search(r"价税合计[（(]大写[）)][^\d]*([\d,]+(?:\.\d{2})?)", raw_text)
    if total_match:
        total_amount = float(total_match.group(1).replace(",", ""))

    # 如果没找到价税合计，尝试找小写金额
    if not total_amount:
        amounts = re.findall(r"[¥¥]?\s*([\d,]+(?:\.\d{2})?)", raw_text)
        if amounts:
            try:
                total_amount = float(amounts[-1].replace(",", ""))
            except ValueError:
                pass

    # 提取税额
    tax_match = re.search(r"税额[：:]\s*[¥¥]?\s*([\d,]+(?:\.\d{2})?)", raw_text)
    if tax_match:
        tax_amount = float(tax_match.group(1).replace(",", ""))

    # 3. 构建发票数据对象
    invoice_data = InvoiceData(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        buyer_name=buyer_name,
        seller_name=seller_name,
        items=[],  # 简化版暂不解析明细行
        total_amount=total_amount,
        tax_amount=tax_amount,
        tax_rate=tax_rate
    )

    # 4. 计算置信度
    confidence = 0.0
    if invoice_number:
        confidence += 0.3
    if invoice_date:
        confidence += 0.2
    if buyer_name:
        confidence += 0.2
    if seller_name:
        confidence += 0.2
    if total_amount is not None:
        confidence += 0.1

    return SourceDocumentResult(
        document_type="invoice",
        confidence=confidence,
        data=invoice_data.model_dump(),
        raw_text=raw_text,
        file_name=file_name
    )


# =============================================================================
# 银行流水解析
# =============================================================================

def parse_bank_statement(path: str, file_name: str = "") -> SourceDocumentResult:
    """
    解析银行流水文件

    支持格式：Excel、CSV

    银行流水是银行提供的交易明细，包含：
    - 交易日期：什么时候发生的
    - 交易金额：多少钱
    - 对方账户：跟谁发生的交易
    - 摘要/用途：做什么用的（转账、货款等）

    银行流水的格式相对固定，通常有标准表头。
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix not in {".xlsx", ".xls", ".csv"}:
        return SourceDocumentResult(
            document_type="bank_statement",
            confidence=0.0,
            data={},
            raw_text="",
            file_name=file_name
        )

    # 读取 Excel/CSV 文件
    try:
        if suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
    except Exception as e:
        logger.warning(f"银行流水文件读取失败 {path}: {e}")
        return SourceDocumentResult(
            document_type="bank_statement",
            confidence=0.0,
            data={},
            raw_text=str(e),
            file_name=file_name
        )

    # 获取原始文本（便于后续AI处理）
    raw_text = df.to_string()

    # 标准化表头（银行流水的列名可能有多种写法）
    headers = [str(h).lower().strip() for h in df.columns]

    # 映射常见的列名
    date_col = None
    amount_col = None
    counterparty_col = None
    summary_col = None
    type_col = None

    for i, h in enumerate(headers):
        if any(kw in h for kw in ["日期", "时间", "date", "time"]):
            date_col = df.columns[i]
        elif any(kw in h for kw in ["金额", "amount"]):
            amount_col = df.columns[i]
        elif any(kw in h for kw in ["对方", "户名", "收款人", "付款人", "counterparty", "beneficiary"]):
            counterparty_col = df.columns[i]
        elif any(kw in h for kw in ["摘要", "用途", "说明", "remark", "memo", "description"]):
            summary_col = df.columns[i]
        elif any(kw in h for kw in ["类型", "收支", "方向", "type", "direction"]):
            type_col = df.columns[i]

    # 解析每行数据
    transactions = []
    for idx, row in df.iterrows():
        # 跳过空行
        if row.isna().all():
            continue

        # 提取日期
        trans_date = ""
        if date_col:
            date_val = row[date_col]
            if pd.notna(date_val):
                if isinstance(date_val, (datetime, pd.Timestamp)):
                    trans_date = pd.to_datetime(date_val).strftime("%Y-%m-%d")
                else:
                    trans_date = str(date_val)

        # 提取金额
        amount = 0.0
        if amount_col:
            amt_val = row[amount_col]
            if pd.notna(amt_val):
                try:
                    amount = float(str(amt_val).replace(",", ""))
                except ValueError:
                    amount = 0.0

        # 判断收支类型
        trans_type = None
        if type_col:
            type_val = row[type_col]
            if pd.notna(type_val):
                type_str = str(type_val).lower()
                if "收" in type_str or "贷" in type_str or "credit" in type_str:
                    trans_type = "收入"
                elif "支" in type_str or "借" in type_str or "debit" in type_str:
                    trans_type = "支出"
        elif amount > 0:
            trans_type = "收入"
        elif amount < 0:
            trans_type = "支出"
            amount = abs(amount)

        # 提取对方户名
        counterparty = None
        if counterparty_col:
            cp_val = row[counterparty_col]
            if pd.notna(cp_val):
                counterparty = str(cp_val).strip()

        # 提取摘要
        summary = None
        if summary_col:
            sm_val = row[summary_col]
            if pd.notna(sm_val):
                summary = str(sm_val).strip()

        transactions.append(BankTransaction(
            transaction_date=trans_date,
            amount=amount,
            counterparty=counterparty,
            summary=summary,
            transaction_type=trans_type
        ).model_dump())

    # 计算置信度
    confidence = 0.0
    if date_col:
        confidence += 0.25
    if amount_col:
        confidence += 0.25
    if counterparty_col:
        confidence += 0.2
    if summary_col:
        confidence += 0.2
    if transactions:
        confidence += 0.1

    return SourceDocumentResult(
        document_type="bank_statement",
        confidence=confidence,
        data={"transactions": transactions, "total_count": len(transactions)},
        raw_text=raw_text,
        file_name=file_name
    )


# =============================================================================
# 合同解析
# =============================================================================

def parse_contract(path: str, file_name: str = "") -> SourceDocumentResult:
    """
    解析合同文件

    支持格式：PDF、TXT

    合同是双方或多方的法律协议，通常包含：
    - 合同编号：合同的唯一标识
    - 签订日期：合同签署的日期
    - 合同金额：涉及的金额
    - 甲乙双方：合同各方
    - 合同期限：有效期
    - 具体条款：权利义务等

    合同格式比较灵活，需要根据关键词来提取。
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    # 1. 提取文本内容
    if suffix == ".pdf":
        raw_text = _extract_text_from_pdf(path)
    elif suffix == ".txt":
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_text = file_path.read_text(encoding="gbk")
    else:
        raw_text = ""

    if not raw_text:
        return SourceDocumentResult(
            document_type="contract",
            confidence=0.0,
            data={},
            raw_text="",
            file_name=file_name
        )

    # 2. 提取合同关键信息
    # 合同编号
    contract_number = None
    for pattern in [
        r"合同编号[：:]\s*([A-Z0-9\-]+)",
        r"合同号[：:]\s*([A-Z0-9\-]+)",
        r"Contract No[.:]\s*([A-Z0-9\-]+)",
        r"Contract Number[.:]\s*([A-Z0-9\-]+)"
    ]:
        match = re.search(pattern, raw_text, re.IGNORECASE)
        if match:
            contract_number = match.group(1)
            break

    # 签订日期
    sign_date = _extract_date(raw_text, [
        r"\d{4}年\d{1,2}月\d{1,2}日",
        r"\d{4}-\d{2}-\d{2}",
        r"\d{4}/\d{2}/\d{2}"
    ])

    # 合同金额
    amount = None
    for pattern in [
        r"合同金额[：:]\s*[¥¥]?\s*([\d,]+(?:\.\d{2})?)\s*元?",
        r"合同总价[：:]\s*[¥¥]?\s*([\d,]+(?:\.\d{2})?)\s*元?",
        r"合同总金额[：:]\s*[¥¥]?\s*([\d,]+(?:\.\d{2})?)\s*元?",
        r"Contract Amount[：:]\s*([\d,]+(?:\.\d{2})?)"
    ]:
        match = re.search(pattern, raw_text)
        if match:
            try:
                amount = float(match.group(1).replace(",", ""))
                break
            except ValueError:
                pass

    # 甲乙双方
    party_a = None
    party_b = None

    party_a_match = re.search(r"甲方[（(]?[：:]\s*([^\n，,]+)", raw_text)
    if party_a_match:
        party_a = _clean_text(party_a_match.group(1))

    party_b_match = re.search(r"乙方[（(]?[：:]\s*([^\n，,]+)", raw_text)
    if party_b_match:
        party_b = _clean_text(party_b_match.group(1))

    # 如果没找到"甲方乙方"，尝试其他常见写法
    if not party_a:
        party_a_match = re.search(r"出卖方[：:]\s*([^\n，,]+)", raw_text)
        if party_a_match:
            party_a = _clean_text(party_a_match.group(1))

    if not party_b:
        party_b_match = re.search(r"买受方[：:]\s*([^\n，,]+)", raw_text)
        if party_b_match:
            party_b = _clean_text(party_b_match.group(1))

    # 构建合同数据
    contract_data = ContractData(
        contract_number=contract_number,
        sign_date=sign_date,
        amount=amount,
        party_a=party_a,
        party_b=party_b,
        content=raw_text[:5000] if len(raw_text) > 5000 else raw_text  # 保留前5000字符
    )

    # 计算置信度
    confidence = 0.0
    if contract_number:
        confidence += 0.25
    if sign_date:
        confidence += 0.2
    if amount:
        confidence += 0.2
    if party_a:
        confidence += 0.175
    if party_b:
        confidence += 0.175

    return SourceDocumentResult(
        document_type="contract",
        confidence=confidence,
        data=contract_data.model_dump(),
        raw_text=raw_text,
        file_name=file_name
    )


# =============================================================================
# 入库单解析
# =============================================================================

def parse_inventory_receipt(path: str, file_name: str = "") -> SourceDocumentResult:
    """
    解析入库单文件

    支持格式：Excel

    入库单是仓库收货的凭证，包含：
    - 入库单号：单据编号
    - 入库日期：收货日期
    - 供应商：谁送的货
    - 商品明细：收了什么货、多少、数量、单价
    - 总金额：收货的总价值

    入库单通常是表格形式，跟会计凭证类似。
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix not in {".xlsx", ".xls"}:
        return SourceDocumentResult(
            document_type="inventory_receipt",
            confidence=0.0,
            data={},
            raw_text="",
            file_name=file_name
        )

    # 读取 Excel 文件
    try:
        # 尝试自动检测表头行
        df_raw = pd.read_excel(file_path, header=None)
        header_row = 0
        for i in range(min(5, len(df_raw))):
            row_str = " ".join(str(v).lower() for v in df_raw.iloc[i].values if pd.notna(v))
            if any(kw in row_str for kw in ["商品", "货品", "名称", "数量", "单价", "金额", "product", "quantity", "price"]):
                header_row = i
                break

        df = pd.read_excel(file_path, header=header_row)
    except Exception as e:
        logger.warning(f"入库单文件读取失败 {path}: {e}")
        return SourceDocumentResult(
            document_type="inventory_receipt",
            confidence=0.0,
            data={},
            raw_text=str(e),
            file_name=file_name
        )

    raw_text = df.to_string()

    # 标准化表头
    headers = [str(h).lower().strip() for h in df.columns]

    # 映射列名
    receipt_no_col = None
    date_col = None
    supplier_col = None
    product_col = None
    quantity_col = None
    price_col = None
    amount_col = None

    for i, h in enumerate(headers):
        if any(kw in h for kw in ["单号", "编号", "no", "number"]):
            receipt_no_col = df.columns[i]
        elif any(kw in h for kw in ["日期", "date"]):
            date_col = df.columns[i]
        elif any(kw in h for kw in ["供应商", "供货方", "vendor", "supplier"]):
            supplier_col = df.columns[i]
        elif any(kw in h for kw in ["商品", "货品", "名称", "品名", "product", "item", "name"]):
            product_col = df.columns[i]
        elif any(kw in h for kw in ["数量", "quantity", "qty", "num"]):
            quantity_col = df.columns[i]
        elif any(kw in h for kw in ["单价", "price", "unit"]):
            price_col = df.columns[i]
        elif any(kw in h for kw in ["金额", "amount", "total"]):
            amount_col = df.columns[i]

    # 提取入库单基本信息
    receipt_number = None
    if receipt_no_col:
        for val in df[receipt_no_col].values:
            if pd.notna(val) and str(val).strip():
                receipt_number = str(val).strip()
                break

    receipt_date = None
    if date_col:
        for val in df[date_col].values:
            if pd.notna(val):
                if isinstance(val, (datetime, pd.Timestamp)):
                    receipt_date = pd.to_datetime(val).strftime("%Y-%m-%d")
                else:
                    receipt_date = str(val)
                break

    supplier = None
    if supplier_col:
        for val in df[supplier_col].values:
            if pd.notna(val) and str(val).strip():
                supplier = str(val).strip()
                break

    # 解析商品明细
    items = []
    total_amount = 0.0

    for idx, row in df.iterrows():
        # 跳过表头行
        if product_col and pd.notna(row[product_col]):
            product_name = str(row[product_col]).strip()
            if any(kw in product_name.lower() for kw in ["商品", "货品", "名称", "品名", "product"]):
                continue

        item = {}

        if product_col and pd.notna(row.get(product_col)):
            item["product_name"] = str(row[product_col]).strip()
        if quantity_col and pd.notna(row.get(quantity_col)):
            try:
                item["quantity"] = float(str(row[quantity_col]).replace(",", ""))
            except ValueError:
                item["quantity"] = 0.0
        if price_col and pd.notna(row.get(price_col)):
            try:
                item["price"] = float(str(row[price_col]).replace(",", ""))
            except ValueError:
                item["price"] = 0.0
        if amount_col and pd.notna(row.get(amount_col)):
            try:
                item["amount"] = float(str(row[amount_col]).replace(",", ""))
                total_amount += item["amount"]
            except ValueError:
                pass

        if item.get("product_name"):
            items.append(item)

    inventory_receipt = InventoryReceipt(
        receipt_number=receipt_number,
        receipt_date=receipt_date,
        supplier=supplier,
        items=items,
        total_amount=total_amount if total_amount > 0 else None
    )

    # 计算置信度
    confidence = 0.0
    if receipt_number:
        confidence += 0.25
    if receipt_date:
        confidence += 0.2
    if supplier:
        confidence += 0.2
    if items:
        confidence += 0.25
    if total_amount > 0:
        confidence += 0.1

    return SourceDocumentResult(
        document_type="inventory_receipt",
        confidence=confidence,
        data=inventory_receipt.model_dump(),
        raw_text=raw_text,
        file_name=file_name
    )


# =============================================================================
# 通用文档解析
# =============================================================================

def parse_general_document(path: str, file_name: str = "") -> SourceDocumentResult:
    """
    通用文档解析

    支持格式：PDF、TXT、图片

    当无法识别为特定类型时，使用此函数。
    直接提取文本内容，保留原始格式，供后续 AI 处理。

    这种设计的好处是：即使不知道是什么类型的文档，
    也能先把内容提取出来，后续可以通过 classify_document
    识别类型后再决定如何进一步处理。
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    raw_text = ""

    if suffix == ".pdf":
        raw_text = _extract_text_from_pdf(path)
    elif suffix == ".txt":
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_text = file_path.read_text(encoding="gbk")
    elif suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
        from app.services.ocr_service import extract_text_from_image
        raw_text = extract_text_from_image(path)
    else:
        raw_text = f"[无法解析的文件格式: {suffix}]"

    # 通用文档置信度较低，因为没有针对性的解析
    confidence = 0.3 if raw_text else 0.0

    return SourceDocumentResult(
        document_type="general",
        confidence=confidence,
        data={"text_length": len(raw_text)},
        raw_text=raw_text,
        file_name=file_name
    )


# =============================================================================
# 智能分类
# =============================================================================

def classify_document(path: str, file_name: str = "") -> SourceDocumentResult:
    """
    智能文档分类

    根据文件名和内容自动识别文档类型。

    分类逻辑：
    1. 先看文件名，通常文件名会包含文档类型的关键词
    2. 如果文件名不明确，再看内容

    常见财务文档类型：
    - 发票：文件名含"发票"、"invoice"
    - 银行流水：文件名含"银行"、"流水"、"bank"、"statement"
    - 合同：文件名含"合同"、"contract"
    - 入库单：文件名含"入库"、"inventory"
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    # 1. 基于文件名的分类
    file_name_lower = file_name.lower()

    # 发票关键词
    if any(kw in file_name_lower for kw in ["发票", "invoice", "增值税"]):
        return parse_invoice(path, file_name)

    # 银行流水关键词
    if any(kw in file_name_lower for kw in ["银行", "流水", "bank", "statement", "交易明细"]):
        return parse_bank_statement(path, file_name)

    # 合同关键词
    if any(kw in file_name_lower for kw in ["合同", "contract", "协议"]):
        return parse_contract(path, file_name)

    # 入库单关键词
    if any(kw in file_name_lower for kw in ["入库", "inventory", "收货", "送货"]):
        return parse_inventory_receipt(path, file_name)

    # 2. 基于后缀的快速判断
    if suffix in {".xlsx", ".xls", ".csv"}:
        # Excel/CSV 文件可能是银行流水或入库单
        # 先尝试银行流水解析
        result = parse_bank_statement(path, file_name)
        if result.confidence > 0.5:
            return result
        # 否则按入库单处理
        return parse_inventory_receipt(path, file_name)

    if suffix == ".pdf":
        # PDF 可能是发票或合同，先提取文本简单判断
        raw_text = _extract_text_from_pdf(path)

        # 简单关键词判断
        if any(kw in raw_text for kw in ["发票号码", "购买方", "销售方", "价税合计"]):
            return parse_invoice(path, file_name)
        if any(kw in raw_text for kw in ["甲方", "乙方", "合同金额", "签订日期"]):
            return parse_contract(path, file_name)

        # 无法明确判断，作为通用文档处理
        return parse_general_document(path, file_name)

    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
        # 图片通常是发票，先尝试 OCR
        from app.services.ocr_service import extract_text_from_image
        raw_text = extract_text_from_image(path)

        if any(kw in raw_text for kw in ["发票", "invoice", "购买方", "销售方"]):
            return parse_invoice(path, file_name)

        return parse_general_document(path, file_name)

    if suffix == ".txt":
        # 文本文件可能是合同
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raw_text = file_path.read_text(encoding="gbk")

        if any(kw in raw_text for kw in ["甲方", "乙方", "合同金额"]):
            return parse_contract(path, file_name)

        return parse_general_document(path, file_name)

    # 无法识别
    return parse_general_document(path, file_name)
