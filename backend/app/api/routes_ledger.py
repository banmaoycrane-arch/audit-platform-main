# -*- coding: utf-8 -*-
"""
模块功能：账套管理 API 路由
业务场景：前端调用创建账套、切换账套、授权用户、查询账套列表
政策依据：会计信息系统内部控制规范——账套隔离与权限管理
输入数据：HTTP 请求（JSON 或路径参数）
输出结果：账套 JSON 数据
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建账套管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user, get_current_ledger
from app.models.user_ledger_auth import UserLedgerAuth
from app.models.user import User
from app.models.ledger import Ledger
from app.services import ledger_management_service

router = APIRouter(prefix="/api/ledgers", tags=["ledgers"])


class CreateLedgerRequest(BaseModel):
    """创建账套请求体"""
    team_id: int
    name: str


class AuthUserRequest(BaseModel):
    """授权用户请求体"""
    user_id: int
    role: str


class LedgerResponse(BaseModel):
    """账套响应体"""
    id: int
    name: str
    team_id: int
    status: str
    activated_at: str | None
    suspended_at: str | None
    archived_at: str | None
    deleted_at: str | None
    lifecycle_reason: str | None
    role: str | None = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """授权记录响应体"""
    id: int
    user_id: int
    ledger_id: int
    role: str
    granted_at: str | None
    granted_by: int | None

    model_config = {"from_attributes": True}


class LifecycleReasonRequest(BaseModel):
    """生命周期变更原因请求体"""
    reason: str | None = None


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
        role=role,
    )


@router.post("", response_model=LedgerResponse)
def create_ledger(
    payload: CreateLedgerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Ledger:
    """
    创建账套。

    需要 team_id 和 name。
    创建后自动给当前用户授权 admin 角色。
    """
    team = ledger_management_service.get_team_by_id(db, payload.team_id)
    if not team:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="团队不存在")

    ledger = ledger_management_service.create_ledger(db, payload.team_id, payload.name)

    # 自动给创建者授权 admin
    ledger_management_service.authorize_user_to_ledger(
        db, ledger.id, current_user.id, "admin", granted_by=current_user.id
    )

    return ledger


@router.get("", response_model=list[LedgerResponse])
def list_user_ledgers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LedgerResponse]:
    """
    返回当前用户授权账套列表。
    """
    auths = db.query(UserLedgerAuth).filter(UserLedgerAuth.user_id == current_user.id).all()
    if not auths:
        return []
    role_by_ledger_id = {auth.ledger_id: auth.role for auth in auths}
    ledgers = ledger_management_service.get_ledgers_by_user(db, current_user.id)
    return [build_ledger_response(ledger, role_by_ledger_id.get(ledger.id)) for ledger in ledgers]


@router.post("/{ledger_id}/switch")
def switch_ledger(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    切换账套。

    更新 user.last_ledger_id。
    验证用户是否有该账套访问权限。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账套")

    ledger_management_service.switch_ledger(db, current_user.id, ledger_id)

    return {"message": "账套切换成功", "ledger_id": ledger_id}


@router.post("/{ledger_id}/auth")
def authorize_user(
    ledger_id: int,
    payload: AuthUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    授权用户访问账套。

    需要 user_id 和 role。
    当前用户必须对该账套有 admin 权限才能授权他人。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    # 检查当前用户是否有 admin 权限
    current_auth = (
        db.query(UserLedgerAuth)
        .filter(UserLedgerAuth.user_id == current_user.id, UserLedgerAuth.ledger_id == ledger_id)
        .first()
    )
    if not current_auth or current_auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有 admin 可以授权其他用户")

    auth = ledger_management_service.authorize_user_to_ledger(
        db, ledger_id, payload.user_id, payload.role, granted_by=current_user.id
    )

    return {
        "message": "授权成功",
        "user_id": auth.user_id,
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
    激活账套。

    将账套状态设置为 active。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账套")

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
    暂停账套。

    将账套状态设置为 suspended，暂停期间禁止新增凭证。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账套")

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
    归档账套。

    将账套状态设置为 archived，归档后进入只读状态。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账套")

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
    恢复账套。

    将 suspended 或 archived 状态的账套恢复为 active。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账套")

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
    查询账套授权列表。

    返回该账套下所有用户的授权记录。
    当前用户必须对该账套有访问权限才能查询。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账套")

    auths = ledger_management_service.get_ledger_auths(db, ledger_id)
    return [
        AuthResponse(
            id=auth.id,
            user_id=auth.user_id,
            ledger_id=auth.ledger_id,
            role=auth.role,
            granted_at=str(auth.granted_at) if auth.granted_at else None,
            granted_by=auth.granted_by,
        )
        for auth in auths
    ]


@router.delete("/{ledger_id}/auths/{auth_id}")
def revoke_ledger_auth(
    ledger_id: int,
    auth_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    撤销账套授权。

    删除指定授权记录。
    当前用户必须对该账套有 admin 权限才能撤销授权。
    """
    ledger = ledger_management_service.get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")

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
