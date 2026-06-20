# -*- coding: utf-8 -*-
"""
模块功能：低风险 Agent 工具调用服务
业务场景：允许 Agent 在白名单范围内执行只读或预览类低风险工具
政策依据：会计信息系统内部控制要求，自动化执行必须受岗位授权、风险等级和审计留痕约束
输入数据：工具名称、Agent 角色、工具参数、当前用户和账套上下文
输出结果：低风险工具执行结果
创建日期：2026-06-19
更新记录：
    2026-06-19  初始创建低风险 Agent 工具调用服务
"""
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ChartOfAccounts, Counterparty
from app.services.agent_service import detect_intent
from app.services.agent_tool_registry import get_agent_tool


def _serialize_account(account: ChartOfAccounts) -> dict:
    return {
        "code": account.code,
        "name": account.name,
        "parent_code": account.parent_code,
        "level": account.level,
        "category": account.category,
        "direction": account.direction,
        "status": account.status,
        "is_system": account.is_system,
    }


def _serialize_counterparty(counterparty: Counterparty) -> dict:
    return {
        "id": counterparty.id,
        "name": counterparty.name,
        "role": counterparty.role,
        "unified_credit_no": counterparty.unified_credit_no,
        "is_related_party": counterparty.is_related_party,
        "default_entity_id": counterparty.default_entity_id,
        "is_active": counterparty.is_active,
    }


def _run_suggest_system_path(args: dict) -> dict:
    message = str(args.get("message") or "")
    if not message.strip():
        return {
            "intent": "general_help",
            "suggested_path": "/",
            "reply": "请描述你想完成的财务或审计任务。",
            "steps": ["说明业务场景", "补充资料类型", "根据建议路径进入页面"],
        }
    return detect_intent(message)


def _run_list_chart_of_accounts(db: Session, args: dict) -> dict:
    limit = int(args.get("limit") or 50)
    limit = max(1, min(limit, 200))
    accounts = (
        db.query(ChartOfAccounts)
        .order_by(ChartOfAccounts.code)
        .limit(limit)
        .all()
    )
    return {
        "items": [_serialize_account(account) for account in accounts],
        "count": len(accounts),
        "limit": limit,
    }


def _run_list_counterparties(db: Session, args: dict) -> dict:
    limit = int(args.get("limit") or 50)
    limit = max(1, min(limit, 200))
    counterparties = (
        db.query(Counterparty)
        .order_by(Counterparty.id)
        .limit(limit)
        .all()
    )
    return {
        "items": [_serialize_counterparty(counterparty) for counterparty in counterparties],
        "count": len(counterparties),
        "limit": limit,
    }


def run_low_risk_agent_tool(
    db: Session,
    tool_name: str,
    agent_role: str,
    args: dict | None = None,
) -> dict[str, Any]:
    """
    功能描述：执行白名单中的低风险 Agent 工具。
    业务逻辑：先检查工具是否存在、是否为低风险、是否免人工确认、当前 Agent 角色是否被授权。
    会计口径：该函数只允许查询或导航类动作，不允许修改凭证、期间、审计结论等关键数据。

    Args:
        db: 数据库会话。
        tool_name: 工具名称。
        agent_role: 当前 Agent 角色。
        args: 工具参数。

    Returns:
        dict[str, Any]: 工具执行结果和工具配置摘要。

    注意事项：
        1. 中高风险工具必须走人工确认机制，不能通过本函数执行。
        2. 所有调用入口必须在路由层写入统一执行留痕。
    """
    tool = get_agent_tool(tool_name)
    if tool is None:
        raise PermissionError("工具不在 Agent 白名单中")
    if agent_role not in tool["allowed_agent_roles"]:
        raise PermissionError("当前 Agent 角色无权调用该工具")
    if tool["risk_level"] != "low" or tool["approval_required"]:
        raise PermissionError("该工具不是低风险免确认工具，不能自动执行")

    safe_args = args or {}
    if tool_name == "suggest_system_path":
        result = _run_suggest_system_path(safe_args)
    elif tool_name == "list_chart_of_accounts":
        result = _run_list_chart_of_accounts(db, safe_args)
    elif tool_name == "list_counterparties":
        result = _run_list_counterparties(db, safe_args)
    else:
        raise NotImplementedError("该低风险工具尚未接入执行器")

    return {
        "tool": tool,
        "result": result,
    }
