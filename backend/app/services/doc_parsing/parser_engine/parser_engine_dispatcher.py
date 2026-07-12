# -*- coding: utf-8 -*-
"""
模块功能：解析引擎调度层
业务场景：双引擎并行解析、多LLM引擎对比、结果融合、未识别文件处理
政策依据：各类会计准则（CAS 1/9/14/22等）
输入数据：文件路径、用户预选类型、配置参数
输出结果：ParseResult 或 LLMComparisonResult
创建日期：2026-06-26
更新记录：
    2026-06-26  初始创建，实现双引擎并行、多LLM对比、结果融合
"""

import asyncio
import json
import logging
import time
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

from app.core.config import get_settings
from app.services.doc_parsing.parser_engine.config_service import (
    config_for_parse_llm,
    get_runtime_parser_engine_config,
    resolve_effective_comparison_engines,
    resolve_parse_model,
)
from app.services.doc_parsing.parser_engine.parse_result import (
    DocumentType,
    DocumentSubType,
    EngineType,
    FileFormat,
    ParseResult,
    LLMComparisonResult,
    FormatRecognitionResult,
    TypeClassificationResult,
    UnrecognizedFile,
    SealRecognitionResult,
)
from app.services.doc_parsing.parser_engine.field_alias_catalog import (
    ALL_FIELD_ALIASES,
    normalize_field_name as normalize_field_name_from_catalog,
)
from app.services.doc_parsing.parser_engine.parser_engine_analyzer import (
    analyze_dual_engine_result,
    report_to_dict,
)
from app.services.doc_parsing.parser_engine.parse_quality_metric_service import (
    record_parse_quality_metric,
)
from app.services.doc_parsing.parser_engine.format_recognizer import recognize_file_format
from app.services.doc_parsing.parser_engine.document_type_classifier import classify_document_type
from app.services.basic_data.source_document_service import classify_document
from app.services.agent.llm_client_service import LightweightLLMClient

logger = logging.getLogger(__name__)


def _load_seal_services() -> tuple[Any, Any, Any, Any]:
    """按需加载印章服务，避免 Excel-only 部署强依赖 OpenCV。"""
    from app.services.basic_data.seal_detection_service import detect_seals
    from app.services.basic_data.seal_extraction_service import extract_seal_region
    from app.services.basic_data.seal_ocr_service import (
        recognize_seal_text,
        text_items_to_dict_list,
    )

    return detect_seals, extract_seal_region, recognize_seal_text, text_items_to_dict_list


# =============================================================================
# 辅助函数：文本提取
# =============================================================================

def _extract_text_from_ofd(file_path: str) -> str:
    """
    从OFD文件中提取文本内容
    
    OFD（Open Fixed-layout Document）是中国国家标准的电子文件格式，
    本质上是一个ZIP压缩包，包含XML文件描述文档内容。
    
    功能描述：解压OFD文件，提取XML内容并解析文本
    业务逻辑：
        1. 将OFD文件作为ZIP解压
        2. 读取Document.xml文件获取文档结构
        3. 读取Content.xml文件获取页面内容
        4. 提取文本元素并合并
    
    Args:
        file_path: OFD文件路径
        
    Returns:
        str: 提取的文本内容
    """
    text_parts = []
    
    try:
        with zipfile.ZipFile(file_path, 'r') as zf:
            file_list = zf.namelist()
            
            for file_name in file_list:
                if file_name.endswith('.xml'):
                    try:
                        with zf.open(file_name) as xml_file:
                            content = xml_file.read().decode('utf-8', errors='ignore')
                            text_parts.append(f"=== {file_name} ===")
                            text_parts.append(_format_xml_text(content))
                    except Exception as e:
                        logger.debug(f"读取OFD中的XML文件失败 {file_name}: {e}")
        
        return "\n\n".join(text_parts)
    
    except Exception as e:
        logger.warning(f"OFD文本提取失败 {file_path}: {e}")
        return ""


def _format_xml_text(xml_content: str) -> str:
    """
    格式化XML文本，提取标签内容
    
    功能描述：将XML格式的文本转换为易读的文本格式
    业务逻辑：
        1. 解析XML结构
        2. 提取所有文本节点
        3. 去除多余空白字符
        4. 返回纯文本内容
    
    Args:
        xml_content: XML格式的字符串
        
    Returns:
        str: 格式化后的纯文本内容
    """
    try:
        root = ET.fromstring(xml_content)
        
        def _get_text(element: ET.Element) -> str:
            texts = []
            if element.text:
                texts.append(element.text.strip())
            for child in element:
                texts.append(_get_text(child))
                if child.tail:
                    texts.append(child.tail.strip())
            return "\n".join(t for t in texts if t)
        
        return _get_text(root)
    
    except Exception as e:
        logger.debug(f"XML解析失败，返回原始内容: {e}")
        return xml_content


def extract_text_from_file(file_path: str, file_format: FileFormat, sheet_name: str | None = None) -> str:
    """
    从文件中提取文本内容
    
    功能描述：根据文件格式选择合适的提取方法
    业务逻辑：
        - PDF文字型：使用 pdfplumber
        - PDF图片型/图片：使用 OCR
        - Excel/CSV：使用 pandas
        - XML/OFD/TEXT：直接读取
        - Word：使用 docx
    
    Args:
        file_path: 文件存储路径
        file_format: 文件格式类型
        sheet_name: Excel工作表名称（可选）
        
    Returns:
        str: 提取的文本内容
    """
    path = Path(file_path)
    
    try:
        if file_format == FileFormat.PDF_TEXT:
            import pdfplumber
            text_parts = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ""
                    text_parts.append(page_text)
            return "\n".join(text_parts)
        
        elif file_format in {FileFormat.PDF_IMAGE, FileFormat.IMAGE}:
            # 图片型文件需要OCR
            from app.services.doc_parsing.ocr_service import extract_text_from_image
            return extract_text_from_image(file_path)
        
        elif file_format == FileFormat.EXCEL:
            import pandas as pd
            if sheet_name:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
            else:
                df = pd.read_excel(file_path)
            return cast(str, df.to_string())
        
        elif file_format == FileFormat.CSV:
            import pandas as pd
            df = pd.read_csv(file_path)
            return cast(str, df.to_string())
        
        elif file_format == FileFormat.XML:
            raw_content = path.read_text(encoding="utf-8", errors="ignore")
            return _format_xml_text(raw_content)
        
        elif file_format == FileFormat.OFD:
            return _extract_text_from_ofd(file_path)
        
        elif file_format in {FileFormat.TEXT, FileFormat.MARKDOWN}:
            return path.read_text(encoding="utf-8", errors="ignore")
        
        elif file_format == FileFormat.WORD:
            try:
                import docx
                doc = docx.Document(file_path)
                return "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                return ""
        
    except Exception as e:
        logger.warning(f"文本提取失败 {file_path}: {e}")
        return ""
    
    return ""


# =============================================================================
# 规则引擎解析
# =============================================================================

FIELD_IMPORTANCE_WEIGHTS: dict[str, dict[str, float]] = {
    "invoice": {
        "invoice_no": 1.0,
        "invoice_code": 0.8,
        "invoice_date": 1.0,
        "seller_name": 1.0,
        "seller_tax_id": 0.8,
        "buyer_name": 1.0,
        "buyer_tax_id": 0.8,
        "total_amount": 1.0,
        "amount_excl_tax": 0.8,
        "tax_amount": 0.8,
        "tax_rate": 0.6,
        "goods_name": 0.6,
    },
    "bank_statement": {
        "account_name": 1.0,
        "account_no": 1.0,
        "bank_name": 0.8,
        "transaction_amount": 1.0,
        "transaction_time": 0.8,
        "receipt_no": 0.8,
        "counterparty_name": 0.8,
        "counterparty_account_no": 0.6,
        "purpose": 0.6,
    },
    "contract": {
        "contract_no": 1.0,
        "contract_name": 1.0,
        "party_a_name": 1.0,
        "party_b_name": 1.0,
        "contract_amount": 1.0,
        "sign_date": 1.0,
        "effective_date": 0.8,
        "expiry_date": 0.8,
        "contract_subject": 0.6,
    },
    "inventory_receipt": {
        "receipt_no": 1.0,
        "receipt_date": 1.0,
        "supplier_name": 1.0,
        "warehouse_name": 0.8,
        "total_amount": 1.0,
        "total_quantity": 0.8,
    },
    "salary_table": {
        "salary_period": 1.0,
        "department": 0.8,
        "gross_total": 1.0,
        "net_total": 1.0,
        "employee_count": 0.6,
    },
    "expense_document": {
        "document_no": 0.8,
        "expense_date": 1.0,
        "applicant_name": 1.0,
        "applicant_department": 0.8,
        "total_amount": 1.0,
        "approval_status": 0.8,
    },
    "receipt": {
        "receipt_no": 1.0,
        "receipt_date": 1.0,
        "payer_name": 1.0,
        "payee_name": 1.0,
        "amount": 1.0,
        "reason": 0.6,
    },
    "accounting_entry": {
        "document_no": 1.0,
        "date": 1.0,
        "summary": 0.8,
        "subject_code": 1.0,
        "subject_name": 1.0,
        "debit_amount": 1.0,
        "credit_amount": 1.0,
        "balance": 0.6,
    },
}


def _calculate_weighted_confidence(parsed_data: dict[str, Any], document_type: str) -> float:
    """
    计算加权置信度
    
    功能描述：根据字段重要性权重计算解析结果的置信度
    业务逻辑：
        1. 获取该文档类型的字段权重配置
        2. 遍历解析结果，累加已填充字段的权重
        3. 计算加权置信度（已填充权重/总权重）
        4. 对关键字段缺失进行额外惩罚
        
    Args:
        parsed_data: 解析结果数据
        document_type: 文档类型
        
    Returns:
        float: 加权置信度（0.0-1.0）
    """
    weights = FIELD_IMPORTANCE_WEIGHTS.get(document_type, {})
    
    if not weights:
        total_fields = len(parsed_data)
        filled_fields = sum(1 for v in parsed_data.values() if v is not None and v != "")
        return min(0.95, filled_fields / total_fields) if total_fields > 0 else 0.0
    
    total_weight = sum(weights.values())
    filled_weight = 0.0
    
    critical_fields_missing = 0
    critical_fields = [k for k, w in weights.items() if w >= 1.0]
    
    for field, weight in weights.items():
        value = parsed_data.get(field)
        if value is not None and value != "" and value != []:
            filled_weight += weight
        elif weight >= 1.0:
            critical_fields_missing += 1
    
    confidence = filled_weight / total_weight if total_weight > 0 else 0.0
    
    if critical_fields_missing > len(critical_fields) // 2:
        confidence *= 0.7
    
    return min(0.95, max(0.0, confidence))


def parse_with_rule_engine(
    file_path: str,
    document_type: DocumentType,
    extracted_text: str,
    file_format: FileFormat | None = None,
    db: Any = None,
) -> ParseResult:
    """
    规则引擎解析
    
    功能描述：使用规则解析器解析各类财务文档的结构化数据
    业务逻辑：
        1. 根据文档类型选择对应的规则解析器
        2. 使用正则表达式提取关键字段
        3. 构建结构化数据
        4. 如果传入数据库会话，应用动态规则补丁
        5. 计算加权置信度（基于字段重要性权重）
    
    Args:
        file_path: 文件存储路径
        document_type: 文档类型
        extracted_text: 已提取的文本内容
        file_format: 文件格式（可选）
        db: 数据库会话（可选，用于动态规则加载）
        
    Returns:
        ParseResult: 规则引擎解析结果
    """
    from app.services.doc_parsing.parser_engine.rule_parsers import parse_with_rules
    from app.services.doc_parsing.parser_engine.parser_evolution_service import (
        get_active_column_header_aliases,
    )
    
    try:
        parsed_data = parse_with_rules(
            document_type.value,
            extracted_text,
            file_path,
            header_aliases=(
                get_active_column_header_aliases(db, document_type.value) if db is not None else None
            ),
        )
        
        if db is not None:
            from app.services.doc_parsing.parser_engine.correction_loop_service import (
                apply_dynamic_rules,
            )
            parsed_data = apply_dynamic_rules(db, document_type.value, parsed_data, extracted_text)
        
        confidence = _calculate_weighted_confidence(parsed_data, document_type.value)
        
        # 判断细分类型（基于数据内容）
        sub_type = _determine_sub_type(document_type, parsed_data)
        
        return ParseResult(
            document_type=document_type,
            sub_type=sub_type,
            file_format=file_format,
            data=parsed_data,
            confidence=confidence,
            engine=EngineType.RULE,
            engine_name="rule_engine",
            raw_text=extracted_text[:2000],
            validation_errors=[],
            accounting_notes="",
        )
        
    except Exception as e:
        logger.error(f"规则引擎解析失败 {file_path}: {e}")
        return ParseResult(
            document_type=document_type,
            file_format=file_format,
            confidence=0.0,
            engine=EngineType.RULE,
            engine_name="rule_engine",
            validation_errors=[f"规则引擎解析失败: {e}"],
        )


def _determine_sub_type(document_type: DocumentType, data: dict[str, Any]) -> DocumentSubType | None:
    """
    根据解析数据确定文档细分类型
    
    功能描述：基于解析出的数据特征判断文档细分类型
    业务逻辑：
        发票：根据金额和税率判断专用/普通/电子发票
        银行流水：根据交易记录数量判断流水单/对账单
        合同：根据金额大小判断
        
    Args:
        document_type: 文档类型
        data: 解析出的结构化数据
        
    Returns:
        DocumentSubType: 细分类型，或 None
    """
    if document_type == DocumentType.INVOICE:
        amount = data.get("total_amount")
        if amount and amount > 0:
            if data.get("tax_rate"):
                return DocumentSubType.INVOICE_NORMAL
            return DocumentSubType.INVOICE_ELECTRONIC
        return DocumentSubType.INVOICE_NORMAL
    
    elif document_type == DocumentType.BANK_STATEMENT:
        transactions = data.get("transactions", [])
        if len(transactions) > 10:
            return DocumentSubType.BANK_TRANSACTION_LIST
        return DocumentSubType.BANK_STATEMENT
    
    elif document_type == DocumentType.CONTRACT:
        amount = data.get("contract_amount")
        if amount and amount > 100000:
            return DocumentSubType.CONTRACT_STANDARD
        return DocumentSubType.CONTRACT_STANDARD
    
    return None


# =============================================================================
# LLM 引擎解析
# =============================================================================

def _calculate_objective_confidence(
    document_type: DocumentType,
    fields: dict[str, Any],
) -> float:
    """
    计算客观置信度（基于关键字段提取率）

    功能描述：根据提取到的关键字段比例计算客观置信度
    业务逻辑：
        1. 定义各文档类型的关键字段（核心字段权重高）
        2. 统计成功提取的字段比例
        3. 按权重加权计算置信度
        4. 核心字段提取率影响更大

    会计口径：
        - 核心字段（金额、日期、编号、双方名称）权重更高
        - 辅助字段权重较低
        - 确保关键会计信息完整时置信度较高

    Args:
        document_type: 文档类型
        fields: 提取到的字段字典

    Returns:
        float: 客观置信度（0-1之间）
    """
    if not fields:
        return 0.0

    # 定义各文档类型的关键字段及权重
    # 格式：[(字段名, 权重)]
    key_fields_config = {
        DocumentType.CONTRACT: [
            ("party_a_name", 1.5),      # 甲方名称 - 核心
            ("party_b_name", 1.5),      # 乙方名称 - 核心
            ("contract_amount", 1.5),   # 合同金额 - 核心
            ("contract_no", 1.2),       # 合同编号 - 重要
            ("sign_date", 1.2),         # 签订日期 - 重要
            ("contract_type", 1.0),     # 合同类型
            ("contract_term", 0.8),     # 合同期限
            ("project_name", 0.8),      # 项目名称
            ("payment_terms", 0.7),     # 付款方式
            ("liability_clause", 0.5),  # 违约责任
            ("party_a_tax_id", 0.7),    # 甲方税号
            ("party_b_tax_id", 0.7),    # 乙方税号
        ],
        DocumentType.INVOICE: [
            ("total_amount", 1.5),      # 价税合计 - 核心
            ("invoice_no", 1.2),        # 发票号码 - 重要
            ("invoice_date", 1.2),      # 开票日期 - 重要
            ("seller_name", 1.2),       # 销售方名称 - 重要
            ("buyer_name", 1.2),        # 购买方名称 - 重要
            ("amount_excl_tax", 1.0),   # 不含税金额
            ("tax_amount", 1.0),        # 税额
            ("tax_rate", 0.8),          # 税率
            ("invoice_code", 0.8),      # 发票代码
            ("seller_tax_id", 0.7),     # 销售方税号
            ("buyer_tax_id", 0.7),      # 购买方税号
        ],
        DocumentType.BANK_STATEMENT: [
            ("transaction_amount", 1.5),  # 交易金额 - 核心
            ("transaction_date", 1.2),    # 交易日期 - 重要
            ("counterparty_name", 1.2),   # 对方名称 - 重要
            ("account_no", 1.0),          # 账号
            ("bank_name", 0.8),           # 银行名称
            ("summary", 0.8),             # 摘要
            ("balance", 0.7),             # 余额
        ],
    }

    # 默认权重配置（如果没有特殊配置）
    default_fields = list(fields.keys())[:8]
    fields_config = key_fields_config.get(
        document_type,
        [(f, 1.0) for f in default_fields],
    )

    if not fields_config:
        return 0.5

    total_weight = 0.0
    extracted_weight = 0.0

    for field_name, weight in fields_config:
        total_weight += weight
        value = fields.get(field_name)
        # 字段不为空、不为null、不为空字符串才算提取成功
        if value is not None and value != "" and value != "null":
            extracted_weight += weight

    if total_weight == 0:
        return 0.0

    confidence = extracted_weight / total_weight
    return round(min(1.0, confidence), 3)


def parse_with_llm_engine(
    file_path: str,
    document_type: DocumentType,
    extracted_text: str,
    model_name: str | None = None,
    file_format: FileFormat | None = None,
    llm_config: dict[str, Any] | None = None,
) -> ParseResult:
    """
    LLM 引擎解析
    
    功能描述：使用 LLM 进行语义理解解析
    业务逻辑：
        - 构建提示词（包含文档类型和会计准则要求）
        - 调用 LLM API
        - 解析 JSON 结果
        - 计算置信度
    
    Args:
        file_path: 文件存储路径
        document_type: 文档类型
        extracted_text: 已提取的文本内容
        model_name: LLM 模型名称（可选）
        file_format: 文件格式（可选）
        llm_config: LLM配置字典（可选），包含ai_base_url, ai_model, ai_api_key等
        
    Returns:
        ParseResult: LLM 引擎解析结果
    """
    settings = get_settings()
    
    # 确定LLM配置
    if llm_config is None:
        llm_config = {}
    
    # 确定模型名称
    if model_name is None:
        model_name = llm_config.get("ai_model") or settings.llm_preferred_model
    
    # 构建 LLM 客户端
    llm_client = LightweightLLMClient(config=llm_config if llm_config.get("ai_base_url") else None)
    
    if not llm_client.is_configured():
        logger.warning(f"LLM 未配置，跳过 LLM 解析")
        return ParseResult(
            document_type=document_type,
            file_format=file_format,
            confidence=0.0,
            engine=EngineType.LLM,
            engine_name=model_name,
            validation_errors=["LLM 未配置"],
        )
    
    # 构建提示词
    prompt = build_llm_prompt(document_type, extracted_text)

    # 注入知识库：优先使用运行时配置中的 llm_knowledge_base，未配置则回退到环境变量
    knowledge_base = llm_config.get("llm_knowledge_base") or settings.llm_knowledge_base or ""
    if knowledge_base:
        system_content = (
            "你是一个专业的财务审计助手，擅长解析各类财务文档。"
            "请严格按照JSON格式返回结果。\n\n"
            "【解析知识库】\n"
            f"{knowledge_base}"
        )
        logger.info(f"LLM解析注入知识库，长度: {len(knowledge_base)} 字符")
    else:
        system_content = "你是一个专业的财务审计助手，擅长解析各类财务文档。请严格按照JSON格式返回结果。"

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": prompt},
    ]
    
    try:
        # 调用 LLM
        llm_result = llm_client.chat(messages, temperature=0.1)
        
        if not llm_result.available:
            logger.warning(f"LLM 调用失败: {llm_result.error}")
            validation_errors = [llm_result.error] if llm_result.error else []
            return ParseResult(
                document_type=document_type,
                file_format=file_format,
                confidence=0.0,
                engine=EngineType.LLM,
                engine_name=model_name,
                validation_errors=validation_errors,
            )
        
        # 解析 JSON 结果
        content = llm_result.content
        if content:
            # 去除 Markdown 代码块标记（如 ```json ... ```），兼容不同 LLM 输出格式
            cleaned_content = content.strip()
            if cleaned_content.startswith("```"):
                cleaned_content = cleaned_content.split("\n", 1)[1] if "\n" in cleaned_content else ""
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content.rsplit("\n", 1)[0]
            cleaned_content = cleaned_content.strip()
            data = json.loads(cleaned_content)
            
            # 提取置信度（LLM 自评估）
            llm_self_confidence = data.get("confidence", 0.7)
            
            # 计算客观置信度（基于关键字段提取率）
            objective_confidence = _calculate_objective_confidence(
                document_type, data.get("fields", {})
            )
            
            # 融合置信度：客观60% + 主观40%，避免模型过度自谦
            confidence = objective_confidence * 0.6 + llm_self_confidence * 0.4
            confidence = round(min(1.0, max(0.0, confidence)), 3)
            
            # 提取校验错误
            validation_errors = data.get("validation_errors", [])
            
            # 提取会计建议
            accounting_notes = data.get("accounting_notes", "")
            
            logger.info(
                f"LLM解析完成 - 文档类型: {document_type.value}, "
                f"客观置信度: {objective_confidence:.3f}, "
                f"模型自评估: {llm_self_confidence:.3f}, "
                f"融合置信度: {confidence:.3f}"
            )

            # 金额字段后处理：清洗LLM返回的金额字符串，去除符号和千分位
            parsed_fields = data.get("fields", {})
            parsed_fields = _clean_llm_amount_fields(parsed_fields)

            return ParseResult(
                document_type=document_type,
                sub_type=None,
                file_format=file_format,
                data=parsed_fields,
                confidence=confidence,
                engine=EngineType.LLM,
                engine_name=model_name,
                raw_text=extracted_text[:1000],
                validation_errors=validation_errors,
                accounting_notes=accounting_notes,
            )
        
    except json.JSONDecodeError as e:
        logger.error(f"LLM 结果 JSON 解析失败: {e}")
        return ParseResult(
            document_type=document_type,
            file_format=file_format,
            confidence=0.0,
            engine=EngineType.LLM,
            engine_name=model_name,
            validation_errors=[f"JSON 解析失败: {e}"],
        )
    
    except Exception as e:
        logger.error(f"LLM 引擎解析失败 {file_path}: {e}")
        return ParseResult(
            document_type=document_type,
            file_format=file_format,
            confidence=0.0,
            engine=EngineType.LLM,
            engine_name=model_name,
            validation_errors=[f"LLM 引擎解析失败: {e}"],
        )
    
    return ParseResult(
        document_type=document_type,
        file_format=file_format,
        confidence=0.0,
        engine=EngineType.LLM,
        engine_name=model_name,
    )


# 需要清洗的金额字段名集合
_AMOUNT_FIELD_NAMES = {
    "amount_excl_tax", "tax_amount", "total_amount",
    "transaction_amount", "balance", "contract_amount",
    "closing_balance", "opening_balance",
    "total_inflow", "total_outflow",
}


def _clean_llm_amount_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """
    功能描述：清洗LLM返回的金额字段，去除货币符号和千分位逗号
    业务逻辑：
        1. 识别金额相关字段名
        2. 去除 ¥、￥、元、, 等非数字字符（保留负号和小数点）
        3. 如果清洗后为空或非数字，保留原始值
    会计口径：金额统一为纯数字字符串，便于后续Decimal转换

    Args:
        fields: LLM返回的字段字典

    Returns:
        dict: 清洗后的字段字典
    """
    import re

    cleaned = dict(fields)
    for key in list(cleaned.keys()):
        if key in _AMOUNT_FIELD_NAMES:
            value = cleaned[key]
            if value is None or not isinstance(value, str):
                continue
            # 去除货币符号、千分位逗号、中文单位
            cleaned_value = re.sub(r'[¥￥元,\s]', '', value.strip())
            # 验证清洗后是否为有效数字（含负号和小数点）
            if cleaned_value and re.match(r'^-?\d+\.?\d*$', cleaned_value):
                cleaned[key] = cleaned_value
            elif cleaned_value == '' and value.strip() != '':
                # 原始值非空但清洗后为空，说明格式异常，记录但不覆盖
                logger.warning(f"金额字段 {key} 清洗异常：原始值='{value}', 清洗后='{cleaned_value}'")
    return cleaned


def build_llm_prompt(document_type: DocumentType, extracted_text: str) -> str:
    """
    构建 LLM 提示词
    
    功能描述：根据文档类型构建针对性的提示词
    业务逻辑：
        - 包含文档类型说明
        - 包含字段提取要求（明确中英文对应）
        - 包含返回格式示例
        - 包含置信度自评估要求
    
    会计口径：
        - 字段名与规则引擎保持一致，便于后续对比
    
    Args:
        document_type: 文档类型
        extracted_text: 已提取的文本内容
        
    Returns:
        str: 构建的提示词
    """
    # 文档类型说明
    type_descriptions = {
        DocumentType.INVOICE: "增值税发票（可能为专用发票、普通发票、定额发票、电子发票）",
        DocumentType.BANK_STATEMENT: "银行流水单、银行对账单或银行回单",
        DocumentType.CONTRACT: "合同协议（可能为标准合同、简易合同、采购合同、销售合同、工程合同等）",
        DocumentType.INVENTORY_RECEIPT: "入库单、物流单、销售单或电商订单",
        DocumentType.SALARY_TABLE: "工资表或薪酬计算表",
        DocumentType.EXPENSE_DOCUMENT: "费用报销单据（可能为差旅报销、招待单、行程单等）",
        DocumentType.RECEIPT: "收据凭证",
    }
    
    doc_type_desc = type_descriptions.get(document_type, "财务文档")
    
    # 字段提取要求（中英文对照，确保LLM输出正确的英文key）
    field_requirements = {
        DocumentType.INVOICE: [
            ("invoice_no", "发票号码"),
            ("invoice_code", "发票代码"),
            ("invoice_date", "开票日期"),
            ("buyer_name", "购买方名称"),
            ("buyer_tax_id", "购买方税号"),
            ("seller_name", "销售方名称"),
            ("seller_tax_id", "销售方税号"),
            ("amount_excl_tax", "不含税金额"),
            ("tax_rate", "税率"),
            ("tax_amount", "税额"),
            ("total_amount", "价税合计"),
            ("invoice_type", "发票类型"),
        ],
        DocumentType.BANK_STATEMENT: [
            ("bank_name", "银行名称"),
            ("account_no", "账号"),
            ("transaction_date", "交易日期"),
            ("transaction_amount", "交易金额"),
            ("counterparty_account", "对方账户"),
            ("counterparty_name", "对方名称"),
            ("summary", "摘要"),
            ("balance", "余额"),
            ("document_type", "单据类型"),
        ],
        DocumentType.CONTRACT: [
            ("contract_no", "合同编号"),
            ("contract_name", "合同名称"),
            ("party_a_name", "甲方名称"),
            ("party_a_tax_id", "甲方税号/统一社会信用代码"),
            ("party_a_address", "甲方地址"),
            ("party_b_name", "乙方名称"),
            ("party_b_tax_id", "乙方税号/统一社会信用代码"),
            ("party_b_address", "乙方地址"),
            ("sign_date", "签订日期"),
            ("contract_amount", "合同金额（含税总价）"),
            ("contract_amount_cn", "合同金额大写"),
            ("contract_term", "合同期限"),
            ("contract_type", "合同类型（如采购合同、销售合同、工程合同、服务合同等）"),
            ("project_name", "项目名称（如涉及）"),
            ("payment_terms", "付款方式和条件"),
            ("liability_clause", "违约责任简述"),
        ],
        DocumentType.INVENTORY_RECEIPT: [
            ("document_no", "单据编号"),
            ("date", "日期"),
            ("counterparty_name", "供应商/客户名称"),
            ("goods_name", "物品名称"),
            ("quantity", "数量"),
            ("unit_price", "单价"),
            ("total_amount", "金额"),
            ("document_type", "单据类型"),
        ],
        DocumentType.SALARY_TABLE: [
            ("salary_period", "工资期间"),
            ("employee_count", "员工数"),
            ("total_salary", "工资总额"),
            ("total_personal_income_tax", "个税合计"),
            ("total_social_insurance", "社保合计"),
            ("total_housing_fund", "公积金合计"),
            ("total_net_pay", "实发合计"),
        ],
        DocumentType.EXPENSE_DOCUMENT: [
            ("reimbursement_date", "报销日期"),
            ("reimburser_name", "报销人"),
            ("expense_type", "报销类型"),
            ("total_amount", "报销金额"),
            ("expense_details", "费用明细"),
            ("approval_status", "审批状态"),
        ],
        DocumentType.RECEIPT: [
            ("receipt_no", "收据编号"),
            ("date", "日期"),
            ("payee_name", "收款人"),
            ("payer_name", "付款人"),
            ("amount", "金额"),
            ("reason", "事由"),
        ],
    }
    
    fields_list = field_requirements.get(document_type, [])
    
    # 构建字段说明文本
    fields_desc = "\n".join([
        f'  - "{en}": {cn}' for en, cn in fields_list
    ])
    
    # 构建JSON示例
    example_fields = {}
    for en, cn in fields_list[:3]:
        example_fields[en] = f"示例值（{cn}）"
    
    json_format_example = json.dumps({
        "fields": example_fields,
        "confidence": 0.85,
        "validation_errors": [],
        "accounting_notes": "",
    }, ensure_ascii=False, indent=2)
    
    # 文本长度：合同等长文档取前4000字，其他取前2500字
    max_text_len = 4000 if document_type in (DocumentType.CONTRACT, DocumentType.BANK_STATEMENT) else 2500
    truncated_text = extracted_text[:max_text_len]
    if len(extracted_text) > max_text_len:
        truncated_text += f"\n\n...（文本过长，已截断，共 {len(extracted_text)} 字符）"
    
    prompt = f"""请作为专业的财务审计助理，解析以下{doc_type_desc}，提取关键字段信息。

【文档内容】
{truncated_text}

【提取要求】
请提取以下字段（如果存在于文档中）：
{fields_desc}

【返回格式】
请严格按照以下 JSON 格式返回，不要包含任何其他文字：
{json_format_example}

【重要规则】
1. fields中的key必须使用上面列出的英文名称，不能自己造新的key
2. 字段不存在时填 null，不要填空字符串
3. 【金额提取 - 最高优先级】金额字段必须提取为纯数字字符串（不含¥、￥、元、逗号等符号）：
   - 示例："价税合计（小写）：¥11,300.00" → "11300.00"
   - 示例："金额（不含税）：10000.00元" → "10000.00"
   - 示例："税额：1,300.00" → "1300.00"
   - 负数金额保留负号："-3000.00"
   - 严禁返回0或null（除非文档中确实没有该金额）
4. 日期字段统一格式为 YYYY-MM-DD（如2024-01-15）
5. 【价税勾稽校验】发票类文档必须验证：不含税金额 + 税额 = 价税合计
   - 如果差异超过1元，在validation_errors中标注"价税勾稽异常"
6. confidence是你对提取结果整体准确性的置信度（0-1之间）：
   - 0.9以上：所有关键字段都清晰明确，完全确定
   - 0.8-0.9：大部分字段明确，少量字段需推断
   - 0.7-0.8：部分字段需要推断或存在模糊
   - 0.6-0.7：较多字段不确定，仅提取了部分信息
   - 0.6以下：信息严重不足，结果仅供参考
7. 如果发现金额大小写不一致等问题，请在validation_errors中列出
8. 如果能识别适用的会计准则或税务处理要点，请在accounting_notes中说明
"""
    
    return prompt


# =============================================================================
# 多LLM引擎对比
# =============================================================================

async def multi_llm_comparison(
    file_path: str,
    document_type: DocumentType,
    extracted_text: str,
    file_format: FileFormat | None = None,
    db: Any = None,
) -> LLMComparisonResult:
    """
    多LLM引擎对比流程
    
    功能描述：并行调用多个LLM引擎，对比解析结果，选择最优
    业务逻辑：
        1. 从数据库读取多LLM引擎配置
        2. 并行调用配置的所有启用的LLM引擎
        3. 收集各引擎解析结果
        4. 进行字段一致性分析
        5. 根据对比策略选择最优结果
        6. 标注字段来源
    
    会计口径：
        - 字段一致性率用于判断结果可信度
        - 加权投票综合各引擎优势
        - 字段来源标注便于审计追溯
    
    Args:
        file_path: 文件存储路径
        document_type: 文档类型
        extracted_text: 已提取的文本内容
        file_format: 文件格式
        db: 数据库会话
        
    Returns:
        LLMComparisonResult: 多LLM引擎对比结果
    """
    from app.services.agent.llm_engine_config_service import get_llm_engines_config
    
    config = get_runtime_parser_engine_config(db)
    
    # 从数据库读取多LLM引擎配置
    engines_config = []
    comparison_strategy = config.get("llm_comparison_strategy", "weighted_vote")
    weights = {}
    
    if db:
        try:
            llm_config = get_llm_engines_config(db)
            engines_config = [e for e in llm_config.engines if e.enabled]
            comparison_strategy = llm_config.comparison_strategy
            weights = {e.id: e.weight for e in engines_config}
        except Exception as e:
            logger.warning(f"读取多LLM引擎配置失败，使用默认配置: {e}")
    
    # 如果数据库中没有配置，回退到统一主模型配置
    if not engines_config:
        settings = get_settings()
        engines_list = resolve_effective_comparison_engines(config)
        try:
            weights = json.loads(settings.llm_engine_weights) if settings.llm_engine_weights else {}
        except Exception:
            weights = {}
        comparison_strategy = settings.llm_comparison_strategy
        # 构造成引擎配置字典格式，保持后续逻辑一致
        engines_config = [
            {
                "id": name.strip(),
                "name": name.strip(),
                "base_url": config.get("ai_base_url", ""),
                "model": name.strip(),
                "api_key": config.get("ai_api_key", ""),
                "weight": weights.get(name.strip(), 0.3),
            }
            for name in engines_list if name.strip()
        ]
    
    # 1. 并行调用所有引擎
    engine_tasks = []
    for engine in engines_config:
        engine_id = engine.get("id", "") if isinstance(engine, dict) else engine.id
        engine_name = engine.get("name", engine_id) if isinstance(engine, dict) else engine.name
        engine_model = engine.get("model", "") if isinstance(engine, dict) else engine.model
        engine_base_url = engine.get("base_url", "") if isinstance(engine, dict) else engine.base_url
        engine_api_key = engine.get("api_key", "") if isinstance(engine, dict) else engine.api_key
        
        engine_config_dict = {
            "ai_base_url": engine_base_url,
            "ai_model": engine_model,
            "ai_api_key": engine_api_key,
        }
        
        task = asyncio.create_task(
            asyncio.to_thread(
                parse_with_llm_engine,
                file_path,
                document_type,
                extracted_text,
                engine_model,
                file_format,
                engine_config_dict,
            )
        )
        engine_tasks.append((engine_id, engine_name, task))
    
    # 2. 收集结果（设置超时）
    engine_results: dict[str, ParseResult | None] = {}
    timeout = config.get("llm_timeout_seconds", 30)
    
    for engine_id, engine_name, task in engine_tasks:
        try:
            result = await asyncio.wait_for(task, timeout=timeout)
            engine_results[engine_id] = result
        except asyncio.TimeoutError:
            logger.warning(f"LLM 引擎 {engine_name} 超时")
            engine_results[engine_id] = None
        except Exception as e:
            logger.error(f"LLM 引擎 {engine_name} 调用失败: {e}")
            engine_results[engine_id] = None
    
    # 3. 字段一致性分析
    field_agreement = calculate_field_agreement(engine_results)
    
    # 4. 根据策略选择结果
    final_result = None
    selection_reason = ""
    field_sources = {}
    
    # 兼容字段交叉验证策略（用户选择的C方案）
    if comparison_strategy in ("field_consensus", "intersection"):
        # 字段一致/交叉验证：一致的字段才采纳，不一致的取置信度最高的
        final_result = field_consensus_selection(engine_results, weights)
        selection_reason = "字段交叉验证"
        field_sources = determine_field_sources(engine_results, final_result)
    
    elif comparison_strategy == "weighted_vote":
        final_result = weighted_vote_selection(engine_results, weights)
        selection_reason = "加权投票"
        field_sources = determine_field_sources(engine_results, final_result)
    
    elif comparison_strategy == "highest_confidence":
        valid_results = [r for r in engine_results.values() if r and r.confidence > 0]
        if valid_results:
            final_result = max(valid_results, key=lambda r: r.confidence)
            selection_reason = "置信度最高"
            field_sources = {field: final_result.engine_name for field in final_result.data.keys()}
    
    elif comparison_strategy in ("user_review", "user_choose"):
        # 返回所有结果，前端让用户选择
        return LLMComparisonResult(
            engine_results=engine_results,
            field_agreement=field_agreement,
            final_result=None,
            selection_reason="等待用户选择",
            field_sources={},
        )
    
    return LLMComparisonResult(
        engine_results=engine_results,
        field_agreement=field_agreement,
        final_result=final_result,
        selection_reason=selection_reason,
        field_sources=field_sources,
    )


def calculate_field_agreement(results: dict[str, ParseResult | None]) -> dict[str, float]:
    """
    计算各字段的一致性率
    
    功能描述：统计各字段在多引擎中的一致性
    业务逻辑：
        - 对于每个字段，统计各引擎给出的值
        - 计算相同值的比例
    
    会计口径：
        - 一致性率越高表示结果越可信
    
    Args:
        results: 各引擎的解析结果
        
    Returns:
        dict: 各字段的一致性率（0-1之间）
    """
    agreement = {}
    
    # 获取所有字段名
    all_fields: set[str] = set()
    for result in results.values():
        if result and result.data:
            all_fields.update(result.data.keys())
    
    # 计算每个字段的一致性
    for field in all_fields:
        values = []
        for result in results.values():
            if result and result.data and field in result.data:
                values.append(str(result.data[field]))
        
        if len(values) > 1:
            # 计算一致性率（相同值的比例）
            unique_values = set(values)
            max_count = max(sum(1 for v in values if v == uv) for uv in unique_values)
            agreement[field] = max_count / len(values)
        else:
            agreement[field] = 1.0 if values else 0.0
    
    return agreement


def weighted_vote_selection(
    results: dict[str, ParseResult | None],
    weights: dict[str, float],
) -> ParseResult:
    """
    加权投票选择最优结果
    
    功能描述：根据引擎权重计算得分，选择最优值
    业务逻辑：
        1. 对于每个字段，统计各引擎给出的值
        2. 按引擎权重计算每个值的加权得分
        3. 选择得分最高的值
        4. 合成最终结果
    
    会计口径：
        - 权重根据各引擎历史准确率配置
    
    Args:
        results: 各引擎的解析结果
        weights: 引擎权重配置
        
    Returns:
        ParseResult: 加权投票后的最终结果
    """
    if not results:
        return ParseResult(document_type=DocumentType.UNKNOWN, confidence=0.0)
    
    # 获取第一个有效结果的文档类型
    first_result = next((r for r in results.values() if r), None)
    if not first_result:
        return ParseResult(document_type=DocumentType.UNKNOWN, confidence=0.0)
    
    document_type = first_result.document_type
    
    final_data = {}
    
    # 获取所有字段名
    all_fields: set[str] = set()
    for result in results.values():
        if result and result.data:
            all_fields.update(result.data.keys())
    
    # 对每个字段进行加权投票
    for field in all_fields:
        value_scores: dict[str, float] = {}
        
        for engine_name, result in results.items():
            if result and result.data and field in result.data:
                value = str(result.data[field])
                weight = weights.get(engine_name, 0.25)
                value_scores[value] = value_scores.get(value, 0) + weight
        
        # 选择得分最高的值
        if value_scores:
            best_value = max(value_scores.keys(), key=lambda v: value_scores[v])
            
            # 找到给出该值的引擎，使用其原始数据类型
            for engine_name, result in results.items():
                if result and result.data and field in result.data:
                    if str(result.data[field]) == best_value:
                        final_data[field] = result.data[field]
                        break
    
    # 计算综合置信度（加权平均）
    total_weight = 0.0
    weighted_confidence = 0.0
    for engine_name, result in results.items():
        if result:
            weight = weights.get(engine_name, 0.25)
            weighted_confidence += result.confidence * weight
            total_weight += weight
    
    final_confidence = weighted_confidence / total_weight if total_weight > 0 else 0.0
    
    return ParseResult(
        document_type=document_type,
        data=final_data,
        confidence=final_confidence,
        engine=EngineType.WEIGHTED_VOTE,
        engine_name="weighted_vote",
        raw_text="",  # 不重复保存
        validation_errors=[],
        accounting_notes="",
    )


def intersection_selection(results: dict[str, ParseResult]) -> ParseResult:
    """
    交集选择（只取各引擎一致的字段）
    
    功能描述：只保留各引擎完全一致的字段
    业务逻辑：
        - 对于每个字段，只有所有引擎都给出相同值才保留
    
    会计口径：
        - 严格保守，确保字段准确性
    
    Args:
        results: 各引擎的解析结果
        
    Returns:
        ParseResult: 交集选择后的结果
    """
    if not results:
        return ParseResult(document_type=DocumentType.UNKNOWN, confidence=0.0)
    
    first_result = next((r for r in results.values() if r), None)
    if not first_result:
        return ParseResult(document_type=DocumentType.UNKNOWN, confidence=0.0)
    
    document_type = first_result.document_type
    final_data = {}
    
    # 获取所有字段名
    all_fields: set[str] = set()
    for result in results.values():
        if result and result.data:
            all_fields.update(result.data.keys())
    
    # 对每个字段检查一致性
    for field in all_fields:
        values = []
        for result in results.values():
            if result and result.data and field in result.data:
                values.append(str(result.data[field]))
        
        # 只有所有值相同才保留
        if values and len(set(values)) == 1:
            final_data[field] = results[list(results.keys())[0]].data[field]
    
    return ParseResult(
        document_type=document_type,
        data=final_data,
        confidence=1.0,  # 交集选择置信度默认为1.0（严格一致）
        engine=EngineType.FUSED,
        engine_name="intersection",
        raw_text="",
        validation_errors=[],
        accounting_notes="",
    )


def field_consensus_selection(
    results: dict[str, ParseResult | None],
    weights: dict[str, float] | None = None,
) -> ParseResult:
    """
    字段交叉验证选择（C方案：一致的字段采纳，不一致选置信度最高的）

    功能描述：字段级别的交叉验证策略
    业务逻辑：
        1. 对于每个字段，检查各引擎的值是否一致
        2. 一致的直接采纳（置信度高）
        3. 不一致的，选择置信度最高引擎的值
        4. 综合计算最终置信度

    会计口径：
        - 一致字段可信度高，不一致字段取最优
        - 平衡准确性和完整性

    Args:
        results: 各引擎的解析结果
        weights: 引擎权重（可选）

    Returns:
        ParseResult: 字段交叉验证后的结果
    """
    if not results:
        return ParseResult(document_type=DocumentType.UNKNOWN, confidence=0.0)

    first_result = next((r for r in results.values() if r), None)
    if not first_result:
        return ParseResult(document_type=DocumentType.UNKNOWN, confidence=0.0)

    document_type = first_result.document_type
    final_data = {}
    weights = weights or {}

    # 获取所有字段名
    all_fields: set[str] = set()
    for result in results.values():
        if result and result.data:
            all_fields.update(result.data.keys())

    # 对每个字段进行交叉验证
    total_confidence = 0.0
    field_count = 0

    for field in all_fields:
        values_and_confidence = []
        for engine_id, result in results.items():
            if result and result.data and field in result.data:
                weight = weights.get(engine_id, 1.0)
                values_and_confidence.append({
                    "value": result.data[field],
                    "confidence": result.confidence * weight,
                    "engine_id": engine_id,
                })

        if not values_and_confidence:
            continue

        # 检查是否所有值都一致
        str_values = [str(v["value"]) for v in values_and_confidence]
        unique_values = set(str_values)

        if len(unique_values) == 1:
            # 完全一致，直接采纳
            final_data[field] = values_and_confidence[0]["value"]
            # 一致字段置信度取平均
            avg_conf = sum(v["confidence"] for v in values_and_confidence) / len(values_and_confidence)
            total_confidence += min(1.0, avg_conf * 1.2)  # 一致有加成
        else:
            # 不一致，选置信度最高的
            best = max(values_and_confidence, key=lambda v: v["confidence"])
            final_data[field] = best["value"]
            total_confidence += best["confidence"] * 0.8  # 不一致有折扣

        field_count += 1

    # 计算综合置信度
    final_confidence = total_confidence / field_count if field_count > 0 else 0.0
    final_confidence = min(1.0, final_confidence)

    return ParseResult(
        document_type=document_type,
        data=final_data,
        confidence=final_confidence,
        engine=EngineType.FUSED,
        engine_name="field_consensus",
        raw_text="",
        validation_errors=[],
        accounting_notes="",
    )


def determine_field_sources(
    results: dict[str, ParseResult | None],
    final_result: ParseResult,
) -> dict[str, str]:
    """
    确定各字段的来源引擎
    
    功能描述：标注每个字段来自哪个引擎
    业务逻辑：
        - 对于每个字段，找到给出该值的引擎
    
    会计口径：
        - 来源标注便于审计追溯
    
    Args:
        results: 各引擎的解析结果
        final_result: 最终选择的解析结果
        
    Returns:
        dict: 各字段的来源引擎
    """
    field_sources = {}
    
    for field, value in final_result.data.items():
        # 找到给出该值的引擎
        for engine_name, result in results.items():
            if result and result.data and field in result.data:
                if result.data[field] == value:
                    field_sources[field] = engine_name
                    break
    
    return field_sources


# =============================================================================
# 双引擎并行解析
# =============================================================================

def _normalize_comparison_value(value: Any) -> str:
    """将字段值标准化，便于比较规则引擎和LLM结果是否一致。"""
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    return (
        text.replace(" ", "")
        .replace("，", ",")
        .replace("。", ".")
        .replace("￥", "")
        .replace("¥", "")
        .replace("元", "")
        .lower()
    )


# 财务审计常见字段别名映射：统一由 field_alias_catalog 维护，避免多个模块各自定义。
_FIELD_NAME_ALIASES: dict[str, list[str]] = ALL_FIELD_ALIASES


def _normalize_field_name(field_name: str, document_type: str | None = None) -> str:
    """将字段名标准化，便于跨引擎识别同一业务字段。"""
    return normalize_field_name_from_catalog(field_name, document_type=document_type)


def _build_field_mapping(
    data: dict[str, Any], document_type: str | None = None
) -> dict[str, list[str]]:
    """建立标准化字段名到原始字段名的映射。"""
    from app.services.doc_parsing.parser_engine.field_alias_catalog import build_field_mapping

    return build_field_mapping(data, document_type=document_type)


def _build_engine_result_diagnosis(
    rule_result: Any, llm_result: Any, document_type: str | None = None
) -> dict[str, Any]:
    """
    生成双引擎结果诊断。

    业务含义：
        置信度高不代表结论一定正确。审计场景更需要看到两个引擎
        在关键字段上是否一致，以及哪些字段需要人工复核。
    """
    if not rule_result or not llm_result:
        return {
            "consistency_rate": 0.0,
            "consistent_fields": [],
            "conflict_fields": [],
            "rule_only_fields": [],
            "llm_only_fields": [],
            "review_required": True,
            "review_reason": "仅一个引擎返回结果，无法交叉验证",
            "confidence_gap": abs(
                (rule_result.confidence if rule_result else 0.0)
                - (llm_result.confidence if llm_result else 0.0)
            ),
        }

    rule_data = rule_result.data or {}
    llm_data = llm_result.data or {}

    # 建立标准化字段名映射，支持字段别名对比
    rule_field_mapping = _build_field_mapping(rule_data, document_type=document_type)
    llm_field_mapping = _build_field_mapping(llm_data, document_type=document_type)
    all_normalized_fields = sorted(set(rule_field_mapping.keys()) | set(llm_field_mapping.keys()))

    consistent_fields: list[dict[str, Any]] = []
    conflict_fields: list[dict[str, Any]] = []
    rule_only_fields: list[dict[str, Any]] = []
    llm_only_fields: list[dict[str, Any]] = []

    for normalized_name in all_normalized_fields:
        rule_original_names = rule_field_mapping.get(normalized_name, [])
        llm_original_names = llm_field_mapping.get(normalized_name, [])

        # 取第一个原始字段名作为展示名
        display_name = rule_original_names[0] if rule_original_names else llm_original_names[0]

        if rule_original_names and llm_original_names:
            rule_value = rule_data[rule_original_names[0]]
            llm_value = llm_data[llm_original_names[0]]
            rule_text = _normalize_comparison_value(rule_value)
            llm_text = _normalize_comparison_value(llm_value)

            if rule_text and llm_text:
                if rule_text == llm_text:
                    consistent_fields.append({
                        "field": display_name,
                        "normalized_field": normalized_name,
                        "value": rule_value,
                        "rule_value": rule_value,
                        "llm_value": llm_value,
                    })
                else:
                    conflict_fields.append({
                        "field": display_name,
                        "normalized_field": normalized_name,
                        "rule_value": rule_value,
                        "llm_value": llm_value,
                    })
            elif rule_text:
                rule_only_fields.append({
                    "field": display_name,
                    "normalized_field": normalized_name,
                    "rule_value": rule_value,
                })
            elif llm_text:
                llm_only_fields.append({
                    "field": display_name,
                    "normalized_field": normalized_name,
                    "llm_value": llm_value,
                })
        elif rule_original_names:
            rule_value = rule_data[rule_original_names[0]]
            if _normalize_comparison_value(rule_value):
                rule_only_fields.append({
                    "field": display_name,
                    "normalized_field": normalized_name,
                    "rule_value": rule_value,
                })
        elif llm_original_names:
            llm_value = llm_data[llm_original_names[0]]
            if _normalize_comparison_value(llm_value):
                llm_only_fields.append({
                    "field": display_name,
                    "normalized_field": normalized_name,
                    "llm_value": llm_value,
                })

    comparable_count = len(consistent_fields) + len(conflict_fields)
    consistency_rate = (
        round(len(consistent_fields) / comparable_count, 4)
        if comparable_count > 0
        else 0.0
    )
    confidence_gap = abs(rule_result.confidence - llm_result.confidence)
    review_required = (
        len(conflict_fields) > 0
        or consistency_rate < 0.6
        or confidence_gap >= 0.25
        or llm_result.confidence < 0.7
    )

    review_reasons = []
    if conflict_fields:
        review_reasons.append(f"存在 {len(conflict_fields)} 个字段冲突")
    if consistency_rate < 0.6:
        review_reasons.append("两个引擎共同识别字段的一致率低于60%")
    if confidence_gap >= 0.25:
        review_reasons.append("规则引擎与LLM置信度差异较大")
    if llm_result.confidence < 0.7:
        review_reasons.append("LLM置信度低于70%，可能存在文本噪声或字段不完整")

    return {
        "consistency_rate": consistency_rate,
        "consistent_fields": consistent_fields,
        "conflict_fields": conflict_fields,
        "rule_only_fields": rule_only_fields,
        "llm_only_fields": llm_only_fields,
        "review_required": review_required,
        "review_reason": "；".join(review_reasons) if review_reasons else "两个引擎结果基本一致",
        "confidence_gap": round(confidence_gap, 4),
        "rule_field_count": len(rule_data),
        "llm_field_count": len(llm_data),
    }


async def dual_engine_parallel_parse(file_path: str, document_type: DocumentType, extracted_text: str, file_format: FileFormat | None = None, db: Any = None) -> dict[str, Any]:
    """
    双引擎并行解析
    
    功能描述：规则引擎和LLM引擎并行解析，按置信度选择最优，返回完整对比信息
    业务逻辑：
        1. 从数据库读取配置
        2. 并行调用规则引擎和LLM引擎
        3. 收集两个引擎的结果
        4. 比较置信度，选择最优结果
        5. 返回完整的对比信息，便于前端展示
    
    会计口径：
        - 置信度选择确保结果准确性
        - 保留两个引擎的结果便于审计追溯
    
    Args:
        file_path: 文件存储路径
        document_type: 文档类型
        extracted_text: 已提取的文本内容
        file_format: 文件格式
        db: 数据库会话
        
    Returns:
        dict: 包含两个引擎结果和最终选择的对比信息
    """
    config = get_runtime_parser_engine_config(db)
    
    # 1. 并行调用两个引擎
    rule_task = asyncio.create_task(
        asyncio.to_thread(
            parse_with_rule_engine,
            file_path,
            document_type,
            extracted_text,
            file_format,
            db,
        )
    )
    
    llm_task = asyncio.create_task(
        asyncio.to_thread(
            parse_with_llm_engine,
            file_path,
            document_type,
            extracted_text,
            resolve_parse_model(config),
            file_format,
            config_for_parse_llm(config),
        )
    )
    
    # 2. 收集结果
    rule_result = None
    llm_result = None
    
    try:
        rule_result = await asyncio.wait_for(rule_task, timeout=config.get("llm_parallel_timeout_seconds", 60))
    except asyncio.TimeoutError:
        logger.warning("规则引擎解析超时")
    
    # LLM 解析通常比规则引擎慢，给予更宽松的超时时间
    llm_timeout = config.get("llm_timeout_seconds", 120)
    if llm_timeout < 60:
        llm_timeout = 120
    try:
        llm_result = await asyncio.wait_for(llm_task, timeout=llm_timeout)
    except asyncio.TimeoutError:
        logger.warning(f"LLM 引擎解析超时（{llm_timeout}秒）")
    
    # 3. 选择最优结果
    final_result = None
    selection_reason = ""
    
    if rule_result and llm_result:
        if rule_result.confidence >= llm_result.confidence:
            logger.info(f"双引擎并行：选择规则引擎结果（置信度 {rule_result.confidence} vs {llm_result.confidence}）")
            final_result = rule_result
            selection_reason = f"规则引擎置信度更高 ({rule_result.confidence:.2f} vs {llm_result.confidence:.2f})"
        else:
            logger.info(f"双引擎并行：选择LLM引擎结果（置信度 {llm_result.confidence} vs {rule_result.confidence}）")
            final_result = llm_result
            selection_reason = f"LLM引擎置信度更高 ({llm_result.confidence:.2f} vs {rule_result.confidence:.2f})"
    elif rule_result:
        logger.info("双引擎并行：仅有规则引擎结果")
        final_result = rule_result
        selection_reason = "LLM引擎未返回结果，使用规则引擎"
    elif llm_result:
        logger.info("双引擎并行：仅有LLM引擎结果")
        final_result = llm_result
        selection_reason = "规则引擎未返回结果，使用LLM引擎"
    else:
        logger.error("双引擎并行：两个引擎都失败")
        final_result = ParseResult(
            document_type=document_type,
            file_format=file_format,
            confidence=0.0,
            engine=EngineType.RULE,
            validation_errors=["双引擎并行解析失败"],
        )
        selection_reason = "两个引擎都失败"
    
    # 4. 使用增强版双引擎对比分析工具生成完整诊断报告
    # 业务含义：不仅输出字段级冲突，还要定位原始文本位置、生成热力图、
    # 输出稳定性评分，并生成给下游服务的两个关键参数。
    raw_text = (rule_result.raw_text if rule_result else None) or (llm_result.raw_text if llm_result else None)
    analysis_report = analyze_dual_engine_result(rule_result, llm_result, raw_text)
    diagnosis = report_to_dict(analysis_report)

    # 5. 基于稳定性阈值自动标记人工复核
    # 业务含义：一致性率或稳定性评分低于 96% 时，强制要求人工复核，
    # 确保低质量解析结果不会直接进入下游记账流程。
    STABILITY_REVIEW_THRESHOLD = 0.96
    if analysis_report.consistency_rate < STABILITY_REVIEW_THRESHOLD or analysis_report.stability_score < STABILITY_REVIEW_THRESHOLD:
        analysis_report.review_required = True
        threshold_reason = (
            f"稳定性指标低于阈值（consistency_rate={analysis_report.consistency_rate:.2f}, "
            f"stability_score={analysis_report.stability_score:.2f}，阈值={STABILITY_REVIEW_THRESHOLD:.2f}）"
        )
        if threshold_reason not in analysis_report.review_reasons:
            analysis_report.review_reasons.append(threshold_reason)
        diagnosis["review_required"] = True
        diagnosis["review_reasons"] = analysis_report.review_reasons

    # 6. 记录解析质量指标，支撑稳定性看板
    if db is not None:
        try:
            record_parse_quality_metric(
                db=db,
                file_name=str(Path(file_path).name),
                document_type=str(document_type.value if hasattr(document_type, "value") else document_type),
                comparison_report=analysis_report,
                source_file_id=None,
                rule_engine_used=rule_result is not None,
                llm_engine_used=llm_result is not None,
                correction_applied_count=0,
            )
        except Exception as e:
            logger.warning(f"记录解析质量指标失败: {e}")

    # 7. 返回完整的对比信息
    return {
        "rule_engine_result": rule_result.to_dict() if rule_result else None,
        "llm_engine_result": llm_result.to_dict() if llm_result else None,
        "final_result": final_result,
        "selection_reason": selection_reason,
        "engine_comparison": {
            "rule_confidence": rule_result.confidence if rule_result else 0.0,
            "llm_confidence": llm_result.confidence if llm_result else 0.0,
            "selection_reason": selection_reason,
            "diagnosis": diagnosis,
            "stability_score": analysis_report.stability_score,
            "consistency_rate": analysis_report.consistency_rate,
            "review_required": analysis_report.review_required,
            "review_reasons": analysis_report.review_reasons,
        },
    }


# =============================================================================
# 未识别文件处理
# =============================================================================

def _perform_seal_recognition(file_path: str) -> SealRecognitionResult:
    """
    执行印章识别
    
    功能描述：对文件进行印章区域检测、提取和文字识别
    业务逻辑：
        1. 检测印章区域（使用传统CV技术）
        2. 提取印章子图
        3. OCR识别印章文字
        4. 汇总识别结果
    
    会计口径：
        - 印章识别结果用于合同真实性校验
        - 识别置信度用于判断结果可靠性
    
    Args:
        file_path: 文件存储路径
        
    Returns:
        SealRecognitionResult: 印章识别结果
    """
    try:
        detect_seals, extract_seal_region, recognize_seal_text, text_items_to_dict_list = (
            _load_seal_services()
        )
        detected_seals = detect_seals(file_path)
        
        if not detected_seals:
            return SealRecognitionResult(
                detected=False,
                seal_count=0,
                seals=[],
            )
        
        seal_details = []
        for detection in detected_seals:
            seal_sub_image_path = extract_seal_region(
                file_path,
                detection.bbox,
                output_dir="app/storage/seals",
            )
            
            ocr_result = recognize_seal_text(
                str(seal_sub_image_path),
                offset=(detection.bbox[0], detection.bbox[1]),
            )
            
            recognized_text = ocr_result.recognized_text or ""
            
            seal_type = "unknown"
            if "合同专用章" in recognized_text or "合同章" in recognized_text:
                seal_type = "contract_seal"
            elif "财务" in recognized_text:
                seal_type = "finance_seal"
            elif "法人" in recognized_text:
                seal_type = "legal_person_seal"
            
            seal_details.append({
                "bbox": {
                    "x1": detection.bbox[0],
                    "y1": detection.bbox[1],
                    "x2": detection.bbox[2],
                    "y2": detection.bbox[3],
                },
                "seal_image_path": str(seal_sub_image_path),
                "recognized_text": recognized_text,
                "text_items": text_items_to_dict_list(ocr_result.text_items),
                "seal_type": seal_type,
                "confidence": detection.confidence,
                "detection_method": detection.detection_method,
            })
        
        logger.info(f"印章识别完成：检测到 {len(seal_details)} 个印章")
        
        return SealRecognitionResult(
            detected=True,
            seal_count=len(seal_details),
            seals=seal_details,
        )

    except ImportError as e:
        logger.warning("印章模块未安装（可选 pip install -e backend[vision]）: %s", e)
        return SealRecognitionResult(
            detected=False,
            seal_count=0,
            seals=[],
        )
    except Exception as e:
        logger.warning(f"印章识别失败: {e}")
        return SealRecognitionResult(
            detected=False,
            seal_count=0,
            seals=[],
        )


def handle_unrecognized_file(
    file_path: str,
    file_format: FileFormat,
    extracted_text: str,
) -> UnrecognizedFile:
    """
    未识别文件处理
    
    功能描述：对于无法识别类型的文件，记录并准备二次分析
    业务逻辑：
        1. 创建 UnrecognizedFile 对象
        2. 记录初次分析结果
        3. 准备二次分析流程
    
    会计口径：
        - 未识别文件需要人工复核或二次分析
    
    Args:
        file_path: 文件存储路径
        file_format: 文件格式
        extracted_text: 已提取的文本内容
        
    Returns:
        UnrecognizedFile: 未识别文件对象
    """
    from datetime import datetime
    
    # 创建未识别文件对象
    unrecognized = UnrecognizedFile(
        file_id=0,  # 需要在数据库中创建后填入
        file_path=file_path,
        file_name=Path(file_path).name,
        file_format=file_format,
        upload_time=datetime.now(),
        analysis_status="pending",
        extracted_text=extracted_text,
        extracted_features={},
    )
    
    # 初次分析（尝试遍历所有类型）
    first_analysis = {}
    for doc_type in DocumentType.get_all_types():
        try:
            # 尝试使用LLM解析
            result = parse_with_llm_engine(file_path, doc_type, extracted_text)
            if result.confidence > 0.5:
                first_analysis[doc_type.value] = {
                    "confidence": result.confidence,
                    "data": result.data,
                }
        except Exception:
            pass
    
    unrecognized.first_analysis = first_analysis
    unrecognized.analysis_status = "analyzing"
    
    return unrecognized


# =============================================================================
# 主调度器类
# =============================================================================

class ParserEngineDispatcher:
    """
    解析引擎调度器
    
    功能描述：统一调度各类解析引擎，实现最优解析
    业务逻辑：
        1. 格式识别 → 类型判断 → 引擎调度 → 结果融合
        2. 支持双引擎并行和多LLM对比
        3. 处理未识别文件
    
    会计口径：
        - 确保解析结果符合会计准则要求
        - 提供置信度和校验错误便于复核
    """
    
    def __init__(self, db: Any = None) -> None:
        self.settings = get_settings()
        self.db = db
        self.config = get_runtime_parser_engine_config(db)
    
    async def parse(
        self,
        file_path: str,
        user_preselected_type: DocumentType | None = None,
        sheet_name: str | None = None,
    ) -> ParseResult | LLMComparisonResult | dict[str, Any]:
        """
        统一解析入口
        
        功能描述：完整的解析流程（格式→类型→引擎→结果）
        业务逻辑：
            1. 格式识别
            2. 类型判断
            3. 提取文本
            4. 选择引擎调度策略
            5. 执行解析
            6. 返回结果
        
        Args:
            file_path: 文件存储路径
            user_preselected_type: 用户预选的文档类型（可选）
            sheet_name: Excel工作表名称（可选）
            
        Returns:
            ParseResult 或 LLMComparisonResult: 解析结果
        """
        # 1. 格式识别
        format_result = recognize_file_format(file_path)
        
        if format_result.file_format == FileFormat.UNKNOWN:
            logger.error(f"文件格式无法识别: {file_path}")
            return ParseResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                validation_errors=[format_result.error_message or "文件格式无法识别"],
            )
        
        # 2. 类型判断
        type_result = classify_document_type(
            file_path,
            format_result.file_format,
            None,  # extracted_text 由类型判断器自己提取
            user_preselected_type,
        )
        
        if type_result.document_type == DocumentType.UNKNOWN:
            logger.warning(f"文档类型无法识别: {file_path}")
            # 返回未识别文件对象（后续二次分析）
            return ParseResult(
                document_type=DocumentType.UNKNOWN,
                confidence=0.0,
                validation_errors=[type_result.conflict_reason or "文档类型无法识别"],
            )

        # 3. 结构化 CSV/Excel：直接走规则引擎，跳过 LLM（避免阻塞与超时）
        if (
            format_result.file_format in {FileFormat.EXCEL, FileFormat.CSV}
            and type_result.document_type
            in {
                DocumentType.ACCOUNTING_ENTRY,
                DocumentType.BANK_STATEMENT,
                DocumentType.SALARY_TABLE,
            }
        ):
            logger.info(
                "结构化表格 %s / %s，跳过 LLM，直接使用规则引擎",
                format_result.file_format.value,
                type_result.document_type.value,
            )
            extracted_text = extract_text_from_file(
                file_path, format_result.file_format, sheet_name=sheet_name
            )
            rule_result = parse_with_rule_engine(
                file_path,
                type_result.document_type,
                extracted_text,
                format_result.file_format,
                self.db,
            )
            return rule_result
        
        # 3. 提取文本
        extracted_text = extract_text_from_file(file_path, format_result.file_format, sheet_name=sheet_name)
        
        # 3.5 合同文档自动触发印章识别（异步执行，不阻塞主解析流程）
        seal_info: SealRecognitionResult | None = None
        if type_result.document_type == DocumentType.CONTRACT:
            logger.info(f"检测到合同文档，触发印章识别")
            seal_info = _perform_seal_recognition(file_path)
        
        # 4. 选择引擎调度策略
        if self.config.get("llm_multi_engine_enabled", False):
            # 多LLM引擎对比
            logger.info(f"启用多LLM引擎对比策略: {self.config.get('llm_comparison_strategy', 'weighted_vote')}")
            result = await multi_llm_comparison(
                file_path,
                type_result.document_type,
                extracted_text,
                format_result.file_format,
                self.db,
            )
            if isinstance(result, LLMComparisonResult) and result.final_result:
                result.final_result.seal_info = seal_info
            return result
        
        elif self.config.get("llm_enable_parallel_parsing", False):
            # 双引擎并行
            logger.info("启用双引擎并行策略")
            result = await dual_engine_parallel_parse(
                file_path,
                type_result.document_type,
                extracted_text,
                format_result.file_format,
                self.db,
            )
            if isinstance(result, dict) and result.get("final_result"):
                result["final_result"].seal_info = seal_info
            return result
        
        else:
            # 单引擎（优先LLM，失败则规则）
            if self.config.get("ai_local_model_enabled", True):
                llm_result = parse_with_llm_engine(
                    file_path,
                    type_result.document_type,
                    extracted_text,
                    self.config.get("ai_model") or self.config.get("llm_preferred_model", ""),
                    format_result.file_format,
                    self.config,
                )
                if llm_result.confidence > 0.5:
                    llm_result.seal_info = seal_info
                    return llm_result
            
            # 规则引擎兜底
            rule_result = parse_with_rule_engine(
                file_path,
                type_result.document_type,
                extracted_text,
                format_result.file_format,
                self.db,
            )
            rule_result.seal_info = seal_info
            return rule_result


# =============================================================================
# 便捷函数
# =============================================================================

async def parse_file(
    file_path: str,
    user_preselected_type: DocumentType | None = None,
    db: Any = None,
) -> ParseResult | LLMComparisonResult | dict[str, Any]:
    """
    便捷函数：解析文件
    
    功能描述：一键完成文件解析流程
    业务逻辑：调用 ParserEngineDispatcher.parse()
    
    Args:
        file_path: 文件存储路径
        user_preselected_type: 用户预选的文档类型（可选）
        db: 数据库会话（可选，传入后会从数据库读取配置）
        
    Returns:
        ParseResult 或 LLMComparisonResult: 解析结果
    """
    dispatcher = ParserEngineDispatcher(db)
    return await dispatcher.parse(file_path, user_preselected_type)


def parse_result_to_source_document_result(
    parse_result: ParseResult | LLMComparisonResult,
    filename: str,
) -> object:
    """
    将新引擎的 ParseResult 或 LLMComparisonResult 转换为旧引擎的 SourceDocumentResult
    
    功能描述：保持向后兼容，使新引擎结果可以无缝集成到现有导入流程
    业务逻辑：
        - 对于 ParseResult：直接转换文档类型枚举为字符串，保持数据结构
        - 对于 LLMComparisonResult：使用最终选择的结果（如果存在）或第一个引擎的结果
    
    会计口径：
        - 保持置信度和文本信息的准确性
        - 保留校验错误和会计建议
    
    Args:
        parse_result: 新引擎的解析结果（ParseResult 或 LLMComparisonResult）
        filename: 文件名
        
    Returns:
        SourceDocumentResult: 旧引擎格式的解析结果
    """
    from app.services.basic_data.source_document_service import SourceDocumentResult
    
    # 处理 LLMComparisonResult
    if isinstance(parse_result, LLMComparisonResult):
        # 使用最终选择的结果，如果没有则使用第一个有效结果
        final_result = parse_result.final_result
        if not final_result:
            # 取第一个有效结果
            for result in parse_result.engine_results.values():
                if result:
                    final_result = result
                    break
        
        if final_result:
            parse_result = final_result
        else:
            # 没有有效结果，返回空结果
            return SourceDocumentResult(
                document_type="general",
                confidence=0.0,
                data={},
                raw_text="",
                file_name=filename,
            )
    
    # 处理 ParseResult
    if isinstance(parse_result, ParseResult):
        return SourceDocumentResult(
            document_type=parse_result.document_type.value,
            confidence=parse_result.confidence,
            data=parse_result.data,
            raw_text=parse_result.raw_text,
            file_name=filename,
        )
    
    # 如果既不是 LLMComparisonResult 也不是 ParseResult，返回空结果
    raise ValueError(f"不支持的解析结果类型: {type(parse_result)}")


# =============================================================================
# 性能监控与统计
# =============================================================================

class ParserPerformanceMonitor:
    """
    解析引擎性能监控器
    
    功能描述：统计和记录解析引擎的性能指标，便于优化和监控
    业务逻辑：
        - 记录各阶段耗时（格式识别、类型判断、文本提取、解析执行）
        - 按文档类型和文件格式统计平均耗时
        - 记录成功率和错误率
        - 支持获取性能统计报告
    
    会计口径：
        - 性能数据用于系统优化，不影响财务数据准确性
        - 监控数据可用于审计系统运行状态
    """
    
    def __init__(self) -> None:
        self._total_parses: int = 0
        self._successful_parses: int = 0
        self._failed_parses: int = 0
        
        self._stage_durations: dict[str, list[float]] = defaultdict(list)
        self._format_durations: dict[str, list[float]] = defaultdict(list)
        self._doctype_durations: dict[str, list[float]] = defaultdict(list)
        
        self._error_counts: dict[str, int] = defaultdict(int)
    
    def record_parse_start(self) -> float:
        """记录解析开始时间"""
        return time.time()
    
    def record_stage_duration(self, stage_name: str, duration_ms: float) -> None:
        """记录某个阶段的耗时"""
        self._stage_durations[stage_name].append(duration_ms)
    
    def record_parse_complete(
        self,
        file_format: str,
        document_type: str,
        total_duration_ms: float,
        success: bool,
        error_type: str | None = None,
    ) -> None:
        """
        记录一次解析完成
        
        Args:
            file_format: 文件格式
            document_type: 文档类型
            total_duration_ms: 总耗时（毫秒）
            success: 是否成功
            error_type: 错误类型（如果失败）
        """
        self._total_parses += 1
        if success:
            self._successful_parses += 1
        else:
            self._failed_parses += 1
            if error_type:
                self._error_counts[error_type] += 1
        
        self._format_durations[file_format].append(total_duration_ms)
        self._doctype_durations[document_type].append(total_duration_ms)
    
    def get_stats(self) -> dict[str, Any]:
        """
        获取性能统计报告
        
        Returns:
            包含各项性能指标的字典
        """
        def _avg(values: list[float]) -> float:
            return round(sum(values) / len(values), 2) if values else 0.0
        
        def _max(values: list[float]) -> float:
            return round(max(values), 2) if values else 0.0
        
        def _min(values: list[float]) -> float:
            return round(min(values), 2) if values else 0.0
        
        success_rate = (
            round(self._successful_parses / self._total_parses * 100, 2)
            if self._total_parses > 0
            else 0.0
        )
        
        return {
            "total_parses": self._total_parses,
            "successful_parses": self._successful_parses,
            "failed_parses": self._failed_parses,
            "success_rate_percent": success_rate,
            "stage_stats": {
                stage: {
                    "count": len(durations),
                    "avg_ms": _avg(durations),
                    "max_ms": _max(durations),
                    "min_ms": _min(durations),
                }
                for stage, durations in self._stage_durations.items()
            },
            "format_stats": {
                fmt: {
                    "count": len(durations),
                    "avg_ms": _avg(durations),
                    "max_ms": _max(durations),
                    "min_ms": _min(durations),
                }
                for fmt, durations in self._format_durations.items()
            },
            "doctype_stats": {
                doctype: {
                    "count": len(durations),
                    "avg_ms": _avg(durations),
                    "max_ms": _max(durations),
                    "min_ms": _min(durations),
                }
                for doctype, durations in self._doctype_durations.items()
            },
            "error_stats": dict(self._error_counts),
        }
    
    def reset(self) -> None:
        """重置所有统计数据"""
        self._total_parses = 0
        self._successful_parses = 0
        self._failed_parses = 0
        self._stage_durations.clear()
        self._format_durations.clear()
        self._doctype_durations.clear()
        self._error_counts.clear()


# 全局性能监控器实例
performance_monitor = ParserPerformanceMonitor()


def get_performance_stats() -> dict[str, Any]:
    """获取解析引擎性能统计数据"""
    return performance_monitor.get_stats()


def reset_performance_stats() -> None:
    """重置解析引擎性能统计数据"""
    performance_monitor.reset()