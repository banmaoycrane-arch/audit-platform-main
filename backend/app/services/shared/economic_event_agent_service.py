# -*- coding: utf-8 -*-
"""
模块功能：经济事件工单的 Agent 驱动服务（E3）
业务场景：Agent 开草稿工单、推进到待入账前状态，并把 Tool 调用写入 steps
政策依据：AI 不绕过人工复核；过账必须由人确认
输入数据：账簿 ID、标题/摘要、目标状态、操作人
输出结果：事件工单对象或步骤日志
创建日期：2026-08-02
更新记录：
    2026-08-02  E3 首版：开草稿、安全推进、Tool steps 留痕、禁止 Agent 过账
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import EconomicEvent, EconomicEventStep
from app.services.shared import economic_event_service as event_svc


# Agent 允许推进到的状态（禁止 posted / closed）
_AGENT_ALLOWED_TARGET_STATUSES = {
    "collecting",
    "pending_review",
    "pending_post",
    "failed",
    "cancelled",
}


def create_draft_event_from_agent(
    db: Session,
    *,
    ledger_id: int,
    title: str,
    summary: str | None = None,
    event_type: str = "manual",
    actor_user_id: int | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    tool_name: str = "create_economic_event_draft",
) -> EconomicEvent:
    """
    功能描述：由 Agent 创建草稿事件工单（不入账）。
    业务逻辑：source=agent；写 create step 后再写 tool_call step。
    会计口径：仅产生工单草稿，不生成借贷分录、不改期间。

    Args:
        db: 数据库会话
        ledger_id: 账簿 ID
        title: 事件标题
        summary: 可检索叙述（供 E4 向量）
        event_type: 事件类型
        actor_user_id: 触发 Agent 的用户
        model_provider: 模型厂商（可空）
        model_name: 模型名（可空）
        tool_name: 工具名，写入 steps.api_name

    Returns:
        EconomicEvent: 新建的草稿工单
    """
    clean_title = (title or "").strip()
    if not clean_title:
        raise ValueError("事件标题不能为空")
    if ledger_id is None:
        raise ValueError("缺少 ledger_id")

    event = event_svc.create_event(
        db,
        ledger_id=int(ledger_id),
        title=clean_title,
        event_type=event_type or "manual",
        summary=summary,
        source="agent",
        created_by=actor_user_id,
        assignee_user_id=actor_user_id,
    )
    # create_event 已 commit；补一条 Tool 调用留痕
    _append_tool_step(
        db,
        event_id=event.id,
        tool_name=tool_name,
        result_summary=f"Agent 创建草稿工单 {event.event_no}",
        actor_user_id=actor_user_id,
        model_provider=model_provider,
        model_name=model_name,
        to_status="draft",
    )
    db.refresh(event)
    return event


def advance_event_from_agent(
    db: Session,
    *,
    event_id: int,
    to_status: str,
    actor_user_id: int | None = None,
    reason: str | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    tool_name: str = "advance_economic_event",
) -> EconomicEvent:
    """
    功能描述：Agent 推进事件状态（不得过账）。
    业务逻辑：目标状态必须在 Agent 白名单；过账闸门由 transition 强制。
    会计口径：可推到 pending_post，posted 必须由人操作。

    Args:
        db: 数据库会话
        event_id: 事件 ID
        to_status: 目标状态
        actor_user_id: 操作人
        reason: 推进原因
        model_provider: 模型厂商
        model_name: 模型名
        tool_name: 工具名

    Returns:
        EconomicEvent: 推进后的事件
    """
    if to_status not in _AGENT_ALLOWED_TARGET_STATUSES:
        raise ValueError(
            f"Agent 不允许将事件推进到 {to_status}；"
            "过账(posted)/关闭(closed)必须由人工确认"
        )

    event = event_svc.transition(
        db,
        event_id,
        to_status,
        actor_user_id=actor_user_id,
        actor_type="agent",
        reason=reason or f"Agent 工具 {tool_name} 推进",
    )
    _append_tool_step(
        db,
        event_id=event.id,
        tool_name=tool_name,
        result_summary=reason or f"Agent 推进到 {to_status}",
        actor_user_id=actor_user_id,
        model_provider=model_provider,
        model_name=model_name,
        from_status=None,
        to_status=to_status,
    )
    db.refresh(event)
    return event


def log_agent_tool_call_on_event(
    db: Session,
    *,
    event_id: int,
    tool_name: str,
    result_summary: str | None = None,
    actor_user_id: int | None = None,
    model_provider: str | None = None,
    model_name: str | None = None,
    payload_digest: str | None = None,
) -> EconomicEventStep:
    """
    功能描述：将一次 Agent Tool 调用写入事件 steps（不改状态）。
    业务逻辑：仅留痕，便于审计「办了什么」。
    """
    event = event_svc.get_event(db, event_id)
    if event is None:
        raise ValueError("事件不存在")
    return _append_tool_step(
        db,
        event_id=event_id,
        tool_name=tool_name,
        result_summary=result_summary,
        actor_user_id=actor_user_id,
        model_provider=model_provider,
        model_name=model_name,
        payload_digest=payload_digest,
    )


def _append_tool_step(
    db: Session,
    *,
    event_id: int,
    tool_name: str,
    result_summary: str | None,
    actor_user_id: int | None,
    model_provider: str | None = None,
    model_name: str | None = None,
    payload_digest: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
) -> EconomicEventStep:
    step = event_svc._log_step(
        db,
        event_id,
        "agent_tool",
        f"Agent 工具: {tool_name}",
        actor_user_id=actor_user_id,
        actor_type="agent",
        api_name=tool_name,
        payload_digest=payload_digest,
        result_summary=result_summary,
        from_status=from_status,
        to_status=to_status,
        model_provider=model_provider,
        model_name=model_name,
    )
    db.commit()
    db.refresh(step)
    return step


def serialize_event_brief(event: EconomicEvent) -> dict[str, Any]:
    """输出 Agent 可读的事件摘要（不含借贷主数据）。"""
    return {
        "id": event.id,
        "event_no": event.event_no,
        "ledger_id": event.ledger_id,
        "title": event.title,
        "event_type": event.event_type,
        "status": event.status,
        "summary": event.summary,
        "source": event.source,
        "review_required": event.status in {"pending_review", "pending_post"},
        "formal_post_allowed": False,
        "notice": "事件工单仅为办理载体；过账必须由人工在待入账状态确认。",
    }
