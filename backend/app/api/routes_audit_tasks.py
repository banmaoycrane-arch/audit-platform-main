"""审计任务 API 路由。

模块功能：提供审计任务的增删改查、分配、状态流转等接口
业务场景：审计项目协作中的任务管理
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit_workflow import (
    AuditTaskAssign,
    AuditTaskCreate,
    AuditTaskListResponse,
    AuditTaskRead,
    AuditTaskStatusUpdate,
    AuditTaskUpdate,
)
from app.services import audit_task_service

router = APIRouter(prefix="/api/audit/tasks", tags=["audit-tasks"])


@router.get("", response_model=AuditTaskListResponse)
def list_tasks(
    project_id: int = Query(...),
    status: str | None = Query(default=None),
    assignee_id: int | None = Query(default=None),
    task_type: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditTaskListResponse:
    result = audit_task_service.get_task_list(
        db,
        project_id,
        status=status,
        assignee_id=assignee_id,
        task_type=task_type,
        priority=priority,
        page=page,
        page_size=page_size,
    )
    return AuditTaskListResponse.model_validate(result)


@router.get("/{task_id}", response_model=AuditTaskRead)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditTaskRead:
    task = audit_task_service.get_task_by_id(db, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return AuditTaskRead.model_validate(task)


@router.post("", response_model=AuditTaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: AuditTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditTaskRead:
    try:
        task = audit_task_service.create_task(db, payload, creator_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return AuditTaskRead.model_validate(task)


@router.put("/{task_id}", response_model=AuditTaskRead)
def update_task(
    task_id: int,
    payload: AuditTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditTaskRead:
    try:
        task = audit_task_service.update_task(db, task_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AuditTaskRead.model_validate(task)


@router.patch("/{task_id}/assign", response_model=AuditTaskRead)
def assign_task(
    task_id: int,
    payload: AuditTaskAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditTaskRead:
    try:
        task = audit_task_service.assign_task(db, task_id, payload.assignee_id)
    except ValueError as exc:
        if str(exc) == "任务不存在":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuditTaskRead.model_validate(task)


@router.patch("/{task_id}/status", response_model=AuditTaskRead)
def update_task_status(
    task_id: int,
    payload: AuditTaskStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditTaskRead:
    try:
        task = audit_task_service.update_task_status(
            db, task_id, payload.status, comment=payload.comment
        )
    except ValueError as exc:
        if str(exc) == "任务不存在":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuditTaskRead.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        audit_task_service.delete_task(db, task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
