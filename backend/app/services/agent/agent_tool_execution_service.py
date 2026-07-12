# -*- coding: utf-8 -*-
"""
模块功能：低风险 Agent 工具调用服务
业务场景：允许 Agent 在白名单范围内执行只读或预览类低风险工具
政策依据：会计信息系统内部控制要求，自动化执行必须受岗位授权、风险等级和审计留痕约束
输入数据：工具名称、Agent 角色、工具参数、当前用户和账簿上下文
输出结果：低风险工具执行结果
创建日期：2026-06-19
更新记录：
    2026-06-19  初始创建低风险 Agent 工具调用服务
    2025-01-20  封装为 AgentToolExecutionService 类
"""
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, AuditFinding, ChartOfAccounts, Counterparty, ImportJob, SourceFile
from app.services.agent.agent_service import detect_intent
from app.services.agent.agent_tool_registry import get_agent_tool
from app.services.accounting.financial_statements_service import trial_balance_report
from app.services.doc_parsing.draft_archive_service import get_evidence_lifecycle, load_archive_metadata


def _serialize_account(account: ChartOfAccounts) -> dict[str, Any]:
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


def _serialize_counterparty(counterparty: Counterparty) -> dict[str, Any]:
    return {
        "id": counterparty.id,
        "name": counterparty.name,
        "role": counterparty.role,
        "unified_credit_no": counterparty.unified_credit_no,
        "is_related_party": counterparty.is_related_party,
        "default_entity_id": counterparty.default_entity_id,
        "is_active": counterparty.is_active,
    }


def _run_suggest_system_path(args: dict[str, Any]) -> dict[str, Any]:
    message = str(args.get("message") or "")
    if not message.strip():
        return {
            "intent": "general_help",
            "suggested_path": "/",
            "reply": "请描述你想完成的财务或审计任务。",
            "steps": ["说明业务场景", "补充资料类型", "根据建议路径进入页面"],
        }
    return detect_intent(message)


def _run_list_chart_of_accounts(db: Session, args: dict[str, Any]) -> dict[str, Any]:
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


def _run_list_counterparties(db: Session, args: dict[str, Any]) -> dict[str, Any]:
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


def _run_list_accounting_periods(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    ledger_id = args.get("ledger_id")
    if not ledger_id:
        raise ValueError("缺少 ledger_id")
    limit = max(1, min(int(args.get("limit") or 24), 100))
    rows = (
        db.query(AccountingPeriod)
        .filter(AccountingPeriod.ledger_id == int(ledger_id))
        .order_by(AccountingPeriod.period_code.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "period_code": row.period_code,
                "status": row.status,
                "start_date": str(row.start_date) if row.start_date else None,
                "end_date": str(row.end_date) if row.end_date else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


def _run_list_import_jobs(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    ledger_id = args.get("ledger_id")
    if not ledger_id:
        raise ValueError("缺少 ledger_id")
    limit = max(1, min(int(args.get("limit") or 20), 50))
    rows = (
        db.query(ImportJob)
        .filter(ImportJob.ledger_id == int(ledger_id))
        .order_by(ImportJob.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "items": [
            {
                "id": row.id,
                "source_type": row.source_type,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


def _run_list_evidence_inbox(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    ledger_id = args.get("ledger_id")
    if not ledger_id:
        raise ValueError("缺少 ledger_id")
    lifecycle = str(args.get("lifecycle") or "inbox")
    limit = max(1, min(int(args.get("limit") or 30), 100))
    rows = (
        db.query(SourceFile)
        .outerjoin(ImportJob, SourceFile.import_job_id == ImportJob.id)
        .filter(or_(SourceFile.ledger_id == int(ledger_id), ImportJob.ledger_id == int(ledger_id)))
        .order_by(SourceFile.id.desc())
        .limit(limit * 3)
        .all()
    )
    items = []
    for row in rows:
        row_lifecycle = get_evidence_lifecycle(row)
        if lifecycle != "all" and row_lifecycle != lifecycle:
            continue
        archive = load_archive_metadata(row) or {}
        items.append({
            "id": row.id,
            "filename": row.filename,
            "file_type": row.file_type,
            "lifecycle": row_lifecycle,
            "parse_status": row.text_extract_status,
            "archive_path": archive.get("archive_path"),
            "period_code": archive.get("period_code"),
        })
        if len(items) >= limit:
            break
    return {"items": items, "count": len(items), "lifecycle": lifecycle}


def _run_get_trial_balance(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    ledger_id = args.get("ledger_id")
    period_id = args.get("period_id")
    if not ledger_id or not period_id:
        raise ValueError("缺少 ledger_id 或 period_id")
    report = trial_balance_report(db, int(ledger_id), int(period_id))
    rows = report.get("rows") or []
    preview = [
        {
            "account_code": row.get("account_code"),
            "account_name": row.get("account_name"),
            "closing_debit": row.get("closing_debit"),
            "closing_credit": row.get("closing_credit"),
        }
        for row in rows[:40]
    ]
    return {
        "period_code": report.get("period_code"),
        "is_balanced": report.get("is_balanced"),
        "totals": report.get("totals"),
        "row_preview": preview,
        "row_count": len(rows),
    }


def _run_list_internal_control_findings(db: Session, args: dict[str, Any]) -> dict[str, Any]:
    ledger_id = args.get("ledger_id")
    status = args.get("status")
    limit = max(1, min(int(args.get("limit") or 30), 100))
    query = db.query(AuditFinding).filter(AuditFinding.finding_type == "internal_control")
    if ledger_id:
        query = query.filter(AuditFinding.ledger_id == int(ledger_id))
    if status and status != "all":
        query = query.filter(AuditFinding.status == str(status))
    rows = query.order_by(AuditFinding.id.desc()).limit(limit).all()
    return {
        "items": [
            {
                "id": row.id,
                "status": row.status,
                "title": row.finding_title,
                "description": row.finding_description,
                "job_id": row.job_id,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ],
        "count": len(rows),
    }


def _dispatch_tool(db: Session, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "suggest_system_path":
        return _run_suggest_system_path(args)
    if tool_name == "list_chart_of_accounts":
        return _run_list_chart_of_accounts(db, args)
    if tool_name == "list_counterparties":
        return _run_list_counterparties(db, args)
    if tool_name == "list_accounting_periods":
        return _run_list_accounting_periods(db, args)
    if tool_name == "list_import_jobs":
        return _run_list_import_jobs(db, args)
    if tool_name == "list_evidence_inbox":
        return _run_list_evidence_inbox(db, args)
    if tool_name == "get_trial_balance":
        return _run_get_trial_balance(db, args)
    if tool_name == "list_internal_control_findings":
        return _run_list_internal_control_findings(db, args)
    raise NotImplementedError("该工具尚未接入执行器")


class AgentToolExecutionService:
    """
    低风险 Agent 工具调用服务
    
    功能描述：执行白名单中的低风险 Agent 工具
    业务逻辑：先检查工具是否存在、是否为低风险、是否免人工确认、当前 Agent 角色是否被授权
    会计口径：该服务只允许查询或导航类动作，不允许修改凭证、期间、审计结论等关键数据
    
    注意事项：
        1. 中高风险工具必须走人工确认机制，不能通过本服务执行
        2. 所有调用入口必须在路由层写入统一执行留痕
    """
    
    def run_low_risk_agent_tool(
        self,
        db: Session,
        tool_name: str,
        agent_role: str,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        执行白名单中的低风险 Agent 工具
        
        Args:
            db: 数据库会话
            tool_name: 工具名称
            agent_role: 当前 Agent 角色
            args: 工具参数
            
        Returns:
            dict[str, Any]: 工具执行结果和工具配置摘要
        """
        tool = get_agent_tool(tool_name)
        if tool is None:
            raise PermissionError("工具不在 Agent 白名单中")
        if agent_role not in tool["allowed_agent_roles"]:
            raise PermissionError("当前 Agent 角色无权调用该工具")
        if tool["risk_level"] != "low" or tool["approval_required"]:
            raise PermissionError("该工具不是低风险免确认工具，不能自动执行")

        safe_args = args or {}
        result = _dispatch_tool(db, tool_name, safe_args)

        return {
            "tool": tool,
            "result": result,
        }


def run_agent_tool_for_assist(
    db: Session,
    *,
    tool_name: str,
    agent_role: str,
    args: dict[str, Any] | None = None,
    user_id: int | None = None,
    ledger_id: int | None = None,
) -> dict[str, Any]:
    """对话助手专用：执行低风险工具，注入账簿上下文。"""
    _ = user_id
    service = AgentToolExecutionService()
    safe_args = dict(args or {})
    if ledger_id is not None and "ledger_id" not in safe_args:
        safe_args["ledger_id"] = ledger_id
    return service.run_low_risk_agent_tool(db, tool_name, agent_role, safe_args)


_tool_execution_service_instance = AgentToolExecutionService()


def run_low_risk_agent_tool(
    db: Session,
    tool_name: str,
    agent_role: str,
    args: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _tool_execution_service_instance.run_low_risk_agent_tool(
        db, tool_name, agent_role, args
    )
