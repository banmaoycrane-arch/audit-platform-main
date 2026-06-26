"""审计任务管理服务。

模块功能：提供审计任务的创建、查询、更新、分配、状态流转等核心业务逻辑
业务场景：审计项目协作中的任务管理，对应审计工作流中的任务分配与执行跟踪
政策依据：中国注册会计师审计准则第1121号（对财务报表审计实施的质量控制）
输入数据：任务创建/更新请求参数、用户身份信息、项目上下文
输出结果：任务详情、任务列表、统计数据等结构化响应
创建日期：2026-06-26
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AuditTask
from app.schemas.audit_workflow import AuditTaskCreate, AuditTaskUpdate


STATUS_LABELS = {
    "open": "待分配",
    "todo": "待办",
    "in_progress": "进行中",
    "review": "复核中",
    "closed": "已关闭",
    "rejected": "已拒绝",
}

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "open": ["todo", "closed"],
    "todo": ["in_progress", "closed"],
    "in_progress": ["review", "closed"],
    "review": ["closed", "in_progress", "rejected"],
    "rejected": ["in_progress", "closed"],
    "closed": [],
}


def _validate_status_transition(current: str, target: str) -> None:
    """校验状态流转是否合法。

    Args:
        current: 当前状态
        target: 目标状态

    Raises:
        ValueError: 非法的状态跳转
    """
    allowed = ALLOWED_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise ValueError(
            f"无法从状态「{STATUS_LABELS.get(current, current)}」"
            f"跳转到「{STATUS_LABELS.get(target, target)}」"
        )


def _generate_task_no(db: Session, project_id: int) -> str:
    """生成项目内的任务编号。

    编号规则：T- + 三位序号，按项目内自增，如 T-001、T-002。

    Args:
        db: 数据库会话
        project_id: 项目ID

    Returns:
        生成的任务编号字符串
    """
    count = (
        db.query(func.count(AuditTask.id))
        .filter(AuditTask.project_id == project_id)
        .scalar()
    )
    next_seq = count + 1
    return f"T-{next_seq:03d}"


def _serialize_task(task: AuditTask) -> dict[str, Any]:
    """将任务模型序列化为字典。

    Args:
        task: 审计任务ORM对象

    Returns:
        任务详情字典
    """
    return {
        "id": task.id,
        "project_id": task.project_id,
        "ledger_id": task.ledger_id,
        "task_no": task.task_no,
        "title": task.title,
        "description": task.description,
        "task_type": task.task_type,
        "audit_area": task.audit_area,
        "status": task.status,
        "status_label": STATUS_LABELS.get(task.status, task.status),
        "priority": task.priority,
        "created_by": task.created_by,
        "assignee_id": task.assignee_id,
        "reviewer_ids": task.reviewer_ids or [],
        "related_finding_id": task.related_finding_id,
        "related_procedure_key": task.related_procedure_key,
        "parent_task_id": task.parent_task_id,
        "labels": task.labels or [],
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "closed_at": task.closed_at.isoformat() if task.closed_at else None,
        "allowed_next_statuses": ALLOWED_TRANSITIONS.get(task.status, []),
    }


def get_task_list(
    db: Session,
    project_id: int,
    *,
    status: str | None = None,
    assignee_id: int | None = None,
    task_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    """分页查询项目任务列表。

    Args:
        db: 数据库会话
        project_id: 项目ID
        status: 任务状态筛选（可选）
        assignee_id: 分配人ID筛选（可选）
        task_type: 任务类型筛选（可选）
        page: 页码，从1开始
        page_size: 每页条数

    Returns:
        包含 items、total、page、page_size 的分页结果
    """
    query = db.query(AuditTask).filter(AuditTask.project_id == project_id)

    if status is not None:
        query = query.filter(AuditTask.status == status)
    if assignee_id is not None:
        query = query.filter(AuditTask.assignee_id == assignee_id)
    if task_type is not None:
        query = query.filter(AuditTask.task_type == task_type)

    total = query.count()
    offset = (page - 1) * page_size
    rows = (
        query.order_by(AuditTask.id.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return {
        "items": [_serialize_task(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_task_by_id(db: Session, task_id: int) -> dict[str, Any] | None:
    """根据ID获取任务详情。

    Args:
        db: 数据库会话
        task_id: 任务ID

    Returns:
        任务详情字典，不存在则返回None
    """
    task = db.query(AuditTask).filter(AuditTask.id == task_id).first()
    if task is None:
        return None
    return _serialize_task(task)


def create_task(
    db: Session,
    task_data: AuditTaskCreate,
    creator_id: int,
) -> dict[str, Any]:
    """创建审计任务。

    自动生成项目内唯一的任务编号，初始状态为 open。

    Args:
        db: 数据库会话
        task_data: 任务创建数据
        creator_id: 创建人用户ID

    Returns:
        创建后的任务详情字典
    """
    task_no = _generate_task_no(db, task_data.project_id)

    task = AuditTask(
        project_id=task_data.project_id,
        ledger_id=task_data.ledger_id,
        task_no=task_no,
        title=task_data.title,
        description=task_data.description,
        task_type=task_data.task_type,
        audit_area=task_data.audit_area,
        status="open",
        priority=task_data.priority,
        created_by=creator_id,
        assignee_id=task_data.assignee_id,
        due_date=task_data.due_date,
        related_finding_id=task_data.related_finding_id,
        related_procedure_key=task_data.related_procedure_key,
    )

    if task_data.assignee_id is not None:
        task.status = "todo"

    db.add(task)
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


def update_task(
    db: Session,
    task_id: int,
    update_data: AuditTaskUpdate,
) -> dict[str, Any]:
    """更新任务基本信息。

    仅更新传入的非空字段，不涉及状态流转和分配逻辑。

    Args:
        db: 数据库会话
        task_id: 任务ID
        update_data: 任务更新数据

    Returns:
        更新后的任务详情字典

    Raises:
        ValueError: 任务不存在
    """
    task = db.query(AuditTask).filter(AuditTask.id == task_id).first()
    if task is None:
        raise ValueError("任务不存在")

    update_dict = update_data.model_dump(exclude_unset=True)

    for field, value in update_dict.items():
        if field == "status":
            continue
        setattr(task, field, value)

    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


def assign_task(
    db: Session,
    task_id: int,
    assignee_id: int,
) -> dict[str, Any]:
    """分配任务给指定用户。

    分配成功后任务状态自动变更为 todo。

    Args:
        db: 数据库会话
        task_id: 任务ID
        assignee_id: 分配人用户ID

    Returns:
        更新后的任务详情字典

    Raises:
        ValueError: 任务不存在或状态不允许分配
    """
    task = db.query(AuditTask).filter(AuditTask.id == task_id).first()
    if task is None:
        raise ValueError("任务不存在")

    if task.status not in ("open", "todo"):
        raise ValueError(
            f"当前状态「{STATUS_LABELS.get(task.status, task.status)}」不允许重新分配"
        )

    task.assignee_id = assignee_id
    task.status = "todo"
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return _serialize_task(task)


def update_task_status(
    db: Session,
    task_id: int,
    new_status: str,
    comment: str | None = None,
) -> dict[str, Any]:
    """更新任务状态。

    按照状态机规则校验流转合法性，关闭时自动记录关闭时间。

    Args:
        db: 数据库会话
        task_id: 任务ID
        new_status: 目标状态
        comment: 状态变更备注（可选）

    Returns:
        更新后的任务详情字典

    Raises:
        ValueError: 任务不存在或非法状态跳转
    """
    task = db.query(AuditTask).filter(AuditTask.id == task_id).first()
    if task is None:
        raise ValueError("任务不存在")

    _validate_status_transition(task.status, new_status)

    task.status = new_status
    task.updated_at = datetime.utcnow()

    if new_status == "closed" and task.closed_at is None:
        task.closed_at = datetime.utcnow()
    elif new_status != "closed" and task.closed_at is not None:
        task.closed_at = None

    db.commit()
    db.refresh(task)
    return _serialize_task(task)


def delete_task(db: Session, task_id: int) -> None:
    """删除任务（硬删除）。

    MVP版本采用硬删除，后续可扩展为软删除。

    Args:
        db: 数据库会话
        task_id: 任务ID

    Raises:
        ValueError: 任务不存在
    """
    task = db.query(AuditTask).filter(AuditTask.id == task_id).first()
    if task is None:
        raise ValueError("任务不存在")

    db.delete(task)
    db.commit()


def count_tasks_by_project(
    db: Session,
    project_id: int,
    status: str | None = None,
) -> int:
    """统计项目内的任务数量。

    Args:
        db: 数据库会话
        project_id: 项目ID
        status: 按状态筛选（可选）

    Returns:
        任务数量
    """
    query = db.query(func.count(AuditTask.id)).filter(
        AuditTask.project_id == project_id
    )
    if status is not None:
        query = query.filter(AuditTask.status == status)
    return query.scalar() or 0


def get_user_todo_tasks(
    db: Session,
    user_id: int,
    project_id: int | None = None,
) -> list[dict[str, Any]]:
    """获取用户待办任务列表。

    待办定义：状态为 todo 或 in_progress，且分配给该用户的任务。

    Args:
        db: 数据库会话
        user_id: 用户ID
        project_id: 按项目筛选（可选）

    Returns:
        待办任务列表，按创建时间倒序
    """
    query = db.query(AuditTask).filter(
        AuditTask.assignee_id == user_id,
        AuditTask.status.in_(["todo", "in_progress"]),
    )

    if project_id is not None:
        query = query.filter(AuditTask.project_id == project_id)

    rows = query.order_by(AuditTask.created_at.desc()).all()
    return [_serialize_task(row) for row in rows]
