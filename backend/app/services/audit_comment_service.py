"""审计评论服务。

模块功能：提供审计评论的增删查操作
业务场景：审计工作中在任务、分支、复核请求、底稿版本上进行沟通留痕
政策依据：中国注册会计师审计准则第1121号（项目质量控制）
输入数据：评论目标类型、目标ID、评论内容等
输出结果：评论列表、单条评论信息
创建日期：2026-06-26
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditComment, AuditReviewRequest, AuditTask, AuditWorkBranch, WorkpaperVersion
from app.schemas.audit_workflow import AuditCommentCreate
from app.services import audit_notification_service


VALID_TARGET_TYPES = {"task", "branch", "review_request", "workpaper_version"}


def _get_notification_context(db: Session, target_type: str, target_id: int) -> tuple[int | None, int | None]:
    if target_type == "task":
        row = db.get(AuditTask, target_id)
        return (row.project_id, row.ledger_id) if row else (None, None)
    if target_type == "branch":
        row = db.get(AuditWorkBranch, target_id)
        return (row.project_id, row.ledger_id) if row else (None, None)
    if target_type == "review_request":
        row = db.get(AuditReviewRequest, target_id)
        return (row.project_id, row.ledger_id) if row else (None, None)
    if target_type == "workpaper_version":
        version = db.get(WorkpaperVersion, target_id)
        if version and version.workpaper_index:
            return version.workpaper_index.project_id, version.workpaper_index.ledger_id
    return None, None


def _create_comment_notifications(db: Session, comment: AuditComment, creator_id: int) -> None:
    mentioned_users = comment.mention_user_ids or []
    if not mentioned_users:
        return
    project_id, ledger_id = _get_notification_context(db, comment.target_type, comment.target_id)
    title = "审计评论提及你"
    if comment.marker_type:
        title = "底稿标记提及你"
    audit_notification_service.create_notifications(
        db,
        recipient_user_ids=mentioned_users,
        actor_user_id=creator_id,
        event_type="comment_mentioned" if not comment.marker_type else "workpaper_marker_mentioned",
        target_type=comment.target_type,
        target_id=comment.target_id,
        title=title,
        content=comment.content,
        project_id=project_id,
        ledger_id=ledger_id,
    )


def _serialize(comment: AuditComment) -> dict[str, Any]:
    """将 AuditComment 模型序列化为字典。"""
    return {
        "id": comment.id,
        "target_type": comment.target_type,
        "target_id": comment.target_id,
        "content": comment.content,
        "mention_user_ids": comment.mention_user_ids,
        "marker_type": comment.marker_type,
        "sheet_name": comment.sheet_name,
        "cell_ref": comment.cell_ref,
        "range_ref": comment.range_ref,
        "severity": comment.severity,
        "resolved_at": comment.resolved_at.isoformat() if comment.resolved_at else None,
        "resolved_by": comment.resolved_by,
        "created_by": comment.created_by,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
        "updated_at": comment.updated_at.isoformat() if comment.updated_at else None,
    }


def get_comments(
    db: Session,
    target_type: str,
    target_id: int,
) -> list[dict[str, Any]]:
    """获取指定对象的评论列表，按创建时间升序排列。

    Args:
        db: 数据库会话
        target_type: 评论目标类型（task/branch/review_request/workpaper_version）
        target_id: 评论目标ID

    Returns:
        评论列表，按创建时间升序排列

    Raises:
        ValueError: target_type 不在允许的类型范围内
    """
    if target_type not in VALID_TARGET_TYPES:
        raise ValueError(f"invalid target_type: {target_type}")

    rows = (
        db.query(AuditComment)
        .filter(
            AuditComment.target_type == target_type,
            AuditComment.target_id == target_id,
        )
        .order_by(AuditComment.created_at.asc())
        .all()
    )
    return [_serialize(row) for row in rows]


def create_comment(
    db: Session,
    comment_data: AuditCommentCreate,
    creator_id: int,
) -> dict[str, Any]:
    """创建评论。

    Args:
        db: 数据库会话
        comment_data: 评论创建数据
        creator_id: 创建人用户ID

    Returns:
        创建后的评论信息

    Raises:
        ValueError: target_type 不在允许的类型范围内
    """
    if comment_data.target_type not in VALID_TARGET_TYPES:
        raise ValueError(f"invalid target_type: {comment_data.target_type}")

    comment = AuditComment(
        target_type=comment_data.target_type,
        target_id=comment_data.target_id,
        content=comment_data.content,
        mention_user_ids=comment_data.mention_user_ids,
        marker_type=comment_data.marker_type,
        sheet_name=comment_data.sheet_name,
        cell_ref=comment_data.cell_ref,
        range_ref=comment_data.range_ref,
        severity=comment_data.severity,
        created_by=creator_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(comment)
    db.flush()

    _create_comment_notifications(db, comment, creator_id)

    db.commit()
    db.refresh(comment)
    return _serialize(comment)


def get_comment_by_id(
    db: Session,
    comment_id: int,
) -> dict[str, Any] | None:
    """根据ID获取评论。

    Args:
        db: 数据库会话
        comment_id: 评论ID

    Returns:
        评论信息，不存在则返回 None
    """
    row = db.query(AuditComment).filter(AuditComment.id == comment_id).first()
    if row is None:
        return None
    return _serialize(row)


def delete_comment(
    db: Session,
    comment_id: int,
    user_id: int,
) -> bool:
    """删除评论（只能删除自己发布的）。

    Args:
        db: 数据库会话
        comment_id: 评论ID
        user_id: 当前操作人用户ID

    Returns:
        删除成功返回 True

    Raises:
        ValueError: 评论不存在或无权限删除
    """
    comment = db.query(AuditComment).filter(AuditComment.id == comment_id).first()
    if comment is None:
        raise ValueError("comment not found")

    if comment.created_by != user_id:
        raise ValueError("cannot delete comment created by others")

    db.delete(comment)
    db.commit()
    return True
