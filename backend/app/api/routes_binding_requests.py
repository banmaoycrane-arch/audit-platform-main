# -*- coding: utf-8 -*-
"""
模块功能：绑定申请 API 路由
业务场景：访客用户提交团队/账套/项目绑定申请，管理员审批后完成授权
政策依据：会计信息系统内部控制规范——权限申请、审批、授权留痕
输入数据：HTTP 请求中的团队、账套、项目、角色、审批意见
输出结果：绑定申请 JSON 数据和审批结果
创建日期：2026-06-20
更新记录：
    2026-06-20  初始创建绑定申请路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.binding_request import BindingRequest
from app.models.user import User
from app.services import binding_request_service

router = APIRouter(prefix="/api/binding-requests", tags=["binding-requests"])


class BindingRequestCreate(BaseModel):
    """提交绑定申请请求体"""
    team_id: int
    ledger_id: int | None = None
    project_id: int | None = None
    requested_role: str = "viewer"
    reason: str | None = None


class BindingRequestReview(BaseModel):
    """审批绑定申请请求体"""
    review_comment: str | None = None


class BindingRequestResponse(BaseModel):
    """绑定申请响应体"""
    id: int
    requester_user_id: int
    requester_name: str | None
    requester_phone: str | None
    team_id: int
    team_name: str | None
    ledger_id: int | None
    ledger_name: str | None
    project_id: int | None
    project_name: str | None
    requested_role: str
    status: str
    reason: str | None
    reviewer_user_id: int | None
    review_comment: str | None
    created_at: str | None
    reviewed_at: str | None


class BindingOptionResponse(BaseModel):
    """可申请对象响应体"""
    id: int
    name: str


class BindingOptionsResponse(BaseModel):
    """绑定申请下拉选项响应体"""
    teams: list[BindingOptionResponse]
    ledgers: list[BindingOptionResponse]
    projects: list[BindingOptionResponse]


def build_binding_request_response(request: BindingRequest) -> BindingRequestResponse:
    """把数据库申请记录转换成前端响应。"""
    return BindingRequestResponse(
        id=request.id,
        requester_user_id=request.requester_user_id,
        requester_name=request.requester.username if request.requester else None,
        requester_phone=request.requester.phone if request.requester else None,
        team_id=request.team_id,
        team_name=getattr(request, "team_name", None),
        ledger_id=request.ledger_id,
        ledger_name=getattr(request, "ledger_name", None),
        project_id=request.project_id,
        project_name=getattr(request, "project_name", None),
        requested_role=request.requested_role,
        status=request.status,
        reason=request.reason,
        reviewer_user_id=request.reviewer_user_id,
        review_comment=request.review_comment,
        created_at=str(request.created_at) if request.created_at else None,
        reviewed_at=str(request.reviewed_at) if request.reviewed_at else None,
    )


def attach_display_names(db: Session, request: BindingRequest) -> BindingRequest:
    """补充团队、账套、项目名称，仅用于申请列表展示。"""
    from app.models.ledger import Ledger
    from app.models.project import Project
    from app.models.team import Team

    team = db.query(Team).filter(Team.id == request.team_id).first()
    ledger = db.query(Ledger).filter(Ledger.id == request.ledger_id).first() if request.ledger_id else None
    project = db.query(Project).filter(Project.id == request.project_id).first() if request.project_id else None
    request.team_name = team.name if team else None
    request.ledger_name = ledger.name if ledger else None
    request.project_name = project.name if project else None
    return request


@router.get("/options", response_model=BindingOptionsResponse)
def get_binding_options(
    team_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BindingOptionsResponse:
    """返回提交绑定申请所需的团队、账套、项目下拉选项。"""
    teams = binding_request_service.get_visible_teams(db)
    ledgers = binding_request_service.get_visible_ledgers(db, team_id) if team_id else []
    projects = binding_request_service.get_visible_projects(db, team_id) if team_id else []
    return BindingOptionsResponse(
        teams=[BindingOptionResponse(id=team.id, name=team.name) for team in teams],
        ledgers=[BindingOptionResponse(id=ledger.id, name=ledger.name) for ledger in ledgers],
        projects=[BindingOptionResponse(id=project.id, name=project.name) for project in projects],
    )


@router.post("", response_model=BindingRequestResponse)
def create_binding_request(
    payload: BindingRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BindingRequestResponse:
    """提交绑定申请，不直接授予任何数据权限。"""
    try:
        request = binding_request_service.create_binding_request(
            db,
            requester_user_id=current_user.id,
            team_id=payload.team_id,
            ledger_id=payload.ledger_id,
            project_id=payload.project_id,
            requested_role=payload.requested_role,
            reason=payload.reason,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return build_binding_request_response(attach_display_names(db, request))


@router.get("", response_model=list[BindingRequestResponse])
def list_binding_requests(
    scope: str = Query(default="mine"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BindingRequestResponse]:
    """查询本人申请或当前用户可审批的申请。"""
    if scope not in {"mine", "reviewable"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="scope 只能是 mine 或 reviewable")
    requests = binding_request_service.list_binding_requests(db, current_user.id, scope)
    return [build_binding_request_response(attach_display_names(db, request)) for request in requests]


@router.post("/{request_id}/approve", response_model=BindingRequestResponse)
def approve_binding_request(
    request_id: int,
    payload: BindingRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BindingRequestResponse:
    """管理员审批通过申请，并写入正式授权关系。"""
    try:
        request = binding_request_service.approve_binding_request(
            db,
            request_id=request_id,
            reviewer_user_id=current_user.id,
            review_comment=payload.review_comment,
        )
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return build_binding_request_response(attach_display_names(db, request))


@router.post("/{request_id}/reject", response_model=BindingRequestResponse)
def reject_binding_request(
    request_id: int,
    payload: BindingRequestReview,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BindingRequestResponse:
    """管理员驳回申请，不写入任何授权关系。"""
    try:
        request = binding_request_service.reject_binding_request(
            db,
            request_id=request_id,
            reviewer_user_id=current_user.id,
            review_comment=payload.review_comment,
        )
    except PermissionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return build_binding_request_response(attach_display_names(db, request))
