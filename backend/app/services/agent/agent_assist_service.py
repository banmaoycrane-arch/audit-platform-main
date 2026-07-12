"""对话式 Agent：鉴权上下文下规划并自动执行低风险 API 工具。"""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.orm import Session

from app.services.agent.agent_model_resolver import build_agent_llm_client, resolve_agent_llm_config
from app.services.agent.agent_service import detect_intent
from app.services.agent.agent_tool_execution_service import run_agent_tool_for_assist
from app.services.agent.agent_tool_registry import AGENT_TOOL_REGISTRY, get_agent_tool

ASSIST_SYSTEM_PROMPT = """你是财务向量审计系统的对话助手。
你的目标是通过调用已授权的后端工具，帮用户直接完成查询与准备工作，而不是只让用户去点页面。

规则：
1. 只使用工具清单中的 tool_name；参数放在 args 中。
2. 低风险只读工具可自动执行；中高风险工具只生成 pending_action，不假装已执行。
3. 涉及账簿的业务查询必须带上 ledger_id（系统会注入当前账簿）。
4. 回复使用中文，简洁说明已完成的操作与结果摘要。
5. 必须返回 JSON，格式：
{
  "reply": "给用户看的总结",
  "tool_calls": [{"tool_name": "...", "agent_role": "accounting_assistant_agent", "args": {}}],
  "pending_actions": [{"tool_name": "...", "reason": "需人工确认的原因"}]
}
若无工具调用，tool_calls 与 pending_actions 为空数组。"""

RULE_TOOL_MAP: dict[str, list[dict[str, Any]]] = {
    "basic_data": [
        {"tool_name": "list_chart_of_accounts", "agent_role": "accounting_assistant_agent", "args": {"limit": 30}},
    ],
    "period_close": [
        {"tool_name": "list_accounting_periods", "agent_role": "accounting_assistant_agent", "args": {"limit": 12}},
    ],
    "accounting_import": [
        {"tool_name": "list_evidence_inbox", "agent_role": "accounting_assistant_agent", "args": {"limit": 20}},
        {"tool_name": "list_import_jobs", "agent_role": "accounting_assistant_agent", "args": {"limit": 10}},
    ],
    "audit_workflow": [
        {"tool_name": "list_internal_control_findings", "agent_role": "audit_assistant_agent", "args": {"status": "pending", "limit": 20}},
    ],
    "report_export": [
        {"tool_name": "list_accounting_periods", "agent_role": "accounting_assistant_agent", "args": {"limit": 6}},
    ],
}


def _tool_catalog_for_prompt() -> list[dict[str, str]]:
    catalog: list[dict[str, str]] = []
    for tool in AGENT_TOOL_REGISTRY.values():
        catalog.append({
            "tool_name": tool["tool_name"],
            "description": tool["description"],
            "risk_level": tool["risk_level"],
            "approval_required": str(tool["approval_required"]),
        })
    return catalog


def _parse_assist_json(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        return {"reply": "", "tool_calls": [], "pending_actions": []}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    return {"reply": text, "tool_calls": [], "pending_actions": []}


def _rules_assist_plan(message: str) -> dict[str, Any]:
    intent_result = detect_intent(message)
    tool_calls = RULE_TOOL_MAP.get(intent_result["intent"], [])
    if "科目" in message:
        tool_calls = [{"tool_name": "list_chart_of_accounts", "agent_role": "accounting_assistant_agent", "args": {"limit": 50}}]
    elif "往来" in message or "客户" in message or "供应商" in message:
        tool_calls = [{"tool_name": "list_counterparties", "agent_role": "accounting_assistant_agent", "args": {"limit": 50}}]
    elif "试算" in message or "余额表" in message:
        tool_calls = [
            {"tool_name": "list_accounting_periods", "agent_role": "accounting_assistant_agent", "args": {"limit": 6}},
        ]
    elif "收件" in message or "证据" in message or "云空间" in message or "发票" in message:
        tool_calls = [{"tool_name": "list_evidence_inbox", "agent_role": "accounting_assistant_agent", "args": {"limit": 30}}]
    elif "内控" in message or "待办" in message:
        tool_calls = [{"tool_name": "list_internal_control_findings", "agent_role": "audit_assistant_agent", "args": {"status": "pending", "limit": 30}}]
    return {
        "reply": intent_result["reply"],
        "tool_calls": tool_calls,
        "pending_actions": [],
        "source": "rules",
    }


def _execute_tool_calls(
    db: Session,
    *,
    tool_calls: list[dict[str, Any]],
    user_id: int,
    ledger_id: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    executed: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    for call in tool_calls[:5]:
        tool_name = str(call.get("tool_name") or "")
        agent_role = str(call.get("agent_role") or "accounting_assistant_agent")
        args = dict(call.get("args") or {})
        if ledger_id is not None and "ledger_id" not in args:
            args["ledger_id"] = ledger_id
        tool = get_agent_tool(tool_name)
        if not tool:
            pending.append({"tool_name": tool_name, "reason": "工具未在白名单注册"})
            continue
        if tool["risk_level"] != "low" or tool["approval_required"]:
            pending.append({
                "tool_name": tool_name,
                "reason": tool.get("description") or "该工具需人工确认后执行",
                "risk_level": tool["risk_level"],
            })
            continue
        try:
            result = run_agent_tool_for_assist(
                db,
                tool_name=tool_name,
                agent_role=agent_role,
                args=args,
                user_id=user_id,
                ledger_id=ledger_id,
            )
            executed.append({
                "tool_name": tool_name,
                "status": "success",
                "result": result.get("result"),
            })
        except Exception as exc:
            executed.append({
                "tool_name": tool_name,
                "status": "failed",
                "error": str(exc),
            })
    return executed, pending


def run_agent_assist(
    db: Session,
    *,
    message: str,
    user_id: int,
    ledger_id: int | None,
    conversation_history: list[dict[str, str]] | None = None,
    max_tool_rounds: int = 2,
) -> dict[str, Any]:
    message = message.strip()
    if not message:
        raise ValueError("message 不能为空")

    llm_config = resolve_agent_llm_config(db)
    client = build_agent_llm_client(db)
    history = conversation_history or []

    plan: dict[str, Any]
    if client.is_configured():
        user_payload = {
            "user_message": message,
            "ledger_id": ledger_id,
            "tools": _tool_catalog_for_prompt(),
            "conversation_history": history[-8:],
        }
        messages = [
            {"role": "system", "content": ASSIST_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ]
        llm_result = client.chat(messages, temperature=0.2)
        if llm_result.available:
            plan = _parse_assist_json(llm_result.content or "")
            plan["source"] = "llm"
            plan["model"] = llm_result.model
        else:
            plan = _rules_assist_plan(message)
            plan["llm_error"] = llm_result.error
    else:
        plan = _rules_assist_plan(message)

    tool_calls = plan.get("tool_calls") or []
    if not isinstance(tool_calls, list):
        tool_calls = []
    pending_actions = plan.get("pending_actions") or []
    if not isinstance(pending_actions, list):
        pending_actions = []

    executed_tools: list[dict[str, Any]] = []
    pending_tools: list[dict[str, Any]] = list(pending_actions)

    rounds = 0
    while tool_calls and rounds < max_tool_rounds:
        rounds += 1
        batch_executed, batch_pending = _execute_tool_calls(
            db,
            tool_calls=tool_calls,
            user_id=user_id,
            ledger_id=ledger_id,
        )
        executed_tools.extend(batch_executed)
        pending_tools.extend(batch_pending)
        if rounds >= max_tool_rounds or not client.is_configured():
            break
        follow_messages = [
            {"role": "system", "content": ASSIST_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({
                "user_message": message,
                "tool_results": batch_executed,
                "instruction": "根据工具结果生成最终 reply，tool_calls 置空",
            }, ensure_ascii=False)},
        ]
        follow = client.chat(follow_messages, temperature=0.2)
        if follow.available:
            parsed = _parse_assist_json(follow.content or "")
            plan["reply"] = parsed.get("reply") or plan.get("reply")
        tool_calls = []

    reply = str(plan.get("reply") or "").strip()
    if executed_tools and not reply:
        reply = f"已执行 {len(executed_tools)} 项查询，请查看工具结果。"

    intent = detect_intent(message)
    return {
        "reply": reply,
        "intent": intent.get("intent"),
        "confidence": intent.get("confidence"),
        "source": plan.get("source", "rules"),
        "model": plan.get("model"),
        "model_config": {
            "provider": llm_config.get("ai_provider"),
            "model_name": llm_config.get("ai_model"),
            "config_source": llm_config.get("source"),
            "is_ollama": llm_config.get("is_ollama"),
            "remote_model_configured": bool(llm_config.get("ai_base_url") and llm_config.get("ai_model")),
        },
        "ledger_id": ledger_id,
        "tool_executions": executed_tools,
        "pending_actions": pending_tools,
        "suggested_path": None,
        "steps": [],
    }
