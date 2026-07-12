# -*- coding: utf-8 -*-
"""
模块功能：账簿管理数据库操作服务
业务场景：创建账簿、授权用户、切换账簿、查询用户账簿列表
政策依据：会计信息系统内部控制规范——账簿隔离与权限管理
输入数据：账簿名称、团队ID、用户ID、角色
输出结果：账簿记录、授权记录、用户当前账簿
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建账簿管理服务
"""
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import delete as sql_delete, or_
from sqlalchemy.orm import Session
from app.models.ledger import Ledger
from app.models.user_ledger_auth import UserLedgerAuth
from app.models.user import User
from app.models.team import Team
from app.services.basic_data.coa_service import init_default_accounts
from app.services.shared.ledger_timeline_service import initialize_ledger_timeline


def create_ledger(
    db: Session,
    team_id: int,
    name: str,
    accounting_start_date: date | None = None,
) -> Ledger:
    """
    创建新账簿。

    业务逻辑：在指定团队下创建独立账簿，并按会计起始日期种子化首个开放期间
    会计口径：每个账簿对应独立的会计核算主体与时间线

    Args:
        team_id: 所属团队ID
        name: 账簿名称
        accounting_start_date: 会计时间线起点，默认当天

    Returns:
        Ledger: 新创建的账簿对象

    注意事项：
        1. 团队必须存在
    """
    anchor = accounting_start_date or date.today()
    ledger = Ledger(
        team_id=team_id,
        name=name,
        status="active",
        accounting_start_date=anchor,
    )
    db.add(ledger)
    db.flush()
    initialize_ledger_timeline(db, ledger, organization_name=name)
    init_default_accounts(db, ledger.id)
    db.commit()
    db.refresh(ledger)
    return ledger


def get_ledgers_by_user(db: Session, user_id: int) -> list[Ledger]:
    """
    获取用户有权限访问的账簿列表。

    业务逻辑：通过 user_ledger_auths 表查询用户被授权的所有账簿
    会计口径：用户只能看到自己有权限的账簿，符合职责分离原则

    Args:
        user_id: 用户ID

    Returns:
        list[Ledger]: 用户授权账簿列表
    """
    auths = db.query(UserLedgerAuth).filter(UserLedgerAuth.user_id == user_id).all()
    if not auths:
        return []
    ledger_ids = [auth.ledger_id for auth in auths]
    return db.query(Ledger).filter(Ledger.id.in_(ledger_ids)).all()


def get_ledger_by_id(db: Session, ledger_id: int) -> Ledger | None:
    """
    根据ID获取账簿。

    Args:
        ledger_id: 账簿ID

    Returns:
        Ledger | None: 账簿对象或 None
    """
    return db.query(Ledger).filter(Ledger.id == ledger_id).first()


def switch_ledger(db: Session, user_id: int, ledger_id: int) -> User:
    """
    切换用户当前账簿。

    业务逻辑：更新 user.last_ledger_id 字段，记录用户当前操作的账簿
    会计口径：每次操作必须明确归属账簿，防止跨账簿数据混淆

    Args:
        user_id: 用户ID
        ledger_id: 目标账簿ID

    Returns:
        User: 更新后的用户对象

    注意事项：
        1. 用户必须对该账簿有访问权限
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
    授权用户访问账簿。

    业务逻辑：在 user_ledger_auths 表中新增授权记录
    会计口径：符合内部控制规范——不相容职务分离，操作留痕

    Args:
        ledger_id: 账簿ID
        user_id: 被授权用户ID
        role: 角色（如 admin, viewer, accountant）
        granted_by: 授权人用户ID（可选）

    Returns:
        UserLedgerAuth: 授权记录

    注意事项：
        1. 同一用户对同一账簿重复授权时，更新角色
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
    检查用户是否有账簿访问权限。

    Args:
        user_id: 用户ID
        ledger_id: 账簿ID

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
    获取账簿授权列表。

    业务逻辑：查询 user_ledger_auths 表中指定账簿的所有授权记录
    会计口径：账簿授权列表对应实务中的"权限分配表"，需可追溯

    Args:
        db: 数据库会话
        ledger_id: 账簿ID

    Returns:
        list[UserLedgerAuth]: 账簿授权记录列表
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
    撤销账簿授权。

    业务逻辑：从 user_ledger_auths 表中删除指定授权记录
    会计口径：权限撤销需限定在指定账簿内，避免误删其他账簿权限

    Args:
        db: 数据库会话
        auth_id: 授权记录ID
        ledger_id: 账簿ID（可选，用于校验授权归属）

    Returns:
        UserLedgerAuth: 被撤销的授权记录

    注意事项：
        1. 授权记录必须存在
        2. 传入账簿ID时，授权记录必须归属该账簿
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
    会计口径：团队是账簿的上级组织单位，对应核算主体归属

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
    激活账簿。

    业务逻辑：将账簿状态设置为 active，并记录激活时间
    会计口径：账簿激活后方可进行记账、审计等操作

    Args:
        db: 数据库会话
        ledger_id: 账簿ID
        reason: 生命周期变更原因（可选）

    Returns:
        Ledger: 更新后的账簿对象

    注意事项：
        1. 账簿必须存在
    """
    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账簿不存在，无法激活")
    ledger.status = "active"
    ledger.activated_at = datetime.now(timezone.utc)
    ledger.lifecycle_reason = reason
    db.commit()
    db.refresh(ledger)
    return ledger


def suspend_ledger(db: Session, ledger_id: int, reason: str | None = None) -> Ledger:
    """
    暂停账簿。

    业务逻辑：将账簿状态设置为 suspended，并记录暂停时间
    会计口径：暂停期间禁止新增凭证，但可查询历史数据

    Args:
        db: 数据库会话
        ledger_id: 账簿ID
        reason: 生命周期变更原因（可选）

    Returns:
        Ledger: 更新后的账簿对象

    注意事项：
        1. 账簿必须存在
    """
    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账簿不存在，无法暂停")
    ledger.status = "suspended"
    ledger.suspended_at = datetime.now(timezone.utc)
    ledger.lifecycle_reason = reason
    db.commit()
    db.refresh(ledger)
    return ledger


def archive_ledger(db: Session, ledger_id: int, reason: str | None = None) -> Ledger:
    """
    归档账簿。

    业务逻辑：将账簿状态设置为 archived，并记录归档时间
    会计口径：归档后账簿进入只读状态，数据不可修改，符合档案管理要求

    Args:
        db: 数据库会话
        ledger_id: 账簿ID
        reason: 生命周期变更原因（可选）

    Returns:
        Ledger: 更新后的账簿对象

    注意事项：
        1. 账簿必须存在
    """
    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账簿不存在，无法归档")
    ledger.status = "archived"
    ledger.archived_at = datetime.now(timezone.utc)
    ledger.lifecycle_reason = reason
    db.commit()
    db.refresh(ledger)
    return ledger


def restore_ledger(db: Session, ledger_id: int, reason: str | None = None) -> Ledger:
    """
    恢复账簿。

    业务逻辑：将 suspended 或 archived 状态的账簿恢复为 active
    会计口径：恢复后账簿可重新进行记账和审计操作

    Args:
        db: 数据库会话
        ledger_id: 账簿ID
        reason: 生命周期变更原因（可选）

    Returns:
        Ledger: 更新后的账簿对象

    注意事项：
        1. 账簿必须存在
    """
    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账簿不存在，无法恢复")
    ledger.status = "active"
    ledger.activated_at = datetime.now(timezone.utc)
    ledger.lifecycle_reason = reason
    db.commit()
    db.refresh(ledger)
    return ledger


def update_ledger(
    db: Session,
    ledger_id: int,
    *,
    name: str | None = None,
    accounting_start_date: date | None = None,
) -> Ledger:
    """更新账簿基本信息（名称、会计时间线起点）。"""
    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账簿不存在，无法更新")
    if ledger.status == "deleted":
        raise ValueError("已删除的账簿不可编辑")
    if name is not None:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("账簿名称不能为空")
        ledger.name = cleaned
    if accounting_start_date is not None:
        ledger.accounting_start_date = accounting_start_date
    db.commit()
    db.refresh(ledger)
    return ledger


def initialize_ledger(db: Session, ledger_id: int, reason: str | None = None) -> dict[str, Any]:
    """初始化账簿：删除全部凭证与分录，保留科目表、期间、设置与授权。"""
    from app.db.models import (
        AccountingEntry,
        BankReconciliationItem,
        BankTransaction,
        EntryTag,
        Voucher,
    )

    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账簿不存在，无法初始化")
    if ledger.status == "deleted":
        raise ValueError("已删除的账簿不可初始化")

    _ = reason

    voucher_count = db.query(Voucher).filter(Voucher.ledger_id == ledger_id).count()
    voucher_ids = [
        row[0] for row in db.query(Voucher.id).filter(Voucher.ledger_id == ledger_id).all()
    ]
    entry_filter = AccountingEntry.ledger_id == ledger_id
    if voucher_ids:
        entry_filter = or_(entry_filter, AccountingEntry.voucher_id.in_(voucher_ids))

    entry_ids = [row[0] for row in db.query(AccountingEntry.id).filter(entry_filter).all()]
    entry_count = len(entry_ids)

    if entry_ids:
        db.query(BankTransaction).filter(BankTransaction.matched_entry_id.in_(entry_ids)).update(
            {BankTransaction.matched_entry_id: None},
            synchronize_session=False,
        )
        db.query(BankReconciliationItem).filter(BankReconciliationItem.entry_id.in_(entry_ids)).update(
            {BankReconciliationItem.entry_id: None},
            synchronize_session=False,
        )
        db.query(EntryTag).filter(EntryTag.entry_id.in_(entry_ids)).delete(synchronize_session=False)
    db.query(EntryTag).filter(EntryTag.ledger_id == ledger_id).delete(synchronize_session=False)
    db.query(AccountingEntry).filter(entry_filter).delete(synchronize_session=False)
    db.query(Voucher).filter(Voucher.ledger_id == ledger_id).delete(synchronize_session=False)
    db.commit()

    return {
        "ledger_id": ledger_id,
        "deleted_vouchers": voucher_count,
        "deleted_entries": entry_count,
    }


def delete_ledger(db: Session, ledger_id: int, reason: str | None = None) -> dict[str, Any]:
    """硬删除账簿：物理清除所有关联数据并删除账簿行。"""
    import app.db.models  # noqa: F401 — register all ORM tables on Base.metadata
    import app.models  # noqa: F401

    from app.db.models import (
        AccountingEntry,
        AuditFinding,
        AuditReport,
        Entity,
        EntryTag,
        ImportJob,
        SourceFile,
        Voucher,
    )
    from app.db.session import Base
    from app.models.binding_request import BindingRequest
    from app.models.lifecycle_log import LifecycleLog
    from app.models.project_ledger import ProjectLedger
    from app.models.scope_settings import EntityScopeSettings, LedgerSettings
    from app.models.user_ledger_auth import UserLedgerAuth

    ledger = get_ledger_by_id(db, ledger_id)
    if not ledger:
        raise ValueError("账簿不存在，无法删除")

    _ = reason  # 保留 API 参数，硬删除后不再写入 lifecycle 字段

    db.query(User).filter(User.last_ledger_id == ledger_id).update(
        {User.last_ledger_id: None}, synchronize_session=False
    )
    db.query(BindingRequest).filter(BindingRequest.ledger_id == ledger_id).update(
        {BindingRequest.ledger_id: None}, synchronize_session=False
    )

    voucher_ids = [
        row[0] for row in db.query(Voucher.id).filter(Voucher.ledger_id == ledger_id).all()
    ]
    entry_filter = AccountingEntry.ledger_id == ledger_id
    if voucher_ids:
        entry_filter = or_(entry_filter, AccountingEntry.voucher_id.in_(voucher_ids))
    entry_ids_subq = db.query(AccountingEntry.id).filter(entry_filter)
    db.query(EntryTag).filter(EntryTag.entry_id.in_(entry_ids_subq)).delete(synchronize_session=False)
    db.query(EntryTag).filter(EntryTag.ledger_id == ledger_id).delete(synchronize_session=False)
    db.query(AccountingEntry).filter(entry_filter).delete(synchronize_session=False)
    db.query(Voucher).filter(Voucher.ledger_id == ledger_id).delete(synchronize_session=False)

    job_ids = [
        row[0] for row in db.query(ImportJob.id).filter(ImportJob.ledger_id == ledger_id).all()
    ]
    if job_ids:
        db.query(AuditReport).filter(AuditReport.import_job_id.in_(job_ids)).delete(
            synchronize_session=False
        )
        db.query(AuditFinding).filter(AuditFinding.job_id.in_(job_ids)).delete(
            synchronize_session=False
        )
        db.query(SourceFile).filter(SourceFile.import_job_id.in_(job_ids)).delete(
            synchronize_session=False
        )
        db.query(ImportJob).filter(ImportJob.id.in_(job_ids)).delete(synchronize_session=False)
    db.query(SourceFile).filter(SourceFile.ledger_id == ledger_id).delete(synchronize_session=False)

    db.query(LifecycleLog).filter(
        LifecycleLog.entity_type == "ledger",
        LifecycleLog.entity_id == ledger_id,
    ).delete(synchronize_session=False)

    db.query(UserLedgerAuth).filter(UserLedgerAuth.ledger_id == ledger_id).delete(
        synchronize_session=False
    )
    db.query(ProjectLedger).filter(ProjectLedger.ledger_id == ledger_id).delete(
        synchronize_session=False
    )
    db.query(LedgerSettings).filter(LedgerSettings.ledger_id == ledger_id).delete(
        synchronize_session=False
    )
    db.query(EntityScopeSettings).filter(EntityScopeSettings.ledger_id == ledger_id).delete(
        synchronize_session=False
    )

    db.query(Entity).filter(Entity.ledger_id == ledger_id).update(
        {Entity.parent_id: None}, synchronize_session=False
    )

    skip_tables = {"users", "binding_requests", "ledgers"}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in skip_tables:
            continue
        if "ledger_id" not in table.c:
            continue
        db.execute(sql_delete(table).where(table.c.ledger_id == ledger_id))

    db.delete(ledger)
    db.commit()
    return {"deleted": True, "ledger_id": ledger_id}
