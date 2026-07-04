# -*- coding: utf-8 -*-
"""
LLM辅助标签识别API路由。

模块功能：
    提供LLM批量识别分录辅助核算维度的API接口，包括：
    - 触发批量LLM解析任务
    - 查询待审批的标签建议
    - 审批通过/拒绝标签建议

创建日期：2026-07-04
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/llm-resolution", tags=["llm-resolution"])


class BatchResolveRequest(BaseModel):
    entry_ids: list[int] | None = None
    ledger_id: int | None = None
    batch_size: int = 50
    dry_run: bool = False


class ApproveRequest(BaseModel):
    suggestion_ids: list[int]


@router.post("/batch-resolve")
def batch_resolve(
    request: BatchResolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    批量调用LLM识别分录的辅助核算维度

    Args:
        request: 批量解析请求参数

    Returns:
        处理结果，包含统计信息和建议标签列表
    """
    from app.services.doc_parsing.llm_tag_resolution_service import LlmTagResolutionService

    service = LlmTagResolutionService(db)
    result = service.batch_resolve(
        entry_ids=request.entry_ids,
        ledger_id=request.ledger_id,
        batch_size=request.batch_size,
        dry_run=request.dry_run,
    )

    return {
        "success": True,
        "task_id": result.task_id,
        "total_entries": result.total_entries,
        "success_count": result.success_count,
        "failed_count": result.failed_count,
        "processing_time_ms": result.processing_time_ms,
        "error_messages": result.error_messages,
        "suggested_tags": [
            {
                "entry_id": s.entry_id,
                "category_code": s.category_code,
                "tag_value": s.tag_value,
                "display_name": s.display_name,
                "confidence": s.confidence,
                "validation_passed": s.validation_passed,
                "validation_reason": s.validation_reason,
            }
            for s in result.suggested_tags
        ],
    }


@router.get("/pending-suggestions")
def get_pending_suggestions(
    ledger_id: Optional[int] = Query(None, description="账簿ID"),
    limit: int = Query(100, description="每页数量"),
    offset: int = Query(0, description="偏移量"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    获取待审批的LLM标签建议列表

    Args:
        ledger_id: 账簿ID（可选）
        limit: 返回数量限制
        offset: 偏移量

    Returns:
        待审批标签列表和总数
    """
    from app.services.doc_parsing.llm_tag_resolution_service import LlmTagResolutionService

    service = LlmTagResolutionService(db)
    items, total = service.get_pending_suggestions(ledger_id, limit, offset)

    return {
        "success": True,
        "items": [
            {
                "id": tag.id,
                "entry_id": tag.entry_id,
                "category_id": tag.category_id,
                "category_code": tag.category.category_code if tag.category else "",
                "category_name": tag.category.category_name if tag.category else "",
                "tag_value": tag.tag_value,
                "display_name": tag.display_name,
                "confidence": tag.confidence,
                "tag_source": tag.tag_source,
                "created_at": tag.created_at.isoformat() if tag.created_at else None,
            }
            for tag in items
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("/approve")
def approve_suggestions(
    request: ApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    审批通过标签建议

    Args:
        request: 审批请求，包含建议ID列表

    Returns:
        成功审批的数量
    """
    from app.services.doc_parsing.llm_tag_resolution_service import LlmTagResolutionService

    service = LlmTagResolutionService(db)
    count = service.approve_suggestions(request.suggestion_ids, current_user.id)

    return {
        "success": True,
        "message": f"成功审批 {count} 个标签建议",
        "approved_count": count,
    }


@router.post("/reject")
def reject_suggestions(
    request: ApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    拒绝标签建议

    Args:
        request: 拒绝请求，包含建议ID列表

    Returns:
        成功拒绝的数量
    """
    from app.services.doc_parsing.llm_tag_resolution_service import LlmTagResolutionService

    service = LlmTagResolutionService(db)
    count = service.reject_suggestions(request.suggestion_ids, current_user.id)

    return {
        "success": True,
        "message": f"成功拒绝 {count} 个标签建议",
        "rejected_count": count,
    }


@router.get("/statistics")
def get_resolution_statistics(
    ledger_id: Optional[int] = Query(None, description="账簿ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    获取LLM解析统计信息

    Args:
        ledger_id: 账簿ID（可选）

    Returns:
        统计信息（待处理数量、已处理数量、待审批数量等）
    """
    from app.db.models import AccountingEntry, EntryTag

    # 待LLM解析的分录数量
    pending_llm = db.query(AccountingEntry).filter(
        AccountingEntry.requires_llm_resolution.is_(True)
    )
    if ledger_id:
        pending_llm = pending_llm.filter(AccountingEntry.ledger_id == ledger_id)

    # 待审批的LLM标签建议数量
    pending_review = db.query(EntryTag).filter(
        EntryTag.reviewed_by_user.is_(False),
        EntryTag.tag_source == "llm",
    )
    if ledger_id:
        pending_review = pending_review.filter(EntryTag.ledger_id == ledger_id)

    # 已审批的LLM标签建议数量
    reviewed = db.query(EntryTag).filter(
        EntryTag.reviewed_by_user.is_(True),
        EntryTag.tag_source == "llm",
    )
    if ledger_id:
        reviewed = reviewed.filter(EntryTag.ledger_id == ledger_id)

    return {
        "success": True,
        "pending_llm_resolution": pending_llm.count(),
        "pending_review": pending_review.count(),
        "reviewed": reviewed.count(),
    }
