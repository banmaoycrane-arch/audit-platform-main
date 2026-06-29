# -*- coding: utf-8 -*-
"""
模块功能：项目管理 API 路由
业务场景：前端调用创建项目、关联账簿、分配人员、查询项目列表
政策依据：会计师事务所质量控制准则——项目立项与人员分派
输入数据：HTTP 请求（JSON 或路径参数）
输出结果：项目 JSON 数据
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建项目管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import project_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    """创建项目请求体"""
    team_id: int
    name: str
    project_type: str = "audit"
    status: str = "active"
    start_date: str | None = None
    end_date: str | None = None
    manager_id: int | None = None


class UpdateProjectRequest(BaseModel):
    """更新项目请求体"""
    team_id: int | None = None
    name: str | None = None
    project_type: str | None = None
    status: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    manager_id: int | None = None


class AssociateLedgerRequest(BaseModel):
    """关联账簿请求体"""
    ledger_id: int


class AssignMemberRequest(BaseModel):
    """分配人员请求体"""
    user_id: int
    role: str = "member"


class ProjectResponse(BaseModel):
    """项目响应体"""
    id: int
    name: str
    team_id: int
    type: str
    status: str
    completed_at: str | None
    cancelled_at: str | None
    lifecycle_reason: str | None
    start_date: str | None
    end_date: str | None
    manager_id: int | None
    created_at: str | None
    updated_at: str | None

    model_config = {"from_attributes": True}


class ProjectMemberResponse(BaseModel):
    """项目成员响应体"""
    id: int
    project_id: int
    user_id: int
    role: str

    model_config = {"from_attributes": True}


class ProjectLedgerResponse(BaseModel):
    """项目账簿关联响应体"""
    id: int
    project_id: int
    ledger_id: int

    model_config = {"from_attributes": True}


class ProjectTaskAssigneeResponse(BaseModel):
    """审计任务负责人候选人响应体"""
    id: int
    username: str | None
    email: str | None
    phone: str | None
    team_id: int | None
    project_role: str | None
    ledger_roles: list[str] = []


class LifecycleReasonRequest(BaseModel):
    """生命周期变更原因请求体"""
    reason: str | None = None


@router.post("", response_model=ProjectResponse)
def create_project(
    payload: CreateProjectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """
    创建项目。

    需要 team_id 和 name，可选项目类型、状态、起止日期、负责人。
    创建后自动将当前用户加入项目成员（role=manager）。
    """
    team = project_service.get_team_by_id(db, payload.team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="团队不存在")

    project = project_service.create_project(
        db,
        team_id=payload.team_id,
        name=payload.name,
        project_type=payload.project_type,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        manager_id=current_user.id,
    )

    # 自动将创建者加入项目成员，角色为 manager
    project_service.assign_member_to_project(
        db, project.id, current_user.id, role="manager"
    )

    return ProjectResponse(
        id=project.id,
        name=project.name,
        team_id=project.team_id,
        type=project.type,
        status=project.status,
        completed_at=str(project.completed_at) if project.completed_at else None,
        cancelled_at=str(project.cancelled_at) if project.cancelled_at else None,
        lifecycle_reason=project.lifecycle_reason,
        start_date=str(project.start_date) if project.start_date else None,
        end_date=str(project.end_date) if project.end_date else None,
        manager_id=project.manager_id,
        created_at=str(project.created_at) if project.created_at else None,
        updated_at=str(project.updated_at) if project.updated_at else None,
    )


@router.get("", response_model=list[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProjectResponse]:
    """
    查询当前用户参与的项目列表。
    """
    projects = project_service.list_projects_by_user(db, current_user.id)
    return [
        ProjectResponse(
            id=p.id,
            name=p.name,
            team_id=p.team_id,
            type=p.type,
            status=p.status,
            completed_at=str(p.completed_at) if p.completed_at else None,
            cancelled_at=str(p.cancelled_at) if p.cancelled_at else None,
            lifecycle_reason=p.lifecycle_reason,
            start_date=str(p.start_date) if p.start_date else None,
            end_date=str(p.end_date) if p.end_date else None,
            manager_id=p.manager_id,
            created_at=str(p.created_at) if p.created_at else None,
            updated_at=str(p.updated_at) if p.updated_at else None,
        )
        for p in projects
    ]


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    payload: UpdateProjectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """
    更新项目信息。

    支持部分更新项目名称、类型、状态、起止日期、负责人等字段。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    update_data = payload.model_dump(exclude_unset=True)

    if "team_id" in update_data and update_data["team_id"] is not None:
        team = project_service.get_team_by_id(db, update_data["team_id"])
        if not team:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="团队不存在")

    if "manager_id" in update_data and update_data["manager_id"] is not None:
        manager = project_service.get_user_by_id(db, update_data["manager_id"])
        if not manager:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="负责人不存在")

    updated = project_service.update_project(db, project_id, **update_data)
    return ProjectResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        type=updated.type,
        status=updated.status,
        completed_at=str(updated.completed_at) if updated.completed_at else None,
        cancelled_at=str(updated.cancelled_at) if updated.cancelled_at else None,
        lifecycle_reason=updated.lifecycle_reason,
        start_date=str(updated.start_date) if updated.start_date else None,
        end_date=str(updated.end_date) if updated.end_date else None,
        manager_id=updated.manager_id,
        created_at=str(updated.created_at) if updated.created_at else None,
        updated_at=str(updated.updated_at) if updated.updated_at else None,
    )


@router.get("/{project_id}/ledgers", response_model=list[dict])
def list_project_ledgers(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """
    查询项目关联的账簿列表。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    ledgers = project_service.get_project_ledgers(db, project_id)
    return [
        {"id": l.id, "name": l.name}
        for l in ledgers
    ]


@router.post("/{project_id}/ledgers", response_model=ProjectLedgerResponse)
def associate_ledger(
    project_id: int,
    payload: AssociateLedgerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectLedgerResponse:
    """
    关联账簿到项目。

    需要 ledger_id。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    ledger = project_service.get_ledger_by_id(db, payload.ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="账簿不存在")

    link = project_service.associate_ledger_to_project(db, project_id, payload.ledger_id)
    return ProjectLedgerResponse(
        id=link.id,
        project_id=link.project_id,
        ledger_id=link.ledger_id,
    )


@router.delete("/{project_id}/ledgers/{ledger_id}")
def remove_ledger(
    project_id: int,
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    解除项目与账簿关联。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    deleted = project_service.remove_ledger_from_project(db, project_id, ledger_id)
    return {"deleted": deleted, "project_id": project_id, "ledger_id": ledger_id}


@router.get("/{project_id}/task-assignees", response_model=list[ProjectTaskAssigneeResponse])
def list_project_task_assignees(
    project_id: int,
    ledger_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ProjectTaskAssigneeResponse]:
    """返回当前项目下可作为审计任务负责人的成员。"""
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    return [ProjectTaskAssigneeResponse(**item) for item in project_service.list_project_task_assignees(db, project_id, ledger_id)]


@router.post("/{project_id}/members", response_model=ProjectMemberResponse)
def assign_member(
    project_id: int,
    payload: AssignMemberRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectMemberResponse:
    """
    分配人员到项目。

    需要 user_id 和 role。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    user = project_service.get_user_by_id(db, payload.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户不存在")

    member = project_service.assign_member_to_project(
        db, project_id, payload.user_id, payload.role
    )
    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role,
    )


@router.post("/{project_id}/start", response_model=ProjectResponse)
def start_project_endpoint(
    project_id: int,
    payload: LifecycleReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """
    启动项目。

    将项目状态设置为 active。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    updated = project_service.start_project(db, project_id, reason=payload.reason)
    return ProjectResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        type=updated.type,
        status=updated.status,
        completed_at=str(updated.completed_at) if updated.completed_at else None,
        cancelled_at=str(updated.cancelled_at) if updated.cancelled_at else None,
        lifecycle_reason=updated.lifecycle_reason,
        start_date=str(updated.start_date) if updated.start_date else None,
        end_date=str(updated.end_date) if updated.end_date else None,
        manager_id=updated.manager_id,
        created_at=str(updated.created_at) if updated.created_at else None,
        updated_at=str(updated.updated_at) if updated.updated_at else None,
    )


@router.post("/{project_id}/pause", response_model=ProjectResponse)
def pause_project_endpoint(
    project_id: int,
    payload: LifecycleReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """
    暂停项目。

    将项目状态设置为 paused。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    updated = project_service.pause_project(db, project_id, reason=payload.reason)
    return ProjectResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        type=updated.type,
        status=updated.status,
        completed_at=str(updated.completed_at) if updated.completed_at else None,
        cancelled_at=str(updated.cancelled_at) if updated.cancelled_at else None,
        lifecycle_reason=updated.lifecycle_reason,
        start_date=str(updated.start_date) if updated.start_date else None,
        end_date=str(updated.end_date) if updated.end_date else None,
        manager_id=updated.manager_id,
        created_at=str(updated.created_at) if updated.created_at else None,
        updated_at=str(updated.updated_at) if updated.updated_at else None,
    )


@router.post("/{project_id}/complete", response_model=ProjectResponse)
def complete_project_endpoint(
    project_id: int,
    payload: LifecycleReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """
    完成项目。

    将项目状态设置为 completed，并记录完成时间。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    updated = project_service.complete_project(db, project_id, reason=payload.reason)
    return ProjectResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        type=updated.type,
        status=updated.status,
        completed_at=str(updated.completed_at) if updated.completed_at else None,
        cancelled_at=str(updated.cancelled_at) if updated.cancelled_at else None,
        lifecycle_reason=updated.lifecycle_reason,
        start_date=str(updated.start_date) if updated.start_date else None,
        end_date=str(updated.end_date) if updated.end_date else None,
        manager_id=updated.manager_id,
        created_at=str(updated.created_at) if updated.created_at else None,
        updated_at=str(updated.updated_at) if updated.updated_at else None,
    )


@router.post("/{project_id}/reopen", response_model=ProjectResponse)
def reopen_project_endpoint(
    project_id: int,
    payload: LifecycleReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """
    重新打开项目。

    将 completed 或 paused 状态的项目恢复为 active。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    updated = project_service.reopen_project(db, project_id, reason=payload.reason)
    return ProjectResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        type=updated.type,
        status=updated.status,
        completed_at=str(updated.completed_at) if updated.completed_at else None,
        cancelled_at=str(updated.cancelled_at) if updated.cancelled_at else None,
        lifecycle_reason=updated.lifecycle_reason,
        start_date=str(updated.start_date) if updated.start_date else None,
        end_date=str(updated.end_date) if updated.end_date else None,
        manager_id=updated.manager_id,
        created_at=str(updated.created_at) if updated.created_at else None,
        updated_at=str(updated.updated_at) if updated.updated_at else None,
    )


@router.post("/{project_id}/cancel", response_model=ProjectResponse)
def cancel_project_endpoint(
    project_id: int,
    payload: LifecycleReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """
    取消项目。

    将项目状态设置为 cancelled，并记录取消时间。
    """
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    updated = project_service.cancel_project(db, project_id, reason=payload.reason)
    return ProjectResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        type=updated.type,
        status=updated.status,
        completed_at=str(updated.completed_at) if updated.completed_at else None,
        cancelled_at=str(updated.cancelled_at) if updated.cancelled_at else None,
        lifecycle_reason=updated.lifecycle_reason,
        start_date=str(updated.start_date) if updated.start_date else None,
        end_date=str(updated.end_date) if updated.end_date else None,
        manager_id=updated.manager_id,
        created_at=str(updated.created_at) if updated.created_at else None,
        updated_at=str(updated.updated_at) if updated.updated_at else None,
    )


@router.get("/{project_id}/consolidated-report")
def get_consolidated_report(
    project_id: int,
    period_start: str | None = None,
    period_end: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取项目跨账簿汇总报告。

    功能描述：
        1. 获取项目关联的所有账簿
        2. 汇总各账簿的会计分录数据
        3. 按科目分类汇总借贷方发生额
        4. 识别潜在的内部交易

    会计口径：
        - 跨账簿数据汇总用于集团层面的分析
        - 仅汇总 entry_source='auto' 的分录

    Args:
        project_id: 项目ID
        period_start: 可选，汇总起始日期 (YYYY-MM-DD)
        period_end: 可选，汇总结束日期 (YYYY-MM-DD)

    Returns:
        dict: 包含汇总数据、项目账簿列表、科目发生额汇总、内部交易识别
    """
    return project_service.get_consolidated_report(db, project_id, period_start, period_end)


@router.get("/{project_id}/files")
def list_project_files(
    project_id: int,
    ledger_id: int | None = None,
    archive_category: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """列出项目下已自动归档的底稿资料。"""
    project = project_service.get_project_by_id(db, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")

    from app.api.routes_files import _to_dict
    from app.services.draft_archive_service import list_project_archived_files, load_archive_metadata

    items = list_project_archived_files(db, project_id, ledger_id=ledger_id)
    if archive_category:
        items = [
            item
            for item in items
            if (load_archive_metadata(item) or {}).get("archive_category") == archive_category
        ]
    return [_to_dict(db, item) for item in items]
