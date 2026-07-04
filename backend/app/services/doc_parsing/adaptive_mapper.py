"""
自适应字段映射服务

使用 AI 辅助识别未知格式文件的字段映射
"""

import json
import re
from typing import Any

from app.core.config import get_settings
from app.services.agent.ai_client_service import AIClient


# 标准会计字段定义（用于 AI 提示）
STANDARD_FIELDS = {
    "voucher_no": "凭证号，用于唯一标识每张凭证",
    "voucher_date": "凭证日期，记账的日期",
    "summary": "摘要，描述这笔分录的内容",
    "account_code": "科目编码，会计科目的编码",
    "account_name": "科目名称，会计科目的名称",
    "debit_amount": "借方金额，借方发生的金额",
    "credit_amount": "贷方金额，贷方发生的金额",
    "counterparty": "往来单位，交易对手方名称",
}


def build_ai_mapping_prompt(headers: list[str]) -> str:
    """构建 AI 映射提示"""
    header_list = "\n".join(f"- {h}" for h in headers)

    field_descriptions = "\n".join(
        f"- {k}: {v}" for k, v in STANDARD_FIELDS.items()
    )

    return f"""你是一个专业的会计软件数据分析师。

给定一个 Excel 或 CSV 文件的表头列表，请识别每个表头对应的标准会计分录字段。

## 表头列表：
{header_list}

## 标准会计分录字段：
{field_descriptions}

## 输出要求：
请返回一个 JSON 对象，格式如下：
{{
  "mappings": {{
    "表头1": "字段名1",
    "表头2": "字段名2",
    ...
  }},
  "confidence": 0.0-1.0之间的置信度,
  "notes": "备注说明"
}}

注意：
1. 只返回 JSON，不要添加任何解释或标记
2. 如果某个表头无法识别，映射值为 null
3. 置信度表示映射的准确程度"""


def parse_ai_response(response: str) -> dict[str, str] | None:
    """解析 AI 返回的映射结果"""
    try:
        # 尝试提取 JSON
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            data = json.loads(json_match.group())
            mappings = data.get("mappings", {})
            return {str(k): str(v) for k, v in mappings.items()} if isinstance(mappings, dict) else None
    except json.JSONDecodeError:
        pass
    return None


def ai_assist_mapping(headers: list[str]) -> dict[str, str] | None:
    """
    使用 AI 辅助字段映射

    当模板匹配失败时，调用 AI 分析表头并生成映射

    Args:
        headers: 表头列表

    Returns:
        映射字典 {表头: 标准字段名} 或 None
    """
    settings = get_settings()

    # 检查 AI 配置
    if not settings.ai_base_url or not settings.ai_api_key:
        return None

    try:
        prompt = build_ai_mapping_prompt(headers)

        ai_client = AIClient()
        response = ai_client.sync_chat_completion(
            messages=[
                {"role": "system", "content": "你是一个专业的会计软件数据分析师。"},
                {"role": "user", "content": prompt},
            ],
            model=settings.ai_model or "gpt-3.5-turbo",
        )

        if response:
            mappings = parse_ai_response(response)
            return mappings

    except Exception:
        pass

    return None


def improve_mapping_with_ai(
    headers: list[str],
    sample_rows: list[dict[str, Any]],
    current_mapping: dict[str, str],
) -> dict[str, str]:
    """
    使用 AI 改进现有映射

    根据样本数据验证和改进字段映射

    Args:
        headers: 表头列表
        sample_rows: 样本数据行
        current_mapping: 当前映射

    Returns:
        改进后的映射
    """
    settings = get_settings()

    if not settings.ai_base_url or not settings.ai_api_key:
        return current_mapping

    try:
        # 构建样本数据摘要
        sample_summary = []
        for i, row in enumerate(sample_rows[:3]):
            row_str = ", ".join(f"{k}={v}" for k, v in row.items() if v)
            sample_summary.append(f"行{i+1}: {row_str}")

        sample_text = "\n".join(sample_summary)
        mapping_str = "\n".join(f"- {h} -> {f}" for h, f in current_mapping.items())

        prompt = f"""给定一个 Excel 或 CSV 文件的样本数据，请验证和改进字段映射。

## 当前映射：
{mapping_str}

## 表头：
{", ".join(headers)}

## 样本数据（前3行）：
{sample_text}

## 任务：
1. 验证当前映射是否正确
2. 如果有不正确的地方，给出改进建议
3. 如果有遗漏的映射，补充完整

## 输出要求：
返回 JSON 格式：
{{
  "improved_mapping": {{
    "表头1": "字段名1",
    ...
  }},
  "changes": [
    {{"header": "表头", "old_field": "旧字段", "new_field": "新字段", "reason": "原因"}}
  ]
}}

只返回 JSON，不要添加任何解释。"""

        ai_client = AIClient()
        response = ai_client.sync_chat_completion(
            messages=[
                {"role": "system", "content": "你是一个专业的会计软件数据分析师。"},
                {"role": "user", "content": prompt},
            ],
            model=settings.ai_model or "gpt-3.5-turbo",
        )

        if response:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
                improved = data.get("improved_mapping", {})
                if isinstance(improved, dict):
                    return {str(k): str(v) for k, v in improved.items()}

    except Exception:
        pass

    return current_mapping


def suggest_mapping_adjustments(
    headers: list[str],
    entries: list[dict[str, Any]],
    quality_score: float,
) -> list[str]:
    """
    根据解析质量建议映射调整

    当质量分数较低时，提供改进建议

    Args:
        headers: 表头列表
        entries: 解析出的分录
        quality_score: 当前质量分数

    Returns:
        建议列表
    """
    suggestions = []

    # 检查是否有空值过多的字段
    empty_counts: dict[str, int] = {}
    for entry in entries:
        for key, value in entry.items():
            if not value:
                empty_counts[key] = empty_counts.get(key, 0) + 1

    high_empty_rate_fields = [
        field for field, count in empty_counts.items()
        if count > len(entries) * 0.5
    ]

    if high_empty_rate_fields:
        suggestions.append(
            f"以下字段空值率较高，可能映射错误：{', '.join(high_empty_rate_fields)}"
        )

    # 检查金额字段
    total_amount = sum(
        abs(e.get("debit_amount", 0)) + abs(e.get("credit_amount", 0))
        for e in entries
    )

    if total_amount == 0 and len(entries) > 0:
        suggestions.append(
            "所有金额字段均为0，请检查金额映射是否正确"
        )

    # 检查日期字段
    has_valid_date = any(e.get("voucher_date") for e in entries)
    if not has_valid_date and len(entries) > 0:
        suggestions.append(
            "未识别到有效日期，请检查日期字段映射"
        )

    return suggestions


# 缓存已学习的映射
_mapping_cache: dict[frozenset[str], dict[str, str]] = {}


def cache_mapping(headers: tuple[str, ...], mapping: dict[str, str]) -> None:
    """缓存映射结果"""
    key = frozenset(headers)
    _mapping_cache[key] = mapping


def get_cached_mapping(headers: list[str]) -> dict[str, str] | None:
    """获取缓存的映射"""
    key = frozenset(headers)
    return _mapping_cache.get(key)


def clear_mapping_cache() -> None:
    """清除映射缓存"""
    _mapping_cache.clear()
