# -*- coding: utf-8 -*-
"""
EntryTag / TagCategory / TagMappingRule API 路由。

提供标签维度分类、分录标签、映射规则、旧标签导入的 RESTful 接口。
"""
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.accounting.entry_tag_service import (
    aggregate_tags_by_category,
    create_entry_tag,
    delete_entry_tag,
    list_entry_tags,
    list_tag_history,
    update_entry_tag,
)
from app.services.accounting.entry_tag_vector_service import EntryTagVectorService
from app.services.doc_parsing.legacy_tag_import_service import (
    LegacyTagRecord,
    import_legacy_tags,
)
from app.services.doc_parsing.tag_category_service import (
    build_category_tree,
    create_category,
    delete_category,
    get_category_by_code,
    get_category_by_id,
    list_categories,
    update_category,
)
from app.services.doc_parsing.tag_mapping_rule_service import (
    apply_mapping_rules,
    create_mapping_rule,
    delete_mapping_rule,
    get_mapping_rule_by_id,
    list_mapping_rules,
    update_mapping_rule,
)

router = APIRouter(prefix="/api/entry-tags", tags=["entry-tags"])


# ============ Pydantic 请求/响应模型 ============

class TagCategoryCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=60)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    parent_id: int | None = None
    value_type: str = "text"
    source_table: str | None = None
    is_mandatory: bool = False
    sort_order: int = 0


class TagCategoryUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    value_type: str | None = None
    source_table: str | None = None
    is_mandatory: bool | None = None
    sort_order: int | None = None
    status: str | None = None


class EntryTagCreate(BaseModel):
    entry_id: int
    ledger_id: int
    category_code: str
    tag_value: str
    value_id: int | None = None
    display_name: str | None = None
    weight: float = 1.0
    tag_source: str = "manual"
    confidence: float = 1.0


class EntryTagUpdate(BaseModel):
    tag_value: str | None = None
    value_id: int | None = None
    display_name: str | None = None
    weight: float | None = None
    confidence: float | None = None
    reviewed_by_user: bool | None = None


class TagMappingRuleCreate(BaseModel):
    source_pattern: str
    target_category_code: str
    target_value: str | None = None
    target_value_id: int | None = None
    source_type: str = "account_code"
    priority: int = 0
    is_regex: bool = False
    description: str | None = None


class TagMappingRuleUpdate(BaseModel):
    target_value: str | None = None
    target_value_id: int | None = None
    priority: int | None = None
    is_active: bool | None = None
    description: str | None = None


class LegacyTagImportRequest(BaseModel):
    ledger_id: int
    records: list[dict[str, Any]]
    default_category_code: str = "legacy"
    auto_create_category: bool = True


class BatchEntryTagQuery(BaseModel):
    entry_ids: list[int] = Field(default_factory=list)
    ledger_id: int | None = None
    category_code: str | None = None


class ApplyMappingRequest(BaseModel):
    source_type: str
    source_values: list[str]
    fallback_category_code: str | None = None


# ============ TagCategory 路由 ============

@router.post("/categories", response_model=dict[str, Any])
def create_tag_category(
    data: TagCategoryCreate,
    ledger_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """创建标签维度分类。"""
    try:
        category = create_category(
            db,
            ledger_id=ledger_id,
            code=data.code,
            name=data.name,
            description=data.description,
            parent_id=data.parent_id,
            value_type=data.value_type,
            source_table=data.source_table,
            is_mandatory=data.is_mandatory,
            sort_order=data.sort_order,
        )
        return {"id": category.id, "code": category.code, "name": category.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/categories", response_model=list[dict[str, Any]])
def get_tag_categories(
    ledger_id: int,
    parent_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """查询标签分类列表或树。"""
    categories: list[dict[str, Any]]
    if parent_id is not None:
        raw_categories = list_categories(db, ledger_id, parent_id=parent_id)
        categories = [{
            "id": c.id, "code": c.code, "name": c.name, "description": c.description or "",
            "parent_id": c.parent_id, "value_type": c.value_type, "source_table": c.source_table or "",
            "is_mandatory": c.is_mandatory, "sort_order": c.sort_order, "status": c.status
        } for c in raw_categories]
    else:
        categories = build_category_tree(db, ledger_id)
    return categories


@router.get("/categories/{category_id}", response_model=dict[str, Any])
def get_tag_category(category_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """根据 ID 查询标签分类。"""
    category = get_category_by_id(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="分类不存在")
    return {
        "id": category.id,
        "code": category.code,
        "name": category.name,
        "description": category.description,
        "level": category.level,
        "value_type": category.value_type,
        "source_table": category.source_table,
        "is_mandatory": category.is_mandatory,
        "status": category.status,
        "sort_order": category.sort_order,
    }


@router.put("/categories/{category_id}", response_model=dict[str, Any])
def update_tag_category(
    category_id: int,
    data: TagCategoryUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """更新标签分类。"""
    try:
        category = update_category(
            db,
            category_id=category_id,
            name=data.name,
            description=data.description,
            value_type=data.value_type,
            source_table=data.source_table,
            is_mandatory=data.is_mandatory,
            sort_order=data.sort_order,
            status=data.status,
        )
        return {"id": category.id, "code": category.code, "name": category.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/categories/{category_id}")
def delete_tag_category(category_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    """删除标签分类。"""
    try:
        delete_category(db, category_id)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============ EntryTag 路由 ============

@router.post("/tags", response_model=dict[str, Any])
def create_entry_tag_api(
    data: EntryTagCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """为分录创建标签。"""
    try:
        tag = create_entry_tag(
            db,
            entry_id=data.entry_id,
            ledger_id=data.ledger_id,
            category_code=data.category_code,
            tag_value=data.tag_value,
            value_id=data.value_id,
            display_name=data.display_name,
            weight=data.weight,
            tag_source=data.tag_source,
            confidence=data.confidence,
        )
        return {"id": tag.id, "entry_id": tag.entry_id, "category_id": tag.category_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tags", response_model=list[dict[str, Any]])
def get_entry_tags(
    entry_id: int | None = None,
    ledger_id: int | None = None,
    category_code: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """查询分录标签。"""
    tags = list_entry_tags(
        db,
        entry_id=entry_id,
        ledger_id=ledger_id,
        category_code=category_code,
    )
    return [
        {
            "id": t.id,
            "entry_id": t.entry_id,
            "ledger_id": t.ledger_id,
            "category_id": t.category_id,
            "tag_name": t.tag_name,
            "tag_value": t.tag_value,
            "display_name": t.display_name,
            "weight": t.weight,
            "confidence": t.confidence,
            "tag_source": t.tag_source,
            "reviewed_by_user": t.reviewed_by_user,
        }
        for t in tags
    ]


@router.post("/tags/batch", response_model=list[dict[str, Any]])
def batch_get_entry_tags(
    data: BatchEntryTagQuery,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    批量查询分录标签。

    业务场景：
        前端导入结果页需要一次性展示大量分录的辅助核算标签，
        避免逐条分录发起的 N+1 查询。

    输入数据：
        entry_ids: 分录 ID 列表
        ledger_id: 可选账簿边界
        category_code: 可选分类过滤

    输出结果：
        命中分录的标签列表（与 /tags 单条查询返回字段一致）
    """
    tags = list_entry_tags(
        db,
        entry_ids=data.entry_ids,
        ledger_id=data.ledger_id,
        category_code=data.category_code,
    )
    return [
        {
            "id": t.id,
            "entry_id": t.entry_id,
            "ledger_id": t.ledger_id,
            "category_id": t.category_id,
            "category_code": t.category.category_code if t.category else None,
            "category_name": t.category.category_name if t.category else None,
            "tag_name": t.tag_name,
            "tag_value": t.tag_value,
            "display_name": t.display_name,
            "weight": t.weight,
            "confidence": t.confidence,
            "tag_source": t.tag_source,
            "reviewed_by_user": t.reviewed_by_user,
        }
        for t in tags
    ]


@router.put("/tags/{entry_tag_id}", response_model=dict[str, Any])
def update_entry_tag_api(
    entry_tag_id: int,
    data: EntryTagUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """更新分录标签。"""
    try:
        tag = update_entry_tag(
            db,
            entry_tag_id=entry_tag_id,
            tag_value=data.tag_value,
            value_id=data.value_id,
            display_name=data.display_name,
            weight=data.weight,
            confidence=data.confidence,
            reviewed_by_user=data.reviewed_by_user,
        )
        return {"id": tag.id, "tag_value": tag.tag_value, "weight": tag.weight}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/tags/{entry_tag_id}")
def delete_entry_tag_api(
    entry_tag_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """删除分录标签。"""
    try:
        delete_entry_tag(db, entry_tag_id)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tags/{entry_tag_id}/history", response_model=list[dict[str, Any]])
def get_entry_tag_history(
    entry_tag_id: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """查询标签历史记录。"""
    history = list_tag_history(db, entry_tag_id=entry_tag_id)
    return [
        {
            "id": h.id,
            "change_type": h.change_type,
            "old_value": h.old_value,
            "new_value": h.new_value,
            "old_weight": h.old_weight,
            "new_weight": h.new_weight,
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }
        for h in history
    ]


@router.get("/aggregate/{category_code}", response_model=list[dict[str, Any]])
def aggregate_tags(
    ledger_id: int,
    category_code: str,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """按分类聚合标签值。"""
    return aggregate_tags_by_category(db, ledger_id, category_code)


# ============ TagMappingRule 路由 ============

@router.post("/mapping-rules", response_model=dict[str, Any])
def create_mapping_rule_api(
    ledger_id: int,
    data: TagMappingRuleCreate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """创建标签映射规则。"""
    try:
        rule = create_mapping_rule(
            db,
            ledger_id=ledger_id,
            source_pattern=data.source_pattern,
            source_type=data.source_type,
            target_category_code=data.target_category_code,
            target_value=data.target_value,
            target_value_id=data.target_value_id,
            priority=data.priority,
            is_regex=data.is_regex,
            description=data.description,
        )
        return {"id": rule.id, "source_pattern": rule.source_pattern}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/mapping-rules", response_model=list[dict[str, Any]])
def get_mapping_rules(
    ledger_id: int,
    source_type: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """查询映射规则列表。"""
    rules = list_mapping_rules(db, ledger_id, source_type=source_type)
    return [
        {
            "id": r.id,
            "source_pattern": r.source_pattern,
            "source_type": r.source_type,
            "target_category_code": r.target_category_code,
            "target_value": r.target_value,
            "priority": r.priority,
            "is_regex": r.is_regex,
            "is_active": r.is_active,
        }
        for r in rules
    ]


@router.put("/mapping-rules/{rule_id}", response_model=dict[str, Any])
def update_mapping_rule_api(
    rule_id: int,
    data: TagMappingRuleUpdate,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """更新映射规则。"""
    try:
        rule = update_mapping_rule(
            db,
            rule_id=rule_id,
            target_value=data.target_value,
            target_value_id=data.target_value_id,
            priority=data.priority,
            is_active=data.is_active,
            description=data.description,
        )
        return {"id": rule.id, "source_pattern": rule.source_pattern}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/mapping-rules/{rule_id}")
def delete_mapping_rule_api(
    rule_id: int,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """删除映射规则。"""
    try:
        delete_mapping_rule(db, rule_id)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mapping-rules/apply", response_model=list[dict[str, Any]])
def apply_mapping_rules_api(
    ledger_id: int,
    data: ApplyMappingRequest,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """应用映射规则到一组外部值。"""
    return apply_mapping_rules(
        db,
        ledger_id=ledger_id,
        source_type=data.source_type,
        source_values=data.source_values,
        fallback_category_code=data.fallback_category_code,
    )


# ============ 旧标签导入兼容层 ============

@router.post("/import/legacy", response_model=dict[str, Any])
def import_legacy_tags_api(
    data: LegacyTagImportRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """导入旧标签数据并转换为新 Dimension 体系。"""
    records = [
        LegacyTagRecord(
            entry_id=r.get("entry_id", 0),
            raw_tag=r.get("raw_tag", ""),
            raw_value=r.get("raw_value"),
            weight=r.get("weight", 1.0),
            tag_source=r.get("tag_source", "import"),
            confidence=r.get("confidence", 0.8),
        )
        for r in data.records
    ]

    report = import_legacy_tags(
        db,
        ledger_id=data.ledger_id,
        records=records,
        auto_create_category=data.auto_create_category,
        default_category_code=data.default_category_code,
    )
    return report.to_dict()


# ============ 向量同步与自然语言检索 ============

@router.post("/sync-vector")
def sync_entry_tags_vector(limit: int = 100, db: Session = Depends(get_db)) -> dict[str, Any]:
    """同步待处理标签到向量库。"""
    return EntryTagVectorService(db).sync_pending(limit)


@router.get("/vector-search", response_model=dict[str, Any])
def search_entry_tags_vector(
    q: str,
    limit: int = 10,
    category_code: str | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """通过自然语言查询标签及关联凭证。"""
    return EntryTagVectorService(db).search(q, limit=limit, category_code=category_code)
