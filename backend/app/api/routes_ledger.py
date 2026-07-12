# -*- coding: utf-8 -*-
from typing import Any
"""
模块功能：账簿管理 API 路由
业务场景：前端调用创建账簿、切换账簿、授权用户、查询账簿列表
政策依据：会计信息系统内部控制规范——账簿隔离与权限管理
输入数据：HTTP 请求（JSON 或路径参数）
输出结果：账簿 JSON 数据
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建账簿管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from datetime import date
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.core.dependencies import get_current_user, get_current_ledger
from app.models.user_ledger_auth import UserLedgerAuth
from app.models.user import User
from app.models.ledger import Ledger
from app.services.shared import ledger_management_service
from app.services.auth import auth_service

router = APIRouter(prefix="/api/ledgers", tags=["ledgers"])


class CreateLedgerRequest(BaseModel):
    """创建账簿请求体"""
    team_id: int
    name: str
    accounting_start_date: date | None = Field(
        default=None,
        description="会计时间线起点，默认创建当天",
    )


class AuthUserRequest(BaseModel):
    """授权用户请求体"""
    user_id: int | None = None
    username: str | None = None
    phone: str | None = None
    role: str


class LedgerResponse(BaseModel):
    """账簿响应体"""
    id: int
    name: str
    team_id: int
    status: str
    activated_at: str | None
    suspended_at: str | None
    archived_at: str | None
    deleted_at: str | None
    lifecycle_reason: str | None
    accounting_start_date: str | None = None
    role: str | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """授权记录响应体"""
    id: int
    user_id: int
    ledger_id: int
    role: str
    username: str | None = None
    phone: str | None = None
    granted_at: str | None
    granted_by: int | None

    model_config = {"from_attributes": True}


def build_auth_response(db: Session, auth: UserLedgerAuth) -> AuthResponse:
    user = auth.user
    if user is None:
        user = db.query(User).filter(User.id == auth.user_id).first()
    if user is not None:
        user = auth_service.ensure_username(db, user)
    return AuthResponse(
        id=auth.id,
        user_id=auth.user_id,
        ledger_id=auth.ledger_id,
        role=auth.role,
        username=user.username if user else None,
        phone=user.phone if user else None,
        granted_at=str(auth.granted_at) if auth.granted_at else None,
        granted_by=auth.granted_by,
    )


class LifecycleReasonRequest(BaseModel):
    """生命周期变更原因请求体"""
    reason: str | None = None


class UpdateLedgerRequest(BaseModel):
    """更新账簿请求体"""
    name: str | None = None
    accounting_start_date: date | None = None


class DeleteLedgerResponse(BaseModel):
    """硬删除账簿响应体"""
    deleted: bool
    ledger_id: int


class InitializeLedgerResponse(BaseModel):
    """初始化账簿响应体"""
    ledger_id: int
    deleted_vouchers: int
    deleted_entries: int


def _require_ledger_admin(db: Session, current_user: User, ledger_id: int) -> UserLedgerAuth:
    auth = (
        db.query(UserLedgerAuth)
        .filter(UserLedgerAuth.user_id == current_user.id, UserLedgerAuth.ledger_id == ledger_id)
        .first()
    )
    if not auth or auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有 admin 可以执行此操作")
    return auth


def build_ledger_response(ledger: Ledger, role: str | None = None) -> LedgerResponse:
    return LedgerResponse(
        id=ledger.id,
        name=ledger.name,
        team_id=ledger.team_id,
        status=ledger.status,
        activated_at=str(ledger.activated_at) if ledger.activated_at else None,
        suspended_at=str(ledger.suspended_at) if ledger.suspended_at else None,
        archived_at=str(ledger.archived_at) if ledger.archived_at else None,
        deleted_at=str(ledger.deleted_at) if ledger.deleted_at else None,
        lifecycle_reason=ledger.lifecycle_reason,
        accounting_start_date=(
            ledger.accounting_start_date.isoformat()
            if ledger.accounting_start_date
            else None
        ),
        role=role,
    )


@router.post("", response_model=LedgerResponse)
def create_ledger(
    payload: CreateLedgerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerResponse:
    """
    创建账簿。

    需要 team_id 和 name。
    创建后自动给当前用户授权 admin 角色。
    """
    team = ledger_management_service.get_team_by_id(db, payload.team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="团队不存在")

    ledger = ledger_management_service.create_ledger(
        db,
        payload.team_id,
        payload.name,
        accounting_start_date=payload.accounting_start_date,
    )

    # 自动给创建者授权 admin
    ledger_management_service.authorize_user_to_ledger(
        db, ledger.id, current_user.id, "admin", granted_by=current_user.id
    )

    return build_ledger_response(ledger, role="admin")


@router.get("", response_model=list[LedgerResponse])
def list_user_ledgers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LedgerResponse]:
    """
    返回当前用户授权账簿列表。
    """
    auths = db.query(UserLedgerAuth).filter(UserLedgerAuth.user_id == current_user.id).all()
    if not auths:
        return []
    role_by_ledger_id = {auth.ledger_id: auth.role for auth in auths}
    ledgers = ledger_management_service.get_ledgers_by_user(db, current_user.id)
    return [build_ledger_response(ledger, role_by_ledger_id.get(ledger.id)) for ledger in ledgers]


@router.put("/{ledger_id}", response_model=LedgerResponse)
def update_ledger_endpoint(
    ledger_id: int,
    payload: UpdateLedgerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerResponse:
    """更新账簿名称或会计时间线起点（仅 admin）。"""
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    auth = _require_ledger_admin(db, current_user, ledger_id)

    if payload.name is None and payload.accounting_start_date is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少提供一个待更新字段")

    try:
        updated = ledger_management_service.update_ledger(
            db,
            ledger_id,
            name=payload.name,
            accounting_start_date=payload.accounting_start_date,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return build_ledger_response(updated, role=auth.role)


@router.post("/{ledger_id}/delete", response_model=DeleteLedgerResponse)
def delete_ledger_endpoint(
    ledger_id: int,
    payload: LifecycleReasonRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DeleteLedgerResponse:
    """硬删除账簿（仅 admin）：物理清除关联数据，不可恢复。"""
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    _require_ledger_admin(db, current_user, ledger_id)

    try:
        result = ledger_management_service.delete_ledger(
            db,
            ledger_id,
            reason=payload.reason if payload else None,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return DeleteLedgerResponse(deleted=bool(result["deleted"]), ledger_id=int(result["ledger_id"]))


@router.post("/{ledger_id}/initialize", response_model=InitializeLedgerResponse)
def initialize_ledger_endpoint(
    ledger_id: int,
    payload: LifecycleReasonRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InitializeLedgerResponse:
    """初始化账簿（仅 admin）：删除全部凭证与分录，保留科目、期间、设置与授权。"""
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    _require_ledger_admin(db, current_user, ledger_id)

    try:
        result = ledger_management_service.initialize_ledger(
            db,
            ledger_id,
            reason=payload.reason if payload else None,
        )
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return InitializeLedgerResponse(
        ledger_id=int(result["ledger_id"]),
        deleted_vouchers=int(result["deleted_vouchers"]),
        deleted_entries=int(result["deleted_entries"]),
    )


@router.post("/{ledger_id}/switch")
def switch_ledger(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    切换账簿。

    更新 user.last_ledger_id。
    验证用户是否有该账簿访问权限。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")

    ledger_management_service.switch_ledger(db, current_user.id, ledger_id)

    return {"message": "账簿切换成功", "ledger_id": ledger_id}


@router.post("/{ledger_id}/auth")
def authorize_user(
    ledger_id: int,
    payload: AuthUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    授权用户访问账簿。

    需要 user_id 和 role。
    当前用户必须对该账簿有 admin 权限才能授权他人。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    # 检查当前用户是否有 admin 权限
    current_auth = (
        db.query(UserLedgerAuth)
        .filter(UserLedgerAuth.user_id == current_user.id, UserLedgerAuth.ledger_id == ledger_id)
        .first()
    )
    if not current_auth or current_auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有 admin 可以授权其他用户")

    if not payload.user_id and not payload.username and not payload.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供 user_id、username 或 phone 中的任意一项",
        )

    target_user = ledger_management_service.get_user_by_identifier(
        db,
        user_id=payload.user_id,
        username=payload.username,
        phone=payload.phone,
    )
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

    target_user = auth_service.ensure_username(db, target_user)

    auth = ledger_management_service.authorize_user_to_ledger(
        db, ledger_id, target_user.id, payload.role, granted_by=current_user.id
    )

    return {
        "message": "授权成功",
        "user_id": auth.user_id,
        "username": target_user.username,
        "ledger_id": auth.ledger_id,
        "role": auth.role,
    }


@router.post("/{ledger_id}/activate", response_model=LedgerResponse)
def activate_ledger_endpoint(
    ledger_id: int,
    payload: LifecycleReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerResponse:
    """
    激活账簿。

    将账簿状态设置为 active。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")

    updated = ledger_management_service.activate_ledger(db, ledger_id, reason=payload.reason)
    return LedgerResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        status=updated.status,
        activated_at=str(updated.activated_at) if updated.activated_at else None,
        suspended_at=str(updated.suspended_at) if updated.suspended_at else None,
        archived_at=str(updated.archived_at) if updated.archived_at else None,
        deleted_at=str(updated.deleted_at) if updated.deleted_at else None,
        lifecycle_reason=updated.lifecycle_reason,
    )


@router.post("/{ledger_id}/suspend", response_model=LedgerResponse)
def suspend_ledger_endpoint(
    ledger_id: int,
    payload: LifecycleReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerResponse:
    """
    暂停账簿。

    将账簿状态设置为 suspended，暂停期间禁止新增凭证。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")

    updated = ledger_management_service.suspend_ledger(db, ledger_id, reason=payload.reason)
    return LedgerResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        status=updated.status,
        activated_at=str(updated.activated_at) if updated.activated_at else None,
        suspended_at=str(updated.suspended_at) if updated.suspended_at else None,
        archived_at=str(updated.archived_at) if updated.archived_at else None,
        deleted_at=str(updated.deleted_at) if updated.deleted_at else None,
        lifecycle_reason=updated.lifecycle_reason,
    )


@router.post("/{ledger_id}/archive", response_model=LedgerResponse)
def archive_ledger_endpoint(
    ledger_id: int,
    payload: LifecycleReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerResponse:
    """
    归档账簿。

    将账簿状态设置为 archived，归档后进入只读状态。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")

    updated = ledger_management_service.archive_ledger(db, ledger_id, reason=payload.reason)
    return LedgerResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        status=updated.status,
        activated_at=str(updated.activated_at) if updated.activated_at else None,
        suspended_at=str(updated.suspended_at) if updated.suspended_at else None,
        archived_at=str(updated.archived_at) if updated.archived_at else None,
        deleted_at=str(updated.deleted_at) if updated.deleted_at else None,
        lifecycle_reason=updated.lifecycle_reason,
    )


@router.post("/{ledger_id}/restore", response_model=LedgerResponse)
def restore_ledger_endpoint(
    ledger_id: int,
    payload: LifecycleReasonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> LedgerResponse:
    """
    恢复账簿。

    将 suspended 或 archived 状态的账簿恢复为 active。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")

    updated = ledger_management_service.restore_ledger(db, ledger_id, reason=payload.reason)
    return LedgerResponse(
        id=updated.id,
        name=updated.name,
        team_id=updated.team_id,
        status=updated.status,
        activated_at=str(updated.activated_at) if updated.activated_at else None,
        suspended_at=str(updated.suspended_at) if updated.suspended_at else None,
        archived_at=str(updated.archived_at) if updated.archived_at else None,
        deleted_at=str(updated.deleted_at) if updated.deleted_at else None,
        lifecycle_reason=updated.lifecycle_reason,
    )


@router.get("/{ledger_id}/auths", response_model=list[AuthResponse])
def list_ledger_auths(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[AuthResponse]:
    """
    查询账簿授权列表。

    返回该账簿下所有用户的授权记录。
    当前用户必须对该账簿有访问权限才能查询。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账簿")

    auths = (
        db.query(UserLedgerAuth)
        .options(joinedload(UserLedgerAuth.user))
        .filter(UserLedgerAuth.ledger_id == ledger_id)
        .all()
    )
    return [build_auth_response(db, auth) for auth in auths]


@router.delete("/{ledger_id}/auths/{auth_id}")
def revoke_ledger_auth(
    ledger_id: int,
    auth_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    撤销账簿授权。

    删除指定授权记录。
    当前用户必须对该账簿有 admin 权限才能撤销授权。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账簿不存在")

    # 检查当前用户是否有 admin 权限
    current_auth = (
        db.query(UserLedgerAuth)
        .filter(UserLedgerAuth.user_id == current_user.id, UserLedgerAuth.ledger_id == ledger_id)
        .first()
    )
    if not current_auth or current_auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有 admin 可以撤销授权")

    try:
        auth = ledger_management_service.revoke_ledger_auth(db, auth_id, ledger_id=ledger_id)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    return {
        "message": "授权撤销成功",
        "auth_id": auth.id,
        "user_id": auth.user_id,
        "ledger_id": auth.ledger_id,
    }
