# -*- coding: utf-8 -*-
"""
模块功能：Agent 高风险动作人工确认服务
业务场景：为中高风险 Agent 工具生成待确认记录，并记录人工确认结果
政策依据：会计信息系统内部控制要求，高风险财务动作必须经过授权确认并留痕
输入数据：工具名称、Agent 角色、工具参数、当前用户和账套上下文
输出结果：agent_approvals 表确认记录
创建日期：2026-06-19
更新记录：
    2026-06-19  初始创建 Agent 人工确认服务
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import AgentApproval
from app.models.user import User
from app.services.agent_tool_registry import get_agent_tool


def request_agent_tool_approval(
    db: Session,
    tool_name: str,
    agent_role: str,
    args: dict | None,
    current_user: User,
    ledger_id: int | None,
) -> AgentApproval:
    """
    功能描述：为需要人工确认的 Agent 工具创建待确认记录。
    业务逻辑：校验工具白名单、Agent 角色和风险属性，只允许中高风险或需确认工具进入待确认状态。
    会计口径：该步骤只记录“申请确认”，不执行真实财务动作。

    Args:
        db: 数据库会话。
        tool_name: 工具名称。
        agent_role: 当前 Agent 角色。
        args: 工具参数摘要。
        current_user: 发起确认申请的用户。
        ledger_id: 当前账套 ID。

    Returns:
        AgentApproval: 新创建的待确认记录。

    注意事项：
        1. 低风险免确认工具应走低风险工具调用接口，不应创建确认记录。
        2. 当前阶段只跑通确认链路，不执行高风险动作。
    """
    tool = get_agent_tool(tool_name)
    if tool is None:
        raise PermissionError("工具不在 Agent 白名单中")
    if agent_role not in tool["allowed_agent_roles"]:
        raise PermissionError("当前 Agent 角色无权申请该工具确认")
    if tool["risk_level"] == "low" and not tool["approval_required"]:
        raise ValueError("低风险免确认工具不需要人工确认")

    approval = AgentApproval(
        tool_name=tool_name,
        agent_role=agent_role,
        risk_level=tool["risk_level"],
        status="pending",
        requested_by_user_id=current_user.id,
        team_id=current_user.team_id,
        ledger_id=ledger_id,
        approval_reason=tool["description"],
        request_args_summary=args or {},
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


def confirm_agent_tool_approval(
    db: Session,
    approval_id: int,
    current_user: User,
    comment: str | None = None,
) -> AgentApproval:
    """
    功能描述：确认一条 Agent 高风险动作申请。
    业务逻辑：把待确认记录更新为 confirmed，并记录确认人和确认意见。
    会计口径：当前阶段只确认授权事实，不执行真实高风险动作。

    Args:
        db: 数据库会话。
        approval_id: 确认记录 ID。
        current_user: 执行确认的用户。
        comment: 确认意见。

    Returns:
        AgentApproval: 已确认的记录。

    注意事项：
        1. 后续真正执行高风险动作时，应复用该确认记录作为前置条件。
    """
    approval = db.get(AgentApproval, approval_id)
    if approval is None:
        raise LookupError("Agent 确认记录不存在")
    if approval.status != "pending":
        raise ValueError("只有待确认状态可以执行确认")

    approval.status = "confirmed"
    approval.confirmed_by_user_id = current_user.id
    approval.confirmation_comment = comment
    approval.confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(approval)
    return approval


def serialize_agent_approval(approval: AgentApproval) -> dict:
    """
    功能描述：把 Agent 确认记录转换为接口返回结构。
    业务逻辑：返回确认状态、工具、角色、风险等级和确认人信息。
    会计口径：该返回结果用于前端复核和事后审计查询。

    Args:
        approval: Agent 确认记录。

    Returns:
        dict: 可序列化的确认记录。
    """
    return {
        "id": approval.id,
        "tool_name": approval.tool_name,
        "agent_role": approval.agent_role,
        "risk_level": approval.risk_level,
        "status": approval.status,
        "requested_by_user_id": approval.requested_by_user_id,
        "confirmed_by_user_id": approval.confirmed_by_user_id,
        "team_id": approval.team_id,
        "ledger_id": approval.ledger_id,
        "approval_reason": approval.approval_reason,
        "request_args_summary": approval.request_args_summary or {},
        "confirmation_comment": approval.confirmation_comment,
        "created_at": approval.created_at.isoformat() if approval.created_at else None,
        "confirmed_at": approval.confirmed_at.isoformat() if approval.confirmed_at else None,
    }
