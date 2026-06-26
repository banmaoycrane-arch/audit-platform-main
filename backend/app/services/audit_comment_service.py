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

from app.db.models import AuditComment
from app.schemas.audit_workflow import AuditCommentCreate


VALID_TARGET_TYPES = {"task", "branch", "review_request", "workpaper_version"}


def _serialize(comment: AuditComment) -> dict[str, Any]:
    """将 AuditComment 模型序列化为字典。"""
    return {
        "id": comment.id,
        "target_type": comment.target_type,
        "target_id": comment.target_id,
        "content": comment.content,
        "mention_user_ids": comment.mention_user_ids,
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
        created_by=creator_id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(comment)
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
