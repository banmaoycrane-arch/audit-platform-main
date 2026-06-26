# -*- coding: utf-8 -*-
from __future__ import annotations

"""
模块功能：解析结果统一数据结构
业务场景：文件解析引擎返回统一格式的解析结果，支持双引擎对比和多LLM对比
政策依据：各类会计准则（CAS 1/9/14/22等）
输入数据：各解析引擎返回的结果
输出结果：统一的ParseResult结构，支持字段来源标注和置信度计算
创建日期：2026-06-26
更新记录：
    2026-06-26  初始创建，定义统一结果数据结构
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import date, datetime
from typing import Any
from enum import Enum


class FileFormat(Enum):
    """
    文件格式类型（扩展支持）
    
    财务文档常见格式分类：
    - PDF类：文字型PDF、图片型PDF、OFD电子发票格式
    - 结构化数据类：Excel、CSV、XML（电子发票标准格式）
    - 图片类：各类图片文件
    - 文档类：纯文本、Word、Markdown
    """
    
    # PDF 类
    PDF_TEXT = "pdf_text"        # 文字型PDF（可直接提取文本）
    PDF_IMAGE = "pdf_image"      # 图片型PDF（需要OCR）
    OFD = "ofd"                  # OFD格式（电子发票专用格式）
    
    # 结构化数据类
    EXCEL = "excel"              # Excel文件（.xlsx/.xls）
    CSV = "csv"                  # CSV文件
    XML = "xml"                  # XML格式（电子发票标准格式）
    
    # 图片类
    IMAGE = "image"              # 图片文件（jpg/png/bmp/tiff）
    
    # 文档类
    TEXT = "text"                # 纯文本文件（.txt）
    WORD = "word"                # Word文档（.doc/.docx）
    MARKDOWN = "markdown"        # Markdown文件（.md）
    
    # 特殊类
    UNKNOWN = "unknown"          # 无法识别


class DocumentType(Enum):
    """
    文档主类型
    
    财务审计常见文档分类：
    - 发票类：各类增值税发票
    - 银行类：流水单、对账单、回单等
    - 合同类：各类合同协议
    - 物流类：入库单、物流单、销售单等
    - 人资类：工资表
    - 费用类：各类费用报销单据
    - 收据类：各类收据凭证
    """
    
    # 现有类型
    INVOICE = "invoice"                  # 发票
    BANK_STATEMENT = "bank_statement"    # 银行流水
    CONTRACT = "contract"                # 合同协议
    INVENTORY_RECEIPT = "inventory_receipt"  # 入库单
    
    # 新增类型
    SALARY_TABLE = "salary_table"        # 工资表
    EXPENSE_DOCUMENT = "expense_document"  # 费用单据
    RECEIPT = "receipt"                  # 收据凭证
    
    # 特殊类型
    ACCOUNTING_ENTRY = "accounting_entry"  # 会计凭证/序时簿
    GENERAL = "general"                  # 通用文档
    UNKNOWN = "unknown"                  # 无法确认（需要二次分析）
    
    @classmethod
    def get_all_types(cls) -> list[DocumentType]:
        """获取所有文档类型列表"""
        return [t for t in cls if t != cls.UNKNOWN]


class DocumentSubType(Enum):
    """
    文档细分类型（引擎自适应识别）
    
    各主类型下的细分场景，用于精确匹配解析策略：
    - 发票细分：专用发票、普通发票、定额发票、电子发票等
    - 银行细分：不同银行、不同单据类型（流水单/对账单/回单）
    - 合同细分：标准合同、简易合同、手写合同、模板化合同等
    """
    
    # === 发票细分类型 ===
    INVOICE_SPECIAL = "invoice_special"        # 增值税专用发票
    INVOICE_NORMAL = "invoice_normal"          # 增值税普通发票
    INVOICE_FIXED = "invoice_fixed"            # 定额发票
    INVOICE_ELECTRONIC = "invoice_electronic"  # 电子发票（XML/OFD格式）
    INVOICE_VAT_GENERAL = "invoice_vat_general"  # 增值税通用机打发票
    
    # === 银行流水细分类型 ===
    BANK_TRANSACTION_LIST = "bank_transaction_list"  # 银行流水单（交易明细）
    BANK_STATEMENT = "bank_statement"                # 银行对账单（期末余额）
    BANK_RECEIPT = "bank_receipt"                    # 银行回单（单笔交易凭证）
    BANK_BALANCE_CONFIRM = "bank_balance_confirm"    # 银行余额确认函
    
    # 银行机构识别（不同银行格式不同）
    BANK_ICBC = "bank_icbc"        # 工商银行
    BANK_ABC = "bank_abc"          # 农业银行
    BANK_BOC = "bank_boc"          # 中国银行
    BANK_CCB = "bank_ccb"          # 建设银行
    BANK_CMBC = "bank_cmbc"        # 招商银行
    BANK_OTHER = "bank_other"      # 其他银行
    
    # === 合同细分类型 ===
    CONTRACT_STANDARD = "contract_standard"        # 标准完整合同（正式格式）
    CONTRACT_SIMPLE = "contract_simple"            # 简易合同（打印版）
    CONTRACT_HANDWRITTEN = "contract_handwritten"  # 手写合同
    CONTRACT_TEMPLATE = "contract_template"        # 模板化合同（如报装单、订单确认单）
    CONTRACT_ORDER = "contract_order"              # 订单/报装单（预定格式）
    
    # === 入库单细分类型（广义物流/销售单据）===
    INVENTORY_STANDARD = "inventory_standard"          # 标准入库单
    LOGISTICS_RECEIPT = "logistics_receipt"            # 物流签收单
    SALES_ORDER = "sales_order"                        # 销售订单
    PURCHASE_ORDER = "purchase_order"                  # 采购订单
    DELIVERY_NOTE = "delivery_note"                    # 送货单
    
    # 电商平台单据
    ECOM_ORDER = "ecom_order"            # 电商平台订单
    ECOM_BILL = "ecom_bill"              # 电商平台账单
    ECOM_SETTLEMENT = "ecom_settlement"  # 电商平台结算单
    
    # === 工资表细分类型 ===
    SALARY_STANDARD = "salary_standard"        # 标准工资表
    SALARY_SIMPLE = "salary_simple"            # 简易工资表
    SALARY_COMMISSION = "salary_commission"    # 提成计算表
    SALARY_DETAILED = "salary_detailed"        # 详细工资明细表
    
    # === 费用单据细分类型（最广义）===
    EXPENSE_TRAVEL = "expense_travel"            # 差旅报销单
    EXPENSE_ENTERTAINMENT = "expense_entertainment"  # 业务招待单
    EXPENSE_OFFICE = "expense_office"            # 办公费用报销单
    EXPENSE_TRANSPORT = "expense_transport"      # 交通费用单
    EXPENSE_TRAIN = "expense_train"              # 培训费用单
    EXPENSE_OTHER = "expense_other"              # 其他费用单据
    
    # 行程类单据
    ITINERARY_FLIGHT = "itinerary_flight"    # 航班行程单
    ITINERARY_TRAIN = "itinerary_train"      # 铁路行程单
    ITINERARY_HOTEL = "itinerary_hotel"      # 酒店订单
    ITINERARY_OTHER = "itinerary_other"      # 其他行程单据
    
    # === 收据细分类型 ===
    RECEIPT_PRINTED = "receipt_printed"      # 印刷收据（标准格式）
    RECEIPT_HANDWRITTEN = "receipt_handwritten"  # 手写收据
    RECEIPT_INVOICE = "receipt_invoice"      # 收据型发票（税务监制）
    RECEIPT_INTERNAL = "receipt_internal"    # 内部收据
    
    # === 未识别类型 ===
    UNKNOWN_PENDING = "unknown_pending"      # 待二次分析
    UNKNOWN_UNSUPPORTED = "unknown_unsupported"  # 不支持的格式


class EngineType(Enum):
    """
    解析引擎类型
    
    标识解析结果来自哪个引擎：
    - RULE: 规则引擎（正则+pandas，速度快）
    - LLM: LLM引擎（语义理解，精度高）
    - FUSED: 融合结果（双引擎合并）
    - WEIGHTED_VOTE: 加权投票结果（多LLM对比）
    """
    
    RULE = "rule"              # 规则引擎
    LLM = "llm"                # LLM引擎
    FUSED = "fused"            # 融合结果
    WEIGHTED_VOTE = "weighted_vote"  # 加权投票结果
    USER_SELECT = "user_select"  # 用户手动选择


@dataclass
class ParseResult:
    """
    统一解析结果数据结构
    
    功能描述：所有解析引擎返回统一格式的结果，便于后续融合和对比
    业务逻辑：
        - document_type: 文档主类型
        - sub_type: 文档细分类型
        - data: 解析提取的字段数据
        - confidence: 解析置信度（0-1）
        - engine: 来源引擎标识
        - raw_text: 原始文本（用于复核）
        - validation_errors: 数据校验错误列表
        - accounting_notes: 会计处理建议
    
    会计口径：
        - 置信度越高表示解析结果越可信
        - validation_errors 用于记录会计勾稽关系错误
        - accounting_notes 提供会计准则级别的处理建议
    """
    
    # 文档类型信息
    document_type: DocumentType
    sub_type: DocumentSubType | None = None
    file_format: FileFormat | None = None
    
    # 解析数据
    data: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    
    # 来源标识
    engine: EngineType = EngineType.RULE
    engine_name: str = ""  # 具体引擎名称（如 "qwen2.5-14b"）
    
    # 文本信息
    raw_text: str = ""
    
    # 校验和说明
    validation_errors: list[str] = field(default_factory=list)
    accounting_notes: str = ""
    
    # 时间戳
    parse_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式，便于JSON序列化"""
        return {
            "file_format": self.file_format.value if self.file_format else "unknown",
            "document_type": self.document_type.value,
            "sub_type": self.sub_type.value if self.sub_type else None,
            "data": self.data,
            "confidence": self.confidence,
            "engine": self.engine.value,
            "engine_name": self.engine_name,
            "validation_errors": self.validation_errors,
            "accounting_notes": self.accounting_notes,
            "parse_time": self.parse_time.isoformat(),
        }


@dataclass
class LLMComparisonResult:
    """
    多LLM引擎对比结果
    
    功能描述：记录多个LLM引擎的解析结果对比分析
    业务逻辑：
        - engine_results: 各引擎的原始解析结果
        - field_agreement: 各字段的一致性率（相同值的比例）
        - final_result: 最终选择的解析结果
        - selection_reason: 选择依据（加权投票/置信度最高/用户选择）
        - field_sources: 各字段的来源引擎标注
    
    会计口径：
        - 字段一致性率越高表示结果越可信
        - 来源标注便于追溯审计
    """
    
    # 各引擎原始结果
    engine_results: dict[str, ParseResult] = field(default_factory=dict)
    # 格式：{"qwen2.5-14b": ParseResult_A, "qwen2.5-7b": ParseResult_B, ...}
    
    # 字段一致性分析
    field_agreement: dict[str, float] = field(default_factory=dict)
    # 格式：{"发票号码": 0.75, "金额": 1.0, ...}
    
    # 最终选择结果
    final_result: ParseResult | None = None
    
    # 选择依据
    selection_reason: str = ""  # "加权投票" / "置信度最高" / "用户选择"
    
    # 引擎来源标注
    field_sources: dict[str, str] = field(default_factory=dict)
    # 格式：{"发票号码": "qwen2.5-14b", "金额": "weighted_vote", ...}
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "engine_results": {
                name: result.to_dict() 
                for name, result in self.engine_results.items()
            },
            "field_agreement": self.field_agreement,
            "final_result": self.final_result.to_dict() if self.final_result else None,
            "selection_reason": self.selection_reason,
            "field_sources": self.field_sources,
        }


@dataclass
class FormatRecognitionResult:
    """
    格式识别结果
    
    功能描述：记录文件格式识别的结果
    业务逻辑：
        - file_format: 识别的文件格式
        - file_suffix: 文件后缀名
        - confidence: 格式识别置信度
        - can_extract_text: 是否可直接提取文本
        - needs_ocr: 是否需要OCR处理
    """
    
    file_format: FileFormat
    file_suffix: str = ""
    confidence: float = 1.0
    can_extract_text: bool = True
    needs_ocr: bool = False
    error_message: str | None = None


@dataclass
class TypeClassificationResult:
    """
    类型判断结果
    
    功能描述：记录文档类型判断的结果
    业务逻辑：
        - document_type: 判断的文档类型
        - sub_type: 细分类型（可选）
        - confidence: 类型判断置信度
        - possible_types: 候选类型列表（冲突时使用）
        - needs_user_confirm: 是否需要用户确认
        - conflict_reason: 冲突原因说明
    """
    
    document_type: DocumentType
    sub_type: DocumentSubType | None = None
    confidence: float = 0.0
    possible_types: list[DocumentType] = field(default_factory=list)
    needs_user_confirm: bool = False
    conflict_reason: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "document_type": self.document_type.value,
            "sub_type": self.sub_type.value if self.sub_type else None,
            "confidence": self.confidence,
            "possible_types": [t.value for t in self.possible_types],
            "needs_user_confirm": self.needs_user_confirm,
            "conflict_reason": self.conflict_reason,
        }


@dataclass
class UnrecognizedFile:
    """
    未识别文件对象
    
    功能描述：对于无法立即识别的文件，记录分析状态和结果
    业务逻辑：
        - 记录文件基本信息和提取内容
        - 记录初次分析和二次分析结果
        - 支持用户手动指定类型
        - 跟踪分析状态（pending/analyzing/identified/failed）
    
    会计口径：
        - 未识别文件需要二次分析或人工复核
        - 分析结果需要记录以便审计追溯
    """
    
    # 基本信息
    file_id: int
    file_path: str
    file_name: str
    file_format: FileFormat
    upload_time: datetime
    
    # 分析状态
    analysis_status: str = "pending"  # pending/analyzing/identified/failed
    
    # 分析结果
    first_analysis: dict[str, Any] = field(default_factory=dict)
    second_analysis: dict[str, Any] = field(default_factory=dict)
    
    # 提取的内容
    extracted_text: str = ""
    extracted_features: dict[str, Any] = field(default_factory=dict)
    
    # 用户反馈
    user_manual_type: DocumentType | None = None
    user_manual_sub_type: DocumentSubType | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "file_id": self.file_id,
            "file_path": self.file_path,
            "file_name": self.file_name,
            "file_format": self.file_format.value,
            "upload_time": self.upload_time.isoformat(),
            "analysis_status": self.analysis_status,
            "first_analysis": self.first_analysis,
            "second_analysis": self.second_analysis,
            "extracted_text": self.extracted_text[:500] if self.extracted_text else "",  # 只返回前500字符
            "extracted_features": self.extracted_features,
            "user_manual_type": self.user_manual_type.value if self.user_manual_type else None,
            "user_manual_sub_type": self.user_manual_sub_type.value if self.user_manual_sub_type else None,
        }


# =============================================================================
# 文档类型标签映射
# =============================================================================

DOCUMENT_TYPE_LABELS: dict[str, str] = {
    "invoice": "发票",
    "bank_statement": "银行流水",
    "contract": "合同",
    "inventory_receipt": "入库单",
    "salary_table": "工资表",
    "expense_document": "费用单据",
    "receipt": "收据凭证",
    "accounting_entry": "会计凭证",
    "general": "通用资料",
    "unknown": "未识别",
}

DOCUMENT_SUB_TYPE_LABELS: dict[str, str] = {
    "invoice_special": "增值税专用发票",
    "invoice_normal": "增值税普通发票",
    "invoice_fixed": "定额发票",
    "invoice_electronic": "电子发票",
    "invoice_vat_general": "增值税通用机打发票",
    
    "bank_transaction_list": "银行流水单",
    "bank_statement": "银行对账单",
    "bank_receipt": "银行回单",
    "bank_balance_confirm": "银行余额确认函",
    "bank_icbc": "工商银行",
    "bank_abc": "农业银行",
    "bank_boc": "中国银行",
    "bank_ccb": "建设银行",
    "bank_cmbc": "招商银行",
    "bank_other": "其他银行",
    
    "contract_standard": "标准完整合同",
    "contract_simple": "简易合同",
    "contract_handwritten": "手写合同",
    "contract_template": "模板化合同",
    "contract_order": "订单/报装单",
    
    "inventory_standard": "标准入库单",
    "logistics_receipt": "物流签收单",
    "sales_order": "销售订单",
    "purchase_order": "采购订单",
    "delivery_note": "送货单",
    "ecom_order": "电商平台订单",
    "ecom_bill": "电商平台账单",
    "ecom_settlement": "电商平台结算单",
    
    "salary_standard": "标准工资表",
    "salary_simple": "简易工资表",
    "salary_commission": "提成计算表",
    "salary_detailed": "详细工资明细表",
    
    "expense_travel": "差旅报销单",
    "expense_entertainment": "业务招待单",
    "expense_office": "办公费用报销单",
    "expense_transport": "交通费用单",
    "expense_train": "培训费用单",
    "expense_other": "其他费用单据",
    
    "itinerary_flight": "航班行程单",
    "itinerary_train": "铁路行程单",
    "itinerary_hotel": "酒店订单",
    "itinerary_other": "其他行程单据",
    
    "receipt_printed": "印刷收据",
    "receipt_handwritten": "手写收据",
    "receipt_invoice": "收据型发票",
    "receipt_internal": "内部收据",
    
    "unknown_pending": "待二次分析",
    "unknown_unsupported": "不支持的格式",
}

FILE_FORMAT_LABELS: dict[str, str] = {
    "pdf_text": "文字型PDF",
    "pdf_image": "图片型PDF",
    "ofd": "OFD电子发票",
    "excel": "Excel文件",
    "csv": "CSV文件",
    "xml": "XML电子发票",
    "image": "图片文件",
    "text": "纯文本",
    "word": "Word文档",
    "markdown": "Markdown文件",
    "unknown": "无法识别",
}