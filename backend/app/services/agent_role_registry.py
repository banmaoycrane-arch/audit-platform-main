# -*- coding: utf-8 -*-
"""
模块功能：Agent 角色注册表
业务场景：定义多 Agent 协同中的岗位职责、权限边界和人工监督要求
政策依据：审计项目质量控制要求，关键判断、最终结论和交付物必须由人工确认
输入数据：Agent 角色名称
输出结果：Agent 角色配置
创建日期：2026-06-19
更新记录：
    2026-06-19  初始创建 Agent 角色注册表
"""

AGENT_ROLE_REGISTRY = {
    "orchestrator_agent": {
        "role_name": "orchestrator_agent",
        "display_name": "主控 Agent",
        "description": "负责理解任务、拆解步骤、调度辅助 Agent，不直接修改业务数据。",
        "allowed_intents": ["due_diligence_audit", "audit_workflow"],
        "file_access": "read_only",
        "can_execute_tools": False,
        "requires_human_supervision": True,
        "prohibited_outputs": ["最终审计结论", "最终交付物", "重大问题定性"],
    },
    "accounting_clerk_agent": {
        "role_name": "accounting_clerk_agent",
        "display_name": "会计文员 Agent",
        "description": "按主控 Agent 分配的现场任务收集原始材料、导入凭证并编制审计底稿草稿。",
        "allowed_intents": ["due_diligence_audit", "accounting_import"],
        "file_access": "read_only",
        "can_execute_tools": True,
        "requires_human_supervision": True,
        "prohibited_outputs": ["审计报告", "最终结论", "重大问题定性"],
    },
    "audit_assistant_agent": {
        "role_name": "audit_assistant_agent",
        "display_name": "审计助理 Agent",
        "description": "执行审计测试、整理风险发现草稿和复核底稿勾稽关系。",
        "allowed_intents": ["due_diligence_audit", "audit_workflow"],
        "file_access": "read_only",
        "can_execute_tools": True,
        "requires_human_supervision": True,
        "prohibited_outputs": ["最终审计结论", "重大问题定性"],
    },
    "quality_reviewer_agent": {
        "role_name": "quality_reviewer_agent",
        "display_name": "质量复核 Agent",
        "description": "复核底稿完整性、程序执行情况和重大事项是否进入人工确认。",
        "allowed_intents": ["due_diligence_audit"],
        "file_access": "read_only",
        "can_execute_tools": True,
        "requires_human_supervision": True,
        "prohibited_outputs": ["最终审计结论", "最终交付物签发"],
    },
    "auditor_agent": {
        "role_name": "auditor_agent",
        "display_name": "审计师 Agent",
        "description": "形成审计初稿和问题汇总草稿，重大判断和最终意见必须人工确认。",
        "allowed_intents": ["due_diligence_audit"],
        "file_access": "read_only",
        "can_execute_tools": True,
        "requires_human_supervision": True,
        "prohibited_outputs": ["最终审计意见", "最终交付物签发"],
    },
    "report_agent": {
        "role_name": "report_agent",
        "display_name": "报告助理 Agent",
        "description": "仅生成报告预览或交付物清单草稿，不直接形成最终报告。",
        "allowed_intents": ["due_diligence_audit", "report_export"],
        "file_access": "read_only",
        "can_execute_tools": True,
        "requires_human_supervision": True,
        "prohibited_outputs": ["最终交付物", "最终报告签发"],
    },
    "permission_agent": {
        "role_name": "permission_agent",
        "display_name": "权限检查 Agent",
        "description": "检查任务步骤、工具白名单、风险等级和人工确认要求。",
        "allowed_intents": ["due_diligence_audit", "audit_workflow", "accounting_import"],
        "file_access": "none",
        "can_execute_tools": False,
        "requires_human_supervision": False,
        "prohibited_outputs": ["业务结论"],
    },
}


def get_agent_role(role_name: str) -> dict | None:
    """
    功能描述：根据角色名称获取 Agent 岗位配置。
    业务逻辑：只有注册表中的角色才能参与多 Agent 协同计划。
    会计口径：角色配置相当于审计项目组岗位分工和授权边界。

    Args:
        role_name: Agent 角色名称。

    Returns:
        dict | None: Agent 角色配置；不存在时返回 None。
    """
    role = AGENT_ROLE_REGISTRY.get(role_name)
    return role.copy() if role else None


def list_agent_roles() -> list[dict]:
    """
    功能描述：返回全部 Agent 角色配置。
    业务逻辑：用于前端展示和协同计划校验。
    会计口径：展示岗位分工，不授予额外业务权限。

    Returns:
        list[dict]: Agent 角色配置列表。
    """
    return [role.copy() for role in AGENT_ROLE_REGISTRY.values()]
