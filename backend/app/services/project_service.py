# -*- coding: utf-8 -*-
"""
模块功能：项目管理数据库操作服务
业务场景：创建项目、关联账套、分配人员、查询项目列表
政策依据：会计师事务所质量控制准则——项目立项、范围界定与人员分派
输入数据：项目信息、账套ID列表、用户ID与角色
输出结果：项目记录、关联记录、成员记录
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建项目管理服务
"""
from sqlalchemy.orm import Session, joinedload
from app.models.project import Project
from app.models.project_ledger import ProjectLedger
from app.models.project_member import ProjectMember
from app.models.team import Team
from app.models.ledger import Ledger
from app.models.user import User


def create_project(
    db: Session,
    team_id: int,
    name: str,
    project_type: str = "audit",
    status: str = "active",
    start_date: str | None = None,
    end_date: str | None = None,
    manager_id: int | None = None,
) -> Project:
    """
    创建新项目。

    业务逻辑：在指定团队下创建项目，用于归集账套与人员
    会计口径：项目对应审计或核算任务，需明确范围与负责人

    Args:
        team_id: 所属团队ID
        name: 项目名称
        project_type: 项目类型（audit / accounting / tax / consulting）
        status: 项目状态（active / paused / completed / archived）
        start_date: 项目开始日期（字符串格式 YYYY-MM-DD）
        end_date: 项目结束日期（字符串格式 YYYY-MM-DD）
        manager_id: 项目负责人用户ID

    Returns:
        Project: 新创建的项目对象

    注意事项：
        1. 团队必须存在
    """
    from datetime import date

    project = Project(
        team_id=team_id,
        name=name,
        type=project_type,
        status=status,
        manager_id=manager_id,
    )
    if start_date:
        project.start_date = date.fromisoformat(start_date)
    if end_date:
        project.end_date = date.fromisoformat(end_date)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_project_by_id(db: Session, project_id: int) -> Project | None:
    """
    根据ID获取项目。

    Args:
        project_id: 项目ID

    Returns:
        Project | None: 项目对象或 None
    """
    return (
        db.query(Project)
        .options(joinedload(Project.ledgers), joinedload(Project.members))
        .filter(Project.id == project_id)
        .first()
    )


def list_projects_by_team(db: Session, team_id: int) -> list[Project]:
    """
    获取指定团队的项目列表。

    Args:
        team_id: 团队ID

    Returns:
        list[Project]: 项目列表
    """
    return (
        db.query(Project)
        .filter(Project.team_id == team_id)
        .order_by(Project.created_at.desc())
        .all()
    )


def list_projects_by_user(db: Session, user_id: int) -> list[Project]:
    """
    获取用户参与的项目列表。

    业务逻辑：通过 project_members 表查询用户所属的所有项目

    Args:
        user_id: 用户ID

    Returns:
        list[Project]: 项目列表
    """
    member_records = db.query(ProjectMember).filter(ProjectMember.user_id == user_id).all()
    if not member_records:
        return []
    project_ids = [m.project_id for m in member_records]
    return db.query(Project).filter(Project.id.in_(project_ids)).order_by(Project.created_at.desc()).all()


def associate_ledger_to_project(db: Session, project_id: int, ledger_id: int) -> ProjectLedger:
    """
    关联账套到项目。

    业务逻辑：在 project_ledgers 表中新增关联记录
    会计口径：明确项目审计/核算范围，防止遗漏或越界

    Args:
        project_id: 项目ID
        ledger_id: 账套ID

    Returns:
        ProjectLedger: 关联记录

    注意事项：
        1. 同一账套重复关联时，返回已有记录
    """
    existing = (
        db.query(ProjectLedger)
        .filter(ProjectLedger.project_id == project_id, ProjectLedger.ledger_id == ledger_id)
        .first()
    )
    if existing:
        return existing
    link = ProjectLedger(project_id=project_id, ledger_id=ledger_id)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


def assign_member_to_project(db: Session, project_id: int, user_id: int, role: str = "member") -> ProjectMember:
    """
    分配人员到项目。

    业务逻辑：在 project_members 表中新增成员记录
    会计口径：符合职责分离要求，项目组成员及角色必须留痕

    Args:
        project_id: 项目ID
        user_id: 用户ID
        role: 角色（manager / leader / member / reviewer / viewer）

    Returns:
        ProjectMember: 成员记录

    注意事项：
        1. 同一用户重复分配时，更新角色
    """
    existing = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id)
        .first()
    )
    if existing:
        existing.role = role
        db.commit()
        db.refresh(existing)
        return existing
    member = ProjectMember(project_id=project_id, user_id=user_id, role=role)
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


def get_team_by_id(db: Session, team_id: int) -> Team | None:
    """
    根据ID获取团队。

    Args:
        team_id: 团队ID

    Returns:
        Team | None: 团队对象或 None
    """
    return db.query(Team).filter(Team.id == team_id).first()


def get_ledger_by_id(db: Session, ledger_id: int) -> Ledger | None:
    """
    根据ID获取账套。

    Args:
        ledger_id: 账套ID

    Returns:
        Ledger | None: 账套对象或 None
    """
    return db.query(Ledger).filter(Ledger.id == ledger_id).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """
    根据ID获取用户。

    Args:
        user_id: 用户ID

    Returns:
        User | None: 用户对象或 None
    """
    return db.query(User).filter(User.id == user_id).first()


def start_project(db: Session, project_id: int, reason: str | None = None) -> Project:
    """
    启动项目。

    业务逻辑：将项目状态设置为 active
    会计口径：项目启动后方可进行审计/核算工作

    Args:
        db: 数据库会话
        project_id: 项目ID
        reason: 生命周期变更原因（可选）

    Returns:
        Project: 更新后的项目对象

    注意事项：
        1. 项目必须存在
    """
    project = get_project_by_id(db, project_id)
    if not project:
        raise ValueError("项目不存在，无法启动")
    project.status = "active"
    project.lifecycle_reason = reason
    db.commit()
    db.refresh(project)
    return project


def pause_project(db: Session, project_id: int, reason: str | None = None) -> Project:
    """
    暂停项目。

    业务逻辑：将项目状态设置为 paused
    会计口径：暂停期间项目工作暂缓，但保留所有数据

    Args:
        db: 数据库会话
        project_id: 项目ID
        reason: 生命周期变更原因（可选）

    Returns:
        Project: 更新后的项目对象

    注意事项：
        1. 项目必须存在
    """
    project = get_project_by_id(db, project_id)
    if not project:
        raise ValueError("项目不存在，无法暂停")
    project.status = "paused"
    project.lifecycle_reason = reason
    db.commit()
    db.refresh(project)
    return project


def complete_project(db: Session, project_id: int, reason: str | None = None) -> Project:
    """
    完成项目。

    业务逻辑：将项目状态设置为 completed，并记录完成时间
    会计口径：项目完成后进入归档准备阶段，数据应完整锁定

    Args:
        db: 数据库会话
        project_id: 项目ID
        reason: 生命周期变更原因（可选）

    Returns:
        Project: 更新后的项目对象

    注意事项：
        1. 项目必须存在
    """
    project = get_project_by_id(db, project_id)
    if not project:
        raise ValueError("项目不存在，无法完成")
    from datetime import datetime, timezone
    project.status = "completed"
    project.completed_at = datetime.now(timezone.utc)
    project.lifecycle_reason = reason
    db.commit()
    db.refresh(project)
    return project


def reopen_project(db: Session, project_id: int, reason: str | None = None) -> Project:
    """
    重新打开项目。

    业务逻辑：将 completed 或 paused 状态的项目恢复为 active
    会计口径：重新打开后项目可继续审计/核算工作

    Args:
        db: 数据库会话
        project_id: 项目ID
        reason: 生命周期变更原因（可选）

    Returns:
        Project: 更新后的项目对象

    注意事项：
        1. 项目必须存在
    """
    project = get_project_by_id(db, project_id)
    if not project:
        raise ValueError("项目不存在，无法重新打开")
    project.status = "active"
    project.lifecycle_reason = reason
    db.commit()
    db.refresh(project)
    return project


def cancel_project(db: Session, project_id: int, reason: str | None = None) -> Project:
    """
    取消项目。

    业务逻辑：将项目状态设置为 cancelled，并记录取消时间
    会计口径：取消后项目数据保留但不可继续操作，符合审计档案管理要求

    Args:
        db: 数据库会话
        project_id: 项目ID
        reason: 生命周期变更原因（可选）

    Returns:
        Project: 更新后的项目对象

    注意事项：
        1. 项目必须存在
    """
    project = get_project_by_id(db, project_id)
    if not project:
        raise ValueError("项目不存在，无法取消")
    from datetime import datetime, timezone
    project.status = "cancelled"
    project.cancelled_at = datetime.now(timezone.utc)
    project.lifecycle_reason = reason
    db.commit()
    db.refresh(project)
    return project
