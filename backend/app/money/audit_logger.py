# -*- coding: utf-8 -*-
"""
模块功能：重大金额操作的审计日志记录
业务场景：对单笔大额交易、币种转换、损益结转、期间关闭等关键操作留痕
创建日期：2026-07-02
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.money.amount import Money


# 默认大额阈值：100万人民币
DEFAULT_SIGNIFICANT_AMOUNT_THRESHOLD: Decimal = Decimal("1000000.00")


@dataclass
class MoneyAuditEvent:
    """金额审计事件"""

    trace_id: str
    user_id: int | None
    team_id: int | None
    ledger_id: int | None
    project_id: int | None
    service_name: str
    tool_name: str
    business_object_type: str
    business_object_id: str | None
    action: str
    input_summary: dict[str, Any]
    before_snapshot: dict[str, Any] | None
    after_snapshot: dict[str, Any] | None
    risk_level: str
    status: str
    error_message: str | None = None


def _determine_risk_level(amount: Decimal, threshold: Decimal | None = None) -> str:
    """
    功能描述：根据金额大小判定风险等级
    业务逻辑：超过阈值为 high，否则根据金额为 medium/low

    Args:
        amount: 金额绝对值
        threshold: 大额阈值

    Returns:
        str: 风险等级 high/medium/low
    """
    threshold = threshold or DEFAULT_SIGNIFICANT_AMOUNT_THRESHOLD
    abs_amount = abs(amount)

    if abs_amount >= threshold:
        return "high"
    if abs_amount >= Decimal("100000.00"):
        return "medium"
    return "low"


def _serialize_money(value: Any) -> Any:
    """将 Money/Decimal 序列化为可 JSON 序列化的格式"""
    if isinstance(value, Money):
        return {
            "amount": str(value.amount),
            "currency": value.currency.code,
        }
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {k: _serialize_money(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_money(v) for v in value]
    return value


def log_money_operation(
    db: Session,
    *,
    user_id: int | None,
    team_id: int | None = None,
    ledger_id: int | None = None,
    project_id: int | None = None,
    service_name: str,
    tool_name: str,
    business_object_type: str,
    business_object_id: str | None = None,
    action: str,
    money_value: Money | Decimal | str | int | float | None = None,
    input_summary: dict[str, Any] | None = None,
    before_snapshot: dict[str, Any] | None = None,
    after_snapshot: dict[str, Any] | None = None,
    status: str = "success",
    error_message: str | None = None,
    trace_id: str | None = None,
) -> None:
    """
    功能描述：记录重大金额操作审计日志
    业务逻辑：复用现有 ExecutionAuditLog 模型，写入金额相关操作记录

    Args:
        db: 数据库会话
        user_id: 操作人 ID
        team_id: 团队 ID
        ledger_id: 账簿 ID
        project_id: 项目 ID
        service_name: 服务名
        tool_name: 工具/函数名
        business_object_type: 业务对象类型
        business_object_id: 业务对象 ID
        action: 动作描述
        money_value: 涉及金额
        input_summary: 输入摘要
        before_snapshot: 变更前快照
        after_snapshot: 变更后快照
        status: 操作状态 success/failed
        error_message: 错误信息
        trace_id: 追踪 ID，默认自动生成

    注意事项：
        1. 单笔金额超过阈值时 risk_level 自动标记为 high
        2. 失败操作同样记录，便于排查
    """
    from app.db.models import ExecutionAuditLog
    from app.money.parsing import parse_decimal

    trace_id = trace_id or str(uuid4())

    # 解析金额用于风险等级判定
    amount = Decimal("0.00")
    if money_value is not None:
        if isinstance(money_value, Money):
            amount = money_value.amount
        else:
            amount = parse_decimal(money_value)

    risk_level = _determine_risk_level(amount)

    summary = _serialize_money(input_summary or {})
    if money_value is not None:
        summary["amount"] = _serialize_money(money_value)
        summary["action"] = action

    audit_log = ExecutionAuditLog(
        trace_id=trace_id,
        request_id=trace_id,
        service_name=service_name,
        tool_name=tool_name,
        execution_source="system",
        business_object_type=business_object_type,
        business_object_id=business_object_id or "",
        user_id=user_id,
        team_id=team_id,
        ledger_id=ledger_id,
        project_id=project_id,
        status=status,
        risk_level=risk_level,
        input_summary=summary,
        before_snapshot=_serialize_money(before_snapshot),
        after_snapshot=_serialize_money(after_snapshot),
        error_message=error_message,
    )

    db.add(audit_log)
