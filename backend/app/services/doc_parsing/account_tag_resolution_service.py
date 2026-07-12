# -*- coding: utf-8 -*-
"""
科目与标签解析服务（Account Tag Resolution Service）。

模块功能：
    将序时簿导入的科目编码/名称，按"一级科目保留、强制二级科目保留、
    其余下级段转 Tag"的原则进行拆分与映射，输出归一化科目信息及建议 Tag。

业务场景：
    - 审计人员从被审计单位导入序时簿，源数据中科目往往包含二级/三级明细
      （如"应收账款-A客户"、"管理费用-工资"）。
    - 系统需要区分：哪些层级属于会计准则/税法强制科目，必须保留；
      哪些属于管理/辅助核算维度，应转为 EntryTag。

政策依据：
    - 项目"一级科目 + Dimension(Tag)"核心设计思想。
    - 税法/会计准则强制要求的二级科目（如"应交税费-应交增值税-进项税额"）
      保留完整层级，不得扁平化。
    - 管理/辅助核算维度（客户、供应商、项目、部门等）转为 EntryTag，
      通过关系数据库记录并通过向量数据库支持语义检索。

输入数据：
    - account_code: 原始科目编码（可能包含多级，如"1122.01"、"2221.01.01"）
    - account_name: 原始科目名称（可能包含"-"、"/"、"_"分隔的下级段）
    - summary: 分录摘要，当科目中缺少辅助核算维度时用于补充识别
    - config: 可选的配置对象，若未提供则从配置服务加载

输出结果：
    - account_code: 归一化后的科目编码（一级或强制完整层级）
    - account_name: 归一化后的科目名称
    - original_code: 原始科目编码（保留审计追溯）
    - original_name: 原始科目名称（保留审计追溯）
    - segments: 剩余科目段列表（下级明细内容）
    - suggested_tags: 建议的 TagCategory + value 列表
    - counterparty_name: 识别到的往来单位名称
    - requires_llm_resolution: 是否需 LLM 从摘要进一步识别维度

创建日期：2026-07-03
更新记录：
    2026-07-03  初始版本，实现科目拆分、强制层级保留、辅助核算维度转 Tag
    2026-07-04  重构为从配置服务加载规则，支持 DB+YAML 双源配置
"""
from dataclasses import dataclass, field
from typing import Any
import re

from app.config.account_tag_config import (
    AccountTagConfig,
    load_account_tag_config,
)
from app.services.doc_parsing.name_standardization_service import infer_name_standardized

# 所有者权益一级科目：其下二级明细保留完整编码，不转 Tag（便于三表勾稽）
_EQUITY_HIERARCHY_ROOTS = frozenset({"4001", "4002", "4101", "4103", "4104"})

# 一级科目保留，下级名称段拆为多 Tag（共享 Tag；不进入实体档案待补，可在待处理队列规范命名）
_STRUCTURED_NAME_TAG_ACCOUNTS: dict[str, tuple[str, str]] = {
    "1601": ("fixed_asset_class", "fixed_asset_item"),
    "1602": ("fixed_asset_class", "fixed_asset_item"),
    "1604": ("cip_category", "cip_project"),
    "2001": ("loan_channel", "counterparty"),
}


@dataclass
class ResolvedAccount:
    """科目解析结果"""

    account_code: str = ""
    account_name: str = ""
    original_code: str = ""
    original_name: str = ""
    segments: list[str] = field(default_factory=list)
    suggested_tags: list[dict[str, Any]] = field(default_factory=list)
    counterparty_name: str | None = None
    requires_llm_resolution: bool = False
    source_sub_code: str | None = None


def _normalize_text(value: Any) -> str:
    """标准化文本"""
    if value is None:
        return ""
    return str(value).strip()


def _expand_numeric_code_segments(account_code: str) -> list[str]:
    """
    将无小数点的纯数字科目编码按 COA 规则拆段（4+2+2…）。

    例如：100202 → [1002, 02]；22210101 → [2221, 01, 01]
    """
    normalized = account_code.strip()
    if not normalized:
        return []
    if "." in normalized:
        return [segment.strip() for segment in normalized.split(".") if segment.strip()]
    if not normalized.isdigit():
        return [normalized]
    if len(normalized) <= 4:
        return [normalized]
    segments = [normalized[:4]]
    rest = normalized[4:]
    while rest:
        segments.append(rest[:2])
        rest = rest[2:]
    return segments


def _split_segment_by_inner_dash(text: str) -> list[str]:
    """拆分段内的 em dash / 中文「一」连接（如 房屋建筑物—堆场及封闭棚）。"""
    normalized = text.strip()
    if not normalized:
        return []
    for sep in ("—", "–", "－"):
        normalized = normalized.replace(sep, "|")
    normalized = re.sub(r"(?<=[\u4e00-\u9fff])一(?=[\u4e00-\u9fff])", "|", normalized)
    if "|" in normalized:
        parts = [part.strip() for part in normalized.split("|") if part.strip()]
        return parts if parts else [text.strip()]
    if "-" in normalized and "+" not in normalized:
        parts = [part.strip() for part in normalized.split("-") if part.strip()]
        if len(parts) > 1:
            return parts
    return [text.strip()]


def _split_name_into_segments(account_name: str) -> list[str]:
    """
    拆分复合科目名称（常见 ERP：固定资产_房屋建筑物—堆场及封闭棚）。

    优先按 `_` 分段，再对每段按 em dash / 中文「一」继续拆分；不拆 `/`（避免破坏括号内说明）。
    """
    normalized = account_name.strip()
    if not normalized:
        return []

    if "_" in normalized:
        parts: list[str] = []
        for chunk in normalized.split("_"):
            parts.extend(_split_segment_by_inner_dash(chunk))
        return [part for part in parts if part]

    return _split_segment_by_inner_dash(normalized)


def _name_segments_for_tagging(name_segments: list[str], base_name: str) -> list[str]:
    """一级科目编码时，从名称段中提取应转为 Tag 的下级段。"""
    if len(name_segments) <= 1:
        return []
    if name_segments[0] == base_name or base_name in name_segments[0]:
        return [segment for segment in name_segments[1:] if segment]
    return [segment for segment in name_segments if segment]


def _split_account_segments(
    account_code: str, account_name: str
) -> tuple[list[str], str, list[str], bool]:
    """
    拆分科目编码和名称为层级段。

    业务逻辑：
        1. 优先使用编码中的小数点分段；无小数点时按 4+2+2 数字层级拆段。
        2. 名称支持 `_`、em dash、中文「一」及 `-/` 等复合分隔。
        3. 返回拆分后的编码段和名称段。
    """
    code_segments = _expand_numeric_code_segments(account_code)
    normalized_code = account_code.strip()
    name_segments = _split_name_into_segments(account_name) if account_name else []

    return code_segments, account_name, name_segments, "." in normalized_code


def _is_mandatory_hierarchical_account(
    account_code: str,
    account_name: str,
    config: AccountTagConfig,
) -> bool:
    """
    判断是否属于强制保留层级的科目。

    判断依据：
        1. 编码前缀匹配配置中的强制科目编码列表。
        2. 名称包含配置中的强制科目关键词。
    """
    normalized_code = account_code.strip()
    normalized_name = account_name.strip()

    root_code = normalized_code.split(".")[0] if normalized_code else ""
    if root_code in _EQUITY_HIERARCHY_ROOTS and len(normalized_code) > len(root_code):
        return True

    for mandatory_code in config.mandatory_hierarchical_accounts:
        if normalized_code.startswith(mandatory_code):
            return True

    for keyword in config.mandatory_hierarchical_keywords:
        if keyword in normalized_name:
            return True

    return False


def _infer_tag_category_from_account(
    base_account_code: str,
    base_account_name: str,
    config: AccountTagConfig,
) -> str | None:
    """
    根据一级科目推断下级段应映射的 TagCategory。
    """
    if base_account_code:
        category = config.account_code_tag_category.get(base_account_code)
        if category:
            return category

    if base_account_name:
        for keyword, category in config.account_name_tag_category.items():
            if keyword in base_account_name:
                return category

    return None


def _resolve_base_account(
    code_segments: list[str],
    name_segments: list[str],
    config: AccountTagConfig,
    *,
    code_used_dot_notation: bool,
) -> tuple[str, str, list[str], bool]:
    """
    解析基础科目编码和名称，以及剩余段。

    业务逻辑：
        1. 如果编码总长度 <= 4 位（一级），直接保留。
        2. 如果编码属于强制保留层级科目，保留完整编码和名称。
        3. 否则取前 4 位作为一级科目，剩余段作为辅助核算维度。
    """
    full_code = ".".join(code_segments)
    full_name = "-".join(name_segments)

    # 情况1：只有一级科目编码 — 若名称含下级段，仍拆 Tag（如 1601 + 固定资产_房屋建筑物—堆场）
    if len(code_segments) == 1 and len(code_segments[0]) <= 4:
        base_code = code_segments[0]
        base_name = name_segments[0] if name_segments else ""
        remaining = _name_segments_for_tagging(name_segments, base_name)
        if remaining:
            return base_code, base_name, remaining, True
        return base_code, base_name, [], False

    # 情况2：强制保留层级
    if _is_mandatory_hierarchical_account(full_code, full_name, config):
        return full_code, full_name, [], False

    # 情况3：取一级科目，剩余段转为 tag
    base_code = code_segments[0] if code_segments else ""
    base_name = name_segments[0] if name_segments else ""
    if len(name_segments) > 1:
        remaining_segments = name_segments[1:]
    elif not code_used_dot_notation and len(code_segments) > 1:
        remaining_segments = code_segments[1:]
    else:
        remaining_segments = []

    return base_code, base_name, remaining_segments, True


def _infer_counterparty_from_segments(
    base_account_code: str,
    base_account_name: str,
    remaining_segments: list[str],
) -> str | None:
    """
    从剩余科目段推断往来单位名称。

    业务逻辑：
        往来类科目（应收/应付/预收/预付/其他应收/其他应付）的下级段，
        通常就是客户、供应商或往来对象名称。
    """
    is_counterparty_account = any(
        keyword in base_account_name
        for keyword in ["应收", "应付", "预收", "预付"]
    )

    if not is_counterparty_account:
        return None

    if remaining_segments:
        # 优先取第一段作为往来单位名称
        return remaining_segments[0]

    return None


def _infer_source_sub_code(code_segments: list[str], flattened: bool) -> str | None:
    """扁平化时保留来源编码段（如 100202 → 02，1002.04 → 04）。"""
    if not flattened or len(code_segments) <= 1:
        return None
    return ".".join(code_segments[1:])


def _build_suggested_tags(
    base_account_code: str,
    base_account_name: str,
    remaining_segments: list[str],
    config: AccountTagConfig,
    *,
    source_sub_code: str | None = None,
) -> list[dict[str, Any]]:
    """
    根据剩余科目段构建建议 Tag。

    业务逻辑：
        1. 推断默认 TagCategory。
        2. 每个剩余段作为一个 tag_value。
        3. 当段数较多时，第一段通常是对应 category 的主体，后续段可能是部门/项目/区域。
    """
    tags: list[dict[str, Any]] = []
    if not remaining_segments:
        return tags

    structured = _STRUCTURED_NAME_TAG_ACCOUNTS.get(base_account_code)
    if structured:
        first_category, detail_category = structured
        tags.append({
            "category_code": first_category,
            "tag_value": remaining_segments[0],
            "display_name": remaining_segments[0],
            "source_sub_code": source_sub_code,
            "name_standardized": True,
            "tag_source": "rule",
            "confidence": 0.92,
        })
        for segment in remaining_segments[1:]:
            tags.append({
                "category_code": detail_category,
                "tag_value": segment,
                "display_name": segment,
                "source_sub_code": source_sub_code,
                "name_standardized": True,
                "tag_source": "rule",
                "confidence": 0.88,
            })
        return tags

    default_category = _infer_tag_category_from_account(
        base_account_code, base_account_name, config
    )
    if not default_category:
        return tags

    # 第一段使用默认 category
    first_segment = remaining_segments[0]
    tags.append({
        "category_code": default_category,
        "tag_value": first_segment,
        "display_name": first_segment,
        "source_sub_code": source_sub_code,
        "name_standardized": infer_name_standardized(
            first_segment,
            category_code=default_category,
            tag_value=first_segment,
            source_sub_code=source_sub_code,
            account_code=base_account_code,
        ),
        "tag_source": "rule",
        "confidence": 0.9,
    })

    # 后续段根据内容推断 category
    fallback_categories = ["department", "project", "region"]
    for idx, segment in enumerate(remaining_segments[1:], start=1):
        category = _infer_tag_category_from_text(segment, config) or fallback_categories[(idx - 1) % 3]
        tags.append({
            "category_code": category,
            "tag_value": segment,
            "display_name": segment,
            "source_sub_code": source_sub_code,
            "name_standardized": infer_name_standardized(
                segment,
                category_code=category,
                tag_value=segment,
                source_sub_code=source_sub_code,
                account_code=base_account_code,
            ),
            "tag_source": "rule",
            "confidence": 0.7,
        })

    return tags


def _infer_tag_category_from_text(text: str, config: AccountTagConfig) -> str | None:
    """
    从文本内容推断 TagCategory。
    """
    text_normalized = text.strip().lower()

    for category, keywords in config.auxiliary_keywords.items():
        for keyword in keywords:
            if keyword in text:
                return category

    return None


def _infer_auxiliary_tags_from_summary(summary: str, config: AccountTagConfig) -> list[dict[str, Any]]:
    """
    从摘要中推断辅助核算维度。

    业务逻辑：
        当科目中未能识别出辅助核算维度时，尝试从摘要中提取
        部门、项目、区域等信息。
    """
    tags: list[dict[str, Any]] = []
    if not summary:
        return tags

    for category, keywords in config.auxiliary_keywords.items():
        for keyword in keywords:
            if keyword in summary:
                tags.append({
                    "category_code": category,
                    "tag_value": keyword,
                    "display_name": keyword,
                    "tag_source": "llm_suggested",
                    "confidence": 0.6,
                })
                break

    return tags


def resolve_account_for_import(
    account_code: str | None,
    account_name: str | None,
    summary: str | None = None,
    config: AccountTagConfig | None = None,
) -> ResolvedAccount:
    """
    解析导入科目，输出归一化科目和标签建议。

    Args:
        account_code: 原始科目编码
        account_name: 原始科目名称
        summary: 分录摘要，用于补充识别
        config: 可选的配置对象，若未提供则从配置服务加载

    Returns:
        ResolvedAccount 对象，包含归一化后的科目信息和建议 Tag
    """
    original_code = _normalize_text(account_code)
    original_name = _normalize_text(account_name)
    normalized_summary = _normalize_text(summary)

    # 加载配置
    if config is None:
        config = load_account_tag_config()

    # 兼容性处理：如果编码为空但名称中包含编码
    if not original_code and original_name:
        parts = original_name.split(maxsplit=1)
        if parts and parts[0].replace(".", "").isdigit():
            original_code = parts[0]
            original_name = parts[1] if len(parts) > 1 else ""

    code_segments, _, name_segments, code_used_dot_notation = _split_account_segments(
        original_code, original_name
    )

    base_code, base_name, remaining_segments, flattened = _resolve_base_account(
        code_segments, name_segments, config, code_used_dot_notation=code_used_dot_notation
    )
    source_sub_code = _infer_source_sub_code(code_segments, flattened)

    # 构建建议 Tag
    suggested_tags = _build_suggested_tags(
        base_code,
        base_name,
        remaining_segments,
        config,
        source_sub_code=source_sub_code,
    )

    # 识别往来单位
    counterparty_name = _infer_counterparty_from_segments(
        base_code, base_name, remaining_segments
    )

    # 当科目中没有识别到辅助核算维度时，尝试从摘要中补充
    if not suggested_tags and normalized_summary:
        summary_tags = _infer_auxiliary_tags_from_summary(normalized_summary, config)
        suggested_tags.extend(summary_tags)

    # 判断是否需要 LLM 进一步识别。
    # 当科目被扁平化（原编码存在下级段）且未能识别出任何辅助核算维度时，
    # 对于往来类/成本费用类等依赖辅助核算的科目，需要 LLM 从摘要中进一步分析。
    is_counterparty_or_analytic_account = any(
        keyword in base_name
        for keyword in ["应收", "应付", "预收", "预付", "主营业务收入", "生产成本", "制造费用", "管理费用", "销售费用", "财务费用"]
    )
    requires_llm = (
        flattened
        and not suggested_tags
        and bool(normalized_summary)
        and is_counterparty_or_analytic_account
    )

    return ResolvedAccount(
        account_code=base_code,
        account_name=base_name,
        original_code=original_code,
        original_name=original_name,
        segments=remaining_segments,
        suggested_tags=suggested_tags,
        counterparty_name=counterparty_name,
        requires_llm_resolution=requires_llm,
        source_sub_code=source_sub_code,
    )
