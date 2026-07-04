# -*- coding: utf-8 -*-
"""
模块功能：解析引擎双引擎对比分析工具
业务场景：对规则引擎与 LLM 引擎解析同一原始凭证文件的结果进行深度对比分析，
        识别不一致位置、记录各自识别边界、统计不一致集中区域，
        并输出给下游服务的两个关键参数：合同结构化内容、合规风险预审。
政策依据：项目解析引擎统一调度策略；AI 输出需人工复核的财务边界规则。
输入数据：规则引擎 ParseResult、LLM 引擎 ParseResult、原始提取文本（可选）、文件元数据。
输出结果：EngineComparisonReport，包含不一致定位、识别边界、区域热力图、稳定性评分、下游参数。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建，增强原有 _build_engine_result_diagnosis 能力，支持位置级定位与可视化统计
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.doc_parsing.parser_engine.field_alias_catalog import (
    ALL_FIELD_ALIASES,
    normalize_field_name as normalize_field_name_from_catalog,
)
from app.services.doc_parsing.parser_engine.field_embedding_aligner import normalize_field_with_embedding
from app.services.doc_parsing.parser_engine.parse_result import DocumentType, EngineType, ParseResult


# =============================================================================
# 数据模型
# =============================================================================

@dataclass
class FieldValueDetail:
    """
    单个字段在原始文本中的识别细节。

    业务含义：明确某个字段“从哪里识别出来的”，是审计可追溯的关键。
    """
    field_name: str
    normalized_field_name: str
    value: Any | None
    engine: EngineType
    # 该值在原始文本中的大致位置索引（字符位置）
    text_position: int | None = None
    # 识别来源片段（原始文本中的相关句子/行）
    source_snippet: str | None = None
    # 置信度
    confidence: float | None = None


@dataclass
class FieldConflictItem:
    """
    规则引擎与 LLM 引擎在某一字段上的冲突项。
    """
    field_name: str
    normalized_field_name: str
    rule_value: Any | None
    llm_value: Any | None
    # 冲突类型：value_mismatch / type_mismatch / format_mismatch / missing_in_one
    conflict_type: str
    # 冲突严重程度：high / medium / low
    severity: str
    # 规则引擎识别细节
    rule_detail: FieldValueDetail | None = None
    # LLM 引擎识别细节
    llm_detail: FieldValueDetail | None = None
    # 冲突说明
    description: str = ""


@dataclass
class FieldCoverageItem:
    """
    仅被某一个引擎识别出的字段。
    """
    field_name: str
    normalized_field_name: str
    value: Any | None
    engine: EngineType
    detail: FieldValueDetail | None = None


@dataclass
class ConflictHeatmapCell:
    """
    冲突热力图单元格。
    """
    # 文本区域起始位置
    start_position: int
    # 文本区域结束位置
    end_position: int
    # 区域文本片段
    snippet: str
    # 该区域涉及的冲突字段数
    conflict_count: int
    # 涉及字段名列表
    field_names: list[str] = field(default_factory=list)
    # 区域冲突密度（0-1）
    density: float = 0.0


@dataclass
class ContractStructuredContent:
    """
    合同结构化内容：输出给下游服务的关键参数之一。

    业务含义：将解析结果中的合同要素标准化，便于合同台账登记、收入确认、履约进度跟踪。
    """
    contract_no: str | None = None
    contract_name: str | None = None
    party_a_name: str | None = None
    party_b_name: str | None = None
    sign_date: str | None = None
    contract_amount: str | None = None
    contract_term: str | None = None
    payment_terms: str | None = None
    project_name: str | None = None
    # 字段来源标注：每个字段来自 rule / llm / consensus
    field_sources: dict[str, str] = field(default_factory=dict)
    # 整体置信度
    overall_confidence: float = 0.0
    # 是否需要人工复核
    review_required: bool = False
    # 复核原因
    review_reasons: list[str] = field(default_factory=list)


@dataclass
class ComplianceRiskItem:
    """
    合规风险预审项：输出给下游服务的关键参数之二。
    """
    risk_type: str
    severity: str
    description: str
    related_fields: list[str] = field(default_factory=list)
    suggested_action: str = ""
    policy_basis: str = ""


@dataclass
class ComplianceRiskPreReview:
    """
    合规风险预审：输出给下游服务的关键参数之二。

    业务含义：基于解析结果中的金额、日期、主体、条款等要素，
            预先识别可能存在的合规与审计风险，供后续审计程序参考。
    """
    risk_level: str = "low"
    risk_items: list[ComplianceRiskItem] = field(default_factory=list)
    # 基于哪些差异生成：rule / llm / conflict / agreement
    based_on: list[str] = field(default_factory=list)


@dataclass
class EngineComparisonReport:
    """
    双引擎对比分析报告。
    """
    # 文档类型
    document_type: str = ""
    # 规则引擎置信度
    rule_confidence: float = 0.0
    # LLM 引擎置信度
    llm_confidence: float = 0.0
    # 整体一致性率（0-1）
    consistency_rate: float = 0.0
    # 整体稳定性评分（0-1），综合一致性、置信度差异、冲突严重程度
    stability_score: float = 0.0
    # 是否需要人工复核
    review_required: bool = False
    # 复核原因
    review_reasons: list[str] = field(default_factory=list)
    # 一致字段
    consistent_fields: list[dict[str, Any]] = field(default_factory=list)
    # 冲突字段
    conflict_fields: list[FieldConflictItem] = field(default_factory=list)
    # 仅规则引擎识别字段
    rule_only_fields: list[FieldCoverageItem] = field(default_factory=list)
    # 仅 LLM 引擎识别字段
    llm_only_fields: list[FieldCoverageItem] = field(default_factory=list)
    # 冲突热力图
    conflict_heatmap: list[ConflictHeatmapCell] = field(default_factory=list)
    # 合同结构化内容（下游参数一）
    contract_structured_content: ContractStructuredContent | None = None
    # 合规风险预审（下游参数二）
    compliance_risk_pre_review: ComplianceRiskPreReview | None = None
    # 原始文本长度
    raw_text_length: int = 0
    # 处理耗时（毫秒）
    processing_time_ms: float = 0.0


# =============================================================================
# 字段标准化与别名映射
# =============================================================================

# 财务审计常见字段别名映射：统一由 field_alias_catalog 维护，避免多个模块各自定义。
_FIELD_NAME_ALIASES: dict[str, list[str]] = ALL_FIELD_ALIASES

# 合同关键字段集合
_CONTRACT_KEY_FIELDS: set[str] = {
    "contract_no", "contract_name", "party_a_name", "party_b_name",
    "sign_date", "contract_amount", "contract_term", "payment_terms", "project_name",
}

# 金额相关字段集合
_AMOUNT_FIELDS: set[str] = {
    "contract_amount", "total_amount", "amount_excl_tax", "tax_amount",
    "transaction_amount", "balance", "amount",
}

# 日期相关字段集合
_DATE_FIELDS: set[str] = {
    "sign_date", "invoice_date", "transaction_date", "date", "contract_term",
}


def _normalize_field_name(field_name: str, document_type: str | None = None, use_embedding: bool = True) -> str:
    """
    将字段名标准化，便于跨引擎识别同一业务字段。

    业务逻辑：
        1. 先使用 field_alias_catalog 静态别名表匹配，确定性高、可解释性强。
        2. 静态表未命中且启用 embedding 时，通过语义相似度兜底对齐。
        3. 仍未命中则返回原始字段名。

    Args:
        field_name: 原始字段名。
        document_type: 文档类型（如 contract/invoice/bank_statement），用于优先匹配该类型的别名。
        use_embedding: 是否启用 embedding 语义对齐兜底（默认 True）。

    Returns:
        str: 标准化后的字段名。
    """
    if not field_name:
        return ""

    text = str(field_name).strip().lower()
    text = re.sub(r"[\s\-]+", "_", text)

    # 1. 静态别名表匹配（按文档类型优先）
    catalog_normalized = normalize_field_name_from_catalog(field_name, document_type=document_type)
    catalog_normalized = re.sub(r"[\s\-]+", "_", catalog_normalized)
    if catalog_normalized and catalog_normalized != text:
        return catalog_normalized

    # 2. embedding 语义对齐兜底
    if use_embedding:
        aligned = normalize_field_with_embedding(
            field_name, static_aliases=_FIELD_NAME_ALIASES, embedding_threshold=0.80
        )
        if aligned and aligned != text:
            return aligned

    return text


def _build_field_mapping(
    data: dict[str, Any],
    document_type: str | None = None,
    use_embedding: bool = True,
) -> dict[str, list[str]]:
    """
    建立标准化字段名到原始字段名的映射。

    Args:
        data: 原始解析结果数据。
        document_type: 文档类型（可选），用于字段别名优先匹配。
        use_embedding: 是否启用 embedding 语义对齐兜底（默认 True）。

    Returns:
        dict[str, list[str]]: 标准化字段名到原始字段名列表的映射。
    """
    mapping: dict[str, list[str]] = defaultdict(list)
    for field_name in data.keys():
        normalized = _normalize_field_name(
            field_name, document_type=document_type, use_embedding=use_embedding
        )
        if normalized:
            mapping[normalized].append(field_name)
    return dict(mapping)


# =============================================================================
# 值标准化与比较
# =============================================================================

def _normalize_comparison_value(value: Any) -> str:
    """
    将字段值标准化，便于比较规则引擎和 LLM 结果是否一致。
    """
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
        .replace(",", "")
        .lower()
    )


def _is_numeric_value(value: Any) -> bool:
    """
    判断值是否可以解析为数字。
    """
    if value is None:
        return False
    try:
        Decimal(str(value).replace(",", "").replace("¥", "").replace("￥", "").replace("元", "").strip())
        return True
    except (InvalidOperation, ValueError):
        return False


def _extract_numeric(value: Any) -> Decimal | None:
    """
    从字符串中提取数字值。
    """
    if value is None:
        return None
    cleaned = re.sub(r"[^\d.\-]", "", str(value))
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _compare_values(rule_value: Any, llm_value: Any) -> tuple[bool, str, str]:
    """
    比较规则引擎和 LLM 引擎的两个字段值。

    Returns:
        (是否一致, 冲突类型, 严重程度)
    """
    rule_text = _normalize_comparison_value(rule_value)
    llm_text = _normalize_comparison_value(llm_value)

    # 两者都为空视为一致
    if not rule_text and not llm_text:
        return True, "", ""

    # 一个为空一个不为空
    if not rule_text or not llm_text:
        return False, "missing_in_one", "medium"

    # 精确一致
    if rule_text == llm_text:
        return True, "", ""

    # 数值型字段：允许 1 元以内差异（财务勾稽容差）
    if _is_numeric_value(rule_value) and _is_numeric_value(llm_value):
        rule_num = _extract_numeric(rule_value)
        llm_num = _extract_numeric(llm_value)
        if rule_num is not None and llm_num is not None:
            diff = abs(rule_num - llm_num)
            if diff <= Decimal("1.00"):
                return True, "", ""
            return False, "value_mismatch", "high" if diff > Decimal("100.00") else "medium"

    # 日期型字段：统一格式后再比较
    if rule_text.replace("-", "") == llm_text.replace("-", ""):
        return True, "", ""

    # 长度差异较大可能是格式问题
    len_diff_ratio = abs(len(rule_text) - len(llm_text)) / max(len(rule_text), len(llm_text), 1)
    if len_diff_ratio > 0.5:
        return False, "format_mismatch", "medium"

    return False, "value_mismatch", "medium"


def _classify_conflict_type(field_name: str, conflict_type: str, document_type: str | None = None) -> str:
    """
    根据字段语义进一步细分冲突类型。
    """
    normalized = _normalize_field_name(field_name, document_type=document_type)
    if normalized in _AMOUNT_FIELDS:
        return "amount_mismatch"
    if normalized in _DATE_FIELDS:
        return "date_mismatch"
    if normalized in {"party_a_name", "party_b_name", "buyer_name", "seller_name", "counterparty_name"}:
        return "party_mismatch"
    return conflict_type


# =============================================================================
# 文本位置定位
# =============================================================================

def _find_text_position(raw_text: str | None, value: Any) -> tuple[int | None, str | None]:
    """
    在原始文本中定位字段值的位置，返回字符索引和相关片段。
    """
    if not raw_text or value is None:
        return None, None

    value_text = str(value).strip()
    if not value_text:
        return None, None

    # 尝试直接查找
    position = raw_text.find(value_text)
    if position >= 0:
        snippet = _extract_snippet(raw_text, position, len(value_text))
        return position, snippet

    # 尝试查找标准化后的值
    normalized = _normalize_comparison_value(value_text)
    if normalized:
        position = raw_text.lower().find(normalized)
        if position >= 0:
            snippet = _extract_snippet(raw_text, position, len(normalized))
            return position, snippet

    # 尝试查找部分值（取前 6 个字符）
    if len(value_text) >= 6:
        partial = value_text[:6]
        position = raw_text.find(partial)
        if position >= 0:
            snippet = _extract_snippet(raw_text, position, len(partial))
            return position, snippet

    return None, None


def _extract_snippet(raw_text: str, position: int, length: int, context: int = 40) -> str:
    """
    提取字段值在原始文本中的上下文片段。
    """
    start = max(0, position - context)
    end = min(len(raw_text), position + length + context)
    snippet = raw_text[start:end].replace("\n", " ")
    return snippet.strip()


def _build_field_value_detail(
    field_name: str,
    normalized_name: str,
    value: Any,
    engine: EngineType,
    raw_text: str | None,
    confidence: float | None,
) -> FieldValueDetail:
    """
    构建字段识别详情。
    """
    position, snippet = _find_text_position(raw_text, value)
    return FieldValueDetail(
        field_name=field_name,
        normalized_field_name=normalized_name,
        value=value,
        engine=engine,
        text_position=position,
        source_snippet=snippet,
        confidence=confidence,
    )


# =============================================================================
# 冲突热力图生成
# =============================================================================

def _build_conflict_heatmap(
    conflict_fields: list[FieldConflictItem],
    raw_text: str | None,
    window_size: int = 200,
) -> list[ConflictHeatmapCell]:
    """
    根据冲突字段在原始文本中的位置，生成冲突热力图。
    """
    if not raw_text or not conflict_fields:
        return []

    # 收集所有有位置的冲突字段
    positioned_conflicts: list[tuple[int, str]] = []
    for conflict in conflict_fields:
        if conflict.rule_detail and conflict.rule_detail.text_position is not None:
            positioned_conflicts.append((conflict.rule_detail.text_position, conflict.field_name))
        elif conflict.llm_detail and conflict.llm_detail.text_position is not None:
            positioned_conflicts.append((conflict.llm_detail.text_position, conflict.field_name))

    if not positioned_conflicts:
        return []

    positioned_conflicts.sort(key=lambda x: x[0])

    # 滑动窗口统计冲突密度
    text_length = len(raw_text)
    cells: list[ConflictHeatmapCell] = []

    for start in range(0, text_length, window_size):
        end = min(text_length, start + window_size)
        window_conflicts: list[tuple[int, str]] = []
        for pos, field_name in positioned_conflicts:
            if start <= pos < end:
                window_conflicts.append((pos, field_name))

        if window_conflicts:
            snippet = _extract_snippet(raw_text, start, end - start, context=0)
            conflict_count = len(window_conflicts)
            field_names = list(sorted(set(f for _, f in window_conflicts)))
            density = min(1.0, conflict_count / max(3, len(positioned_conflicts) // 5 + 1))
            cells.append(ConflictHeatmapCell(
                start_position=start,
                end_position=end,
                snippet=snippet[:150] + ("..." if len(snippet) > 150 else ""),
                conflict_count=conflict_count,
                field_names=field_names,
                density=round(density, 4),
            ))

    return cells


# =============================================================================
# 下游参数生成
# =============================================================================

def _build_contract_structured_content(
    rule_data: dict[str, Any],
    llm_data: dict[str, Any],
    conflict_fields: list[FieldConflictItem],
    consistent_fields: list[dict[str, Any]],
    rule_confidence: float,
    llm_confidence: float,
) -> ContractStructuredContent:
    """
    构建合同结构化内容输出参数。

    业务逻辑：
        - 一致字段直接采纳，来源标注为 consensus
        - 冲突字段按置信度更高的一方采纳，来源标注为 rule 或 llm
        - 缺失字段尝试从另一方补全
    """
    content = ContractStructuredContent()
    field_sources: dict[str, str] = {}
    review_reasons: list[str] = []

    # 一致字段优先采纳
    for item in consistent_fields:
        normalized = item.get("normalized_field", "")
        value = item.get("value")
        if normalized in _CONTRACT_KEY_FIELDS and value is not None:
            setattr(content, normalized, str(value) if value is not None else None)
            field_sources[normalized] = "consensus"

    # 冲突字段按置信度选择
    for conflict in conflict_fields:
        normalized = conflict.normalized_field_name
        if normalized not in _CONTRACT_KEY_FIELDS:
            continue

        if rule_confidence >= llm_confidence:
            chosen_value = conflict.rule_value
            source = "rule"
        else:
            chosen_value = conflict.llm_value
            source = "llm"

        if chosen_value is not None:
            current_value = getattr(content, normalized, None)
            if current_value is None:
                setattr(content, normalized, str(chosen_value) if chosen_value is not None else None)
                field_sources[normalized] = source
                review_reasons.append(f"{conflict.field_name} 双引擎冲突，已按高置信度引擎采纳")

    # 补全缺失字段
    all_data = {**rule_data, **llm_data}
    for normalized in _CONTRACT_KEY_FIELDS:
        if getattr(content, normalized) is not None:
            continue
        # 尝试从原始字段名映射中查找
        for original_name, value in all_data.items():
            if _normalize_field_name(original_name) == normalized and value is not None:
                setattr(content, normalized, str(value) if value is not None else None)
                field_sources[normalized] = "merged"
                break

    content.field_sources = field_sources

    # 计算整体置信度
    consensus_count = sum(1 for s in field_sources.values() if s == "consensus")
    total_count = len(_CONTRACT_KEY_FIELDS)
    content.overall_confidence = round(consensus_count / total_count, 4) if total_count > 0 else 0.0

    # 关键字段缺失时标记复核
    missing_key_fields = [f for f in _CONTRACT_KEY_FIELDS if getattr(content, f) is None]
    if missing_key_fields:
        review_reasons.append(f"缺少关键合同字段：{', '.join(missing_key_fields)}")

    # 金额字段冲突时标记复核
    amount_conflicts = [c for c in conflict_fields if c.normalized_field_name in _AMOUNT_FIELDS]
    if amount_conflicts:
        review_reasons.append(f"金额字段存在冲突：{', '.join({c.field_name for c in amount_conflicts})}")

    content.review_required = len(review_reasons) > 0
    content.review_reasons = list(set(review_reasons))

    return content


def _build_compliance_risk_pre_review(
    content: ContractStructuredContent,
    conflict_fields: list[FieldConflictItem],
) -> ComplianceRiskPreReview:
    """
    构建合规风险预审输出参数。

    业务逻辑：基于合同结构化内容和字段冲突情况，识别常见合规与审计风险。
    """
    review = ComplianceRiskPreReview()
    risk_items: list[ComplianceRiskItem] = []
    based_on: set[str] = set()

    # 风险 1：金额字段冲突
    amount_conflicts = [c for c in conflict_fields if c.normalized_field_name in _AMOUNT_FIELDS]
    if amount_conflicts:
        based_on.add("conflict")
        risk_items.append(ComplianceRiskItem(
            risk_type="金额识别不一致",
            severity="high",
            description="规则引擎与 LLM 对金额字段识别结果不一致，可能影响收入确认、付款审批和审计抽样。",
            related_fields=[c.field_name for c in amount_conflicts],
            suggested_action="人工核对原始凭证金额，确认后更新台账。",
            policy_basis="《企业会计准则第14号——收入》第四条：收入金额能够可靠计量。",
        ))

    # 风险 2：主体名称识别不一致
    party_conflicts = [
        c for c in conflict_fields
        if c.normalized_field_name in {"party_a_name", "party_b_name", "buyer_name", "seller_name"}
    ]
    if party_conflicts:
        based_on.add("conflict")
        risk_items.append(ComplianceRiskItem(
            risk_type="交易主体识别不一致",
            severity="high",
            description="交易双方名称识别存在差异，可能导致往来款挂账错误、关联交易识别遗漏。",
            related_fields=[c.field_name for c in party_conflicts],
            suggested_action="核对合同/发票盖章主体与系统中往来单位一致性。",
            policy_basis="《企业会计准则第36号——关联方披露》",
        ))

    # 风险 3：缺少关键合同信息
    if content.review_required and content.review_reasons:
        missing_fields = content.field_sources.keys()
        if missing_fields:
            based_on.add("rule" if "rule" in content.field_sources.values() else "llm")
            risk_items.append(ComplianceRiskItem(
                risk_type="关键合同信息缺失",
                severity="medium",
                description="合同编号、金额、签订日期、主体等关键信息缺失，影响合同台账完整性。",
                related_fields=list(_CONTRACT_KEY_FIELDS),
                suggested_action="补充上传完整合同文本或人工录入缺失字段。",
                policy_basis="《企业内部控制应用指引第16号——合同管理》",
            ))

    # 风险 4：付款条款识别
    if content.payment_terms:
        based_on.add("agreement")
        payment_text = str(content.payment_terms).lower()
        if any(kw in payment_text for kw in ["预付", "预付款", "advance"]):
            risk_items.append(ComplianceRiskItem(
                risk_type="预付款条款",
                severity="low",
                description="合同包含预付款条款，需关注预付款比例、履约进度及坏账风险。",
                related_fields=["payment_terms"],
                suggested_action="结合履约进度复核预付款合理性。",
                policy_basis="《企业会计准则第22号——金融工具确认和计量》",
            ))

    # 风险 5：大额合同
    if content.contract_amount:
        try:
            amount = Decimal(re.sub(r"[^\d.\-]", "", str(content.contract_amount)))
            if amount >= Decimal("1000000"):
                based_on.add("agreement")
                risk_items.append(ComplianceRiskItem(
                    risk_type="大额合同",
                    severity="medium",
                    description=f"合同金额 {amount} 元，达到大额标准，建议执行更严格的审批与履约跟踪。",
                    related_fields=["contract_amount"],
                    suggested_action="纳入重大合同管理，关注履约进度、变更及验收。",
                    policy_basis="《企业内部控制应用指引第16号——合同管理》",
                ))
        except (InvalidOperation, ValueError):
            pass

    review.risk_items = risk_items
    review.based_on = list(based_on) if based_on else ["agreement"]

    # 确定整体风险等级
    severity_scores = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    max_score = max((severity_scores.get(r.severity, 0) for r in risk_items), default=0)
    if max_score >= 3:
        review.risk_level = "high"
    elif max_score >= 2:
        review.risk_level = "medium"
    else:
        review.risk_level = "low"

    return review


# =============================================================================
# 主分析函数
# =============================================================================

def analyze_dual_engine_result(
    rule_result: ParseResult | None,
    llm_result: ParseResult | None,
    raw_text: str | None = None,
    processing_time_ms: float = 0.0,
) -> EngineComparisonReport:
    """
    分析规则引擎与 LLM 引擎的解析结果，生成完整对比报告。

    业务含义：
        1. 精确识别内容不一致的具体位置和表现形式；
        2. 详细记录两种解析机制分别识别的内容部分及其边界；
        3. 统计并可视化展示不一致情况较为集中的内容区域；
        4. 输出稳定性评分和两个下游关键参数。

    Args:
        rule_result: 规则引擎解析结果
        llm_result: LLM 引擎解析结果
        raw_text: 原始提取文本（可选，用于定位冲突位置）
        processing_time_ms: 处理耗时（毫秒）

    Returns:
        EngineComparisonReport: 双引擎对比分析报告
    """
    report = EngineComparisonReport()
    report.raw_text_length = len(raw_text) if raw_text else 0
    report.processing_time_ms = processing_time_ms

    # 基础信息
    first_valid = rule_result or llm_result
    if first_valid:
        report.document_type = (
            first_valid.document_type.value
            if hasattr(first_valid.document_type, "value")
            else str(first_valid.document_type)
        )

    report.rule_confidence = rule_result.confidence if rule_result else 0.0
    report.llm_confidence = llm_result.confidence if llm_result else 0.0

    # 优先从结果中获取文档类型，用于按类型匹配字段别名
    document_type_for_alias: str | None = None
    if first_valid and first_valid.document_type:
        document_type_for_alias = (
            first_valid.document_type.value
            if hasattr(first_valid.document_type, "value")
            else str(first_valid.document_type)
        )

    # 单一引擎结果处理
    if not rule_result or not llm_result:
        report.consistency_rate = 0.0
        report.stability_score = 0.0
        report.review_required = True
        report.review_reasons = ["仅一个引擎返回结果，无法交叉验证"]
        report.conflict_heatmap = []
        if rule_result:
            report.rule_only_fields = _build_coverage_items(
                rule_result, raw_text, document_type=document_type_for_alias
            )
        if llm_result:
            report.llm_only_fields = _build_coverage_items(
                llm_result, raw_text, document_type=document_type_for_alias
            )
        report.contract_structured_content = _build_contract_structured_content(
            rule_result.data if rule_result else {},
            llm_result.data if llm_result else {},
            report.conflict_fields,
            report.consistent_fields,
            report.rule_confidence,
            report.llm_confidence,
        )
        report.compliance_risk_pre_review = _build_compliance_risk_pre_review(
            report.contract_structured_content,
            report.conflict_fields,
        )
        return report

    # 双引擎都有结果，执行详细对比
    rule_data = rule_result.data or {}
    llm_data = llm_result.data or {}

    rule_field_mapping = _build_field_mapping(rule_data, document_type=document_type_for_alias)
    llm_field_mapping = _build_field_mapping(llm_data, document_type=document_type_for_alias)
    all_normalized_fields = sorted(set(rule_field_mapping.keys()) | set(llm_field_mapping.keys()))

    consistent_fields: list[dict[str, Any]] = []
    conflict_fields: list[FieldConflictItem] = []
    rule_only_fields: list[FieldCoverageItem] = []
    llm_only_fields: list[FieldCoverageItem] = []

    for normalized_name in all_normalized_fields:
        rule_original_names = rule_field_mapping.get(normalized_name, [])
        llm_original_names = llm_field_mapping.get(normalized_name, [])

        display_name = rule_original_names[0] if rule_original_names else (llm_original_names[0] if llm_original_names else normalized_name)

        if rule_original_names and llm_original_names:
            rule_field_name = rule_original_names[0]
            llm_field_name = llm_original_names[0]
            rule_value = rule_data[rule_field_name]
            llm_value = llm_data[llm_field_name]

            is_consistent, conflict_type, severity = _compare_values(rule_value, llm_value)

            if is_consistent:
                consistent_fields.append({
                    "field": display_name,
                    "normalized_field": normalized_name,
                    "value": rule_value,
                    "rule_value": rule_value,
                    "llm_value": llm_value,
                })
            else:
                conflict_type = _classify_conflict_type(display_name, conflict_type, document_type=document_type_for_alias)
                rule_detail = _build_field_value_detail(
                    rule_field_name, normalized_name, rule_value, EngineType.RULE, raw_text, rule_result.confidence
                )
                llm_detail = _build_field_value_detail(
                    llm_field_name, normalized_name, llm_value, EngineType.LLM, raw_text, llm_result.confidence
                )

                description = f"规则引擎识别为 '{rule_value}'，LLM 识别为 '{llm_value}'"
                conflict_fields.append(FieldConflictItem(
                    field_name=display_name,
                    normalized_field_name=normalized_name,
                    rule_value=rule_value,
                    llm_value=llm_value,
                    conflict_type=conflict_type,
                    severity=severity,
                    rule_detail=rule_detail,
                    llm_detail=llm_detail,
                    description=description,
                ))
        elif rule_original_names:
            rule_field_name = rule_original_names[0]
            rule_value = rule_data[rule_field_name]
            detail = _build_field_value_detail(
                rule_field_name, normalized_name, rule_value, EngineType.RULE, raw_text, rule_result.confidence
            )
            rule_only_fields.append(FieldCoverageItem(
                field_name=rule_field_name,
                normalized_field_name=normalized_name,
                value=rule_value,
                engine=EngineType.RULE,
                detail=detail,
            ))
        elif llm_original_names:
            llm_field_name = llm_original_names[0]
            llm_value = llm_data[llm_field_name]
            detail = _build_field_value_detail(
                llm_field_name, normalized_name, llm_value, EngineType.LLM, raw_text, llm_result.confidence
            )
            llm_only_fields.append(FieldCoverageItem(
                field_name=llm_field_name,
                normalized_field_name=normalized_name,
                value=llm_value,
                engine=EngineType.LLM,
                detail=detail,
            ))

    report.consistent_fields = consistent_fields
    report.conflict_fields = conflict_fields
    report.rule_only_fields = rule_only_fields
    report.llm_only_fields = llm_only_fields

    # 计算一致性率
    comparable_count = len(consistent_fields) + len(conflict_fields)
    report.consistency_rate = (
        round(len(consistent_fields) / comparable_count, 4)
        if comparable_count > 0
        else 0.0
    )

    # 生成冲突热力图
    report.conflict_heatmap = _build_conflict_heatmap(conflict_fields, raw_text)

    # 计算稳定性评分
    report.stability_score = _calculate_stability_score(
        report.consistency_rate,
        report.rule_confidence,
        report.llm_confidence,
        conflict_fields,
    )

    # 判断是否需要复核
    report.review_required, report.review_reasons = _determine_review_required(
        report.consistency_rate,
        report.rule_confidence,
        report.llm_confidence,
        conflict_fields,
    )

    # 生成下游参数
    report.contract_structured_content = _build_contract_structured_content(
        rule_data, llm_data, conflict_fields, consistent_fields,
        report.rule_confidence, report.llm_confidence,
    )
    report.compliance_risk_pre_review = _build_compliance_risk_pre_review(
        report.contract_structured_content, conflict_fields,
    )

    return report


def _build_coverage_items(
    result: ParseResult,
    raw_text: str | None,
    document_type: str | None = None,
) -> list[FieldCoverageItem]:
    """
    将单引擎结果的所有字段构建为覆盖项。
    """
    items: list[FieldCoverageItem] = []
    if not result or not result.data:
        return items
    for field_name, value in result.data.items():
        normalized = _normalize_field_name(field_name, document_type=document_type)
        detail = _build_field_value_detail(
            field_name, normalized, value, result.engine, raw_text, result.confidence
        )
        items.append(FieldCoverageItem(
            field_name=field_name,
            normalized_field_name=normalized,
            value=value,
            engine=result.engine,
            detail=detail,
        ))
    return items


def _calculate_stability_score(
    consistency_rate: float,
    rule_confidence: float,
    llm_confidence: float,
    conflict_fields: list[FieldConflictItem],
) -> float:
    """
    计算整体稳定性评分。

    评分维度：
        - 一致性率（40%）
        - 双引擎平均置信度（30%）
        - 置信度差异惩罚（10%）
        - 冲突严重程度惩罚（20%）
    """
    avg_confidence = (rule_confidence + llm_confidence) / 2
    confidence_gap = abs(rule_confidence - llm_confidence)

    severity_penalty = 0.0
    for conflict in conflict_fields:
        if conflict.severity == "high":
            severity_penalty += 0.15
        elif conflict.severity == "medium":
            severity_penalty += 0.08
        else:
            severity_penalty += 0.03

    severity_penalty = min(1.0, severity_penalty)

    score = (
        consistency_rate * 0.4
        + avg_confidence * 0.3
        + (1.0 - confidence_gap) * 0.1
        + (1.0 - severity_penalty) * 0.2
    )
    return round(max(0.0, min(1.0, score)), 4)


def _determine_review_required(
    consistency_rate: float,
    rule_confidence: float,
    llm_confidence: float,
    conflict_fields: list[FieldConflictItem],
) -> tuple[bool, list[str]]:
    """
    判断是否需要人工复核并生成原因。
    """
    reasons: list[str] = []

    if consistency_rate < 0.6:
        reasons.append("两个引擎共同识别字段的一致率低于60%")

    confidence_gap = abs(rule_confidence - llm_confidence)
    if confidence_gap >= 0.25:
        reasons.append("规则引擎与LLM置信度差异较大")

    if llm_confidence < 0.7:
        reasons.append("LLM置信度低于70%，可能存在文本噪声或字段不完整")

    high_conflicts = [c for c in conflict_fields if c.severity == "high"]
    if high_conflicts:
        reasons.append(f"存在 {len(high_conflicts)} 个高风险冲突字段：{', '.join({c.field_name for c in high_conflicts})}")

    medium_conflicts = [c for c in conflict_fields if c.severity == "medium"]
    if len(medium_conflicts) >= 3:
        reasons.append(f"存在 {len(medium_conflicts)} 个中风险冲突字段")

    return len(reasons) > 0, reasons


# =============================================================================
# 序列化辅助
# =============================================================================

def _field_value_detail_to_dict(detail: FieldValueDetail | None) -> dict[str, Any] | None:
    if not detail:
        return None
    return {
        "field_name": detail.field_name,
        "normalized_field_name": detail.normalized_field_name,
        "value": detail.value,
        "engine": detail.engine.value if hasattr(detail.engine, "value") else str(detail.engine),
        "text_position": detail.text_position,
        "source_snippet": detail.source_snippet,
        "confidence": detail.confidence,
    }


def _conflict_item_to_dict(item: FieldConflictItem) -> dict[str, Any]:
    return {
        "field_name": item.field_name,
        "normalized_field_name": item.normalized_field_name,
        "rule_value": item.rule_value,
        "llm_value": item.llm_value,
        "conflict_type": item.conflict_type,
        "severity": item.severity,
        "rule_detail": _field_value_detail_to_dict(item.rule_detail),
        "llm_detail": _field_value_detail_to_dict(item.llm_detail),
        "description": item.description,
    }


def _coverage_item_to_dict(item: FieldCoverageItem) -> dict[str, Any]:
    return {
        "field_name": item.field_name,
        "normalized_field_name": item.normalized_field_name,
        "value": item.value,
        "engine": item.engine.value if hasattr(item.engine, "value") else str(item.engine),
        "detail": _field_value_detail_to_dict(item.detail),
    }


def _heatmap_cell_to_dict(cell: ConflictHeatmapCell) -> dict[str, Any]:
    return {
        "start_position": cell.start_position,
        "end_position": cell.end_position,
        "snippet": cell.snippet,
        "conflict_count": cell.conflict_count,
        "field_names": cell.field_names,
        "density": cell.density,
    }


def _contract_content_to_dict(content: ContractStructuredContent | None) -> dict[str, Any] | None:
    if not content:
        return None
    return {
        "contract_no": content.contract_no,
        "contract_name": content.contract_name,
        "party_a_name": content.party_a_name,
        "party_b_name": content.party_b_name,
        "sign_date": content.sign_date,
        "contract_amount": content.contract_amount,
        "contract_term": content.contract_term,
        "payment_terms": content.payment_terms,
        "project_name": content.project_name,
        "field_sources": content.field_sources,
        "overall_confidence": content.overall_confidence,
        "review_required": content.review_required,
        "review_reasons": content.review_reasons,
    }


def _risk_pre_review_to_dict(review: ComplianceRiskPreReview | None) -> dict[str, Any] | None:
    if not review:
        return None
    return {
        "risk_level": review.risk_level,
        "risk_items": [
            {
                "risk_type": item.risk_type,
                "severity": item.severity,
                "description": item.description,
                "related_fields": item.related_fields,
                "suggested_action": item.suggested_action,
                "policy_basis": item.policy_basis,
            }
            for item in review.risk_items
        ],
        "based_on": review.based_on,
    }


def report_to_dict(report: EngineComparisonReport) -> dict[str, Any]:
    """
    将 EngineComparisonReport 转换为可 JSON 序列化的字典。
    """
    return {
        "document_type": report.document_type,
        "rule_confidence": report.rule_confidence,
        "llm_confidence": report.llm_confidence,
        "consistency_rate": report.consistency_rate,
        "stability_score": report.stability_score,
        "review_required": report.review_required,
        "review_reasons": report.review_reasons,
        "consistent_fields": report.consistent_fields,
        "conflict_fields": [_conflict_item_to_dict(item) for item in report.conflict_fields],
        "rule_only_fields": [_coverage_item_to_dict(item) for item in report.rule_only_fields],
        "llm_only_fields": [_coverage_item_to_dict(item) for item in report.llm_only_fields],
        "conflict_heatmap": [_heatmap_cell_to_dict(cell) for cell in report.conflict_heatmap],
        "contract_structured_content": _contract_content_to_dict(report.contract_structured_content),
        "compliance_risk_pre_review": _risk_pre_review_to_dict(report.compliance_risk_pre_review),
        "raw_text_length": report.raw_text_length,
        "processing_time_ms": report.processing_time_ms,
    }
