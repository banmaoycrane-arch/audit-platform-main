# -*- coding: utf-8 -*-
"""
模块功能：基于 embedding 的字段名自动对齐（POC）
业务场景：当规则引擎与 LLM 引擎输出的字段名表述不一致时，通过语义相似度自动对齐
政策依据：语义等价性识别在财务数据标准化中的应用
输入数据：原始字段名、标准字段名库
输出结果：字段名标准化映射
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建，实现基于 embedding 的字段名自动对齐 POC
"""
import math
from typing import Any

from app.services.doc_parsing.embedding_service import embed_text


# 标准字段名库：key 为标准化字段名，value 为该字段的语义描述
# 用于生成 embedding，提高语义识别能力
STANDARD_FIELD_CATALOG: dict[str, str] = {
    "contract_no": "合同编号 协议编号 合约号",
    "contract_name": "合同名称 协议名称 项目名称",
    "party_a_name": "甲方名称 委托方 买方 采购方 发包方",
    "party_b_name": "乙方名称 受托方 卖方 供应方 承包方",
    "contract_amount": "合同金额 合同总价 标的额 总价款 总金额",
    "sign_date": "签订日期 签署日期 签约日期",
    "payment_terms": "付款方式 结算方式 付款条件",
    "invoice_no": "发票号码 发票编号",
    "invoice_date": "开票日期 发票日期",
    "total_amount": "价税合计 合计金额 总金额",
    "amount_excl_tax": "不含税金额 货款 金额",
    "tax_amount": "税额 税金",
    "transaction_amount": "交易金额 发生额 金额",
    "counterparty_name": "对方户名 对方名称 交易对手",
    "account_no": "银行账号 账号",
}


# 缓存标准字段的 embedding，避免重复计算
_standard_embeddings_cache: dict[str, list[float]] = {}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    计算两个向量的余弦相似度
    
    Args:
        a: 向量 a
        b: 向量 b
        
    Returns:
        float: 余弦相似度（-1.0 到 1.0）
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot / (norm_a * norm_b)


def _get_standard_embeddings() -> dict[str, list[float]]:
    """
    获取标准字段名的 embedding 向量（带缓存）
    
    Returns:
        dict[str, list[float]]: 标准字段名到 embedding 向量的映射
    """
    global _standard_embeddings_cache
    
    if not _standard_embeddings_cache:
        for standard_name, description in STANDARD_FIELD_CATALOG.items():
            text = f"{standard_name} {description}"
            _standard_embeddings_cache[standard_name] = embed_text(text)
    
    return _standard_embeddings_cache


def align_field_by_embedding(field_name: str, threshold: float = 0.80) -> str | None:
    """
    基于 embedding 语义相似度对齐字段名
    
    功能描述：将任意字段名通过语义相似度匹配到标准字段名
    业务逻辑：
        1. 计算输入字段名的 embedding
        2. 与标准字段名库的 embedding 逐一计算余弦相似度
        3. 如果最高相似度超过阈值，返回对应标准字段名
        4. 否则返回 None
    
    Args:
        field_name: 原始字段名
        threshold: 相似度阈值（默认 0.80）
        
    Returns:
        str | None: 对齐后的标准字段名，未匹配返回 None
    """
    if not field_name:
        return None
    
    field_text = str(field_name).strip()
    if not field_text:
        return None
    
    field_embedding = embed_text(field_text)
    standard_embeddings = _get_standard_embeddings()
    
    best_match = None
    best_score = 0.0
    
    for standard_name, standard_embedding in standard_embeddings.items():
        score = _cosine_similarity(field_embedding, standard_embedding)
        if score > best_score:
            best_score = score
            best_match = standard_name
    
    if best_score >= threshold:
        return best_match
    
    return None


def normalize_field_with_embedding(
    field_name: str,
    static_aliases: dict[str, list[str]] | None = None,
    embedding_threshold: float = 0.80,
) -> str:
    """
    融合静态映射和 embedding 对齐的字段名标准化
    
    功能描述：优先使用静态别名映射，未命中时使用 embedding 语义对齐
    业务逻辑：
        1. 先尝试静态别名表匹配（确定性、可解释性强）
        2. 静态表未命中时，使用 embedding 语义相似度兜底
        3. 返回标准化字段名或原始字段名
    
    Args:
        field_name: 原始字段名
        static_aliases: 静态字段别名映射表（可选）
        embedding_threshold: embedding 对齐阈值
        
    Returns:
        str: 标准化后的字段名
    """
    import re
    
    if not field_name:
        return ""
    
    text = str(field_name).strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)
    
    # 1. 静态别名匹配
    if static_aliases:
        if text in static_aliases:
            return text
        
        for standard_name, aliases in static_aliases.items():
            normalized_aliases = [
                re.sub(r"[\s\-]+", "_", a.strip().lower()) for a in aliases
            ]
            if text in normalized_aliases:
                return standard_name
    
    # 2. embedding 语义对齐兜底
    aligned = align_field_by_embedding(field_name, threshold=embedding_threshold)
    if aligned:
        return aligned
    
    return text


def build_field_mapping_with_embedding(
    data: dict[str, Any],
    static_aliases: dict[str, list[str]] | None = None,
    embedding_threshold: float = 0.80,
) -> dict[str, list[str]]:
    """
    建立标准化字段名到原始字段名的映射（支持 embedding 对齐）
    
    Args:
        data: 原始解析结果数据
        static_aliases: 静态字段别名映射表
        embedding_threshold: embedding 对齐阈值
        
    Returns:
        dict[str, list[str]]: 标准化字段名到原始字段名列表的映射
    """
    from collections import defaultdict
    
    mapping: dict[str, list[str]] = defaultdict(list)
    
    for field_name in data.keys():
        normalized = normalize_field_with_embedding(
            field_name, static_aliases, embedding_threshold
        )
        if normalized:
            mapping[normalized].append(field_name)
    
    return dict(mapping)
