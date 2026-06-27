"""审计复核服务

模块功能：管理审计复核请求的创建、提交、复核、合并归档等全流程
业务场景：审计工作底稿的多级复核流程，确保审计质量控制
政策依据：中国注册会计师审计准则第1121号（对财务报表审计实施的质量控制）
输入数据：复核请求数据、复核动作数据
输出结果：复核请求状态、复核记录列表
创建日期：2026-06-26
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AuditReviewAction, AuditReviewRequest, AuditTask, AuditWorkBranch, WorkpaperVersion
from app.services import audit_notification_service

VALID_STATUSES = {"draft", "review", "changes_requested", "approved", "merged", "closed"}

STATUS_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["review", "closed"],
    "review": ["approved", "changes_requested", "closed"],
    "changes_requested": ["review", "closed"],
    "approved": ["merged", "closed"],
    "merged": [],
    "closed": [],
}

VALID_ACTIONS = {"approve", "request_changes"}


def _validate_status_transition(current: str, target: str) -> None:
    """校验状态流转是否合法。

    Args:
        current: 当前状态
        target: 目标状态

    Raises:
        ValueError: 状态流转不合法
    """
    allowed = STATUS_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ValueError(f"非法状态跳转: {current} -> {target}")


def _serialize_review(review: AuditReviewRequest) -> dict[str, Any]:
    """序列化复核请求对象。

    Args:
        review: 复核请求ORM对象

    Returns:
        序列化后的字典
    """
    return {
        "id": review.id,
        "project_id": review.project_id,
        "ledger_id": review.ledger_id,
        "task_id": review.task_id,
        "branch_id": review.branch_id,
        "pr_no": review.pr_no,
        "title": review.title,
        "description": review.description,
        "target_branch": review.target_branch,
        "status": review.status,
        "current_review_level": review.current_review_level,
        "created_by": review.created_by,
        "reviewer_level_1_id": review.reviewer_level_1_id,
        "reviewer_level_2_id": review.reviewer_level_2_id,
        "reviewer_level_3_id": review.reviewer_level_3_id,
        "submitted_version_id": review.submitted_version_id,
        "approved_version_id": review.approved_version_id,
        "merged_version_id": review.merged_version_id,
        "merged_by": review.merged_by,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "submitted_at": review.submitted_at.isoformat() if review.submitted_at else None,
        "approved_at": review.approved_at.isoformat() if review.approved_at else None,
        "merged_at": review.merged_at.isoformat() if review.merged_at else None,
        "closed_at": review.closed_at.isoformat() if review.closed_at else None,
    }


def _serialize_action(action: AuditReviewAction) -> dict[str, Any]:
    """序列化复核动作对象。

    Args:
        action: 复核动作ORM对象

    Returns:
        序列化后的字典
    """
    return {
        "id": action.id,
        "review_request_id": action.review_request_id,
        "review_level": action.review_level,
        "action": action.action,
        "comment": action.comment,
        "reviewer_id": action.reviewer_id,
        "created_at": action.created_at.isoformat() if action.created_at else None,
    }


def _generate_pr_no(db: Session, project_id: int) -> str:
    """生成复核请求编号（PR-XXX格式，项目内自增）。

    Args:
        db: 数据库会话
        project_id: 项目ID

    Returns:
        复核请求编号，如 PR-001
    """
    count = (
        db.query(func.count(AuditReviewRequest.id))
        .filter(AuditReviewRequest.project_id == project_id)
        .scalar()
    )
    return f"PR-{count + 1:03d}"


def get_review_list(
    db: Session,
    project_id: int | None = None,
    status: str | None = None,
    created_by: int | None = None,
    reviewer_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页查询复核请求列表。

    Args:
        db: 数据库会话
        project_id: 项目ID过滤
        status: 状态过滤
        created_by: 创建人过滤
        reviewer_id: 复核人过滤（匹配各级复核人）
        page: 页码，从1开始
        page_size: 每页数量

    Returns:
        包含 items、total、page、page_size 的分页结果
    """
    query = db.query(AuditReviewRequest)

    if project_id is not None:
        query = query.filter(AuditReviewRequest.project_id == project_id)
    if status is not None:
        if status not in VALID_STATUSES:
            raise ValueError(f"无效的状态值: {status}")
        query = query.filter(AuditReviewRequest.status == status)
    if created_by is not None:
        query = query.filter(AuditReviewRequest.created_by == created_by)
    if reviewer_id is not None:
        query = query.filter(
            (AuditReviewRequest.reviewer_level_1_id == reviewer_id)
            | (AuditReviewRequest.reviewer_level_2_id == reviewer_id)
            | (AuditReviewRequest.reviewer_level_3_id == reviewer_id)
        )

    total = query.count()
    items = (
        query.order_by(AuditReviewRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [_serialize_review(item) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_review_by_id(db: Session, review_id: int) -> dict[str, Any] | None:
    """根据ID获取复核请求。

    Args:
        db: 数据库会话
        review_id: 复核请求ID

    Returns:
        复核请求详情，不存在则返回None
    """
    review = db.query(AuditReviewRequest).filter(AuditReviewRequest.id == review_id).first()
    if review is None:
        return None
    return _serialize_review(review)


def create_review_request(
    db: Session,
    review_data: dict[str, Any],
    creator_id: int,
) -> dict[str, Any]:
    """创建复核请求（draft状态）。

    Args:
        db: 数据库会话
        review_data: 复核请求数据，包含 task_id, branch_id, project_id, title 等
        creator_id: 创建人ID

    Returns:
        创建后的复核请求详情

    Raises:
        ValueError: 必要参数缺失或关联数据不存在
    """
    required_fields = ["task_id", "branch_id", "project_id", "title"]
    for field in required_fields:
        if field not in review_data or review_data[field] is None:
            raise ValueError(f"缺少必要参数: {field}")

    task = db.query(AuditTask).filter(AuditTask.id == review_data["task_id"]).first()
    if task is None:
        raise ValueError(f"任务不存在: {review_data['task_id']}")

    branch = db.query(AuditWorkBranch).filter(AuditWorkBranch.id == review_data["branch_id"]).first()
    if branch is None:
        raise ValueError(f"工作分支不存在: {review_data['branch_id']}")

    submitted_version_id = review_data.get("submitted_version_id") or branch.latest_version_id
    if submitted_version_id is None:
        raise ValueError("提交复核必须绑定明确的底稿版本")
    version = db.get(WorkpaperVersion, submitted_version_id)
    if version is None:
        raise ValueError("提交复核绑定的底稿版本不存在")
    if branch.workpaper_index_id and version.workpaper_index_id != branch.workpaper_index_id:
        raise ValueError("提交复核的底稿版本不属于当前工作分支的底稿索引")

    pr_no = _generate_pr_no(db, review_data["project_id"])

    review = AuditReviewRequest(
        project_id=review_data["project_id"],
        ledger_id=review_data.get("ledger_id"),
        task_id=review_data["task_id"],
        branch_id=review_data["branch_id"],
        pr_no=pr_no,
        title=review_data["title"],
        description=review_data.get("description"),
        target_branch=review_data.get("target_branch", "main"),
        status="draft",
        current_review_level=1,
        created_by=creator_id,
        reviewer_level_1_id=review_data.get("reviewer_level_1_id"),
        reviewer_level_2_id=review_data.get("reviewer_level_2_id"),
        reviewer_level_3_id=review_data.get("reviewer_level_3_id"),
        submitted_version_id=submitted_version_id,
    )

    db.add(review)
    db.commit()
    db.refresh(review)
    return _serialize_review(review)


def submit_review(
    db: Session,
    review_id: int,
    reviewer_level_1_id: int | None = None,
) -> dict[str, Any]:
    """提交复核请求（draft -> review）。

    Args:
        db: 数据库会话
        review_id: 复核请求ID
        reviewer_level_1_id: 一级复核人ID（可选，未设置时更新）

    Returns:
        更新后的复核请求详情

    Raises:
        ValueError: 复核请求不存在或状态不合法
    """
    review = db.query(AuditReviewRequest).filter(AuditReviewRequest.id == review_id).first()
    if review is None:
        raise ValueError("复核请求不存在")

    _validate_status_transition(review.status, "review")

    if reviewer_level_1_id is not None:
        review.reviewer_level_1_id = reviewer_level_1_id

    if review.reviewer_level_1_id is None:
        raise ValueError("一级复核人不能为空")

    review.status = "review"
    review.submitted_at = datetime.utcnow()
    audit_notification_service.create_notification(
        db,
        recipient_user_id=review.reviewer_level_1_id,
        actor_user_id=review.created_by,
        event_type="review_submitted",
        target_type="review_request",
        target_id=review.id,
        title=f"新的底稿复核请求：{review.title}",
        content=f"复核请求 {review.pr_no} 已提交，请复核绑定底稿版本 {review.submitted_version_id}",
        project_id=review.project_id,
        ledger_id=review.ledger_id,
    )
    db.commit()
    db.refresh(review)
    return _serialize_review(review)


def perform_review(
    db: Session,
    review_id: int,
    reviewer_id: int,
    action: str,
    comment: str | None = None,
    review_level: int = 1,
) -> dict[str, Any]:
    """执行复核动作。

    MVP版本只支持单级复核（review_level=1）。
    - action: approve -> 状态变为 approved
    - action: request_changes -> 状态变为 changes_requested

    Args:
        db: 数据库会话
        review_id: 复核请求ID
        reviewer_id: 复核人ID
        action: 复核动作，approve 或 request_changes
        comment: 复核意见
        review_level: 复核级别，默认为1

    Returns:
        更新后的复核请求详情

    Raises:
        ValueError: 复核请求不存在、状态不合法、动作无效或复核人不匹配
    """
    if action not in VALID_ACTIONS:
        raise ValueError(f"无效的复核动作: {action}")

    review = db.query(AuditReviewRequest).filter(AuditReviewRequest.id == review_id).first()
    if review is None:
        raise ValueError("复核请求不存在")

    if review.status != "review":
        raise ValueError(f"当前状态 {review.status} 不支持复核操作")

    if review_level != 1:
        raise ValueError("MVP版本仅支持单级复核（review_level=1）")

    expected_reviewer_id = getattr(review, f"reviewer_level_{review_level}_id")
    if expected_reviewer_id is None or expected_reviewer_id != reviewer_id:
        raise ValueError(f"当前用户不是该复核请求的第{review_level}级复核人")

    target_status = "approved" if action == "approve" else "changes_requested"
    _validate_status_transition(review.status, target_status)
    branch = db.get(AuditWorkBranch, review.branch_id)
    if branch and branch.latest_version_id and branch.latest_version_id != review.submitted_version_id:
        raise ValueError("底稿版本已变化，请重新提交复核请求")

    review_action = AuditReviewAction(
        review_request_id=review_id,
        review_level=review_level,
        action=action,
        comment=comment,
        reviewer_id=reviewer_id,
    )
    db.add(review_action)

    review.status = target_status
    review.current_review_level = review_level
    if action == "approve":
        review.approved_at = datetime.utcnow()
        review.approved_version_id = review.submitted_version_id
        audit_notification_service.create_notification(
            db,
            recipient_user_id=review.created_by,
            actor_user_id=reviewer_id,
            event_type="review_approved",
            target_type="review_request",
            target_id=review.id,
            title=f"底稿复核已通过：{review.title}",
            content=f"复核请求 {review.pr_no} 已通过",
            project_id=review.project_id,
            ledger_id=review.ledger_id,
        )
    else:
        audit_notification_service.create_notification(
            db,
            recipient_user_id=review.created_by,
            actor_user_id=reviewer_id,
            event_type="review_changes_requested",
            target_type="review_request",
            target_id=review.id,
            title=f"底稿复核退回修改：{review.title}",
            content=comment or f"复核请求 {review.pr_no} 已退回修改",
            project_id=review.project_id,
            ledger_id=review.ledger_id,
        )

    db.commit()
    db.refresh(review)
    return _serialize_review(review)


def merge_review(
    db: Session,
    review_id: int,
    merged_by: int,
) -> dict[str, Any]:
    """合并归档复核请求（approved -> merged）。

    同时更新关联分支状态为 merged，更新关联任务状态为 closed。
    整个操作在事务中执行，保证数据一致性。

    Args:
        db: 数据库会话
        review_id: 复核请求ID
        merged_by: 合并操作人ID

    Returns:
        更新后的复核请求详情

    Raises:
        ValueError: 复核请求不存在或状态不合法
    """
    review = db.query(AuditReviewRequest).filter(AuditReviewRequest.id == review_id).first()
    if review is None:
        raise ValueError("复核请求不存在")

    _validate_status_transition(review.status, "merged")
    if review.approved_version_id is None:
        raise ValueError("复核请求未绑定已通过的底稿版本，不能合并归档")

    approved_version = db.get(WorkpaperVersion, review.approved_version_id)
    if approved_version is None:
        raise ValueError("已通过的底稿版本不存在，不能合并归档")
    approved_version.status = "reviewed"
    approved_version.reviewed_by = merged_by

    branch = db.query(AuditWorkBranch).filter(AuditWorkBranch.id == review.branch_id).first()
    if branch is not None:
        branch.status = "merged"
        branch.merged_at = datetime.utcnow()

    task = db.query(AuditTask).filter(AuditTask.id == review.task_id).first()
    if task is not None:
        task.status = "closed"
        task.closed_at = datetime.utcnow()

    review.status = "merged"
    review.merged_by = merged_by
    review.merged_version_id = review.approved_version_id
    review.merged_at = datetime.utcnow()
    audit_notification_service.create_notifications(
        db,
        recipient_user_ids=[review.created_by, task.assignee_id if task else None],
        actor_user_id=merged_by,
        event_type="review_merged",
        target_type="review_request",
        target_id=review.id,
        title=f"底稿已合并归档：{review.title}",
        content=f"复核请求 {review.pr_no} 已归档，版本 {review.merged_version_id} 已固化",
        project_id=review.project_id,
        ledger_id=review.ledger_id,
    )

    db.commit()
    db.refresh(review)
    return _serialize_review(review)


def get_review_actions(db: Session, review_id: int) -> list[dict[str, Any]]:
    """获取复核请求的所有复核动作记录。

    Args:
        db: 数据库会话
        review_id: 复核请求ID

    Returns:
        复核动作记录列表，按创建时间升序排列
    """
    actions = (
        db.query(AuditReviewAction)
        .filter(AuditReviewAction.review_request_id == review_id)
        .order_by(AuditReviewAction.id.asc())
        .all()
    )
    return [_serialize_action(action) for action in actions]


def get_pending_my_review(
    db: Session,
    user_id: int,
    project_id: int | None = None,
) -> list[dict[str, Any]]:
    """获取待我复核的请求。

    Args:
        db: 数据库会话
        user_id: 当前用户ID
        project_id: 项目ID过滤（可选）

    Returns:
        待复核的请求列表
    """
    query = db.query(AuditReviewRequest).filter(
        AuditReviewRequest.status == "review",
        (
            (AuditReviewRequest.current_review_level == 1)
            & (AuditReviewRequest.reviewer_level_1_id == user_id)
        )
        | (
            (AuditReviewRequest.current_review_level == 2)
            & (AuditReviewRequest.reviewer_level_2_id == user_id)
        )
        | (
            (AuditReviewRequest.current_review_level == 3)
            & (AuditReviewRequest.reviewer_level_3_id == user_id)
        ),
    )

    if project_id is not None:
        query = query.filter(AuditReviewRequest.project_id == project_id)

    items = query.order_by(AuditReviewRequest.id.desc()).all()
    return [_serialize_review(item) for item in items]


def get_my_submitted(
    db: Session,
    user_id: int,
    project_id: int | None = None,
) -> list[dict[str, Any]]:
    """获取我提交的复核请求。

    Args:
        db: 数据库会话
        user_id: 当前用户ID
        project_id: 项目ID过滤（可选）

    Returns:
        我提交的复核请求列表
    """
    query = db.query(AuditReviewRequest).filter(AuditReviewRequest.created_by == user_id)

    if project_id is not None:
        query = query.filter(AuditReviewRequest.project_id == project_id)

    items = query.order_by(AuditReviewRequest.id.desc()).all()
    return [_serialize_review(item) for item in items]
