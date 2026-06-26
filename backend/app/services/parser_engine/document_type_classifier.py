# -*- coding: utf-8 -*-
"""
模块功能：文档类型判断层
业务场景：根据文件格式+内容关键词+用户预选，推断文档类型及其细分类型
政策依据：各类会计准则（用于细分类型判断）
输入数据：文件路径、格式识别结果、用户预选类型（可选）
输出结果：TypeClassificationResult（文档类型、细分类型、置信度、候选列表等）
创建日期：2026-06-26
更新记录：
    2026-06-26  初始创建，支持发票、银行流水、合同、入库单、工资表、费用单据、收据等类型判断
"""

import logging
import re
from pathlib import Path

from app.services.parser_engine.parse_result import (
    DocumentType,
    DocumentSubType,
    FileFormat,
    TypeClassificationResult,
    DOCUMENT_TYPE_LABELS,
    DOCUMENT_SUB_TYPE_LABELS,
)
from app.services.parser_engine.format_recognizer import recognize_file_format

logger = logging.getLogger(__name__)


# =============================================================================
# 格式与类型候选映射
# =============================================================================

# 根据文件格式推断的候选类型集
FORMAT_TO_CANDIDATE_TYPES: dict[FileFormat, list[DocumentType]] = {
    FileFormat.PDF_TEXT: [
        DocumentType.INVOICE,
        DocumentType.BANK_STATEMENT,
        DocumentType.CONTRACT,
        DocumentType.RECEIPT,
        DocumentType.GENERAL,
    ],
    FileFormat.PDF_IMAGE: [
        DocumentType.INVOICE,
        DocumentType.BANK_STATEMENT,
        DocumentType.CONTRACT,
        DocumentType.RECEIPT,
        DocumentType.GENERAL,
    ],
    FileFormat.OFD: [
        DocumentType.INVOICE,  # OFD主要用于电子发票
    ],
    FileFormat.XML: [
        DocumentType.INVOICE,  # XML主要用于电子发票
    ],
    FileFormat.EXCEL: [
        DocumentType.INVOICE,
        DocumentType.BANK_STATEMENT,
        DocumentType.SALARY_TABLE,
        DocumentType.EXPENSE_DOCUMENT,
        DocumentType.INVENTORY_RECEIPT,
        DocumentType.ACCOUNTING_ENTRY,
    ],
    FileFormat.CSV: [
        DocumentType.INVOICE,
        DocumentType.BANK_STATEMENT,
        DocumentType.SALARY_TABLE,
        DocumentType.EXPENSE_DOCUMENT,
        DocumentType.INVENTORY_RECEIPT,
        DocumentType.ACCOUNTING_ENTRY,
    ],
    FileFormat.IMAGE: [
        DocumentType.INVOICE,
        DocumentType.RECEIPT,
        DocumentType.CONTRACT,  # 手写合同可能是图片
        DocumentType.GENERAL,
    ],
    FileFormat.TEXT: [
        DocumentType.INVOICE,
        DocumentType.BANK_STATEMENT,
        DocumentType.RECEIPT,
        DocumentType.CONTRACT,
        DocumentType.GENERAL,
    ],
    FileFormat.WORD: [
        DocumentType.INVOICE,
        DocumentType.BANK_STATEMENT,
        DocumentType.RECEIPT,
        DocumentType.CONTRACT,
        DocumentType.GENERAL,
    ],
    FileFormat.MARKDOWN: [
        DocumentType.GENERAL,
    ],
}

# 文档类型关键词映射（用于内容特征判断）
TYPE_KEYWORDS: dict[DocumentType, dict[str, list[str]]] = {
    DocumentType.INVOICE: {
        "primary": ["发票", "invoice", "增值税", "价税合计", "购买方", "销售方"],
        "sub_types": {
            "专用发票": ["专用发票", "专用"],
            "普通发票": ["普通发票", "普通"],
            "定额发票": ["定额发票", "定额", "有奖发票"],
            "电子发票": ["电子发票", "数字化发票"],
            "机打发票": ["机打发票", "通用机打"],
        },
    },
    DocumentType.BANK_STATEMENT: {
        "primary": ["银行", "流水", "bank", "statement", "交易明细", "对账单", "回单"],
        "banks": {
            "工商银行": ["工商银行", "ICBC"],
            "农业银行": ["农业银行", "ABC"],
            "中国银行": ["中国银行", "BOC"],
            "建设银行": ["建设银行", "CCB"],
            "招商银行": ["招商银行", "CMBC"],
        },
        "sub_types": {
            "流水单": ["交易明细", "transaction", "对方账户"],
            "对账单": ["期初余额", "期末余额", "期初", "期末"],
            "回单": ["回单", "凭证号"],
            "余额确认函": ["余额确认", "函"],
        },
    },
    DocumentType.CONTRACT: {
        "primary": ["合同", "contract", "协议", "甲方", "乙方", "签订日期", "合同金额"],
        "sub_types": {
            "标准合同": ["合同编号", "甲方", "乙方", "签订日期", "合同金额", "违约责任"],
            "简易合同": ["甲方", "乙方", "合同金额"],
            "模板合同": ["报装单", "订单确认", "订单号", "订购单", "申请单"],
            "订单": ["报装单", "订单确认", "订单号"],
        },
    },
    DocumentType.INVENTORY_RECEIPT: {
        "primary": ["入库", "inventory", "收货", "验收", "送货", "发货", "物流", "快递", "销售", "采购"],
        "ecom_platforms": {
            "淘宝": ["淘宝", "天猫"],
            "京东": ["京东"],
            "拼多多": ["拼多多"],
            "抖音": ["抖音"],
            "美团": ["美团"],
            "饿了么": ["饿了么"],
        },
        "sub_types": {
            "入库单": ["入库", "收货", "验收"],
            "物流单": ["物流", "快递", "签收", "运单"],
            "销售单": ["销售", "出货", "客户", "订单"],
            "采购单": ["采购", "供应商", "进货"],
            "送货单": ["送货", "发货", "配送"],
        },
    },
    DocumentType.SALARY_TABLE: {
        "primary": ["工资", "salary", "薪酬", "员工", "社保", "公积金", "个税", "实发"],
        "sub_types": {
            "标准工资表": ["基本工资", "奖金", "补贴", "社保", "公积金", "个税"],
            "简易工资表": ["工资", "实发"],
            "提成表": ["提成", "佣金", "业绩"],
        },
    },
    DocumentType.EXPENSE_DOCUMENT: {
        "primary": ["报销", "费用", "差旅", "招待", "办公", "交通", "培训"],
        "itinerary": {
            "航班": ["航班", "机票", "航空"],
            "铁路": ["火车", "铁路", "车票"],
            "酒店": ["酒店", "住宿"],
        },
        "sub_types": {
            "差旅报销": ["差旅", "出差"],
            "招待单": ["招待", "宴请"],
            "办公费用": ["办公", "办公用品"],
            "交通费用": ["交通", "打车", "出租"],
            "培训费用": ["培训", "会议"],
        },
    },
    DocumentType.RECEIPT: {
        "primary": ["收据", "receipt", "收款", "付款", "收条"],
        "sub_types": {
            "印刷收据": ["收据", "No", "编号"],
            "手写收据": [],  # 需要通过OCR特征判断
            "收据型发票": ["税务监制", "发票代码"],
        },
    },
}


class DocumentTypeClassifier:
    """
    文档类型判断器
    
    功能描述：根据格式+内容+用户预选，推断文档类型及其细分类型
    业务逻辑：
        1. 用户预选优先：上传时用户选择类型 → 直接使用
        2. 格式特征：根据文件格式推断候选类型集
        3. 内容关键词：提取文本，匹配关键词缩小范围
        4. 细分类型识别：在确定主类型后，进一步识别细分类型
        5. 冲突处理：格式推断与内容特征不一致 → 返回候选列表
    
    会计口径：
        - 类型判断准确率直接影响后续解析策略
        - 细分类型用于匹配对应的会计准则处理逻辑
    """
    
    def classify(
        self,
        file_path: str,
        file_format: FileFormat | None = None,
        extracted_text: str | None = None,
        user_preselected_type: DocumentType | None = None,
    ) -> TypeClassificationResult:
        """
        判断文档类型
        
        Args:
            file_path: 文件存储路径
            file_format: 文件格式（可选，如果未提供会自动识别）
            extracted_text: 已提取的文本内容（可选）
            user_preselected_type: 用户预选的文档类型（可选）
            
        Returns:
            TypeClassificationResult: 类型判断结果
        """
        # 1. 用户预选优先
        if user_preselected_type:
            sub_type = self._identify_sub_type(
                extracted_text or "",
                user_preselected_type,
                file_format or FileFormat.UNKNOWN,
            )
            return TypeClassificationResult(
                document_type=user_preselected_type,
                sub_type=sub_type,
                confidence=1.0,
                needs_user_confirm=False,
            )
        
        # 2. 获取文件格式（如果未提供）
        if file_format is None:
            format_result = recognize_file_format(file_path)
            file_format = format_result.file_format
        
        # 3. 根据格式获取候选类型集
        candidate_types = FORMAT_TO_CANDIDATE_TYPES.get(file_format, [DocumentType.GENERAL])
        
        # 4. 提取文本内容（如果未提供）
        if extracted_text is None:
            extracted_text = self._extract_text_for_classification(file_path, file_format)
        
        # 5. 根据内容关键词缩小范围
        type_scores = self._calculate_type_scores(extracted_text, candidate_types)
        
        # 6. 选择最佳类型
        if not type_scores:
            return TypeClassificationResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                possible_types=candidate_types,
                needs_user_confirm=True,
                conflict_reason="无法根据内容判断文档类型",
            )
        
        # 按得分排序
        sorted_types = sorted(type_scores.items(), key=lambda x: x[1], reverse=True)
        best_type, best_score = sorted_types[0]
        
        # 7. 检查是否需要用户确认
        needs_confirm = False
        conflict_reason = None
        
        if best_score < 0.3:
            needs_confirm = True
            conflict_reason = "置信度过低，请确认文档类型"
        elif len(sorted_types) > 1:
            second_type, second_score = sorted_types[1]
            if abs(best_score - second_score) < 0.1:
                needs_confirm = True
                conflict_reason = f"类型判断存在歧义（{best_type.value} vs {second_type.value}），请确认"
        
        # 8. 识别细分类型
        sub_type = self._identify_sub_type(extracted_text, best_type, file_format)
        
        return TypeClassificationResult(
            document_type=best_type,
            sub_type=sub_type,
            confidence=best_score,
            possible_types=[t for t, s in sorted_types[:3]],
            needs_user_confirm=needs_confirm,
            conflict_reason=conflict_reason,
        )
    
    def _extract_text_for_classification(self, file_path: str, file_format: FileFormat) -> str:
        """
        为类型判断提取文本内容
        
        注意：这里只做简单提取，用于关键词匹配
        完整的文本提取在后续解析引擎中执行
        
        Args:
            file_path: 文件路径
            file_format: 文件格式
            
        Returns:
            str: 提取的文本内容（前500字符）
        """
        path = Path(file_path)
        
        try:
            if file_format == FileFormat.PDF_TEXT:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    # 只读取前2页
                    text = "\n".join(
                        page.extract_text() or ""
                        for page in pdf.pages[:2]
                    )
                    return text[:500]
            
            elif file_format in {FileFormat.EXCEL, FileFormat.CSV}:
                import pandas as pd
                if file_format == FileFormat.EXCEL:
                    df = pd.read_excel(file_path, nrows=10)
                else:
                    df = pd.read_csv(file_path, nrows=10)
                return df.to_string()[:500]
            
            elif file_format in {FileFormat.TEXT, FileFormat.MARKDOWN}:
                return path.read_text(encoding="utf-8", errors="ignore")[:500]
            
            elif file_format == FileFormat.XML:
                return path.read_text(encoding="utf-8", errors="ignore")[:500]
            
            elif file_format == FileFormat.OFD:
                # OFD需要特殊处理，暂返回文件名
                return path.name
            
            elif file_format in {FileFormat.PDF_IMAGE, FileFormat.IMAGE}:
                # 图片型文件需要OCR，这里暂不处理
                return ""
            
            elif file_format == FileFormat.WORD:
                try:
                    import docx
                    doc = docx.Document(file_path)
                    return "\n".join(p.text for p in doc.paragraphs[:10])[:500]
                except Exception:
                    return ""
            
        except Exception as e:
            logger.warning(f"文本提取失败 {file_path}: {e}")
        
        return ""
    
    def _calculate_type_scores(
        self,
        text: str,
        candidate_types: list[DocumentType],
    ) -> dict[DocumentType, float]:
        """
        计算各候选类型的匹配得分
        
        Args:
            text: 文本内容
            candidate_types: 候选类型列表
            
        Returns:
            dict: {DocumentType: score}
        """
        scores = {}
        text_lower = text.lower()
        
        for doc_type in candidate_types:
            keywords_info = TYPE_KEYWORDS.get(doc_type, {})
            primary_keywords = keywords_info.get("primary", [])
            
            if not primary_keywords:
                scores[doc_type] = 0.1  # 默认得分
                continue
            
            # 计算主关键词匹配数
            matched_count = sum(1 for kw in primary_keywords if kw.lower() in text_lower)
            
            # 计算得分（匹配关键词数量 / 总关键词数量）
            score = matched_count / max(len(primary_keywords), 1)
            
            # 修正：至少匹配2个关键词才认为有效
            if matched_count >= 2:
                score = min(score * 1.5, 1.0)  # 加权
            
            scores[doc_type] = score
        
        return scores
    
    def _identify_sub_type(
        self,
        text: str,
        doc_type: DocumentType,
        file_format: FileFormat,
    ) -> DocumentSubType | None:
        """
        识别细分类型
        
        Args:
            text: 文本内容
            doc_type: 主类型
            file_format: 文件格式
            
        Returns:
            DocumentSubType: 细分类型（可选）
        """
        text_lower = text.lower()
        
        if doc_type == DocumentType.INVOICE:
            return self._identify_invoice_sub_type(text, file_format)
        
        elif doc_type == DocumentType.BANK_STATEMENT:
            return self._identify_bank_sub_type(text)
        
        elif doc_type == DocumentType.CONTRACT:
            return self._identify_contract_sub_type(text, file_format)
        
        elif doc_type == DocumentType.INVENTORY_RECEIPT:
            return self._identify_inventory_sub_type(text)
        
        elif doc_type == DocumentType.SALARY_TABLE:
            return self._identify_salary_sub_type(text)
        
        elif doc_type == DocumentType.EXPENSE_DOCUMENT:
            return self._identify_expense_sub_type(text)
        
        elif doc_type == DocumentType.RECEIPT:
            return self._identify_receipt_sub_type(text, file_format)
        
        return None
    
    def _identify_invoice_sub_type(self, text: str, file_format: FileFormat) -> DocumentSubType:
        """
        发票细分类型识别
        
        识别依据：
        1. 文件格式：XML/OFD → 电子发票
        2. 发票代码：专用发票代码范围 vs 普通发票代码范围
        3. 发票内容关键词：定额发票特征、机打发票特征
        """
        # 格式优先判断
        if file_format in {FileFormat.XML, FileFormat.OFD}:
            return DocumentSubType.INVOICE_ELECTRONIC
        
        # 发票代码判断
        invoice_code_match = re.search(r"发票代码[：:]\s*(\d+)", text)
        if invoice_code_match:
            code = invoice_code_match.group(1)
            # 专用发票代码通常以特定数字开头
            if code.startswith(("3100", "3200", "1100")):
                return DocumentSubType.INVOICE_SPECIAL
            elif code.startswith(("1300", "1400")):
                return DocumentSubType.INVOICE_NORMAL
        
        # 关键词判断
        if "定额发票" in text or "有奖发票" in text:
            return DocumentSubType.INVOICE_FIXED
        
        if "机打发票" in text or "通用机打" in text:
            return DocumentSubType.INVOICE_VAT_GENERAL
        
        # 默认返回普通发票
        return DocumentSubType.INVOICE_NORMAL
    
    def _identify_bank_sub_type(self, text: str) -> DocumentSubType:
        """
        银行流水细分类型识别
        
        识别依据：
        1. 银行名称关键词：识别具体银行
        2. 表头特征：流水单（交易明细） vs 对账单（期初/期末余额） vs 回单（单笔）
        """
        text_lower = text.lower()
        
        # 单据类型识别
        # 流水单特征
        if any(kw in text_lower for kw in ["交易明细", "transaction", "对方账户"]):
            return DocumentSubType.BANK_TRANSACTION_LIST
        
        # 对账单特征
        if any(kw in text for kw in ["期初余额", "期末余额", "期初", "期末"]):
            return DocumentSubType.BANK_STATEMENT
        
        # 回单特征
        if "回单" in text or "凭证号" in text:
            return DocumentSubType.BANK_RECEIPT
        
        # 余额确认函特征
        if "余额确认" in text or "函" in text:
            return DocumentSubType.BANK_BALANCE_CONFIRM
        
        # 默认返回流水单
        return DocumentSubType.BANK_TRANSACTION_LIST
    
    def _identify_contract_sub_type(self, text: str, file_format: FileFormat) -> DocumentSubType:
        """
        合同细分类型识别
        
        识别依据：
        1. 合同完整性：是否包含"合同"字样及完整条款
        2. 格式特征：是否为模板化格式（如报装单、订单确认单）
        """
        # 模板化合同判断
        template_keywords = ["报装单", "订单确认", "订单号", "订购单", "申请单"]
        if any(kw in text for kw in template_keywords):
            return DocumentSubType.CONTRACT_ORDER
        
        # 标准完整合同判断
        standard_keywords = ["合同编号", "甲方", "乙方", "签订日期", "合同金额", "违约责任"]
        matched = sum(1 for kw in standard_keywords if kw in text)
        if matched >= 4:
            return DocumentSubType.CONTRACT_STANDARD
        
        # 简易合同判断
        if matched >= 2:
            return DocumentSubType.CONTRACT_SIMPLE
        
        # 图片型文件可能是手写合同
        if file_format in {FileFormat.PDF_IMAGE, FileFormat.IMAGE}:
            return DocumentSubType.CONTRACT_HANDWRITTEN
        
        return DocumentSubType.CONTRACT_TEMPLATE
    
    def _identify_inventory_sub_type(self, text: str) -> DocumentSubType:
        """
        入库单细分类型识别（广义物流/销售单据）
        
        识别依据：
        1. 单据性质：入库单 vs 物流单 vs 销售单 vs 电商订单
        2. 来源特征：电商平台关键词
        """
        # 电商平台单据判断
        ecom_keywords = ["淘宝", "天猫", "京东", "拼多多", "抖音", "美团", "饿了么"]
        for kw in ecom_keywords:
            if kw in text:
                if "订单" in text:
                    return DocumentSubType.ECOM_ORDER
                elif "账单" in text or "结算" in text:
                    return DocumentSubType.ECOM_SETTLEMENT
                else:
                    return DocumentSubType.ECOM_BILL
        
        # 物流单判断
        logistics_keywords = ["物流", "快递", "签收", "运单", "快递单号"]
        if any(kw in text for kw in logistics_keywords):
            return DocumentSubType.LOGISTICS_RECEIPT
        
        # 销售单判断
        sales_keywords = ["销售", "出货", "客户", "订单"]
        if any(kw in text for kw in sales_keywords):
            return DocumentSubType.SALES_ORDER
        
        # 采购单判断
        purchase_keywords = ["采购", "供应商", "进货"]
        if any(kw in text for kw in purchase_keywords):
            return DocumentSubType.PURCHASE_ORDER
        
        # 送货单判断
        delivery_keywords = ["送货", "发货", "配送"]
        if any(kw in text for kw in delivery_keywords):
            return DocumentSubType.DELIVERY_NOTE
        
        # 标准入库单判断
        inventory_keywords = ["入库", "收货", "验收"]
        if any(kw in text for kw in inventory_keywords):
            return DocumentSubType.INVENTORY_STANDARD
        
        return DocumentSubType.INVENTORY_STANDARD
    
    def _identify_salary_sub_type(self, text: str) -> DocumentSubType:
        """
        工资表细分类型识别
        """
        # 详细工资表
        detailed_keywords = ["基本工资", "奖金", "补贴", "加班费", "社保", "公积金", "个税"]
        matched = sum(1 for kw in detailed_keywords if kw in text)
        if matched >= 5:
            return DocumentSubType.SALARY_DETAILED
        
        # 提成计算表
        if "提成" in text or "佣金" in text or "业绩" in text:
            return DocumentSubType.SALARY_COMMISSION
        
        # 简易工资表
        if matched <= 2:
            return DocumentSubType.SALARY_SIMPLE
        
        return DocumentSubType.SALARY_STANDARD
    
    def _identify_expense_sub_type(self, text: str) -> DocumentSubType:
        """
        费用单据细分类型识别（最广义）
        """
        # 行程类单据判断（优先判断）
        if "航班" in text or "机票" in text or "航空" in text:
            return DocumentSubType.ITINERARY_FLIGHT
        
        if "火车" in text or "铁路" in text or "车票" in text:
            return DocumentSubType.ITINERARY_TRAIN
        
        if "酒店" in text or "住宿" in text:
            return DocumentSubType.ITINERARY_HOTEL
        
        # 差旅报销单判断
        if "差旅" in text or "出差" in text:
            return DocumentSubType.EXPENSE_TRAVEL
        
        # 业务招待判断
        if "招待" in text or "宴请" in text:
            return DocumentSubType.EXPENSE_ENTERTAINMENT
        
        # 办公费用判断
        if "办公" in text or "办公用品" in text:
            return DocumentSubType.EXPENSE_OFFICE
        
        # 交通费用判断
        if "交通" in text or "打车" in text or "出租" in text:
            return DocumentSubType.EXPENSE_TRANSPORT
        
        # 培训费用判断
        if "培训" in text or "会议" in text:
            return DocumentSubType.EXPENSE_TRAIN
        
        return DocumentSubType.EXPENSE_OTHER
    
    def _identify_receipt_sub_type(self, text: str, file_format: FileFormat) -> DocumentSubType:
        """
        收据细分类型识别
        """
        # 收据型发票（税务监制）
        if "税务监制" in text or "发票代码" in text:
            return DocumentSubType.RECEIPT_INVOICE
        
        # 图片型可能是手写收据
        if file_format in {FileFormat.PDF_IMAGE, FileFormat.IMAGE}:
            return DocumentSubType.RECEIPT_HANDWRITTEN
        
        # 内部收据
        if "内部" in text or "非税" in text:
            return DocumentSubType.RECEIPT_INTERNAL
        
        # 印刷收据（标准格式）
        return DocumentSubType.RECEIPT_PRINTED
    
    def get_type_label(self, doc_type: DocumentType) -> str:
        """获取文档类型的中文标签"""
        return DOCUMENT_TYPE_LABELS.get(doc_type.value, "未知类型")
    
    def get_sub_type_label(self, sub_type: DocumentSubType) -> str:
        """获取细分类型的中文标签"""
        return DOCUMENT_SUB_TYPE_LABELS.get(sub_type.value, "未知细分类型")


def classify_document_type(
    file_path: str,
    file_format: FileFormat | None = None,
    extracted_text: str | None = None,
    user_preselected_type: DocumentType | None = None,
) -> TypeClassificationResult:
    """
    便捷函数：判断文档类型
    
    Args:
        file_path: 文件存储路径
        file_format: 文件格式（可选）
        extracted_text: 已提取的文本内容（可选）
        user_preselected_type: 用户预选的文档类型（可选）
        
    Returns:
        TypeClassificationResult: 类型判断结果
    """
    classifier = DocumentTypeClassifier()
    return classifier.classify(file_path, file_format, extracted_text, user_preselected_type)