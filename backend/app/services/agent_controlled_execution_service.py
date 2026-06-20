# -*- coding: utf-8 -*-
"""
模块功能：Agent 确认后的草稿受控执行服务
业务场景：人工确认后，只允许 Agent 生成草稿或预览类结果，不触发正式交付或高风险真实动作
"""
from sqlalchemy.orm import Session

from app.db.models import AgentApproval
from app.services.agent_tool_registry import get_agent_tool

DRAFT_EXECUTABLE_TOOLS = {
    "draft_audit_workpaper": {
        "output_type": "draft",
        "title": "审计底稿草稿",
        "notice": "该底稿仅供人工复核，不构成最终审计结论。",
    },
    "review_workpaper_quality": {
        "output_type": "draft",
        "title": "底稿质量复核草稿",
        "notice": "该复核结果仅用于质量控制复核，不替代人工复核意见。",
    },
    "generate_audit_draft": {
        "output_type": "draft",
        "title": "审计初稿草稿",
        "notice": "该审计初稿仅供人工复核，不构成正式报告或最终结论。",
    },
    "generate_issue_classification_draft": {
        "output_type": "draft",
        "title": "重大问题定性草稿",
        "notice": "重大问题最终定性必须由人工确认，本结果不得直接作为最终意见。",
    },
    "generate_final_deliverable_draft": {
        "output_type": "draft",
        "title": "交付物草稿",
        "notice": "该交付物为草稿，正式交付必须另行人工确认。",
    },
}


def execute_confirmed_agent_draft(db: Session, approval_id: int) -> dict:
    approval = db.get(AgentApproval, approval_id)
    if approval is None:
        raise LookupError("Agent 确认记录不存在")
    if approval.status != "confirmed":
        raise ValueError("只有已确认记录可以进入草稿受控执行")

    tool = get_agent_tool(approval.tool_name)
    if tool is None:
        raise PermissionError("工具不在 Agent 白名单中")
    if approval.agent_role not in tool["allowed_agent_roles"]:
        raise PermissionError("确认记录中的 Agent 角色无权执行该工具")
    if approval.tool_name not in DRAFT_EXECUTABLE_TOOLS:
        raise PermissionError("该工具不属于草稿或预览类受控执行范围")

    draft_config = DRAFT_EXECUTABLE_TOOLS[approval.tool_name]
    return {
        "approval_id": approval.id,
        "tool_name": approval.tool_name,
        "agent_role": approval.agent_role,
        "execution_status": "success",
        "output_type": draft_config["output_type"],
        "result": {
            "title": draft_config["title"],
            "notice": draft_config["notice"],
            "source_args": approval.request_args_summary or {},
            "review_required": True,
            "formal_delivery_allowed": False,
        },
    }
