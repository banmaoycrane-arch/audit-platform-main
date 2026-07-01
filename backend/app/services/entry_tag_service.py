# -*- coding: utf-8 -*-
"""
分录标签服务（EntryTag Service）。

业务场景：
    在会计分录上绑定多维标签，替代传统二级科目和辅助核算项目，
    支持标签权重、历史变更追踪、多标签关联，并支持向量化同步标记。

政策依据：
    标签仅用于辅助核算与语义分析，不参与借贷平衡校验。
    正式会计规则（科目、期间、凭证、报表）由确定性规则控制。

输入数据：
    - entry_id / ledger_id: 分录与账簿边界
    - category_code / category_id: 标签维度分类
    - tag_value / value_id: 标签值或关联主数据 ID
    - weight: 标签权重，默认 1.0
    - tag_source / confidence: 标签来源与置信度

输出结果：
    - EntryTag 的增删改查
    - 标签历史记录
    - 按分录/分类/值的查询与聚合
"""
from datetime import datetime
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.models import EntryTag, TagCategory, TagHistory
from app.services.tag_category_service import get_category_by_code


def get_entry_tag_by_id(db: Session, entry_tag_id: int) -> EntryTag | None:
    """
    根据 ID 查询分录标签。
    """
    return db.query(EntryTag).filter(EntryTag.id == entry_tag_id).first()


def list_entry_tags(
    db: Session,
    entry_id: int | None = None,
    ledger_id: int | None = None,
    category_id: int | None = None,
    category_code: str | None = None,
) -> list[EntryTag]:
    """
    查询分录标签列表，支持按分录、账簿、分类过滤。
    """
    query = db.query(EntryTag)
    if entry_id is not None:
        query = query.filter(EntryTag.entry_id == entry_id)
    if ledger_id is not None:
        query = query.filter(EntryTag.ledger_id == ledger_id)
    if category_id is not None:
        query = query.filter(EntryTag.category_id == category_id)
    if category_code is not None:
        category = get_category_by_code(db, ledger_id or 0, category_code)
        if category:
            query = query.filter(EntryTag.category_id == category.id)
    return query.order_by(desc(EntryTag.weight), desc(EntryTag.created_at)).all()


def create_entry_tag(
    db: Session,
    entry_id: int,
    ledger_id: int,
    category_code: str,
    tag_value: str,
    value_id: int | None = None,
    display_name: str | None = None,
    weight: float = 1.0,
    tag_source: str = "rule",
    confidence: float = 0.8,
    reviewed_by_user: bool = False,
    changed_by: int | None = None,
    change_reason: str | None = None,
) -> EntryTag:
    """
    为分录创建标签。

    业务逻辑：
        1. 校验分类存在。
        2. 同一分录同一分类下，相同 tag_value 去重。
        3. 写入标签并记录历史（change_type=create）。
    """
    category = get_category_by_code(db, ledger_id, category_code)
    if category is None:
        raise ValueError(f"标签分类不存在：{category_code}")

    existing = (
        db.query(EntryTag)
        .filter(
            EntryTag.entry_id == entry_id,
            EntryTag.category_id == category.id,
            EntryTag.tag_value == tag_value,
        )
        .first()
    )
    if existing:
        raise ValueError(
            f"标签已存在：entry_id={entry_id}, category={category_code}, value={tag_value}"
        )

    entry_tag = EntryTag(
        entry_id=entry_id,
        ledger_id=ledger_id,
        category_id=category.id,
        tag_name=f"{category.code}:{tag_value}",
        tag_type=category.code,
        tag_value=tag_value,
        tag_value_normalized=_normalize_tag_value(tag_value),
        value_id=value_id,
        display_name=display_name or tag_value,
        weight=weight,
        tag_source=tag_source,
        confidence=confidence,
        reviewed_by_user=reviewed_by_user,
        vector_pending=True,
        created_at=datetime.utcnow(),
    )
    db.add(entry_tag)
    db.flush()

    _record_tag_history(
        db,
        entry_tag=entry_tag,
        change_type="create",
        old_value=None,
        new_value=tag_value,
        old_weight=None,
        new_weight=weight,
        changed_by=changed_by,
        change_reason=change_reason,
    )
    return entry_tag


def update_entry_tag(
    db: Session,
    entry_tag_id: int,
    tag_value: str | None = None,
    value_id: int | None = None,
    display_name: str | None = None,
    weight: float | None = None,
    confidence: float | None = None,
    reviewed_by_user: bool | None = None,
    changed_by: int | None = None,
    change_reason: str | None = None,
) -> EntryTag:
    """
    更新分录标签。

    业务逻辑：
        1. 记录变更前状态到 TagHistory（change_type=update）。
        2. 更新标签字段。
        3. vector_pending 标记为 True，触发后续向量同步。
    """
    entry_tag = get_entry_tag_by_id(db, entry_tag_id)
    if entry_tag is None:
        raise ValueError(f"分录标签不存在：{entry_tag_id}")

    old_value = entry_tag.tag_value
    old_weight = entry_tag.weight

    if tag_value is not None:
        entry_tag.tag_value = tag_value
        entry_tag.tag_value_normalized = _normalize_tag_value(tag_value)
        entry_tag.tag_name = f"{entry_tag.tag_type or entry_tag.category.code}:{tag_value}"
    if value_id is not None:
        entry_tag.value_id = value_id
    if display_name is not None:
        entry_tag.display_name = display_name
    if weight is not None:
        entry_tag.weight = weight
    if confidence is not None:
        entry_tag.confidence = confidence
    if reviewed_by_user is not None:
        entry_tag.reviewed_by_user = reviewed_by_user

    entry_tag.vector_pending = True
    db.flush()

    _record_tag_history(
        db,
        entry_tag=entry_tag,
        change_type="update",
        old_value=old_value,
        new_value=entry_tag.tag_value,
        old_weight=old_weight,
        new_weight=entry_tag.weight,
        changed_by=changed_by,
        change_reason=change_reason,
    )
    return entry_tag


def delete_entry_tag(
    db: Session,
    entry_tag_id: int,
    changed_by: int | None = None,
    change_reason: str | None = None,
) -> None:
    """
    删除分录标签，并记录历史（change_type=delete）。
    """
    entry_tag = get_entry_tag_by_id(db, entry_tag_id)
    if entry_tag is None:
        raise ValueError(f"分录标签不存在：{entry_tag_id}")

    _record_tag_history(
        db,
        entry_tag=entry_tag,
        change_type="delete",
        old_value=entry_tag.tag_value,
        new_value=None,
        old_weight=entry_tag.weight,
        new_weight=None,
        changed_by=changed_by,
        change_reason=change_reason,
    )

    db.delete(entry_tag)
    db.flush()


def list_tag_history(
    db: Session,
    entry_tag_id: int | None = None,
    entry_id: int | None = None,
    ledger_id: int | None = None,
) -> list[TagHistory]:
    """
    查询标签历史记录。
    """
    query = db.query(TagHistory)
    if entry_tag_id is not None:
        query = query.filter(TagHistory.entry_tag_id == entry_tag_id)
    if entry_id is not None:
        query = query.filter(TagHistory.entry_id == entry_id)
    if ledger_id is not None:
        query = query.filter(TagHistory.ledger_id == ledger_id)
    return query.order_by(desc(TagHistory.created_at)).all()


def aggregate_tags_by_category(
    db: Session,
    ledger_id: int,
    category_code: str,
) -> list[dict[str, Any]]:
    """
    按分类聚合标签值及其出现次数、平均权重。

    输出示例：
        [
            {"tag_value": "山西岚县尚德鑫", "count": 15, "avg_weight": 1.0},
            ...
        ]
    """
    category = get_category_by_code(db, ledger_id, category_code)
    if category is None:
        return []

    rows = (
        db.query(
            EntryTag.tag_value,
            func.count(EntryTag.id).label("count"),
            func.avg(EntryTag.weight).label("avg_weight"),
        )
        .filter(
            EntryTag.ledger_id == ledger_id,
            EntryTag.category_id == category.id,
        )
        .group_by(EntryTag.tag_value)
        .order_by(desc("count"))
        .all()
    )
    return [
        {
            "tag_value": row.tag_value,
            "count": row.count,
            "avg_weight": round(row.avg_weight or 0.0, 4),
        }
        for row in rows
    ]


def _normalize_tag_value(value: str) -> str:
    """
    标准化标签值：去除首尾空格，统一大小写。
    """
    return value.strip().lower()


def _record_tag_history(
    db: Session,
    entry_tag: EntryTag,
    change_type: str,
    old_value: str | None,
    new_value: str | None,
    old_weight: float | None,
    new_weight: float | None,
    changed_by: int | None,
    change_reason: str | None,
) -> None:
    """
    记录标签变更历史。
    """
    history = TagHistory(
        entry_tag_id=entry_tag.id,
        entry_id=entry_tag.entry_id,
        ledger_id=entry_tag.ledger_id or 0,
        category_id=entry_tag.category_id,
        change_type=change_type,
        old_value=old_value,
        new_value=new_value,
        old_weight=old_weight,
        new_weight=new_weight,
        changed_by=changed_by,
        change_reason=change_reason,
        created_at=datetime.utcnow(),
    )
    db.add(history)
