# -*- coding: utf-8 -*-
"""
模块功能：统一执行留痕服务
业务场景：记录人工页面、CLI 命令、Agent 自动或辅助执行的关键业务动作
政策依据：会计信息系统内部控制要求，关键操作应可追溯、可复核、可定位责任
输入数据：执行来源、用户、账簿、Agent 角色、工具名称、风险等级和执行结果
输出结果：execution_audit_logs 表记录，用于事后审计追踪
创建日期：2026-06-19
更新记录：
    2026-06-19  初始创建统一执行留痕服务
"""
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import ExecutionAuditLog
from app.models.user import User


def create_execution_audit_log(
    db: Session,
    execution_source: str,
    user: User | None,
    ledger_id: int | None,
    tool_name: str,
    service_name: str,
    status: str,
    risk_level: str = "low",
    approval_required: bool = False,
    approval_id: int | None = None,
    agent_role: str | None = None,
    input_summary: dict | None = None,
    error_message: str | None = None,
    business_object_type: str | None = None,
    business_object_id: str | None = None,
) -> ExecutionAuditLog:
    """
    功能描述：记录一次关键业务动作的执行轨迹。
    业务逻辑：把执行来源、人员、账簿、工具、风险等级和执行结果统一写入日志表。
    会计口径：日志用于还原业务执行过程，不替代凭证、报表或审计底稿本身。

    Args:
        db: 数据库会话。
        execution_source: 执行来源，manual_ui / cli_command / agent_auto / agent_assisted。
        user: 发起执行的登录用户。
        ledger_id: 当前账簿 ID。
        tool_name: 工具或业务动作名称。
        service_name: 实际处理的后端服务名称。
        status: 执行结果，success / failed / cancelled。
        risk_level: 操作风险等级，low / medium / high。
        approval_required: 是否需要人工确认。
        approval_id: 人工确认记录 ID。
        agent_role: Agent 角色，非 Agent 动作为空。
        input_summary: 输入摘要，避免保存敏感原文。
        error_message: 失败原因。
        business_object_type: 业务对象类型。
        business_object_id: 业务对象 ID。

    Returns:
        ExecutionAuditLog: 新创建的执行留痕记录。

    注意事项：
        1. 当前最小闭环先覆盖 Agent 路径，后续再扩展到人工页面和 CLI。
        2. 输入摘要只保存必要信息，不保存完整敏感文件或密钥。
    """
    log = ExecutionAuditLog(
        trace_id=uuid4().hex,
        request_id=uuid4().hex,
        execution_source=execution_source,
        user_id=user.id if user else None,
        team_id=user.team_id if user else None,
        ledger_id=ledger_id,
        agent_role=agent_role,
        tool_name=tool_name,
        service_name=service_name,
        business_object_type=business_object_type,
        business_object_id=business_object_id,
        risk_level=risk_level,
        approval_required=approval_required,
        approval_id=approval_id,
        input_summary=input_summary or {},
        status=status,
        error_message=error_message,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log
