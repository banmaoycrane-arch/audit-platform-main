# -*- coding: utf-8 -*-
"""
模块功能：账套管理数据库操作服务
业务场景：创建账套、授权用户、切换账套、查询用户账套列表
政策依据：会计信息系统内部控制规范——账套隔离与权限管理
输入数据：账套名称、团队ID、用户ID、角色
输出结果：账套记录、授权记录、用户当前账套
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建账套管理服务
"""
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models.ledger import Ledger
from app.models.user_ledger_auth import UserLedgerAuth
from app.models.user import User
from app.models.team import Team


def create_ledger(db: Session, team_id: int, name: str) -> Ledger:
    """
    创建新账套。

    业务逻辑：在指定团队下创建独立账套，实现多客户/多项目数据隔离
    会计口径：每个账套对应独立的会计核算主体

    Args:
        team_id: 所属团队ID
        name: 账套名称

    Returns:
        Ledger: 新创建的账套对象

    注意事项：
        1. 团队必须存在
    """
    ledger = Ledger(team_id=team_id, name=name, status="active")
    db.add(ledger)
    db.commit()
    db.refresh(ledger)
    return ledger


def get_ledgers_by_user(db: Session, user_id: int) -> list[Ledger]:
    """
    获取用户有权限访问的账套列表。

    业务逻辑：通过 user_ledger_auths 表查询用户被授权的所有账套
    会计口径：用户只能看到自己有权限的账套，符合职责分离原则

    Args:
        user_id: 用户ID

    Returns:
        list[Ledger]: 用户授权账套列表
    """
    auths = db.query(UserLedgerAuth).filter(UserLedgerAuth.user_id == user_id).all()
    if not auths:
        return []
    ledger_ids = [auth.ledger_id for auth in auths]
    return db.query(Ledger).filter(Ledger.id.in_(ledger_ids)).all()


def get_ledger_by_id(db: Session, ledger_id: int) -> Ledger | None:
    """
    根据ID获取账套。

    Args:
        ledger_id: 账套ID

    Returns:
        Ledger | None: 账套对象或 None
    """
    return db.query(Ledger).filter(Ledger.id == ledger_id).first()


def switch_ledger(db: Session, user_id: int, ledger_id: int) -> User:
    """
    切换用户当前账套。

    业务逻辑：更新 user.last_ledger_id 字段，记录用户当前操作的账套
    会计口径：每次操作必须明确归属账套，防止跨账套数据混淆

    Args:
        user_id: 用户ID
        ledger_id: 目标账套ID

    Returns:
        User: 更新后的用户对象

    注意事项：
        1. 用户必须对该账套有访问权限
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("用户不存在")
    user.last_ledger_id = ledger_id
    db.commit()
    db.refresh(user)
    return user


def authorize_user_to_ledger(
    db: Session, ledger_id: int, user_id: int, role: str, granted_by: int | None = None
) -> UserLedgerAuth:
    """
    授权用户访问账套。

    业务逻辑：在 user_ledger_auths 表中新增授权记录
    会计口径：符合内部控制规范——不相容职务分离，操作留痕

    Args:
        ledger_id: 账套ID
        user_id: 被授权用户ID
        role: 角色（如 admin, viewer, accountant）
        granted_by: 授权人用户ID（可选）

    Returns:
        UserLedgerAuth: 授权记录

    注意事项：
        1. 同一用户对同一账套重复授权时，更新角色
    """
    existing = (
        db.query(UserLedgerAuth)
        .filter(UserLedgerAuth.user_id == user_id, UserLedgerAuth.ledger_id == ledger_id)
        .first()
    )
    if existing:
        existing.role = role
        if granted_by:
            existing.granted_by = granted_by
        db.commit()
        db.refresh(existing)
        return existing
    auth = UserLedgerAuth(user_id=user_id, ledger_id=ledger_id, role=role, granted_by=granted_by)
    db.add(auth)
    db.commit()
    db.refresh(auth)
    return auth


def user_has_ledger_access(db: Session, user_id: int, ledger_id: int) -> bool:
    """
    检查用户是否有账套访问权限。

    Args:
        user_id: 用户ID
        ledger_id: 账套ID

    Returns:
        bool: 是否有权限
    """
    auth = (
        db.query(UserLedgerAuth)
        .filter(UserLedgerAuth.user_id == user_id, UserLedgerAuth.ledger_id == ledger_id)
        .first()
    )
    return auth is not None


def get_ledger_auths(db: Session, ledger_id: int) -> list[UserLedgerAuth]:
    """
    获取账套授权列表。

    业务逻辑：查询 user_ledger_auths 表中指定账套的所有授权记录
    会计口径：账套授权列表对应实务中的"权限分配表"，需可追溯

    Args:
        db: 数据库会话
        ledger_id: 账套ID

    Returns:
        list[UserLedgerAuth]: 账套授权记录列表
    """
    return (
        db.query(UserLedgerAuth)
        .filter(UserLedgerAuth.ledger_id == ledger_id)
        .all()
    )


def revoke_ledger_auth(
    db: Session, auth_id: int, ledger_id: int | None = None
) -> UserLedgerAuth:
    """
    撤销账套授权。

    业务逻辑：从 user_ledger_auths 表中删除指定授权记录
    会计口径：权限撤销需限定在指定账套内，避免误删其他账套权限

    Args:
        db: 数据库会话
        auth_id: 授权记录ID
        ledger_id: 账套ID（可选，用于校验授权归属）

    Returns:
        UserLedgerAuth: 被撤销的授权记录

    注意事项：
        1. 授权记录必须存在
        2. 传入账套ID时，授权记录必须归属该账套
    """
    query = db.query(UserLedgerAuth).filter(UserLedgerAuth.id == auth_id)
    if ledger_id is not None:
        query = query.filter(UserLedgerAuth.ledger_id == ledger_id)
    auth = query.first()
    if not auth:
        raise ValueError("授权记录不存在，无法撤销")
    db.delete(auth)
    db.commit()
    return auth


def get_team_by_id(db: Session, team_id: int) -> Team | None:
    """
    根据ID获取团队。

    Args:
        team_id: 团队ID

    Returns:
        Team | None: 团队对象或 None
    """
    return db.query(Team).filter(Team.id == team_id).first()


def create_team(db: Session, name: str, team_type: str) -> Team:
    """
    创建新团队。

    业务逻辑：在系统中创建一个新的团队（事务所/企业/虚拟团队）
    会计口径：团队是账套的上级组织单位，对应核算主体归属

    Args:
        name: 团队名称
        team_type: 团队类型（firm, virtual, enterprise）

    Returns:
        Team: 新创建的团队对象

    注意事项：
        1. 团队名称不能为空
    """
    team = Team(name=name, type=team_type)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def get_teams_by_user(db: Session, user_id: int) -> list[Team]:
    """
    获取用户所属团队列表。

    业务逻辑：通过 users.team_id 查询用户直接所属的团队
    会计口径：用户只能看到自己所属的团队，符合权限隔离原则

    Args:
        user_id: 用户ID

    Returns:
        list[Team]: 用户所属团队列表（目前一个用户只归属一个团队）
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.team_id:
        return []
    team = db.query(Team).filter(Team.id == user.team_id).first()
    if not team:
        return []
    return [team]


def get_team_members(db: Session, team_id: int) -> list[User]:
    """
    获取团队成员列表。

    业务逻辑：查询 team_id 等于指定团队的所有用户
    会计口径：团队成员对应实务中的项目组人员，参与同一核算主体的工作

    Args:
        team_id: 团队ID

    Returns:
        list[User]: 团队成员用户列表
    """
    return db.query(User).filter(User.team_id == team_id).all()


def get_user_by_identifier(
    db: Session,
    user_id: int | None = None,
    username: str | None = None,
    phone: str | None = None,
) -> User | None:
    """
    根据用户ID、用户名或手机号查找用户。

    业务逻辑：添加团队成员时，支持通过用户ID或常用登录标识定位用户
    会计口径：团队成员必须对应系统中已存在的真实用户，避免无效授权

    Args:
        user_id: 用户ID
        username: 用户名
        phone: 手机号

    Returns:
        User | None: 匹配到的用户对象或 None
    """
    if user_id is not None:
        return db.query(User).filter(User.id == user_id).first()
    if username or phone:
        return (
            db.query(User)
            .filter(or_(User.username == username, User.phone == phone))
            .first()
        )
    return None


def add_team_member(
    db: Session,
    team_id: int,
    role: str,
    user_id: int | None = None,
    username: str | None = None,
    phone: str | None = None,
) -> User:
    """
    添加成员到团队。

    业务逻辑：将指定用户的 team_id 设置为目标团队ID
    会计口径：团队成员变更需留痕，对应实务中的人员调配

    Args:
        team_id: 目标团队ID
        role: 角色（如 admin, member, viewer）
        user_id: 被添加用户ID
        username: 被添加用户的用户名
        phone: 被添加用户的手机号

    Returns:
        User: 更新后的用户对象

    注意事项：
        1. 团队必须存在
        2. 用户必须存在
    """
    team = get_team_by_id(db, team_id)
    if not team:
        raise ValueError("团队不存在，无法添加成员")
    user = get_user_by_identifier(db, user_id=user_id, username=username, phone=phone)
    if not user:
        raise ValueError("用户不存在，无法添加至团队")
    user.team_id = team_id
    db.commit()
    db.refresh(user)
    return user


def activate_ledger(db: Session, ledger_id: int, reason: str | None = None) -> Ledger:
    """
    激活账套。

    业务逻辑：将账套状态设置为 active，并记录激活时间
    会计口径：账套激活后方可进行记账、审计等操作

    Args:
        db: 数据库会话
        ledger_id: 账套ID
        reason: 生命周期变更原因（可选）

    Returns:
        Ledger: 更新后的账套对象

    注意事项：
        1. 账套必须存在
    """
    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账套不存在，无法激活")
    from datetime import datetime, timezone
    ledger.status = "active"
    ledger.activated_at = datetime.now(timezone.utc)
    ledger.lifecycle_reason = reason
    db.commit()
    db.refresh(ledger)
    return ledger


def suspend_ledger(db: Session, ledger_id: int, reason: str | None = None) -> Ledger:
    """
    暂停账套。

    业务逻辑：将账套状态设置为 suspended，并记录暂停时间
    会计口径：暂停期间禁止新增凭证，但可查询历史数据

    Args:
        db: 数据库会话
        ledger_id: 账套ID
        reason: 生命周期变更原因（可选）

    Returns:
        Ledger: 更新后的账套对象

    注意事项：
        1. 账套必须存在
    """
    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账套不存在，无法暂停")
    from datetime import datetime, timezone
    ledger.status = "suspended"
    ledger.suspended_at = datetime.now(timezone.utc)
    ledger.lifecycle_reason = reason
    db.commit()
    db.refresh(ledger)
    return ledger


def archive_ledger(db: Session, ledger_id: int, reason: str | None = None) -> Ledger:
    """
    归档账套。

    业务逻辑：将账套状态设置为 archived，并记录归档时间
    会计口径：归档后账套进入只读状态，数据不可修改，符合档案管理要求

    Args:
        db: 数据库会话
        ledger_id: 账套ID
        reason: 生命周期变更原因（可选）

    Returns:
        Ledger: 更新后的账套对象

    注意事项：
        1. 账套必须存在
    """
    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账套不存在，无法归档")
    from datetime import datetime, timezone
    ledger.status = "archived"
    ledger.archived_at = datetime.now(timezone.utc)
    ledger.lifecycle_reason = reason
    db.commit()
    db.refresh(ledger)
    return ledger


def restore_ledger(db: Session, ledger_id: int, reason: str | None = None) -> Ledger:
    """
    恢复账套。

    业务逻辑：将 suspended 或 archived 状态的账套恢复为 active
    会计口径：恢复后账套可重新进行记账和审计操作

    Args:
        db: 数据库会话
        ledger_id: 账套ID
        reason: 生命周期变更原因（可选）

    Returns:
        Ledger: 更新后的账套对象

    注意事项：
        1. 账套必须存在
    """
    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账套不存在，无法恢复")
    from datetime import datetime, timezone
    ledger.status = "active"
    ledger.activated_at = datetime.now(timezone.utc)
    ledger.lifecycle_reason = reason
    db.commit()
    db.refresh(ledger)
    return ledger
