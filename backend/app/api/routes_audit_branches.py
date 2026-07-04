"""
审计工作分支管理 API 路由

模块功能：提供审计工作分支的增删改查、状态流转、底稿版本与审计程序关联接口
业务场景：审计任务的工作分支管理，支持多人协作、版本隔离、审计轨迹追溯
政策依据：中国注册会计师审计准则第1121号（项目质量控制）、第1131号（审计工作底稿）
输入数据：项目ID、任务ID、分支信息、用户ID
输出结果：分支记录、分页列表、状态流转结果
创建日期：2026-06-26
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import get_current_user
from app.schemas.audit_workflow import AuditWorkBranchCreate, AuditWorkBranchRead
import app.services.audit.audit_branch_service as audit_branch_service

router = APIRouter(prefix="/api/audit/branches", tags=["audit-branches"])


class AuditBranchListResponse(BaseModel):
    """分支列表分页响应"""
    items: list[AuditWorkBranchRead]
    total: int
    page: int
    page_size: int


class BranchStatusUpdate(BaseModel):
    """分支状态更新请求"""
    status: str


class LinkVersionRequest(BaseModel):
    """关联底稿版本请求"""
    version_id: int


class LinkProcedureRequest(BaseModel):
    """关联审计程序运行请求"""
    procedure_run_id: int


@router.get("", response_model=AuditBranchListResponse)
def list_branches(
    project_id: int | None = Query(default=None),
    task_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditBranchListResponse:
    result = audit_branch_service.get_branch_list(
        db,
        project_id=project_id,
        task_id=task_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return AuditBranchListResponse(
        items=[AuditWorkBranchRead.model_validate(item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/{branch_id}", response_model=AuditWorkBranchRead)
def get_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditWorkBranchRead:
    branch = audit_branch_service.get_branch_by_id(db, branch_id)
    if branch is None:
        raise HTTPException(status_code=404, detail="分支不存在")
    return AuditWorkBranchRead.model_validate(branch)


@router.post("", response_model=AuditWorkBranchRead)
def create_branch(
    payload: AuditWorkBranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditWorkBranchRead:
    try:
        branch = audit_branch_service.create_branch(
            db,
            payload.model_dump(),
            creator_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuditWorkBranchRead.model_validate(branch)


@router.patch("/{branch_id}/status", response_model=AuditWorkBranchRead)
def update_branch_status(
    branch_id: int,
    payload: BranchStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditWorkBranchRead:
    try:
        branch = audit_branch_service.update_branch_status(
            db,
            branch_id,
            new_status=payload.status,
        )
    except ValueError as exc:
        if str(exc) == "分支不存在":
            raise HTTPException(status_code=404, detail="分支不存在") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AuditWorkBranchRead.model_validate(branch)


@router.get("/task/{task_id}", response_model=list[AuditWorkBranchRead])
def get_task_branches(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuditWorkBranchRead]:
    branches = audit_branch_service.get_branches_by_task(db, task_id)
    return [AuditWorkBranchRead.model_validate(branch) for branch in branches]


@router.post("/{branch_id}/link-version", response_model=AuditWorkBranchRead)
def link_workpaper_version(
    branch_id: int,
    payload: LinkVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditWorkBranchRead:
    try:
        branch = audit_branch_service.link_workpaper_version(
            db,
            branch_id,
            version_id=payload.version_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="分支不存在") from exc
    return AuditWorkBranchRead.model_validate(branch)


@router.post("/{branch_id}/link-procedure", response_model=AuditWorkBranchRead)
def link_procedure_run(
    branch_id: int,
    payload: LinkProcedureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuditWorkBranchRead:
    try:
        branch = audit_branch_service.link_procedure_run(
            db,
            branch_id,
            procedure_run_id=payload.procedure_run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="分支不存在") from exc
    return AuditWorkBranchRead.model_validate(branch)
