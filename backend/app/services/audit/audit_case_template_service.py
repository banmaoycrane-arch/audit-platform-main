# -*- coding: utf-8 -*-
"""
模块功能：尽调审计案例模板服务
业务场景：定义尽调审计项目中多 Agent 的参与角色、可执行步骤、草稿规则和交付物规则
政策依据：审计项目质量控制要求，审计初稿、最终结论和交付物必须经过人工确认
输入数据：项目场景类型
输出结果：尽调审计案例模板
创建日期：2026-06-19
更新记录：
    2026-06-19  初始创建尽调审计案例模板服务
"""
from typing import Any

from app.services.agent.agent_role_registry import get_agent_role
from app.services.agent.agent_tool_registry import list_allowed_tools_for_intent


DELIVERABLE_RULES = {
    "internal_control": {
        "scenario": "internal_control",
        "display_name": "企业内控项目",
        "deliverable_policy": "交付物应体现企业自身管理痕迹，而不是单纯输出外部审计报告。",
        "allowed_deliverables": [
            "制度流程梳理记录",
            "控制点执行证据清单",
            "整改跟踪台账",
            "管理层复核记录",
            "内控缺陷沟通草稿",
        ],
        "human_confirmation_required": True,
    },
    "financial_due_diligence": {
        "scenario": "financial_due_diligence",
        "display_name": "财务尽调项目",
        "deliverable_policy": "交付物以尽调底稿、问题清单和审计初稿为主，正式结论必须人工确认。",
        "allowed_deliverables": [
            "资料清单",
            "审计底稿草稿",
            "风险发现清单",
            "审计初稿",
            "重大事项人工确认记录",
        ],
        "human_confirmation_required": True,
    },
}


def _tool_names_for_role(agent_role: str) -> list[str]:
    tools = list_allowed_tools_for_intent("due_diligence_audit", agent_role)
    return [tool["tool_name"] for tool in tools]


def build_due_diligence_case_template(scenario: str = "financial_due_diligence") -> dict[str, Any]:
    """
    功能描述：生成尽调审计案例模板。
    业务逻辑：定义允许参与的 Agent、允许执行的步骤、工具白名单、草稿规则和交付物规则。
    会计口径：生成底稿均为草稿，审计初稿、最终结论和重大问题定性必须人工确认。

    Args:
        scenario: 项目场景，financial_due_diligence / internal_control。

    Returns:
        dict: 尽调审计案例模板。

    注意事项：
        1. 模板只定义边界和规则，不直接执行具体任务。
        2. 所有工具必须在 API 白名单范围内。
    """
    deliverable_rule = DELIVERABLE_RULES.get(scenario, DELIVERABLE_RULES["financial_due_diligence"])
    allowed_agent_roles = [
        "orchestrator_agent",
        "accounting_clerk_agent",
        "quality_reviewer_agent",
        "auditor_agent",
        "permission_agent",
    ]

    execution_steps = [
        {
            "step_no": 1,
            "name": "导入原始资料",
            "agent_role": "accounting_clerk_agent",
            "can_execute": True,
            "output_status": "source_data_imported",
            "approval_required": True,
            "allowed_tools": ["create_import_job", "upload_source_file"],
        },
        {
            "step_no": 2,
            "name": "向量库识别业务循环",
            "agent_role": "accounting_clerk_agent",
            "can_execute": True,
            "output_status": "analysis_reference",
            "approval_required": False,
            "allowed_tools": ["identify_business_cycles_by_vector"],
        },
        {
            "step_no": 3,
            "name": "导入凭证并生成分录草稿",
            "agent_role": "accounting_clerk_agent",
            "can_execute": True,
            "output_status": "draft_only",
            "approval_required": True,
            "allowed_tools": ["generate_entry_drafts"],
        },
        {
            "step_no": 4,
            "name": "编制审计底稿草稿",
            "agent_role": "accounting_clerk_agent",
            "can_execute": True,
            "output_status": "draft_only",
            "approval_required": True,
            "allowed_tools": ["draft_audit_workpaper"],
        },
        {
            "step_no": 5,
            "name": "质量复核底稿",
            "agent_role": "quality_reviewer_agent",
            "can_execute": True,
            "output_status": "review_draft",
            "approval_required": True,
            "allowed_tools": ["review_workpaper_quality", "list_audit_findings"],
        },
        {
            "step_no": 6,
            "name": "生成审计初稿",
            "agent_role": "auditor_agent",
            "can_execute": True,
            "output_status": "draft_only",
            "approval_required": True,
            "allowed_tools": ["generate_audit_draft", "generate_issue_classification_draft"],
        },
    ]

    return {
        "template_code": "due_diligence_audit",
        "template_name": "尽调审计案例模板",
        "scenario": deliverable_rule["scenario"],
        "allowed_agent_roles": allowed_agent_roles,
        "allowed_agents": [get_agent_role(role) for role in allowed_agent_roles],
        "execution_steps": execution_steps,
        "workpaper_policy": "所有生成底稿均为草稿，不得作为最终报告或最终结论。",
        "audit_draft_policy": "生成的审计初稿必须人工确认。",
        "api_tool_policy": "所有工具必须在后端 API 白名单范围以内。",
        "deliverable_rule": deliverable_rule,
        "audit_trace_required": True,
        "immutable_trace_required": True,
    }
