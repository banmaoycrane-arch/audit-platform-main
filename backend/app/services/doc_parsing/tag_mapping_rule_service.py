# -*- coding: utf-8 -*-
"""
标签映射规则服务（Tag Mapping Rule Service）。

业务场景：
    实现外部财务数据（如二级科目编码、辅助核算项、自由标签）到内部 Dimension 的映射。
    当从传统 ERP 导入数据时，系统根据规则自动将外部表达转换为本系统的 TagCategory + tag_value。

政策依据：
    项目采用"一级科目 + Dimension"核心模型，映射规则属于虚拟兼容层，
    不改变内部数据语义，仅用于数据交换时的协议转换。

输入数据：
    - ledger_id: 账簿 ID
    - source_pattern: 外部模式（科目编码、摘要关键词、标签名等）
    - source_type: account_code / summary / tag
    - target_category_code: 内部 Dimension 编码
    - target_value / target_value_id: 内部标签值或主数据 ID

输出结果：
    - TagMappingRule 的 CRUD
    - 根据输入自动匹配并输出内部 Dimension 表达
"""
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import TagMappingRule
from app.services.doc_parsing.tag_category_service import get_category_by_code


def _normalize_pattern(pattern: str) -> str:
    """
    标准化映射模式：去除首尾空格。
    """
    return pattern.strip()


def create_mapping_rule(
    db: Session,
    ledger_id: int,
    source_pattern: str,
    target_category_code: str,
    target_value: str | None = None,
    target_value_id: int | None = None,
    source_type: str = "account_code",
    priority: int = 0,
    is_regex: bool = False,
    is_active: bool = True,
    description: str | None = None,
    created_by: int | None = None,
) -> TagMappingRule:
    """
    创建映射规则。

    业务逻辑：
        1. 校验 target_category_code 在当前 ledger 下存在。
        2. 同一 ledger + source_pattern + source_type + target_category_code 不可重复。

    Raises:
        ValueError: 分类不存在或规则重复
    """
    normalized_pattern = _normalize_pattern(source_pattern)
    category = get_category_by_code(db, ledger_id, target_category_code)
    if category is None:
        raise ValueError(f"目标分类不存在：{target_category_code}")

    existing = (
        db.query(TagMappingRule)
        .filter(
            TagMappingRule.ledger_id == ledger_id,
            TagMappingRule.source_pattern == normalized_pattern,
            TagMappingRule.source_type == source_type,
            TagMappingRule.target_category_code == category.code,
        )
        .first()
    )
    if existing:
        raise ValueError("该映射规则已存在")

    rule = TagMappingRule(
        ledger_id=ledger_id,
        source_pattern=normalized_pattern,
        source_type=source_type,
        target_category_code=category.code,
        target_value=target_value,
        target_value_id=target_value_id,
        priority=priority,
        is_regex=is_regex,
        is_active=is_active,
        description=description,
        created_by=created_by,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(rule)
    db.flush()
    return rule


def get_mapping_rule_by_id(db: Session, rule_id: int) -> TagMappingRule | None:
    """
    根据 ID 查询映射规则。
    """
    return db.query(TagMappingRule).filter(TagMappingRule.id == rule_id).first()


def list_mapping_rules(
    db: Session,
    ledger_id: int,
    source_type: str | None = None,
    is_active: bool | None = None,
) -> list[TagMappingRule]:
    """
    查询映射规则列表，按优先级降序、创建时间降序排列。
    """
    query = db.query(TagMappingRule).filter(TagMappingRule.ledger_id == ledger_id)
    if source_type:
        query = query.filter(TagMappingRule.source_type == source_type)
    if is_active is not None:
        query = query.filter(TagMappingRule.is_active == is_active)
    return query.order_by(
        desc(TagMappingRule.priority), desc(TagMappingRule.created_at)
    ).all()


def update_mapping_rule(
    db: Session,
    rule_id: int,
    target_value: str | None = None,
    target_value_id: int | None = None,
    priority: int | None = None,
    is_active: bool | None = None,
    description: str | None = None,
) -> TagMappingRule:
    """
    更新映射规则。

    注意：
        不允许修改 source_pattern、source_type、target_category_code，
        因为这三项决定规则唯一性；如需调整，建议删除后重建。
    """
    rule = get_mapping_rule_by_id(db, rule_id)
    if rule is None:
        raise ValueError(f"映射规则不存在：{rule_id}")

    if target_value is not None:
        rule.target_value = target_value
    if target_value_id is not None:
        rule.target_value_id = target_value_id
    if priority is not None:
        rule.priority = priority
    if is_active is not None:
        rule.is_active = is_active
    if description is not None:
        rule.description = description

    rule.updated_at = datetime.now(timezone.utc)
    db.flush()
    return rule


def delete_mapping_rule(db: Session, rule_id: int) -> None:
    """
    删除映射规则。
    """
    rule = get_mapping_rule_by_id(db, rule_id)
    if rule is None:
        raise ValueError(f"映射规则不存在：{rule_id}")
    db.delete(rule)
    db.flush()


def _match_single_value(pattern: str, value: str, is_regex: bool) -> bool:
    """
    判断单个值是否命中规则模式。
    """
    if is_regex:
        try:
            return bool(re.search(pattern, value))
        except re.error:
            return False
    return pattern == value


def apply_mapping_rules(
    db: Session,
    ledger_id: int,
    source_type: str,
    source_values: list[str],
    fallback_category_code: str | None = None,
) -> list[dict[str, Any]]:
    """
    对一组外部值应用映射规则，返回内部 Dimension 表达列表。

    Args:
        db: 数据库会话
        ledger_id: 账簿 ID
        source_type: 外部值类型（account_code/summary/tag）
        source_values: 外部值列表
        fallback_category_code: 未命中规则时的默认分类编码

    Returns:
        每个 source_value 对应的匹配结果字典列表，包含：
            - source_value: 原始值
            - matched: 是否命中
            - category_code: 内部分类编码
            - target_value: 内部标签值
            - target_value_id: 内部标签值 ID
            - rule_id: 命中的规则 ID
            - fallback: 是否使用默认分类
    """
    rules = list_mapping_rules(db, ledger_id, source_type=source_type, is_active=True)
    results: list[dict[str, Any]] = []

    for source_value in source_values:
        matched_result: dict[str, Any] = {
            "source_value": source_value,
            "matched": False,
            "category_code": None,
            "target_value": None,
            "target_value_id": None,
            "rule_id": None,
            "fallback": False,
        }

        for rule in rules:
            if _match_single_value(rule.source_pattern, source_value, rule.is_regex):
                matched_result.update({
                    "matched": True,
                    "category_code": rule.target_category_code,
                    "target_value": rule.target_value,
                    "target_value_id": rule.target_value_id,
                    "rule_id": rule.id,
                })
                break

        if not matched_result["matched"] and fallback_category_code:
            category = get_category_by_code(db, ledger_id, fallback_category_code)
            if category:
                matched_result.update({
                    "matched": True,
                    "category_code": category.code,
                    "target_value": source_value,
                    "fallback": True,
                })

        results.append(matched_result)

    return results
