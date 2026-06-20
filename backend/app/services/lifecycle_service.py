# -*- coding: utf-8 -*-
"""
模块功能：生命周期事件日志服务
业务场景：记录 Ledger 和 Project 等实体的生命周期状态变更事件
政策依据：会计信息系统内部控制规范——关键操作必须留痕，支持事后追溯
输入数据：数据库会话、实体信息、操作信息
输出结果：lifecycle_logs 表记录
创建日期：2026-06-18
更新记录：
    2026-06-18  初始创建生命周期日志服务
"""
from sqlalchemy.orm import Session, sessionmaker
from app.models.lifecycle_log import LifecycleLog


def log_lifecycle_event(
    db: Session,
    entity_type: str,
    entity_id: int,
    action: str,
    previous_status: str | None,
    new_status: str | None,
    reason: str | None,
    operator_id: int | None,
    log_metadata: dict | None = None,
) -> LifecycleLog:
    """
    记录生命周期变更事件。

    业务逻辑：在 lifecycle_logs 表中插入一条状态变更记录
    会计口径：所有关键状态变更必须留痕，满足审计可追溯要求

    Args:
        db: 数据库会话
        entity_type: 实体类型（ledger / project）
        entity_id: 实体ID
        action: 操作动作（activate / suspend / archive / restore / start / pause / complete / reopen / cancel）
        previous_status: 变更前状态（可选）
        new_status: 变更后状态（可选）
        reason: 变更原因（可选）
        operator_id: 操作人用户ID（可选）
        log_metadata: 日志扩展信息，用于保存 AI 草稿、证据识别和人工补充字段

    Returns:
        LifecycleLog: 新创建的日志记录

    注意事项：
        1. 该操作独立提交，即使主业务事务回滚，日志也应保留
    """
    bind = db.get_bind()
    independent_session_factory = sessionmaker(bind=bind, autoflush=False, autocommit=False)
    with independent_session_factory() as log_db:
        log = LifecycleLog(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            reason=reason,
            log_metadata=log_metadata or {},
            operator_id=operator_id,
        )
        log_db.add(log)
        log_db.commit()
        log_db.refresh(log)
        log_db.expunge(log)
    return log


def list_lifecycle_logs(
    db: Session,
    entity_type: str | None = None,
    entity_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[LifecycleLog]:
    """
    查询生命周期日志列表。

    业务逻辑：按条件筛选 lifecycle_logs 记录，支持分页

    Args:
        db: 数据库会话
        entity_type: 实体类型筛选（可选）
        entity_id: 实体ID筛选（可选）
        action: 操作动作筛选（可选）
        limit: 返回记录数量上限，默认 100
        offset: 跳过记录数量，默认 0

    Returns:
        list[LifecycleLog]: 日志记录列表
    """
    query = db.query(LifecycleLog)
    if entity_type:
        query = query.filter(LifecycleLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(LifecycleLog.entity_id == entity_id)
    if action:
        query = query.filter(LifecycleLog.action == action)
    return (
        query.order_by(LifecycleLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
