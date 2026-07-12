# -*- coding: utf-8 -*-
"""
标签维度分类服务（TagCategory Service）。

业务场景：
    为每个 Ledger 维护一套标签维度分类体系，支持多级层级结构，
    用于替代传统二级科目和辅助核算项目，实现更灵活的财务维度分析。

政策依据：
    基于项目"一级科目 + Dimension(Tag)"核心设计思想，
    标签维度不作为正式会计科目参与借贷平衡校验，仅用于辅助核算与语义分析。

输入数据：
    - ledger_id: 账簿 ID
    - code/name/description: 分类编码、名称、描述
    - parent_id: 父分类 ID，支持多级层级
    - value_type: text/entity/enum
    - source_table: 可选主数据来源表名

输出结果：
    - TagCategory 对象的创建、查询、更新、删除
    - 层级树形结构
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import TagCategory


# 简单内存缓存，按 (ledger_id, code) 缓存分类 ID
_category_cache: dict[tuple[int, str], int] = {}


def _normalize_category_code(code: str) -> str:
    """
    标准化分类编码：小写、去空格、下划线连接。
    """
    return code.strip().lower().replace(" ", "_")


def get_category_by_code(
    db: Session,
    ledger_id: int,
    code: str,
    use_cache: bool = True,
) -> TagCategory | None:
    """
    根据 ledger_id 和 code 查询标签分类。

    Args:
        db: 数据库会话
        ledger_id: 账簿 ID
        code: 分类编码
        use_cache: 是否使用缓存

    Returns:
        TagCategory 对象或 None
    """
    normalized = _normalize_category_code(code)
    cache_key = (ledger_id, normalized)

    if use_cache and cache_key in _category_cache:
        category_id = _category_cache[cache_key]
        category = db.get(TagCategory, category_id)
        if category is not None:
            return category

    category = (
        db.query(TagCategory)
        .filter(
            TagCategory.ledger_id == ledger_id,
            TagCategory.code == normalized,
        )
        .first()
    )
    if category and use_cache:
        _category_cache[cache_key] = category.id
    return category


def get_category_by_id(db: Session, category_id: int) -> TagCategory | None:
    """
    根据 ID 查询标签分类。
    """
    return db.query(TagCategory).filter(TagCategory.id == category_id).first()


def list_categories(
    db: Session,
    ledger_id: int,
    parent_id: int | None = None,
    status: str | None = "active",
) -> list[TagCategory]:
    """
    查询指定账簿下的标签分类列表。

    Args:
        db: 数据库会话
        ledger_id: 账簿 ID
        parent_id: 父分类 ID，None 表示查询顶层分类
        status: 状态过滤，None 表示不过滤

    Returns:
        分类列表，按 sort_order 升序、created_at 降序排列
    """
    query = db.query(TagCategory).filter(TagCategory.ledger_id == ledger_id)
    if parent_id is not None:
        query = query.filter(TagCategory.parent_id == parent_id)
    else:
        query = query.filter(TagCategory.parent_id.is_(None))
    if status:
        query = query.filter(TagCategory.status == status)
    return query.order_by(TagCategory.sort_order.asc(), desc(TagCategory.created_at)).all()


def build_category_tree(
    db: Session,
    ledger_id: int,
    status: str | None = "active",
) -> list[dict[str, Any]]:
    """
    构建标签分类树。

    Args:
        db: 数据库会话
        ledger_id: 账簿 ID
        status: 状态过滤

    Returns:
        树形结构列表，每个节点包含 children
    """
    categories = list_categories(db, ledger_id, parent_id=None, status=status)

    def _build_children(parent_id: int) -> list[dict[str, Any]]:
        children = list_categories(db, ledger_id, parent_id=parent_id, status=status)
        return [_to_node(c) for c in children]

    def _to_node(category: TagCategory) -> dict[str, Any]:
        return {
            "id": category.id,
            "code": category.code,
            "name": category.name,
            "description": category.description,
            "level": category.level,
            "value_type": category.value_type,
            "source_table": category.source_table,
            "is_mandatory": category.is_mandatory,
            "is_system": category.is_system,
            "status": category.status,
            "sort_order": category.sort_order,
            "children": _build_children(category.id),
        }

    return [_to_node(c) for c in categories]


def create_category(
    db: Session,
    ledger_id: int,
    code: str,
    name: str,
    description: str | None = None,
    parent_id: int | None = None,
    value_type: str = "text",
    source_table: str | None = None,
    is_mandatory: bool = False,
    is_system: bool = False,
    sort_order: int = 0,
    status: str = "active",
) -> TagCategory:
    """
    创建标签分类。

    业务逻辑：
        1. 标准化编码并检查同级唯一性。
        2. 若指定 parent_id，自动计算 level = parent.level + 1。
        3. 写入后刷新缓存。

    Args:
        db: 数据库会话
        ledger_id: 账簿 ID
        code: 分类编码，同一 ledger 下唯一
        name: 分类名称
        description: 描述
        parent_id: 父分类 ID
        value_type: text/entity/enum
        source_table: 主数据来源表名
        is_mandatory: 是否必填
        is_system: 是否系统内置
        sort_order: 排序号
        status: 状态

    Returns:
        新创建的 TagCategory

    Raises:
        ValueError: 编码重复或父分类不存在
    """
    normalized_code = _normalize_category_code(code)
    existing = get_category_by_code(db, ledger_id, normalized_code, use_cache=False)
    if existing:
        raise ValueError(f"标签分类编码已存在：{normalized_code}")

    level = 1
    if parent_id is not None:
        parent = get_category_by_id(db, parent_id)
        if parent is None:
            raise ValueError(f"父分类不存在：{parent_id}")
        if parent.ledger_id != ledger_id:
            raise ValueError("父分类不属于当前账簿")
        level = parent.level + 1

    category = TagCategory(
        ledger_id=ledger_id,
        parent_id=parent_id,
        code=normalized_code,
        name=name.strip(),
        description=description,
        level=level,
        value_type=value_type,
        source_table=source_table,
        is_mandatory=is_mandatory,
        is_system=is_system,
        sort_order=sort_order,
        status=status,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(category)
    db.flush()

    cache_key = (ledger_id, normalized_code)
    _category_cache[cache_key] = category.id
    return category


def update_category(
    db: Session,
    category_id: int,
    name: str | None = None,
    description: str | None = None,
    value_type: str | None = None,
    source_table: str | None = None,
    is_mandatory: bool | None = None,
    sort_order: int | None = None,
    status: str | None = None,
) -> TagCategory:
    """
    更新标签分类。

    注意：
        不允许修改 code，因为 code 是映射规则、entry_tags 引用的关键标识。
        不允许修改 parent_id，避免层级关系混乱；如需调整，建议删除后重建。
    """
    category = get_category_by_id(db, category_id)
    if category is None:
        raise ValueError(f"标签分类不存在：{category_id}")

    if name is not None:
        category.name = name.strip()
    if description is not None:
        category.description = description
    if value_type is not None:
        category.value_type = value_type
    if source_table is not None:
        category.source_table = source_table
    if is_mandatory is not None:
        category.is_mandatory = is_mandatory
    if sort_order is not None:
        category.sort_order = sort_order
    if status is not None:
        category.status = status

    category.updated_at = datetime.now(timezone.utc)
    db.flush()

    cache_key = (category.ledger_id, category.code)
    _category_cache[cache_key] = category.id
    return category


def delete_category(db: Session, category_id: int) -> None:
    """
    删除标签分类。

    业务逻辑：
        1. 检查是否存在子分类，存在则不允许删除。
        2. 删除后清除缓存。

    Raises:
        ValueError: 分类不存在或存在子分类
    """
    category = get_category_by_id(db, category_id)
    if category is None:
        raise ValueError(f"标签分类不存在：{category_id}")

    if category.is_system:
        raise ValueError("系统内置分类不可删除，请改为禁用或归档")

    children_count = (
        db.query(TagCategory)
        .filter(TagCategory.parent_id == category_id)
        .count()
    )
    if children_count > 0:
        raise ValueError(f"分类下存在 {children_count} 个子分类，无法删除")

    db.delete(category)
    db.flush()

    cache_key = (category.ledger_id, category.code)
    _category_cache.pop(cache_key, None)


def clear_category_cache() -> None:
    """
    清除分类缓存。
    """
    _category_cache.clear()


def remove_category_from_cache(ledger_id: int, code: str) -> None:
    """
    移除指定分类缓存。
    """
    _category_cache.pop((ledger_id, _normalize_category_code(code)), None)


def get_or_create_category(
    db: Session,
    ledger_id: int,
    code: str,
    name: str | None = None,
    **kwargs: Any,
) -> TagCategory:
    """
    获取或创建分类，常用于初始化默认维度。
    """
    category = get_category_by_code(db, ledger_id, code)
    if category:
        return category
    return create_category(
        db,
        ledger_id=ledger_id,
        code=code,
        name=name or code,
        **kwargs,
    )
