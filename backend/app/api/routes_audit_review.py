"""审计复核请求 API 路由。

模块功能：提供审计复核请求的创建、提交、复核、合并归档等接口
业务场景：审计工作底稿的多级复核流程，确保审计质量控制
政策依据：中国注册会计师审计准则第1121号（对财务报表审计实施的质量控制）
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit_workflow import (
    AuditReviewActionCreate,
    AuditReviewActionRead,
    AuditReviewRequestCreate,
    AuditReviewRequestRead,
    AuditReviewSubmit,
)
import app.services.audit.audit_review_service as audit_review_service

router = APIRouter(prefix="/api/audit/review-requests", tags=["audit-review"])


class AuditReviewListResponse(BaseModel):
    """复核请求列表分页响应"""
    items: list[AuditReviewRequestRead]
    total: int
    page: int
    page_size: int


@router.get("", response_model=AuditReviewListResponse)
def list_review_requests(
    project_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    created_by: int | None = Query(default=None),
    reviewer_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditReviewListResponse:
    try:
        result = audit_review_service.get_review_list(
            db,
            project_id=project_id,
            status=status,
            created_by=created_by,
            reviewer_id=reviewer_id,
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuditReviewListResponse(
        items=[AuditReviewRequestRead.model_validate(item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/pending/mine", response_model=list[AuditReviewRequestRead])
def get_pending_my_review(
    project_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditReviewRequestRead]:
    items = audit_review_service.get_pending_my_review(
        db,
        user_id=current_user.id,
        project_id=project_id,
    )
    return [AuditReviewRequestRead.model_validate(item) for item in items]


@router.get("/submitted/mine", response_model=list[AuditReviewRequestRead])
def get_my_submitted(
    project_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditReviewRequestRead]:
    items = audit_review_service.get_my_submitted(
        db,
        user_id=current_user.id,
        project_id=project_id,
    )
    return [AuditReviewRequestRead.model_validate(item) for item in items]


@router.get("/{review_id}", response_model=AuditReviewRequestRead)
def get_review_request(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditReviewRequestRead:
    review = audit_review_service.get_review_by_id(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="复核请求不存在")
    return AuditReviewRequestRead.model_validate(review)


@router.post("", response_model=AuditReviewRequestRead, status_code=status.HTTP_201_CREATED)
def create_review_request(
    payload: AuditReviewRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditReviewRequestRead:
    try:
        review = audit_review_service.create_review_request(
            db,
            payload.model_dump(),
            creator_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuditReviewRequestRead.model_validate(review)


@router.post("/{review_id}/submit", response_model=AuditReviewRequestRead)
def submit_review(
    review_id: int,
    payload: AuditReviewSubmit | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditReviewRequestRead:
    try:
        review = audit_review_service.submit_review(
            db,
            review_id,
            reviewer_level_1_id=payload.reviewer_level_1_id if payload else None,
        )
    except ValueError as exc:
        if str(exc) == "复核请求不存在":
            raise HTTPException(status_code=404, detail="复核请求不存在") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuditReviewRequestRead.model_validate(review)


@router.post("/{review_id}/review", response_model=AuditReviewRequestRead)
def perform_review(
    review_id: int,
    payload: AuditReviewActionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditReviewRequestRead:
    try:
        review = audit_review_service.perform_review(
            db,
            review_id,
            reviewer_id=current_user.id,
            action=payload.action,
            comment=payload.comment,
            review_level=payload.review_level,
        )
    except ValueError as exc:
        if str(exc) == "复核请求不存在":
            raise HTTPException(status_code=404, detail="复核请求不存在") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuditReviewRequestRead.model_validate(review)


@router.post("/{review_id}/merge", response_model=AuditReviewRequestRead)
def merge_review(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditReviewRequestRead:
    try:
        review = audit_review_service.merge_review(
            db,
            review_id,
            merged_by=current_user.id,
        )
    except ValueError as exc:
        if str(exc) == "复核请求不存在":
            raise HTTPException(status_code=404, detail="复核请求不存在") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuditReviewRequestRead.model_validate(review)


@router.get("/{review_id}/actions", response_model=list[AuditReviewActionRead])
def get_review_actions(
    review_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditReviewActionRead]:
    review = audit_review_service.get_review_by_id(db, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="复核请求不存在")
    actions = audit_review_service.get_review_actions(db, review_id)
    return [AuditReviewActionRead.model_validate(action) for action in actions]
