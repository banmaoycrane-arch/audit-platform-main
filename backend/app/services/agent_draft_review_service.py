# -*- coding: utf-8 -*-
"""
模块功能：Agent 草稿人工复核记录服务
业务场景：草稿生成后记录人工复核意见、复核状态、退回重做和是否允许进入正式交付设计阶段
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import AgentApproval, AgentDraftReview
from app.models.user import User

VALID_REVIEW_STATUSES = {"approved", "returned"}


def create_pending_draft_review(
    db: Session,
    approval_id: int,
    current_user: User,
    ledger_id: int | None,
) -> AgentDraftReview:
    approval = db.get(AgentApproval, approval_id)
    if approval is None:
        raise LookupError("Agent 确认记录不存在")
    if approval.status != "confirmed":
        raise ValueError("只有已确认并生成草稿后的记录可以创建复核记录")

    existing = (
        db.query(AgentDraftReview)
        .filter(AgentDraftReview.approval_id == approval_id)
        .order_by(AgentDraftReview.id.desc())
        .first()
    )
    if existing is not None:
        return existing

    review = AgentDraftReview(
        approval_id=approval.id,
        tool_name=approval.tool_name,
        agent_role=approval.agent_role,
        draft_output_type="draft",
        review_status="pending",
        team_id=current_user.team_id,
        ledger_id=ledger_id,
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def submit_draft_review(
    db: Session,
    review_id: int,
    current_user: User,
    review_status: str,
    review_comment: str,
    returned_for_rework: bool,
    allow_formal_delivery_design: bool,
) -> AgentDraftReview:
    review = db.get(AgentDraftReview, review_id)
    if review is None:
        raise LookupError("草稿复核记录不存在")
    if review.review_status != "pending":
        raise ValueError("只有待复核记录可以提交复核意见")
    if review_status not in VALID_REVIEW_STATUSES:
        raise ValueError("复核状态必须为 approved 或 returned")
    if not review_comment.strip():
        raise ValueError("复核意见不能为空")
    if review_status == "returned" and allow_formal_delivery_design:
        raise ValueError("退回重做时不能允许进入正式交付设计阶段")
    if review_status == "approved" and returned_for_rework:
        raise ValueError("复核通过时不能标记退回重做")

    review.review_status = review_status
    review.review_comment = review_comment.strip()
    review.reviewed_by_user_id = current_user.id
    review.returned_for_rework = returned_for_rework
    review.allow_formal_delivery_design = allow_formal_delivery_design if review_status == "approved" else False
    review.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(review)
    return review


def serialize_draft_review(review: AgentDraftReview) -> dict:
    return {
        "id": review.id,
        "approval_id": review.approval_id,
        "tool_name": review.tool_name,
        "agent_role": review.agent_role,
        "draft_output_type": review.draft_output_type,
        "review_status": review.review_status,
        "review_comment": review.review_comment,
        "reviewed_by_user_id": review.reviewed_by_user_id,
        "team_id": review.team_id,
        "ledger_id": review.ledger_id,
        "returned_for_rework": review.returned_for_rework,
        "allow_formal_delivery_design": review.allow_formal_delivery_design,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
    }
