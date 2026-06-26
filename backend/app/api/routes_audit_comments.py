"""审计评论 API 路由。

模块功能：提供审计评论的增删查接口
业务场景：审计工作中在任务、分支、复核请求、底稿版本上进行沟通留痕
政策依据：中国注册会计师审计准则第1121号（项目质量控制）
输入数据：评论目标类型、目标ID、评论内容等
输出结果：评论列表、单条评论信息
创建日期：2026-06-26
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit_workflow import AuditCommentCreate, AuditCommentRead
from app.services import audit_comment_service

router = APIRouter(prefix="/api/audit/comments", tags=["audit-comments"])


@router.get("", response_model=list[AuditCommentRead])
def list_comments(
    target_type: str = Query(..., description="评论目标类型"),
    target_id: int = Query(..., description="评论目标ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    try:
        return audit_comment_service.get_comments(db, target_type, target_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("", response_model=AuditCommentRead, status_code=status.HTTP_201_CREATED)
def create_comment(
    payload: AuditCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    try:
        return audit_comment_service.create_comment(db, payload, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        audit_comment_service.delete_comment(db, comment_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
