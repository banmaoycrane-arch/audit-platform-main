"""
模块功能：审计工作分支管理服务
业务场景：审计任务的工作分支创建、状态流转、底稿版本与审计程序关联
政策依据：中国注册会计师审计准则第1121号（项目质量控制）、第1131号（审计工作底稿）
输入数据：项目ID、任务ID、分支信息、用户ID
输出结果：分支记录、分页列表、状态流转结果
创建日期：2026-06-26
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditWorkBranch


STATUS_LABELS = {
    "active": "进行中",
    "review_pending": "待复核",
    "merged": "已合并",
    "archived": "已归档",
    "abandoned": "已废弃",
}

VALID_TRANSITIONS = {
    "active": ["review_pending", "abandoned"],
    "review_pending": ["merged", "active", "abandoned"],
    "merged": ["archived"],
    "archived": [],
    "abandoned": ["archived"],
}


def _serialize_branch(branch: AuditWorkBranch) -> dict[str, Any]:
    """序列化分支对象为字典。

    Args:
        branch: 审计工作分支ORM对象

    Returns:
        dict[str, Any]: 序列化后的分支数据
    """
    allowed = VALID_TRANSITIONS.get(branch.status, [])
    return {
        "id": branch.id,
        "project_id": branch.project_id,
        "ledger_id": branch.ledger_id,
        "task_id": branch.task_id,
        "import_job_id": branch.import_job_id,
        "branch_name": branch.branch_name,
        "base_branch": branch.base_branch,
        "status": branch.status,
        "status_label": STATUS_LABELS.get(branch.status, branch.status),
        "created_by": branch.created_by,
        "assignee_id": branch.assignee_id,
        "workpaper_index_id": branch.workpaper_index_id,
        "procedure_run_id": branch.procedure_run_id,
        "latest_version_id": branch.latest_version_id,
        "allowed_next_statuses": allowed,
        "created_at": branch.created_at.isoformat() if branch.created_at else None,
        "updated_at": branch.updated_at.isoformat() if branch.updated_at else None,
        "merged_at": branch.merged_at.isoformat() if branch.merged_at else None,
    }


def _validate_transition(current: str, target: str) -> None:
    """校验状态流转是否合法。

    Args:
        current: 当前状态
        target: 目标状态

    Raises:
        ValueError: 非法状态跳转
    """
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ValueError(
            f"非法状态跳转：无法从 {STATUS_LABELS.get(current, current)} "
            f"跳转到 {STATUS_LABELS.get(target, target)}"
        )


def get_branch_list(
    db: Session,
    project_id: int | None = None,
    task_id: int | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页查询分支列表。

    业务逻辑：支持按项目、任务、状态多条件筛选，返回分页结果

    Args:
        db: 数据库会话
        project_id: 项目ID（可选）
        task_id: 任务ID（可选）
        status: 分支状态（可选）
        page: 页码，默认1
        page_size: 每页条数，默认20

    Returns:
        dict[str, Any]: 包含 items、total、page、page_size 的分页结果
    """
    query = db.query(AuditWorkBranch)

    if project_id is not None:
        query = query.filter(AuditWorkBranch.project_id == project_id)
    if task_id is not None:
        query = query.filter(AuditWorkBranch.task_id == task_id)
    if status is not None:
        query = query.filter(AuditWorkBranch.status == status)

    total = query.count()
    offset = (page - 1) * page_size
    rows = (
        query.order_by(AuditWorkBranch.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "items": [_serialize_branch(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_branch_by_id(db: Session, branch_id: int) -> dict[str, Any] | None:
    """根据ID获取分支。

    Args:
        db: 数据库会话
        branch_id: 分支ID

    Returns:
        dict[str, Any] | None: 分支数据或None
    """
    row = db.query(AuditWorkBranch).filter(AuditWorkBranch.id == branch_id).first()
    if row is None:
        return None
    return _serialize_branch(row)


def create_branch(
    db: Session,
    branch_data: dict[str, Any],
    creator_id: int,
) -> dict[str, Any]:
    """创建工作分支。

    业务逻辑：在指定任务下创建工作分支，分支名称在同一任务下唯一

    Args:
        db: 数据库会话
        branch_data: 分支数据，包含 task_id、project_id、branch_name 等
        creator_id: 创建人用户ID

    Returns:
        dict[str, Any]: 新创建的分支数据

    Raises:
        ValueError: 分支名称在同一任务下已存在
    """
    task_id = branch_data.get("task_id")
    branch_name = branch_data.get("branch_name")

    existing = (
        db.query(AuditWorkBranch)
        .filter(
            AuditWorkBranch.task_id == task_id,
            AuditWorkBranch.branch_name == branch_name,
        )
        .first()
    )
    if existing is not None:
        raise ValueError(f"任务下已存在同名分支：{branch_name}")

    branch = AuditWorkBranch(
        project_id=branch_data.get("project_id"),
        ledger_id=branch_data.get("ledger_id"),
        task_id=task_id,
        branch_name=branch_name,
        base_branch=branch_data.get("base_branch", "main"),
        status="active",
        created_by=creator_id,
        assignee_id=branch_data.get("assignee_id"),
        workpaper_index_id=branch_data.get("workpaper_index_id"),
        procedure_run_id=branch_data.get("procedure_run_id"),
    )
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return _serialize_branch(branch)


def update_branch(
    db: Session,
    branch_id: int,
    update_data: dict[str, Any],
) -> dict[str, Any]:
    """更新分支信息。

    Args:
        db: 数据库会话
        branch_id: 分支ID
        update_data: 待更新的字段数据

    Returns:
        dict[str, Any]: 更新后的分支数据

    Raises:
        ValueError: 分支不存在
    """
    branch = (
        db.query(AuditWorkBranch).filter(AuditWorkBranch.id == branch_id).first()
    )
    if branch is None:
        raise ValueError("分支不存在")

    updatable_fields = [
        "assignee_id",
        "workpaper_index_id",
        "procedure_run_id",
        "latest_version_id",
    ]
    for field in updatable_fields:
        if field in update_data and update_data[field] is not None:
            setattr(branch, field, update_data[field])

    branch.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(branch)
    return _serialize_branch(branch)


def update_branch_status(
    db: Session,
    branch_id: int,
    new_status: str,
) -> dict[str, Any]:
    """更新分支状态。

    业务逻辑：状态流转需符合预定义规则，非法跳转抛出业务异常
    状态流转路径：active->review_pending->merged / active->abandoned

    Args:
        db: 数据库会话
        branch_id: 分支ID
        new_status: 目标状态

    Returns:
        dict[str, Any]: 更新后的分支数据

    Raises:
        ValueError: 分支不存在或状态跳转非法
    """
    branch = (
        db.query(AuditWorkBranch).filter(AuditWorkBranch.id == branch_id).first()
    )
    if branch is None:
        raise ValueError("分支不存在")

    _validate_transition(branch.status, new_status)

    branch.status = new_status
    if new_status == "merged":
        branch.merged_at = datetime.utcnow()
    branch.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(branch)
    return _serialize_branch(branch)


def get_branches_by_task(db: Session, task_id: int) -> list[dict[str, Any]]:
    """获取任务下的所有分支。

    Args:
        db: 数据库会话
        task_id: 任务ID

    Returns:
        list[dict[str, Any]]: 分支列表
    """
    rows = (
        db.query(AuditWorkBranch)
        .filter(AuditWorkBranch.task_id == task_id)
        .order_by(AuditWorkBranch.id.desc())
        .all()
    )
    return [_serialize_branch(row) for row in rows]


def link_workpaper_version(
    db: Session,
    branch_id: int,
    version_id: int,
) -> dict[str, Any]:
    """关联底稿版本到分支。

    业务逻辑：将最新的底稿版本关联到工作分支，作为分支当前工作成果快照

    Args:
        db: 数据库会话
        branch_id: 分支ID
        version_id: 底稿版本ID

    Returns:
        dict[str, Any]: 更新后的分支数据

    Raises:
        ValueError: 分支不存在
    """
    branch = (
        db.query(AuditWorkBranch).filter(AuditWorkBranch.id == branch_id).first()
    )
    if branch is None:
        raise ValueError("分支不存在")

    branch.latest_version_id = version_id
    branch.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(branch)
    return _serialize_branch(branch)


def link_procedure_run(
    db: Session,
    branch_id: int,
    procedure_run_id: int,
) -> dict[str, Any]:
    """关联审计程序运行到分支。

    业务逻辑：将审计程序执行记录与工作分支关联，建立审计轨迹

    Args:
        db: 数据库会话
        branch_id: 分支ID
        procedure_run_id: 审计程序运行ID

    Returns:
        dict[str, Any]: 更新后的分支数据

    Raises:
        ValueError: 分支不存在
    """
    branch = (
        db.query(AuditWorkBranch).filter(AuditWorkBranch.id == branch_id).first()
    )
    if branch is None:
        raise ValueError("分支不存在")

    branch.procedure_run_id = procedure_run_id
    branch.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(branch)
    return _serialize_branch(branch)


def link_import_job_to_branch(
    db: Session,
    branch_id: int,
    import_job_id: int,
) -> dict[str, Any]:
    """关联导入任务到工作分支。

    将导入的数据与审计工作分支关联，便于后续执行审计测试。

    Args:
        db: 数据库会话
        branch_id: 分支ID
        import_job_id: 导入任务ID

    Returns:
        dict[str, Any]: 更新后的分支数据

    Raises:
        ValueError: 分支不存在或导入任务不存在
    """
    from app.db.models import ImportJob

    branch = (
        db.query(AuditWorkBranch).filter(AuditWorkBranch.id == branch_id).first()
    )
    if branch is None:
        raise ValueError("分支不存在")

    import_job = db.query(ImportJob).filter(ImportJob.id == import_job_id).first()
    if import_job is None:
        raise ValueError("导入任务不存在")

    branch.import_job_id = import_job_id
    branch.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(branch)
    return _serialize_branch(branch)
