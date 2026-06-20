# -*- coding: utf-8 -*-
"""
模块功能：Agent 工具白名单注册表
业务场景：限制 Agent 只能规划或调用经过授权的后端工具，避免越权执行财务动作
政策依据：会计信息系统内部控制要求，关键操作需按岗位授权、风险等级和人工复核规则执行
输入数据：Agent 意图、Agent 角色和工具名称
输出结果：允许使用的工具配置清单
创建日期：2026-06-19
更新记录：
    2026-06-19  初始创建 Agent 工具白名单注册表
"""

AGENT_TOOL_REGISTRY = {
    "suggest_system_path": {
        "tool_name": "suggest_system_path",
        "description": "根据用户自然语言意图推荐系统页面路径，不操作业务数据。",
        "allowed_agent_roles": ["navigation_agent"],
        "intents": ["general_help"],
        "risk_level": "low",
        "approval_required": False,
        "audit_trace_required": True,
    },
    "create_import_job": {
        "tool_name": "create_import_job",
        "description": "创建资料导入任务，用于后续上传原始凭证、流水或合同资料。",
        "allowed_agent_roles": ["accounting_assistant_agent", "accounting_clerk_agent"],
        "intents": ["accounting_import", "due_diligence_audit"],
        "risk_level": "medium",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "upload_source_file": {
        "tool_name": "upload_source_file",
        "description": "上传原始资料文件，文件解析和入账前仍需人工复核。",
        "allowed_agent_roles": ["accounting_assistant_agent", "accounting_clerk_agent", "audit_assistant_agent"],
        "intents": ["accounting_import", "audit_workflow", "due_diligence_audit"],
        "risk_level": "medium",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "collect_readonly_source_files": {
        "tool_name": "collect_readonly_source_files",
        "description": "只读方式收集尽调审计所需原始材料清单，不修改、不删除文件。",
        "allowed_agent_roles": ["accounting_clerk_agent"],
        "intents": ["due_diligence_audit"],
        "risk_level": "low",
        "approval_required": False,
        "audit_trace_required": True,
    },
    "draft_audit_workpaper": {
        "tool_name": "draft_audit_workpaper",
        "description": "根据审计计划和原始资料编制审计底稿草稿，不形成最终报告或结论。",
        "allowed_agent_roles": ["accounting_clerk_agent", "audit_assistant_agent"],
        "intents": ["due_diligence_audit"],
        "risk_level": "medium",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "review_workpaper_quality": {
        "tool_name": "review_workpaper_quality",
        "description": "复核审计底稿完整性、程序执行情况和交叉索引，不形成最终意见。",
        "allowed_agent_roles": ["quality_reviewer_agent"],
        "intents": ["due_diligence_audit"],
        "risk_level": "medium",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "generate_audit_draft": {
        "tool_name": "generate_audit_draft",
        "description": "生成审计初稿，必须由人工确认后才能作为正式输出依据。",
        "allowed_agent_roles": ["auditor_agent"],
        "intents": ["due_diligence_audit"],
        "risk_level": "high",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "generate_issue_classification_draft": {
        "tool_name": "generate_issue_classification_draft",
        "description": "生成重大问题定性草稿，最终定性必须由人工确认。",
        "allowed_agent_roles": ["audit_assistant_agent"],
        "intents": ["due_diligence_audit"],
        "risk_level": "high",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "generate_final_deliverable_draft": {
        "tool_name": "generate_final_deliverable_draft",
        "description": "生成最终交付物草稿，正式交付必须由人工确认。",
        "allowed_agent_roles": ["report_agent"],
        "intents": ["due_diligence_audit"],
        "risk_level": "high",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "identify_business_cycles_by_vector": {
        "tool_name": "identify_business_cycles_by_vector",
        "description": "利用向量库辅助识别原始资料对应的业务循环，比固定关系字段更灵活。",
        "allowed_agent_roles": ["accounting_clerk_agent", "audit_assistant_agent"],
        "intents": ["due_diligence_audit"],
        "risk_level": "low",
        "approval_required": False,
        "audit_trace_required": True,
    },
    "generate_entry_drafts": {
        "tool_name": "generate_entry_drafts",
        "description": "根据原始资料生成会计分录草稿，不直接形成正式入账凭证。",
        "allowed_agent_roles": ["accounting_assistant_agent", "accounting_clerk_agent"],
        "intents": ["accounting_import", "due_diligence_audit"],
        "risk_level": "medium",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "run_audit_tests": {
        "tool_name": "run_audit_tests",
        "description": "执行审计测试并形成待复核的风险发现或测试结果。",
        "allowed_agent_roles": ["audit_assistant_agent", "auditor_agent"],
        "intents": ["audit_workflow", "due_diligence_audit"],
        "risk_level": "medium",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "list_audit_findings": {
        "tool_name": "list_audit_findings",
        "description": "查询审计发现列表，仅用于查看和辅助复核。",
        "allowed_agent_roles": ["audit_assistant_agent", "auditor_agent", "quality_reviewer_agent"],
        "intents": ["audit_workflow", "due_diligence_audit"],
        "risk_level": "low",
        "approval_required": False,
        "audit_trace_required": True,
    },
    "draft_audit_conclusion": {
        "tool_name": "draft_audit_conclusion",
        "description": "生成审计结论草稿，最终结论必须由人工确认。",
        "allowed_agent_roles": ["audit_assistant_agent"],
        "intents": ["audit_workflow"],
        "risk_level": "medium",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "generate_report_preview": {
        "tool_name": "generate_report_preview",
        "description": "生成报告预览或报表预览，不直接作为正式归档报告。",
        "allowed_agent_roles": ["report_agent"],
        "intents": ["report_export"],
        "risk_level": "low",
        "approval_required": False,
        "audit_trace_required": True,
    },
    "export_audit_report": {
        "tool_name": "export_audit_report",
        "description": "导出正式审计报告，导出前必须确认报告范围和结论。",
        "allowed_agent_roles": ["report_agent"],
        "intents": ["report_export"],
        "risk_level": "medium",
        "approval_required": True,
        "audit_trace_required": True,
    },
    "list_chart_of_accounts": {
        "tool_name": "list_chart_of_accounts",
        "description": "查询会计科目列表，仅用于辅助基础资料维护。",
        "allowed_agent_roles": ["accounting_assistant_agent"],
        "intents": ["basic_data"],
        "risk_level": "low",
        "approval_required": False,
        "audit_trace_required": True,
    },
    "list_counterparties": {
        "tool_name": "list_counterparties",
        "description": "查询客户、供应商等往来单位列表。",
        "allowed_agent_roles": ["accounting_assistant_agent"],
        "intents": ["basic_data"],
        "risk_level": "low",
        "approval_required": False,
        "audit_trace_required": True,
    },
    "generate_trial_balance": {
        "tool_name": "generate_trial_balance",
        "description": "生成试算平衡表或结账前检查结果。",
        "allowed_agent_roles": ["accounting_assistant_agent", "report_agent"],
        "intents": ["period_close"],
        "risk_level": "low",
        "approval_required": False,
        "audit_trace_required": True,
    },
    "preview_profit_loss_transfer": {
        "tool_name": "preview_profit_loss_transfer",
        "description": "预览损益结转影响，不直接执行正式结转。",
        "allowed_agent_roles": ["accounting_assistant_agent"],
        "intents": ["period_close"],
        "risk_level": "high",
        "approval_required": True,
        "audit_trace_required": True,
    },
}


def list_allowed_tools_for_intent(intent: str, agent_role: str | None = None) -> list[dict]:
    """
    功能描述：按业务意图和 Agent 角色返回可用工具白名单。
    业务逻辑：只返回已在 AGENT_TOOL_REGISTRY 中登记且匹配意图、角色的工具。
    会计口径：工具白名单相当于岗位授权清单，不在清单内的动作不能由 Agent 规划执行。

    Args:
        intent: Agent 识别出的业务意图。
        agent_role: 当前 Agent 角色，可为空。

    Returns:
        list[dict]: 可用工具配置列表。

    注意事项：
        1. 当前只做规划白名单，不实际执行工具。
        2. 后续执行型 Agent 必须继续复用该白名单。
    """
    allowed_tools = []
    for tool in AGENT_TOOL_REGISTRY.values():
        if intent not in tool["intents"]:
            continue
        if agent_role and agent_role not in tool["allowed_agent_roles"]:
            continue
        allowed_tools.append(tool.copy())
    return allowed_tools


def get_agent_tool(tool_name: str) -> dict | None:
    """
    功能描述：根据工具名称获取白名单配置。
    业务逻辑：只有注册表中存在的工具才视为 Agent 可识别工具。
    会计口径：未登记工具不得进入 Agent 规划或执行范围。

    Args:
        tool_name: 工具名称。

    Returns:
        dict | None: 工具配置；不存在时返回 None。
    """
    tool = AGENT_TOOL_REGISTRY.get(tool_name)
    return tool.copy() if tool else None
