# -*- coding: utf-8 -*-
"""
文档标签服务（DocumentTag Service）。

业务场景：
    为原始文档（发票、合同、银行流水、收据等）绑定语义标签，
    支持标签分类、向量索引、置信度管理，用于文件证据分类和AI检索。

政策依据：
    DocumentTag 仅用于原始资料语义分析与检索，不替代正式会计规则。
    标签不参与借贷平衡校验，正式记账由确定性规则控制。

输入数据：
    - document_id / document_type: 文档标识与类型
    - tag / tag_type: 标签值与分类（business/risk/relation/time/amount/status）
    - confidence / source: 置信度与来源

输出结果：
    - DocumentTag 的增删改查
    - 按文档/类型/标签类型的查询与聚合
    - 向量同步标记
    - 标签变更历史记录
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.db.models import DocumentTag, DocumentTagHistory


def get_document_tag_by_id(db: Session, document_tag_id: int) -> DocumentTag | None:
    """
    根据 ID 查询文档标签。
    """
    return db.query(DocumentTag).filter(DocumentTag.id == document_tag_id).first()


def list_document_tags(
    db: Session,
    document_id: int | None = None,
    document_type: str | None = None,
    tag_type: str | None = None,
    source: str | None = None,
    vector_stored: bool | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> list[DocumentTag]:
    """
    查询文档标签列表，支持按文档ID、文档类型、标签类型、来源、向量状态、创建时间过滤。
    """
    query = db.query(DocumentTag)
    if document_id is not None:
        query = query.filter(DocumentTag.document_id == document_id)
    if document_type is not None:
        query = query.filter(DocumentTag.document_type == document_type)
    if tag_type is not None:
        query = query.filter(DocumentTag.tag_type == tag_type)
    if source is not None:
        query = query.filter(DocumentTag.source == source)
    if vector_stored is not None:
        query = query.filter(DocumentTag.vector_stored == vector_stored)
    if created_from is not None:
        query = query.filter(DocumentTag.created_at >= created_from)
    if created_to is not None:
        query = query.filter(DocumentTag.created_at <= created_to)
    return query.order_by(desc(DocumentTag.confidence), desc(DocumentTag.created_at)).all()


def create_document_tag(
    db: Session,
    document_id: int,
    document_type: str,
    tag: str,
    tag_type: str,
    confidence: float = 0.8,
    source: str = "rule",
) -> DocumentTag:
    """
    为文档创建标签。

    业务逻辑：
        1. 校验标签类型合法。
        2. 同一文档同一标签类型下，相同 tag 去重。
        3. 写入标签。
    """
    valid_tag_types = {"business", "risk", "relation", "time", "amount", "status"}
    if tag_type not in valid_tag_types:
        raise ValueError(f"无效的标签类型：{tag_type}，有效值：{valid_tag_types}")

    existing = (
        db.query(DocumentTag)
        .filter(
            DocumentTag.document_id == document_id,
            DocumentTag.document_type == document_type,
            DocumentTag.tag == tag,
            DocumentTag.tag_type == tag_type,
        )
        .first()
    )
    if existing:
        return existing

    document_tag = DocumentTag(
        document_id=document_id,
        document_type=document_type,
        tag=tag,
        tag_type=tag_type,
        confidence=confidence,
        source=source,
        vector_stored=False,
        created_at=datetime.now(timezone.utc),
    )
    db.add(document_tag)
    db.flush()
    
    _record_tag_history(
        db=db,
        document_tag=document_tag,
        action="create",
        after_tag=document_tag.tag,
        after_tag_type=document_tag.tag_type,
        after_confidence=document_tag.confidence,
        after_source=document_tag.source,
    )
    
    return document_tag


def create_document_tags_batch(
    db: Session,
    document_id: int,
    document_type: str,
    tags: list[dict[str, Any]],
) -> list[DocumentTag]:
    """
    批量为文档创建标签。

    Args:
        db: 数据库会话
        document_id: 文档ID
        document_type: 文档类型
        tags: 标签列表，每个元素包含 tag、tag_type、confidence、source 字段

    Returns:
        list[DocumentTag]: 创建的标签列表
    """
    created_tags = []
    for tag_data in tags:
        try:
            tag = create_document_tag(
                db=db,
                document_id=document_id,
                document_type=document_type,
                tag=tag_data.get("tag", ""),
                tag_type=tag_data.get("tag_type", "business"),
                confidence=tag_data.get("confidence", 0.8),
                source=tag_data.get("source", "rule"),
            )
            created_tags.append(tag)
        except ValueError:
            continue
    return created_tags


def update_document_tag(
    db: Session,
    document_tag_id: int,
    tag: str | None = None,
    tag_type: str | None = None,
    confidence: float | None = None,
    source: str | None = None,
    operator: str | None = None,
    reason: str | None = None,
) -> DocumentTag | None:
    """
    更新文档标签。
    """
    document_tag = get_document_tag_by_id(db, document_tag_id)
    if document_tag is None:
        return None

    before_tag = document_tag.tag
    before_tag_type = document_tag.tag_type
    before_confidence = document_tag.confidence
    before_source = document_tag.source

    has_change = False
    if tag is not None and tag != document_tag.tag:
        document_tag.tag = tag
        has_change = True
    if tag_type is not None:
        valid_tag_types = {"business", "risk", "relation", "time", "amount", "status"}
        if tag_type not in valid_tag_types:
            raise ValueError(f"无效的标签类型：{tag_type}")
        if tag_type != document_tag.tag_type:
            document_tag.tag_type = tag_type
            has_change = True
    if confidence is not None and confidence != document_tag.confidence:
        document_tag.confidence = confidence
        has_change = True
    if source is not None and source != document_tag.source:
        document_tag.source = source
        has_change = True
    if tag is not None or tag_type is not None:
        document_tag.vector_stored = False

    if has_change:
        _record_tag_history(
            db=db,
            document_tag=document_tag,
            action="update",
            before_tag=before_tag,
            before_tag_type=before_tag_type,
            before_confidence=before_confidence,
            before_source=before_source,
            after_tag=document_tag.tag,
            after_tag_type=document_tag.tag_type,
            after_confidence=document_tag.confidence,
            after_source=document_tag.source,
            operator=operator,
            reason=reason,
        )

    db.flush()
    return document_tag


def delete_document_tag(db: Session, document_tag_id: int) -> bool:
    """
    删除文档标签。
    """
    document_tag = get_document_tag_by_id(db, document_tag_id)
    if document_tag is None:
        return False
    
    _record_tag_history(
        db=db,
        document_tag=document_tag,
        action="delete",
        before_tag=document_tag.tag,
        before_tag_type=document_tag.tag_type,
        before_confidence=document_tag.confidence,
        before_source=document_tag.source,
    )
    
    db.delete(document_tag)
    db.flush()
    return True


def delete_document_tags_by_document(db: Session, document_id: int) -> int:
    """
    删除指定文档的所有标签。

    Returns:
        int: 删除的标签数量
    """
    count = db.query(DocumentTag).filter(DocumentTag.document_id == document_id).count()
    db.query(DocumentTag).filter(DocumentTag.document_id == document_id).delete()
    db.flush()
    return count


def get_document_tag_stats(
    db: Session,
    document_type: str | None = None,
) -> dict[str, Any]:
    """
    获取文档标签统计信息。
    """
    query = db.query(
        DocumentTag.tag_type,
        func.count(DocumentTag.id).label("count"),
        func.avg(DocumentTag.confidence).label("avg_confidence"),
    )
    if document_type is not None:
        query = query.filter(DocumentTag.document_type == document_type)
    query = query.group_by(DocumentTag.tag_type).order_by(desc("count"))

    stats = []
    for row in query.all():
        stats.append({
            "tag_type": row.tag_type,
            "count": row.count,
            "avg_confidence": round(row.avg_confidence, 3) if row.avg_confidence else 0.0,
        })

    return {
        "total_tags": db.query(func.count(DocumentTag.id)).scalar(),
        "total_documents": db.query(func.count(func.distinct(DocumentTag.document_id))).scalar(),
        "by_tag_type": stats,
    }


def _record_tag_history(
    db: Session,
    document_tag: DocumentTag,
    action: str,
    before_tag: str | None = None,
    before_tag_type: str | None = None,
    before_confidence: float | None = None,
    before_source: str | None = None,
    after_tag: str | None = None,
    after_tag_type: str | None = None,
    after_confidence: float | None = None,
    after_source: str | None = None,
    operator: str | None = None,
    reason: str | None = None,
) -> None:
    """
    记录标签变更历史。
    """
    history = DocumentTagHistory(
        document_tag_id=document_tag.id,
        document_id=document_tag.document_id,
        document_type=document_tag.document_type,
        action=action,
        before_tag=before_tag,
        before_tag_type=before_tag_type,
        before_confidence=before_confidence,
        before_source=before_source,
        after_tag=after_tag,
        after_tag_type=after_tag_type,
        after_confidence=after_confidence,
        after_source=after_source,
        operator=operator,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(history)


def list_document_tag_history(
    db: Session,
    document_tag_id: int | None = None,
    document_id: int | None = None,
    action: str | None = None,
    limit: int = 50,
) -> list[DocumentTagHistory]:
    """
    查询标签变更历史记录。
    """
    query = db.query(DocumentTagHistory).order_by(desc(DocumentTagHistory.created_at))
    
    if document_tag_id is not None:
        query = query.filter(DocumentTagHistory.document_tag_id == document_tag_id)
    if document_id is not None:
        query = query.filter(DocumentTagHistory.document_id == document_id)
    if action is not None:
        query = query.filter(DocumentTagHistory.action == action)
    
    return query.limit(limit).all()


def batch_update_document_tags(
    db: Session,
    tag_ids: list[int],
    updates: dict[str, Any],
    operator: str | None = None,
    reason: str | None = None,
) -> int:
    """
    批量更新标签。
    
    Args:
        db: 数据库会话
        tag_ids: 要更新的标签ID列表
        updates: 更新内容，包含 tag/tag_type/confidence/source
        operator: 操作人
        reason: 操作原因
    
    Returns:
        int: 更新的标签数量
    """
    updated_count = 0
    
    for tag_id in tag_ids:
        document_tag = get_document_tag_by_id(db, tag_id)
        if document_tag is None:
            continue
        
        before_tag = document_tag.tag
        before_tag_type = document_tag.tag_type
        before_confidence = document_tag.confidence
        before_source = document_tag.source
        
        if "tag" in updates:
            document_tag.tag = updates["tag"]
        if "tag_type" in updates:
            valid_tag_types = {"business", "risk", "relation", "time", "amount", "status"}
            if updates["tag_type"] not in valid_tag_types:
                continue
            document_tag.tag_type = updates["tag_type"]
        if "confidence" in updates:
            document_tag.confidence = updates["confidence"]
        if "source" in updates:
            document_tag.source = updates["source"]
        
        if "tag" in updates or "tag_type" in updates:
            document_tag.vector_stored = False
        
        _record_tag_history(
            db=db,
            document_tag=document_tag,
            action="update",
            before_tag=before_tag,
            before_tag_type=before_tag_type,
            before_confidence=before_confidence,
            before_source=before_source,
            after_tag=document_tag.tag,
            after_tag_type=document_tag.tag_type,
            after_confidence=document_tag.confidence,
            after_source=document_tag.source,
            operator=operator,
            reason=reason,
        )
        
        updated_count += 1
    
    db.flush()
    return updated_count


def batch_delete_document_tags(
    db: Session,
    tag_ids: list[int],
    operator: str | None = None,
    reason: str | None = None,
) -> int:
    """
    批量删除标签。
    
    Args:
        db: 数据库会话
        tag_ids: 要删除的标签ID列表
        operator: 操作人
        reason: 操作原因
    
    Returns:
        int: 删除的标签数量
    """
    deleted_count = 0
    
    for tag_id in tag_ids:
        document_tag = get_document_tag_by_id(db, tag_id)
        if document_tag is None:
            continue
        
        _record_tag_history(
            db=db,
            document_tag=document_tag,
            action="delete",
            before_tag=document_tag.tag,
            before_tag_type=document_tag.tag_type,
            before_confidence=document_tag.confidence,
            before_source=document_tag.source,
            operator=operator,
            reason=reason,
        )
        
        db.delete(document_tag)
        deleted_count += 1
    
    db.flush()
    return deleted_count


def batch_assign_tags_to_documents(
    db: Session,
    document_ids: list[int],
    document_type: str,
    tags: list[dict[str, Any]],
) -> int:
    """
    批量为多个文档分配标签。
    
    Args:
        db: 数据库会话
        document_ids: 文档ID列表
        document_type: 文档类型
        tags: 标签列表
    
    Returns:
        int: 创建的标签总数
    """
    total_created = 0
    
    for document_id in document_ids:
        created = create_document_tags_batch(db, document_id, document_type, tags)
        total_created += len(created)
    
    db.flush()
    return total_created
