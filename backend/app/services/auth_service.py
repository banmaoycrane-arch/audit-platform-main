from datetime import datetime, timedelta
from secrets import randbelow

from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.user import User
from app.core.security import get_password_hash, verify_password
from app.db.models import Entity, SmsVerificationCode
from app.models.user_ledger_auth import UserLedgerAuth
from app.services import ledger_management_service, project_service


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_phone(db: Session, phone: str) -> User | None:
    return db.query(User).filter(User.phone == phone).first()


def register_user(
    db: Session,
    username: str | None,
    phone: str | None,
    password: str,
    agreed_terms: bool,
    agreed_privacy: bool,
) -> User:
    hashed = get_password_hash(password)
    user = User(
        username=username,
        phone=phone,
        hashed_password=hashed,
        agreed_terms=agreed_terms,
        agreed_privacy=agreed_privacy,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_password_login_user(db: Session, username: str) -> User | None:
    return db.query(User).filter(
        or_(User.username == username, User.phone == username)
    ).first()


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = get_password_login_user(db, username)
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


SMS_CODE_TTL_MINUTES = 5


def get_sms_code(db: Session, phone: str) -> str:
    code = f"{randbelow(1_000_000):06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=SMS_CODE_TTL_MINUTES)
    db.query(SmsVerificationCode).filter(
        SmsVerificationCode.phone == phone,
        SmsVerificationCode.consumed.is_(False),
    ).update({"consumed": True})
    db.add(SmsVerificationCode(phone=phone, code=code, expires_at=expires_at))
    db.commit()
    return code


def verify_sms_code(db: Session, phone: str, code: str) -> bool:
    verification = (
        db.query(SmsVerificationCode)
        .filter(
            SmsVerificationCode.phone == phone,
            SmsVerificationCode.code == code,
            SmsVerificationCode.consumed.is_(False),
            SmsVerificationCode.expires_at >= datetime.utcnow(),
        )
        .order_by(SmsVerificationCode.created_at.desc())
        .first()
    )
    if verification is None:
        return False
    verification.consumed = True
    db.add(verification)
    db.commit()
    return True


def authenticate_user_by_sms(db: Session, phone: str, code: str) -> User | None:
    if not verify_sms_code(db, phone, code):
        return None
    user = get_user_by_phone(db, phone)
    if not user:
        # 如果手机号未注册，检查是否有其他账号需要关联手机号
        # 这种情况通常不会发生，因为密码登录时同时支持用户名和手机号
        # 但保留此逻辑以防万一
        user = User(
            phone=phone,
            is_active=True,
            agreed_terms=True,
            agreed_privacy=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def set_user_password(db: Session, user: User, password: str) -> User:
    user.hashed_password = get_password_hash(password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_auth_context(db: Session, user: User) -> dict:
    """
    功能描述：汇总用户进入系统前必须确认的团队、账簿、项目和会计主体上下文。
    业务逻辑：用真实团队、账簿、项目授权关系判断当前用户是否已完成首次登录引导。
    会计口径：账簿和会计主体决定凭证、报表、审计证据的归属，未确认前不得自动合并历史资料。

    Args:
        db: 数据库会话。
        user: 当前登录用户。

    Returns:
        dict: 用户上下文、缺失绑定项、下一步动作和开发占位边界。

    注意事项：
        1. historical_candidates 仅返回占位结构，不自动认领或并入当前账簿。
    """
    teams = ledger_management_service.get_teams_by_user(db, user.id)
    ledgers = ledger_management_service.get_ledgers_by_user(db, user.id)
    projects = project_service.list_projects_by_user(db, user.id)

    current_ledger_id = user.last_ledger_id
    if current_ledger_id and not any(ledger.id == current_ledger_id for ledger in ledgers):
        current_ledger_id = None
    if not current_ledger_id and ledgers:
        current_ledger_id = ledgers[0].id

    accounting_entities = []
    if ledgers:
        ledger_ids = [ledger.id for ledger in ledgers]
        accounting_entities = (
            db.query(Entity)
            .filter(Entity.ledger_id.in_(ledger_ids), Entity.is_accounting_entity.is_(True))
            .all()
        )

    missing_bindings = []
    if not teams:
        missing_bindings.append("team")
    if not ledgers:
        missing_bindings.append("ledger")
    if not projects:
        missing_bindings.append("project")
    if not accounting_entities:
        missing_bindings.append("accounting_entity")

    if "team" in missing_bindings:
        next_action = "create_team"
    elif "ledger" in missing_bindings:
        next_action = "select_or_create_ledger"
    elif "project" in missing_bindings:
        next_action = "select_or_create_project"
    elif "accounting_entity" in missing_bindings:
        next_action = "confirm_accounting_entity"
    else:
        next_action = "workspace"

    current_ledger_role = None
    current_team_type = None
    can_use_ledger_without_project = False
    if current_ledger_id:
        current_ledger = next((ledger for ledger in ledgers if ledger.id == current_ledger_id), None)
        current_team = next((team for team in teams if current_ledger and team.id == current_ledger.team_id), None)
        current_auth = (
            db.query(UserLedgerAuth)
            .filter(UserLedgerAuth.user_id == user.id, UserLedgerAuth.ledger_id == current_ledger_id)
            .first()
        )
        current_ledger_role = current_auth.role if current_auth else None
        current_team_type = current_team.type if current_team else None
        can_use_ledger_without_project = (
            current_team_type == "enterprise"
            and current_ledger_role in {"accountant", "admin"}
        )

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "phone": user.phone,
            "email": user.email,
            "has_password": bool(user.hashed_password),
        },
        "teams": [
            {
                "id": team.id,
                "name": team.name,
                "type": team.type,
                "created_at": str(team.created_at) if team.created_at else None,
            }
            for team in teams
        ],
        "ledgers": [
            {
                "id": ledger.id,
                "name": ledger.name,
                "team_id": ledger.team_id,
                "status": ledger.status,
                "activated_at": str(ledger.activated_at) if ledger.activated_at else None,
                "suspended_at": str(ledger.suspended_at) if ledger.suspended_at else None,
                "archived_at": str(ledger.archived_at) if ledger.archived_at else None,
                "deleted_at": str(ledger.deleted_at) if ledger.deleted_at else None,
                "lifecycle_reason": ledger.lifecycle_reason,
            }
            for ledger in ledgers
        ],
        "projects": [
            {
                "id": project.id,
                "name": project.name,
                "team_id": project.team_id,
                "type": project.type,
                "status": project.status,
                "start_date": str(project.start_date) if project.start_date else None,
                "end_date": str(project.end_date) if project.end_date else None,
                "manager_id": project.manager_id,
                "created_at": str(project.created_at) if project.created_at else None,
                "updated_at": str(project.updated_at) if project.updated_at else None,
            }
            for project in projects
        ],
        "current_ledger_id": current_ledger_id,
        "current_ledger_role": current_ledger_role,
        "current_team_type": current_team_type,
        "can_use_ledger_without_project": can_use_ledger_without_project,
        "missing_bindings": missing_bindings,
        "requires_onboarding": next_action != "workspace",
        "next_action": next_action,
        "temporary_status": "onboarding_pending" if next_action != "workspace" else "ready",
        "historical_candidates": [],
        "mock_boundaries": {
            "sms_code": "development_mock",
            "terms": "placeholder",
            "privacy": "placeholder",
            "onboarding_data": "real_api",
        },
    }
