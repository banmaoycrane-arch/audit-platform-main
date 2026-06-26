"""审计工作台 API 路由。

模块功能：提供审计工作台统计和列表接口
业务场景：审计人员首页工作台，展示待办任务、复核任务、提交记录等
政策依据：中国注册会计师审计准则第1121号（项目质量控制）
输入数据：用户身份信息、项目筛选条件
输出结果：工作台统计数据、待办任务列表、待复核列表、已提交列表
创建日期：2026-06-26
"""

from datetime import date, datetime, time

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models import AuditReviewRequest, AuditTask
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit_workflow import (
    AuditDashboardStats,
    AuditReviewRequestRead,
    AuditTaskRead,
)
from app.services import audit_review_service, audit_task_service

router = APIRouter(prefix="/api/audit/dashboard", tags=["audit-dashboard"])


@router.get("/stats", response_model=AuditDashboardStats)
def get_dashboard_stats(
    project_id: int | None = Query(default=None, description="项目ID筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditDashboardStats:
    user_id = current_user.id

    todo_count = (
        db.query(func.count(AuditTask.id))
        .filter(
            AuditTask.assignee_id == user_id,
            AuditTask.status == "todo",
        )
    )

    in_progress_count = (
        db.query(func.count(AuditTask.id))
        .filter(
            AuditTask.assignee_id == user_id,
            AuditTask.status == "in_progress",
        )
    )

    review_count = (
        db.query(func.count(AuditTask.id))
        .filter(
            AuditTask.assignee_id == user_id,
            AuditTask.status == "review",
        )
    )

    if project_id is not None:
        todo_count = todo_count.filter(AuditTask.project_id == project_id)
        in_progress_count = in_progress_count.filter(AuditTask.project_id == project_id)
        review_count = review_count.filter(AuditTask.project_id == project_id)

    todo_tasks_count = todo_count.scalar() or 0
    in_progress_tasks_count = in_progress_count.scalar() or 0
    review_tasks_count = review_count.scalar() or 0

    pending_review_query = db.query(func.count(AuditReviewRequest.id)).filter(
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

    submitted_query = db.query(func.count(AuditReviewRequest.id)).filter(
        AuditReviewRequest.created_by == user_id,
    )

    if project_id is not None:
        pending_review_query = pending_review_query.filter(
            AuditReviewRequest.project_id == project_id
        )
        submitted_query = submitted_query.filter(AuditReviewRequest.project_id == project_id)

    pending_my_review_count = pending_review_query.scalar() or 0
    submitted_by_me_count = submitted_query.scalar() or 0

    today_start = datetime.combine(date.today(), time.min)
    today_end = datetime.combine(date.today(), time.max)

    closed_today_query = db.query(func.count(AuditTask.id)).filter(
        AuditTask.assignee_id == user_id,
        AuditTask.status == "closed",
        AuditTask.closed_at >= today_start,
        AuditTask.closed_at <= today_end,
    )

    if project_id is not None:
        closed_today_query = closed_today_query.filter(AuditTask.project_id == project_id)

    closed_today_count = closed_today_query.scalar() or 0

    return AuditDashboardStats(
        todo_tasks_count=todo_tasks_count,
        in_progress_tasks_count=in_progress_tasks_count,
        review_tasks_count=review_tasks_count,
        pending_my_review_count=pending_my_review_count,
        submitted_by_me_count=submitted_by_me_count,
        closed_today_count=closed_today_count,
    )


@router.get("/todo-tasks", response_model=list[AuditTaskRead])
def get_todo_tasks(
    project_id: int | None = Query(default=None, description="项目ID筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return audit_task_service.get_user_todo_tasks(db, current_user.id, project_id=project_id)


@router.get("/pending-review", response_model=list[AuditReviewRequestRead])
def get_pending_review(
    project_id: int | None = Query(default=None, description="项目ID筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return audit_review_service.get_pending_my_review(
        db, current_user.id, project_id=project_id
    )


@router.get("/submitted", response_model=list[AuditReviewRequestRead])
def get_submitted(
    project_id: int | None = Query(default=None, description="项目ID筛选"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    return audit_review_service.get_my_submitted(
        db, current_user.id, project_id=project_id
    )
