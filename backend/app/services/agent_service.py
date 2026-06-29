import json

from app.services.agent_tool_registry import list_allowed_tools_for_intent
from app.services.llm_client_service import LightweightLLMClient


SYSTEM_CONTEXT = """你是财务向量审计系统的导航助手。
系统已有页面和能力：
- 首页 `/`：查看工作台概览。
- 记账模式 `/accounting/step/1` 到 `/accounting/step/5`：选择资料、上传原始凭证/流水/合同、解析资料、生成并复核会计分录、导出或进入后续处理。
- 审计模式 `/audit/step/1` 到 `/audit/step/6`：选择审计范围、导入资料和序时簿、执行完整性/准确性/截止性/分类测试、复核风险发现、形成和导出审计报告。
- 基础资料 `/basic/coa`：维护会计科目、客户、供应商和往来单位等基础数据。
- 会计期间 `/accounting-periods`：期间管理、结账、损益结转。
- 报表页面：查看试算平衡表、资产负债表、利润表等财务报表。
- 风险列表和审计发现：复核风险、证据、处理状态。
- 已实现 EntryTag、文档解析、业务循环、内控审计等能力。
只推荐系统已有路径，不要编造不存在页面。请以 JSON 输出，字段为 intent、confidence、reply、suggested_path、steps。"""


INTENT_RULES = {
    "accounting_import": {
        "keywords": ["记账", "凭证", "分录", "导入", "原始凭证"],
        "suggested_path": "/accounting/step/1",
        "reply": "我识别到你想处理记账导入或凭证分录生成，可以从记账模式开始。",
        "steps": [
            "选择原始资料类型",
            "上传原始凭证、流水或合同资料",
            "生成并复核会计分录",
            "确认无误后导出或进入后续账务处理",
        ],
    },
    "audit_workflow": {
        "keywords": ["审计", "测试", "风险", "发现", "序时簿"],
        "suggested_path": "/audit/step/1",
        "reply": "我识别到你想执行审计流程，可以从审计范围选择开始。",
        "steps": [
            "选择审计范围",
            "导入原始资料和被审计单位分录",
            "执行完整性、准确性、截止性、分类等测试",
            "复核风险发现并形成审计结论",
        ],
    },
    "report_export": {
        "keywords": ["报告", "导出", "xlsx", "excel"],
        "suggested_path": "/audit/step/6",
        "reply": "我识别到你想导出审计报告，可以前往审计报告导出步骤。",
        "steps": [
            "确认审计测试已完成",
            "复核审计发现和处理状态",
            "选择报告格式，例如 XLSX 或 JSON",
            "导出并归档审计报告",
        ],
    },
    "basic_data": {
        "keywords": ["科目", "客户", "供应商", "往来", "基础资料"],
        "suggested_path": "/basic/coa",
        "reply": "我识别到你想维护基础资料，可以先进入会计科目或往来单位维护。",
        "steps": [
            "维护会计科目",
            "维护客户、供应商等往来单位",
            "检查期初余额等基础数据",
            "再进入凭证、报表或审计流程",
        ],
    },
    "period_close": {
        "keywords": ["期间", "结账", "结转", "损益"],
        "suggested_path": "/accounting-periods",
        "reply": "我识别到你想处理会计期间、结账或损益结转，可以进入会计期间页面。",
        "steps": [
            "选择需要处理的会计期间",
            "检查本期凭证和报表数据",
            "执行损益结转",
            "确认后完成期间结账或后续报表检查",
        ],
    },
}

GENERAL_HELP = {
    "intent": "general_help",
    "confidence": 0.2,
    "reply": "我可以帮你定位记账导入、审计测试、报告导出、基础资料和期间结账等功能。请描述你想完成的财务工作。",
    "suggested_path": "/",
    "steps": [
        "说明你当前要处理的业务场景",
        "可包含关键词：导入、审计、报告、凭证、科目、期间",
        "根据建议路径进入对应页面继续操作",
    ],
}

TASK_PLAN_RULES = {
    "accounting_import": {
        "task_type": "accounting_assisted_import",
        "agent_role": "accounting_assistant_agent",
        "risk_level": "medium",
        "required_inputs": ["原始凭证、银行流水或合同资料", "当前账簿", "会计期间"],
        "allowed_tools": ["create_import_job", "upload_source_file", "generate_entry_drafts"],
        "approval_required": True,
        "approval_reason": "Agent 只能生成分录草稿，正式入账前需要人工复核确认。",
    },
    "audit_workflow": {
        "task_type": "audit_assisted_test",
        "agent_role": "audit_assistant_agent",
        "risk_level": "medium",
        "required_inputs": ["审计范围", "序时簿或分录数据", "审计期间"],
        "allowed_tools": ["run_audit_tests", "list_audit_findings", "draft_audit_conclusion"],
        "approval_required": True,
        "approval_reason": "Agent 可形成审计发现草稿，最终审计结论需要人工确认。",
    },
    "report_export": {
        "task_type": "report_assisted_export",
        "agent_role": "report_agent",
        "risk_level": "medium",
        "required_inputs": ["报告范围", "审计发现复核状态", "导出格式"],
        "allowed_tools": ["generate_report_preview", "export_audit_report"],
        "approval_required": True,
        "approval_reason": "正式报告导出前需要确认报告范围和审计结论。",
    },
    "basic_data": {
        "task_type": "basic_data_assistance",
        "agent_role": "accounting_assistant_agent",
        "risk_level": "medium",
        "required_inputs": ["当前账簿", "科目或往来单位资料"],
        "allowed_tools": ["list_chart_of_accounts", "list_counterparties"],
        "approval_required": True,
        "approval_reason": "基础资料变更会影响后续凭证、报表和审计口径，需要人工确认。",
    },
    "period_close": {
        "task_type": "period_close_assistance",
        "agent_role": "accounting_assistant_agent",
        "risk_level": "high",
        "required_inputs": ["当前账簿", "会计期间", "结账前检查结果"],
        "allowed_tools": ["generate_trial_balance", "preview_profit_loss_transfer"],
        "approval_required": True,
        "approval_reason": "损益结转、结账和反结账属于高风险动作，必须人工确认并留痕。",
    },
    "general_help": {
        "task_type": "navigation_help",
        "agent_role": "navigation_agent",
        "risk_level": "low",
        "required_inputs": ["用户希望完成的财务或审计任务"],
        "allowed_tools": ["suggest_system_path"],
        "approval_required": False,
        "approval_reason": "仅提供导航建议，不直接操作财务数据。",
    },
}


def detect_intent(message: str) -> dict:
    text = message.lower()
    best_intent = "general_help"
    best_hits = 0

    for intent, rule in INTENT_RULES.items():
        hits = sum(1 for keyword in rule["keywords"] if keyword.lower() in text)
        if hits > best_hits:
            best_intent = intent
            best_hits = hits

    if best_hits == 0:
        return GENERAL_HELP.copy()

    confidence = min(0.95, 0.55 + best_hits * 0.1)
    rule = INTENT_RULES[best_intent]
    return {
        "intent": best_intent,
        "confidence": round(confidence, 2),
        "reply": rule["reply"],
        "suggested_path": rule["suggested_path"],
        "steps": rule["steps"],
    }


def plan_task(intent: str, message: str) -> dict:
    if intent == "general_help" or intent not in INTENT_RULES:
        return GENERAL_HELP.copy()

    plan = detect_intent(message)
    if plan["intent"] == intent:
        return plan

    rule = INTENT_RULES[intent]
    return {
        "intent": intent,
        "confidence": 0.6,
        "reply": rule["reply"],
        "suggested_path": rule["suggested_path"],
        "steps": rule["steps"],
    }


def normalize_agent_response(raw: dict, fallback: dict, source: str, model_available: bool) -> dict:
    steps = raw.get("steps")
    if not isinstance(steps, list) or not steps:
        steps = fallback["steps"]

    confidence = raw.get("confidence", fallback["confidence"])
    try:
        confidence = float(confidence)
    except (TypeError, ValueError):
        confidence = fallback["confidence"]

    return {
        "intent": raw.get("intent") or fallback["intent"],
        "confidence": max(0, min(1, confidence)),
        "reply": raw.get("reply") or fallback["reply"],
        "suggested_path": raw.get("suggested_path") or fallback["suggested_path"],
        "steps": [str(step) for step in steps],
        "source": source,
        "model_available": model_available,
    }


def build_task_plan(agent_result: dict, user_id: int, ledger_id: int | None) -> dict:
    intent = agent_result.get("intent") or "general_help"
    rule = TASK_PLAN_RULES.get(intent, TASK_PLAN_RULES["general_help"])
    tool_details = list_allowed_tools_for_intent(intent, rule["agent_role"])
    allowed_tool_names = [tool["tool_name"] for tool in tool_details]
    context_notes = ["Agent 接口已绑定当前登录用户，后续执行必须继续复用同一套鉴权逻辑。"]
    if ledger_id is None:
        context_notes.append("当前未指定账簿；涉及凭证、报表、审计数据前需要先选择账簿。")
    else:
        context_notes.append(f"当前任务将以账簿 {ledger_id} 作为业务上下文。")

    return {
        "task_type": rule["task_type"],
        "agent_role": rule["agent_role"],
        "risk_level": rule["risk_level"],
        "required_inputs": rule["required_inputs"],
        "allowed_tools": allowed_tool_names,
        "tool_details": tool_details,
        "approval_required": rule["approval_required"],
        "approval_reason": rule["approval_reason"],
        "execution_source": "agent_assisted",
        "user_id": user_id,
        "ledger_id": ledger_id,
        "audit_trace_required": True,
        "context_notes": context_notes,
    }


def plan_agent_task(message: str, user_id: int, ledger_id: int | None, llm_client=None) -> dict:
    agent_result = chat_with_agent(message, llm_client=llm_client)
    agent_result["task_plan"] = build_task_plan(agent_result, user_id, ledger_id)
    return agent_result


def chat_with_agent(message: str, llm_client=None) -> dict:
    fallback = detect_intent(message)
    client = llm_client or LightweightLLMClient()

    if not client.is_configured():
        return normalize_agent_response(fallback, fallback, "rules", False)

    messages = [
        {"role": "system", "content": SYSTEM_CONTEXT},
        {
            "role": "user",
            "content": (
                "请理解用户在财务向量审计系统中的需求，并只返回 JSON。"
                f"用户消息：{message}"
            ),
        },
    ]
    result = client.chat(messages, temperature=0.2)
    if not result.available:
        return normalize_agent_response(fallback, fallback, "rules", False)

    content = result.content or ""
    try:
        raw = json.loads(content)
        if not isinstance(raw, dict):
            raw = {"reply": content}
    except json.JSONDecodeError:
        raw = {"reply": content}

    return normalize_agent_response(raw, fallback, "llm", True)
