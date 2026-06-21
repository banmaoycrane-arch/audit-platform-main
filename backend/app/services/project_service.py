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


def get_project_ledgers(db: Session, project_id: int) -> list[Ledger]:
    """
    获取项目关联的所有账套。

    Args:
        db: 数据库会话
        project_id: 项目ID

    Returns:
        list[Ledger]: 账套列表
    """
    project = get_project_by_id(db, project_id)
    if not project:
        return []
    return [pl.ledger for pl in project.ledgers if pl.ledger]


def get_consolidated_report(db: Session, project_id: int, period_start: str | None = None, period_end: str | None = None) -> dict:
    """
    获取项目跨账套汇总数据。

    功能描述：
        1. 获取项目关联的所有账套
        2. 汇总各账套的会计分录数据
        3. 按科目分类汇总借贷方发生额
        4. 识别潜在的内部交易

    会计口径：
        - 跨账套数据汇总用于集团层面的分析
        - 内部交易识别基于往来单位+金额+日期的匹配

    Args:
        db: 数据库会话
        project_id: 项目ID
        period_start: 可选，汇总起始日期 (YYYY-MM-DD)
        period_end: 可选，汇总结束日期 (YYYY-MM-DD)

    Returns:
        dict: 包含汇总数据的字典

    注意事项：
        1. 仅汇总 entry_source='auto' 的分录（自动导入）
        2. 内部交易抵销需要在应用层单独处理
    """
    from app.db.models import AccountingEntry
    from datetime import date

    project = get_project_by_id(db, project_id)
    if not project:
        raise ValueError("项目不存在")

    ledgers = get_project_ledgers(db, project_id)
    if not ledgers:
        return {
            "project_id": project_id,
            "project_name": project.name,
            "ledger_count": 0,
            "total_entries": 0,
            "by_ledger": [],
            "by_account": [],
            "potential_internal_transactions": [],
        }

    # 构建查询
    ledger_ids = [l.id for l in ledgers]
    query = db.query(AccountingEntry).filter(
        AccountingEntry.ledger_id.in_(ledger_ids),
        AccountingEntry.entry_source == "auto"
    )

    # 按日期过滤
    if period_start:
        start_date = date.fromisoformat(period_start)
        query = query.filter(AccountingEntry.voucher_date >= start_date)
    if period_end:
        end_date = date.fromisoformat(period_end)
        query = query.filter(AccountingEntry.voucher_date <= end_date)

    entries = query.all()

    # 按账套分组汇总
    by_ledger = {}
    for ledger in ledgers:
        ledger_entries = [e for e in entries if e.ledger_id == ledger.id]
        total_debit = sum((e.debit_amount or 0) for e in ledger_entries)
        total_credit = sum((e.credit_amount or 0) for e in ledger_entries)
        by_ledger[ledger.id] = {
            "ledger_id": ledger.id,
            "ledger_name": ledger.name,
            "entry_count": len(ledger_entries),
            "total_debit": float(total_debit),
            "total_credit": float(total_credit),
        }

    # 按科目分组汇总
    by_account: dict[str, dict] = {}
    for entry in entries:
        key = entry.account_code or "UNKNOWN"
        if key not in by_account:
            by_account[key] = {
                "account_code": key,
                "account_name": entry.account_name or "未知科目",
                "debit_total": 0.0,
                "credit_total": 0.0,
                "entry_count": 0,
            }
        by_account[key]["debit_total"] += float(entry.debit_amount or 0)
        by_account[key]["credit_total"] += float(entry.credit_amount or 0)
        by_account[key]["entry_count"] += 1

    # 识别潜在内部交易
    # 逻辑：同一日期、同一金额、一方借一方贷、同一往来单位
    potential_internal = []
    transaction_map: dict[str, list] = {}

    for entry in entries:
        if not entry.counterparty or not entry.voucher_date:
            continue
        amount = entry.debit_amount or entry.credit_amount or 0
        if amount <= 0:
            continue

        # 构建交易键：(日期, 金额, 往来单位)
        key = f"{entry.voucher_date}:{amount}:{entry.counterparty}"

        if key not in transaction_map:
            transaction_map[key] = []
        transaction_map[key].append(entry)

    for key, tx_list in transaction_map.items():
        if len(tx_list) >= 2:
            # 存在至少一条借方和一条贷方
            debits = [t for t in tx_list if t.debit_amount and t.debit_amount > 0]
            credits = [t for t in tx_list if t.credit_amount and t.credit_amount > 0]
            if debits and credits:
                potential_internal.append({
                    "voucher_date": str(tx_list[0].voucher_date),
                    "amount": float(tx_list[0].debit_amount or tx_list[0].credit_amount or 0),
                    "counterparty": tx_list[0].counterparty,
                    "debit_count": len(debits),
                    "credit_count": len(credits),
                    "debit_ledger_ids": list(set(t.ledger_id for t in debits if t.ledger_id)),
                    "credit_ledger_ids": list(set(t.ledger_id for t in credits if t.ledger_id)),
                })

    return {
        "project_id": project_id,
        "project_name": project.name,
        "ledger_count": len(ledgers),
        "total_entries": len(entries),
        "period_start": period_start,
        "period_end": period_end,
        "by_ledger": list(by_ledger.values()),
        "by_account": sorted(by_account.values(), key=lambda x: x["account_code"]),
        "potential_internal_transactions": potential_internal[:50],  # 限制返回50条
    }
