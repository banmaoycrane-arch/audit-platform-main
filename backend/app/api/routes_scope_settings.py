"""账套 / 团队 / 项目 / 主体 管理配置 API。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.ledger import Ledger
from app.models.project import Project
from app.models.user import User
from app.models.user_ledger_auth import UserLedgerAuth
from app.services import ledger_management_service, scope_settings_service

router = APIRouter(prefix="/api/scope-settings", tags=["scope-settings"])


class LedgerSettingsUpdate(BaseModel):
    currency_mode: str | None = None
    base_currency: str | None = None
    balance_direction_rule: str | None = None
    account_code_pattern: str | None = None
    allow_custom_subjects: bool | None = None


class TeamSettingsUpdate(BaseModel):
    allow_multi_team_membership: bool | None = None
    require_binding_approval: bool | None = None
    default_ledger_role: str | None = None
    ledger_grant_policy: str | None = None
    team_roles_enabled: list[str] | None = None


class ProjectSettingsUpdate(BaseModel):
    allow_merge: bool | None = None
    allow_virtual_project: bool | None = None
    virtual_project_label: str | None = None
    require_manager_on_create: bool | None = None


class EntityScopeSettingsUpdate(BaseModel):
    allow_virtual_entity: bool | None = None
    require_tax_registration: bool | None = None
    default_entity_category: str | None = None
    allow_multi_entity_per_ledger: bool | None = None


def _patch_from_model(model: BaseModel) -> dict[str, Any]:
    return {k: v for k, v in model.model_dump().items() if v is not None}


def _require_ledger_admin(db: Session, user_id: int, ledger_id: int) -> None:
    if not ledger_management_service.user_has_ledger_access(db, user_id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账套")
    auth = (
        db.query(UserLedgerAuth)
        .filter(UserLedgerAuth.user_id == user_id, UserLedgerAuth.ledger_id == ledger_id)
        .first()
    )
    if auth is None or auth.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要账套管理员权限")


def _require_team_member(user: User, team_id: int) -> None:
    if user.team_id != team_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该团队")


def _require_project_access(db: Session, user_id: int, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if project.manager_id == user_id:
        return project
    from app.models.project_member import ProjectMember

    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if member is None and project.team_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user and user.team_id == project.team_id:
            return project
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    return project


def _require_project_manager(db: Session, user_id: int, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="项目不存在")
    if project.manager_id == user_id:
        return project
    from app.models.project_member import ProjectMember

    member = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
            ProjectMember.role == "manager",
        )
        .first()
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要项目负责人权限")
    return project


@router.get("/catalog")
def get_catalog() -> dict[str, Any]:
    """返回各作用域配置项说明，供前端渲染表单。"""
    return scope_settings_service.get_settings_catalog()


@router.get("/ledger/{ledger_id}")
def get_ledger_settings(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账套")
    return scope_settings_service.get_ledger_settings(db, ledger_id)


@router.put("/ledger/{ledger_id}")
def update_ledger_settings(
    ledger_id: int,
    payload: LedgerSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")
    _require_ledger_admin(db, current_user.id, ledger_id)
    return scope_settings_service.upsert_ledger_settings(
        db, ledger_id, _patch_from_model(payload)
    )


@router.get("/team/{team_id}")
def get_team_settings(
    team_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_team_member(current_user, team_id)
    return scope_settings_service.get_team_settings(db, team_id)


@router.put("/team/{team_id}")
def update_team_settings(
    team_id: int,
    payload: TeamSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_team_member(current_user, team_id)
    return scope_settings_service.upsert_team_settings(db, team_id, _patch_from_model(payload))


@router.get("/project/{project_id}")
def get_project_settings(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_project_access(db, current_user.id, project_id)
    return scope_settings_service.get_project_settings(db, project_id)


@router.put("/project/{project_id}")
def update_project_settings(
    project_id: int,
    payload: ProjectSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    _require_project_manager(db, current_user.id, project_id)
    return scope_settings_service.upsert_project_settings(
        db, project_id, _patch_from_model(payload)
    )


@router.get("/entity/{ledger_id}")
def get_entity_scope_settings(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该账套")
    return scope_settings_service.get_entity_scope_settings(db, ledger_id)


@router.put("/entity/{ledger_id}")
def update_entity_scope_settings(
    ledger_id: int,
    payload: EntityScopeSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="账套不存在")
    _require_ledger_admin(db, current_user.id, ledger_id)
    return scope_settings_service.upsert_entity_scope_settings(
        db, ledger_id, _patch_from_model(payload)
    )
