# -*- coding: utf-8 -*-
"""
模块功能：多 Agent 协同计划服务
业务场景：以尽调审计任务为案例，由主控 Agent 拆解任务并分配给辅助 Agent
政策依据：审计项目质量控制要求，最终结论、最终交付物和重大问题定性必须人工确认
输入数据：用户自然语言任务、当前用户 ID、当前账簿 ID
输出结果：多 Agent 协同计划，不直接执行高风险动作
创建日期：2026-06-19
更新记录：
    2026-06-19  初始创建尽调审计多 Agent 协同计划服务
    2025-01-20  封装为 AgentOrchestrationService 类
"""
from typing import Any

from app.services.agent.agent_role_registry import get_agent_role
from app.services.agent.agent_tool_registry import list_allowed_tools_for_intent


def _tool_names_for_role(intent: str, agent_role: str) -> list[str]:
    tools = list_allowed_tools_for_intent(intent, agent_role)
    return [tool["tool_name"] for tool in tools]


class AgentOrchestrationService:
    """
    多 Agent 协同计划服务
    
    功能描述：生成尽调审计任务的多 Agent 协同计划
    业务逻辑：主控 Agent 只拆解和调度，辅助 Agent 按现场任务收集材料、编制底稿和形成草稿
    会计口径：最终结论、最终交付物、重大问题定性均必须人工确认，所有工作内容必须留痕
    
    注意事项：
        1. 本服务只生成计划，不执行工具
        2. 每一步是否可执行由项目案例和工具白名单共同决定
    """
    
    def build_due_diligence_orchestration_plan(
        self,
        message: str,
        user_id: int,
        ledger_id: int | None,
    ) -> dict[str, Any]:
        """
        生成尽调审计任务的多 Agent 协同计划
        
        Args:
            message: 用户自然语言任务
            user_id: 当前登录用户 ID
            ledger_id: 当前账簿 ID
            
        Returns:
            dict: 多 Agent 协同计划
        """
        intent = "due_diligence_audit"
        primary_agent_role = "orchestrator_agent"
        supporting_agent_roles = [
            "accounting_clerk_agent",
            "quality_reviewer_agent",
            "auditor_agent",
            "permission_agent",
        ]

        coordination_steps = [
            {
                "step_no": 1,
                "agent_role": "orchestrator_agent",
                "task": "只读查看用户任务和文件清单，拆解尽调审计现场任务。",
                "can_execute": False,
                "execution_policy": "plan_only",
                "approval_required": False,
                "audit_trace_required": True,
                "allowed_tools": [],
            },
            {
                "step_no": 2,
                "agent_role": "accounting_clerk_agent",
                "task": "按主控 Agent 分配收集原始材料与文件，只读整理资料清单。",
                "can_execute": True,
                "execution_policy": "read_only_tools_only",
                "approval_required": False,
                "audit_trace_required": True,
                "allowed_tools": _tool_names_for_role(intent, "accounting_clerk_agent"),
            },
            {
                "step_no": 3,
                "agent_role": "accounting_clerk_agent",
                "task": "根据审计计划编制审计底稿草稿，不形成报告。",
                "can_execute": True,
                "execution_policy": "draft_only_requires_review",
                "approval_required": True,
                "audit_trace_required": True,
                "allowed_tools": ["draft_audit_workpaper"],
            },
            {
                "step_no": 4,
                "agent_role": "quality_reviewer_agent",
                "task": "复核底稿完整性、程序执行情况和重大事项确认状态。",
                "can_execute": True,
                "execution_policy": "review_only_requires_human_confirmation",
                "approval_required": True,
                "audit_trace_required": True,
                "allowed_tools": _tool_names_for_role(intent, "quality_reviewer_agent"),
            },
            {
                "step_no": 5,
                "agent_role": "auditor_agent",
                "task": "生成审计初稿和问题汇总草稿，最终结论必须人工确认。",
                "can_execute": True,
                "execution_policy": "draft_only_requires_review",
                "approval_required": True,
                "audit_trace_required": True,
                "allowed_tools": _tool_names_for_role(intent, "auditor_agent"),
            },
            {
                "step_no": 6,
                "agent_role": "permission_agent",
                "task": "检查最终结论、最终交付物、重大问题定性是否均进入人工确认。",
                "can_execute": False,
                "execution_policy": "control_check_only",
                "approval_required": True,
                "audit_trace_required": True,
                "allowed_tools": [],
            },
        ]

        return {
            "intent": intent,
            "task_message": message,
            "primary_agent_role": primary_agent_role,
            "primary_agent": get_agent_role(primary_agent_role),
            "supporting_agent_roles": supporting_agent_roles,
            "supporting_agents": [get_agent_role(role) for role in supporting_agent_roles],
            "coordination_steps": coordination_steps,
            "human_confirmation_required_for": [
                "最终结论",
                "最终交付物",
                "重大问题定性",
                "审计底稿草稿复核",
            ],
            "file_access_policy": "read_only",
            "case_execution_definition": "每一步是否实际执行由具体项目案例定义；本接口只生成协同计划。",
            "audit_trace_required": True,
            "audit_trace_policy": "所有 Agent 工作内容必须写入不可篡改留痕链。",
            "user_id": user_id,
            "ledger_id": ledger_id,
        }


_orchestration_service_instance = AgentOrchestrationService()


def build_due_diligence_orchestration_plan(
    message: str,
    user_id: int,
    ledger_id: int | None,
) -> dict[str, Any]:
    return _orchestration_service_instance.build_due_diligence_orchestration_plan(
        message, user_id, ledger_id
    )
