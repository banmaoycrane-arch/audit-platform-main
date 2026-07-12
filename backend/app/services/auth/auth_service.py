# -*- coding: utf-8 -*-
"""
模块功能：用户认证服务
业务场景：用户注册、登录、密码管理、身份验证
政策依据：会计信息系统内部控制要求，用户认证必须安全可靠
输入数据：用户名、密码、手机号、验证码
输出结果：用户对象、认证上下文
创建日期：2026-06-01
更新记录：
    2025-01-20  封装为 AuthService 类
"""
from datetime import datetime, timezone, timedelta
from secrets import randbelow, token_hex
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.user import User
from app.core.config import get_settings
from app.core.security import get_password_hash, verify_password
from app.db.models import Entity, SmsVerificationCode
from app.models.user_ledger_auth import UserLedgerAuth
from app.services.shared.project_service import list_projects_by_user
from app.services.shared.ledger_management_service import get_teams_by_user, get_ledgers_by_user
from app.services.auth.platform_permission_service import is_super_admin, SUPER_ADMIN_ROLE


class AuthService:
    """
    用户认证服务
    
    功能描述：处理用户注册、登录、密码管理、身份验证等认证相关操作
    业务逻辑：支持用户名密码登录和手机号验证码登录
    会计口径：认证服务不参与具体会计核算，仅提供身份验证
    
    注意事项：
        1. SMS_CODE_TTL_MINUTES 控制验证码有效期
        2. 超级管理员通过配置文件指定
    """
    
    SMS_CODE_TTL_MINUTES = 5
    
    def get_user_by_id(self, db: Session, user_id: int) -> User | None:
        return db.query(User).filter(User.id == user_id).first()

    def get_user_by_username(self, db: Session, username: str) -> User | None:
        return db.query(User).filter(User.username == username).first()

    def get_user_by_phone(self, db: Session, phone: str) -> User | None:
        return db.query(User).filter(User.phone == phone).first()

    def _split_config_values(self, value: str) -> set[str]:
        return {item.strip() for item in value.split(",") if item.strip()}

    def sync_configured_super_admin(self, db: Session, user: User) -> User:
        settings = get_settings()
        configured_usernames = self._split_config_values(settings.super_admin_usernames)
        configured_phones = self._split_config_values(settings.super_admin_phones)
        if (user.username and user.username in configured_usernames) or (user.phone and user.phone in configured_phones):
            if getattr(user, "platform_role", "user") != SUPER_ADMIN_ROLE:
                user.platform_role = SUPER_ADMIN_ROLE
                db.add(user)
                db.commit()
                db.refresh(user)
        return user

    def ensure_username(self, db: Session, user: User) -> User:
        """为缺少用户名的账号分配唯一 username（短信注册等场景）。"""
        if user.username and user.username.strip():
            return user
        for _ in range(32):
            candidate = f"user_{token_hex(4)}"
            if not self.get_user_by_username(db, candidate):
                user.username = candidate
                db.add(user)
                db.commit()
                db.refresh(user)
                return user
        raise RuntimeError("无法生成唯一用户名")

    def register_user(
        self,
        db: Session,
        username: str | None,
        phone: str | None,
        password: str,
        agreed_terms: bool,
        agreed_privacy: bool,
    ) -> User:
        """
        注册新用户
        
        Args:
            db: 数据库会话
            username: 用户名（可选）
            phone: 手机号（可选）
            password: 密码
            agreed_terms: 是否同意服务条款
            agreed_privacy: 是否同意隐私政策
            
        Returns:
            User: 新注册的用户对象
        """
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
        user = self.ensure_username(db, user)
        return self.sync_configured_super_admin(db, user)

    def get_password_login_user(self, db: Session, username: str) -> User | None:
        return db.query(User).filter(
            or_(User.username == username, User.phone == username)
        ).first()

    def authenticate_user(self, db: Session, username: str, password: str) -> User | None:
        """
        通过用户名和密码认证用户
        
        Args:
            db: 数据库会话
            username: 用户名或手机号
            password: 密码
            
        Returns:
            User | None: 认证成功返回用户对象，失败返回 None
        """
        user = self.get_password_login_user(db, username)
        if not user or not user.hashed_password:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return self.sync_configured_super_admin(db, user)

    def get_sms_code(self, db: Session, phone: str) -> str:
        """
        生成并保存短信验证码
        
        Args:
            db: 数据库会话
            phone: 手机号
            
        Returns:
            str: 6位验证码
        """
        code = f"{randbelow(1_000_000):06d}"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.SMS_CODE_TTL_MINUTES)
        db.query(SmsVerificationCode).filter(
            SmsVerificationCode.phone == phone,
            SmsVerificationCode.consumed.is_(False),
        ).update({"consumed": True})
        db.add(SmsVerificationCode(phone=phone, code=code, expires_at=expires_at))
        db.commit()
        return code

    def verify_sms_code(self, db: Session, phone: str, code: str) -> bool:
        """
        验证短信验证码
        
        Args:
            db: 数据库会话
            phone: 手机号
            code: 验证码
            
        Returns:
            bool: 验证是否通过
        """
        verification = (
            db.query(SmsVerificationCode)
            .filter(
                SmsVerificationCode.phone == phone,
                SmsVerificationCode.code == code,
                SmsVerificationCode.consumed.is_(False),
                SmsVerificationCode.expires_at >= datetime.now(timezone.utc),
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

    def authenticate_user_by_sms(self, db: Session, phone: str, code: str) -> User | None:
        """
        通过短信验证码认证用户
        
        Args:
            db: 数据库会话
            phone: 手机号
            code: 验证码
            
        Returns:
            User | None: 认证成功返回用户对象，失败返回 None
        """
        if not self.verify_sms_code(db, phone, code):
            return None
        user = self.get_user_by_phone(db, phone)
        if not user:
            user = User(
                phone=phone,
                is_active=True,
                agreed_terms=True,
                agreed_privacy=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            user = self.ensure_username(db, user)
        return self.sync_configured_super_admin(db, user)

    def set_user_password(self, db: Session, user: User, password: str) -> User:
        """
        设置用户密码
        
        Args:
            db: 数据库会话
            user: 用户对象
            password: 新密码
            
        Returns:
            User: 更新后的用户对象
        """
        user.hashed_password = get_password_hash(password)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def update_user_profile(
        self,
        db: Session,
        user: User,
        username: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> User:
        """
        更新当前用户的基本资料
        
        Args:
            db: 数据库会话
            user: 当前登录用户
            username: 新用户名（可选）
            phone: 新手机号（可选）
            email: 新邮箱（可选）
            
        Returns:
            User: 更新后的用户对象
            
        注意事项：
            1. 用户名、手机号、邮箱若已存在且不属于当前用户，则抛出业务异常
            2. 空字符串会被视为未提供，不做更新
        """
        if username is not None and username.strip():
            existing = self.get_user_by_username(db, username.strip())
            if existing and existing.id != user.id:
                raise ValueError("用户名已被其他账号使用")
            user.username = username.strip()

        if phone is not None and phone.strip():
            existing = self.get_user_by_phone(db, phone.strip())
            if existing and existing.id != user.id:
                raise ValueError("手机号已被其他账号使用")
            user.phone = phone.strip()

        if email is not None and email.strip():
            existing = db.query(User).filter(User.email == email.strip()).first()
            if existing and existing.id != user.id:
                raise ValueError("邮箱已被其他账号使用")
            user.email = email.strip()

        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def get_auth_context(self, db: Session, user: User) -> dict[str, Any]:
        """
        汇总用户进入系统前必须确认的团队、账簿、项目和会计主体上下文
        
        Args:
            db: 数据库会话
            user: 当前登录用户
            
        Returns:
            dict: 用户上下文、缺失绑定项、下一步动作和开发占位边界
            
        会计口径：账簿和会计主体决定凭证、报表、审计证据的归属，未确认前不得自动合并历史资料
        
        注意事项：
            1. historical_candidates 仅返回占位结构，不自动认领或并入当前账簿
        """
        teams = get_teams_by_user(db, user.id)
        ledgers = get_ledgers_by_user(db, user.id)
        projects = list_projects_by_user(db, user.id)
        is_super_admin_flag = is_super_admin(user)
        platform_role = getattr(user, "platform_role", "user")

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

        if is_super_admin_flag:
            missing_bindings = []
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
            can_use_ledger_without_project = bool(
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
                "platform_role": platform_role,
                "is_super_admin": is_super_admin_flag,
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
            "platform_role": platform_role,
            "is_super_admin": is_super_admin_flag,
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


# 向后兼容的函数包装器
_auth_service_instance = AuthService()

SMS_CODE_TTL_MINUTES = AuthService.SMS_CODE_TTL_MINUTES

def get_user_by_id(db: Session, user_id: int) -> User | None:
    return _auth_service_instance.get_user_by_id(db, user_id)

def get_user_by_username(db: Session, username: str) -> User | None:
    return _auth_service_instance.get_user_by_username(db, username)

def get_user_by_phone(db: Session, phone: str) -> User | None:
    return _auth_service_instance.get_user_by_phone(db, phone)

def register_user(
    db: Session,
    username: str | None,
    phone: str | None,
    password: str,
    agreed_terms: bool,
    agreed_privacy: bool,
) -> User:
    return _auth_service_instance.register_user(db, username, phone, password, agreed_terms, agreed_privacy)

def get_password_login_user(db: Session, username: str) -> User | None:
    return _auth_service_instance.get_password_login_user(db, username)

def sync_configured_super_admin(db: Session, user: User) -> User:
    return _auth_service_instance.sync_configured_super_admin(db, user)

def ensure_username(db: Session, user: User) -> User:
    return _auth_service_instance.ensure_username(db, user)

def authenticate_user(db: Session, username: str, password: str) -> User | None:
    return _auth_service_instance.authenticate_user(db, username, password)

def get_sms_code(db: Session, phone: str) -> str:
    return _auth_service_instance.get_sms_code(db, phone)

def verify_sms_code(db: Session, phone: str, code: str) -> bool:
    return _auth_service_instance.verify_sms_code(db, phone, code)

def authenticate_user_by_sms(db: Session, phone: str, code: str) -> User | None:
    return _auth_service_instance.authenticate_user_by_sms(db, phone, code)

def set_user_password(db: Session, user: User, password: str) -> User:
    return _auth_service_instance.set_user_password(db, user, password)

def update_user_profile(
    db: Session,
    user: User,
    username: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> User:
    return _auth_service_instance.update_user_profile(db, user, username, phone, email)

def get_auth_context(db: Session, user: User) -> dict[str, Any]:
    return _auth_service_instance.get_auth_context(db, user)
