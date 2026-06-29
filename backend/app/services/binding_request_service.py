# -*- coding: utf-8 -*-
"""
模块功能：用户绑定申请服务
业务场景：访客用户提交绑定申请，管理员审批后写入团队、账簿、项目授权关系
政策依据：会计信息系统内部控制规范——权限申请、审批、授权三步分离
输入数据：申请人、团队ID、账簿ID、项目ID、角色、审批意见
输出结果：绑定申请记录和正式授权关系
创建日期：2026-06-20
更新记录：
    2026-06-20  初始创建绑定申请服务
"""
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.binding_request import BindingRequest
from app.models.ledger import Ledger
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.team import Team
from app.models.user import User
from app.models.user_ledger_auth import UserLedgerAuth
from app.services import ledger_management_service, project_service, platform_permission_service

VALID_REQUEST_ROLES = {"viewer", "accountant", "admin"}
PROJECT_ROLE_BY_REQUEST_ROLE = {
    "viewer": "viewer",
    "accountant": "member",
    "admin": "manager",
}


def get_visible_teams(db: Session) -> list[Team]:
    """
    功能描述：返回可供用户申请加入的团队清单。
    业务逻辑：团队名称属于公共申请入口信息，不返回账簿、项目等隔离数据。
    会计口径：未获授权用户只能看到可申请对象，不能看到团队内部财务数据。
    """
    return db.query(Team).order_by(Team.created_at.desc()).all()


def get_visible_ledgers(db: Session, team_id: int) -> list[Ledger]:
    """
    功能描述：返回指定团队下可申请访问的账簿名称清单。
    业务逻辑：仅用于提交申请，不返回凭证、期间、报表等账簿数据。
    会计口径：账簿名称可作为授权申请对象，账簿内容仍保持隔离。
    """
    return db.query(Ledger).filter(Ledger.team_id == team_id).order_by(Ledger.created_at.desc()).all()


def get_visible_projects(db: Session, team_id: int) -> list[Project]:
    """
    功能描述：返回指定团队下可申请关联的项目名称清单。
    业务逻辑：仅用于申请选择项目，不返回项目底层业务数据。
    会计口径：项目作为工作任务边界，可被申请加入，但正式数据需审批后访问。
    """
    return db.query(Project).filter(Project.team_id == team_id).order_by(Project.created_at.desc()).all()


def user_can_review_team(db: Session, reviewer_user_id: int, team_id: int) -> bool:
    """
    功能描述：判断当前用户是否可审批指定团队的绑定申请。
    业务逻辑：团队创建者/归属用户或团队下任一账簿 admin 可审批。
    会计口径：审批人必须已在该团队或账簿权限范围内，避免越权授权。
    """
    reviewer = db.query(User).filter(User.id == reviewer_user_id).first()
    if platform_permission_service.is_super_admin(reviewer):
        return True
    if reviewer and reviewer.team_id == team_id:
        return True

    ledger_ids = [ledger.id for ledger in db.query(Ledger).filter(Ledger.team_id == team_id).all()]
    if not ledger_ids:
        return False
    admin_auth = (
        db.query(UserLedgerAuth)
        .filter(
            UserLedgerAuth.user_id == reviewer_user_id,
            UserLedgerAuth.ledger_id.in_(ledger_ids),
            UserLedgerAuth.role == "admin",
        )
        .first()
    )
    return admin_auth is not None


def create_binding_request(
    db: Session,
    requester_user_id: int,
    team_id: int,
    requested_role: str,
    ledger_id: int | None = None,
    project_id: int | None = None,
    reason: str | None = None,
) -> BindingRequest:
    """
    功能描述：提交绑定申请。
    业务逻辑：校验团队、账簿、项目归属一致；同一目标已有待审批申请时复用并更新。
    会计口径：申请不会直接授予数据访问权，必须等待管理员审批。
    """
    if requested_role not in VALID_REQUEST_ROLES:
        raise ValueError("申请角色只能是查看、记账或管理")

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise ValueError("申请团队不存在")

    if ledger_id:
        ledger = db.query(Ledger).filter(Ledger.id == ledger_id).first()
        if not ledger or ledger.team_id != team_id:
            raise ValueError("申请账簿不属于所选团队")

    if project_id:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project or project.team_id != team_id:
            raise ValueError("申请项目不属于所选团队")

    existing_query = db.query(BindingRequest).filter(
        BindingRequest.requester_user_id == requester_user_id,
        BindingRequest.team_id == team_id,
        BindingRequest.status == "pending",
    )
    if ledger_id is None:
        existing_query = existing_query.filter(BindingRequest.ledger_id.is_(None))
    else:
        existing_query = existing_query.filter(BindingRequest.ledger_id == ledger_id)
    if project_id is None:
        existing_query = existing_query.filter(BindingRequest.project_id.is_(None))
    else:
        existing_query = existing_query.filter(BindingRequest.project_id == project_id)
    existing = existing_query.first()
    if existing:
        existing.requested_role = requested_role
        existing.reason = reason
        db.commit()
        db.refresh(existing)
        return existing

    binding_request = BindingRequest(
        requester_user_id=requester_user_id,
        team_id=team_id,
        ledger_id=ledger_id,
        project_id=project_id,
        requested_role=requested_role,
        reason=reason,
        status="pending",
    )
    db.add(binding_request)
    db.commit()
    db.refresh(binding_request)
    return binding_request


def list_binding_requests(db: Session, current_user_id: int, scope: str) -> list[BindingRequest]:
    """
    功能描述：查询绑定申请。
    业务逻辑：scope=mine 返回本人申请；scope=reviewable 返回本人可审批的团队申请。
    会计口径：申请单属于权限资料，不展示账簿内业务数据。
    """
    if scope == "mine":
        return (
            db.query(BindingRequest)
            .filter(BindingRequest.requester_user_id == current_user_id)
            .order_by(BindingRequest.created_at.desc())
            .all()
        )

    requests = db.query(BindingRequest).order_by(BindingRequest.created_at.desc()).all()
    reviewer = db.query(User).filter(User.id == current_user_id).first()
    if platform_permission_service.is_super_admin(reviewer):
        return requests
    return [request for request in requests if user_can_review_team(db, current_user_id, request.team_id)]


def approve_binding_request(
    db: Session,
    request_id: int,
    reviewer_user_id: int,
    review_comment: str | None = None,
) -> BindingRequest:
    """
    功能描述：审批通过绑定申请并写入正式授权关系。
    业务逻辑：通过后写入用户团队、账簿授权、项目成员；最后更新申请状态。
    会计口径：只有审批通过后，用户刷新上下文才可看到对应账簿隔离数据。
    """
    binding_request = db.query(BindingRequest).filter(BindingRequest.id == request_id).first()
    if not binding_request:
        raise ValueError("绑定申请不存在")
    if binding_request.status != "pending":
        raise ValueError("该申请已处理，不能重复审批")
    if not user_can_review_team(db, reviewer_user_id, binding_request.team_id):
        raise PermissionError("无权审批该团队的绑定申请")

    requester = db.query(User).filter(User.id == binding_request.requester_user_id).first()
    if not requester:
        raise ValueError("申请用户不存在")

    requester.team_id = binding_request.team_id

    if binding_request.ledger_id:
        ledger_management_service.authorize_user_to_ledger(
            db,
            binding_request.ledger_id,
            binding_request.requester_user_id,
            binding_request.requested_role,
            granted_by=reviewer_user_id,
        )
        if not requester.last_ledger_id:
            requester.last_ledger_id = binding_request.ledger_id

    if binding_request.project_id:
        project_role = PROJECT_ROLE_BY_REQUEST_ROLE[binding_request.requested_role]
        project_service.assign_member_to_project(
            db,
            binding_request.project_id,
            binding_request.requester_user_id,
            role=project_role,
        )

    binding_request.status = "approved"
    binding_request.reviewer_user_id = reviewer_user_id
    binding_request.review_comment = review_comment
    binding_request.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(binding_request)
    return binding_request


def reject_binding_request(
    db: Session,
    request_id: int,
    reviewer_user_id: int,
    review_comment: str | None = None,
) -> BindingRequest:
    """
    功能描述：驳回绑定申请。
    业务逻辑：仅更新申请状态，不写入任何授权关系。
    会计口径：驳回后用户仍保持访客/待绑定状态，不能查看隔离数据。
    """
    binding_request = db.query(BindingRequest).filter(BindingRequest.id == request_id).first()
    if not binding_request:
        raise ValueError("绑定申请不存在")
    if binding_request.status != "pending":
        raise ValueError("该申请已处理，不能重复审批")
    if not user_can_review_team(db, reviewer_user_id, binding_request.team_id):
        raise PermissionError("无权审批该团队的绑定申请")

    binding_request.status = "rejected"
    binding_request.reviewer_user_id = reviewer_user_id
    binding_request.review_comment = review_comment
    binding_request.reviewed_at = datetime.utcnow()
    db.commit()
    db.refresh(binding_request)
    return binding_request
