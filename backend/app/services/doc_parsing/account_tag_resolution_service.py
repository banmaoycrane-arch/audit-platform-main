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

from app.config.account_tag_config import (
    AccountTagConfig,
    load_account_tag_config,
)


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


def _normalize_text(value: Any) -> str:
    """标准化文本"""
    if value is None:
        return ""
    return str(value).strip()


def _split_account_segments(account_code: str, account_name: str) -> tuple[str, str, list[str]]:
    """
    拆分科目编码和名称为层级段。

    业务逻辑：
        1. 优先使用编码中的小数点分段。
        2. 名称中使用 "-"、"/"、"_" 分隔。
        3. 返回拆分后的编码段和名称段。
    """
    code_segments = [s.strip() for s in account_code.split(".") if s.strip()]
    name_segments = []

    if account_name:
        for sep in ["-", "/", "_", "|"]:
            if sep in account_name:
                name_segments = [s.strip() for s in account_name.split(sep) if s.strip()]
                break
        if not name_segments:
            name_segments = [account_name]

    return code_segments, account_name, name_segments


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

    # 情况1：只有一级科目
    if len(code_segments) == 1 and len(code_segments[0]) <= 4:
        return code_segments[0], name_segments[0] if name_segments else "", [], False

    # 情况2：强制保留层级
    if _is_mandatory_hierarchical_account(full_code, full_name, config):
        return full_code, full_name, [], False

    # 情况3：取一级科目，剩余段转为 tag
    base_code = code_segments[0] if code_segments else ""
    base_name = name_segments[0] if name_segments else ""
    remaining_name_segments = name_segments[1:] if len(name_segments) > 1 else []

    return base_code, base_name, remaining_name_segments, True


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


def _build_suggested_tags(
    base_account_code: str,
    base_account_name: str,
    remaining_segments: list[str],
    config: AccountTagConfig,
) -> list[dict[str, Any]]:
    """
    根据剩余科目段构建建议 Tag。

    业务逻辑：
        1. 推断默认 TagCategory。
        2. 每个剩余段作为一个 tag_value。
        3. 当段数较多时，第一段通常是对应 category 的主体，后续段可能是部门/项目/区域。
    """
    tags: list[dict[str, Any]] = []
    default_category = _infer_tag_category_from_account(
        base_account_code, base_account_name, config
    )

    if not remaining_segments or not default_category:
        return tags

    # 第一段使用默认 category
    tags.append({
        "category_code": default_category,
        "tag_value": remaining_segments[0],
        "display_name": remaining_segments[0],
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

    code_segments, _, name_segments = _split_account_segments(
        original_code, original_name
    )

    base_code, base_name, remaining_segments, flattened = _resolve_base_account(
        code_segments, name_segments, config
    )

    # 构建建议 Tag
    suggested_tags = _build_suggested_tags(base_code, base_name, remaining_segments, config)

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
    )
