from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import AgentApproval, AgentDraftReview, ChartOfAccounts, Counterparty, ExecutionAuditLog
from app.db.session import SessionLocal
from app.main import app
from app.services.agent.agent_orchestration_service import build_due_diligence_orchestration_plan
from app.services.agent.agent_role_registry import get_agent_role
from app.services.agent.agent_tool_registry import get_agent_tool, list_allowed_tools_for_intent
from app.services.audit.audit_case_template_service import build_due_diligence_case_template
from app.services.agent.llm_client_service import LLMResult
from app.services.agent.model_config_service import get_model_config_status

client = TestClient(app)


def auth_headers(username: str, phone: str) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    phone_suffix = str(uuid4().int % 100).zfill(2)
    response = client.post("/api/auth/register", json={
        "username": f"{username}_{suffix}",
        "phone": f"{phone}{phone_suffix}",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def latest_audit_log(tool_name: str) -> ExecutionAuditLog | None:
    db = SessionLocal()
    try:
        return (
            db.query(ExecutionAuditLog)
            .filter(ExecutionAuditLog.tool_name == tool_name)
            .order_by(ExecutionAuditLog.id.desc())
            .first()
        )
    finally:
        db.close()


def latest_agent_approval(tool_name: str) -> AgentApproval | None:
    db = SessionLocal()
    try:
        return (
            db.query(AgentApproval)
            .filter(AgentApproval.tool_name == tool_name)
            .order_by(AgentApproval.id.desc())
            .first()
        )
    finally:
        db.close()


def latest_draft_review(approval_id: int) -> AgentDraftReview | None:
    db = SessionLocal()
    try:
        return (
            db.query(AgentDraftReview)
            .filter(AgentDraftReview.approval_id == approval_id)
            .order_by(AgentDraftReview.id.desc())
            .first()
        )
    finally:
        db.close()


def seed_agent_tool_basic_data(account_code: str, counterparty_name: str) -> None:
    db = SessionLocal()
    try:
        db.add(
            ChartOfAccounts(
                code=account_code,
                name="Agent测试科目",
                category="asset",
                direction="debit",
            )
        )
        db.add(Counterparty(name=counterparty_name, role="customer"))
        db.commit()
    finally:
        db.close()


class FakeUnconfiguredLLMClient:
    def is_configured(self) -> bool:
        return False

    def chat(self, messages: list[dict], temperature: float = 0.2) -> LLMResult:
        return LLMResult(available=False, error="fake unconfigured")


@pytest.fixture(autouse=True)
def force_rules_fallback(monkeypatch):
    monkeypatch.setattr("app.services.agent.agent_service.LightweightLLMClient", FakeUnconfiguredLLMClient)


def test_agent_tool_registry_filters_by_intent_and_role():
    tools = list_allowed_tools_for_intent("accounting_import", "accounting_assistant_agent")
    tool_names = {tool["tool_name"] for tool in tools}
    assert {"create_import_job", "upload_source_file", "generate_entry_drafts"}.issubset(tool_names)
    assert "run_audit_tests" not in tool_names
    assert all(tool["audit_trace_required"] is True for tool in tools)


def test_agent_tool_registry_rejects_unknown_tool():
    assert get_agent_tool("unsafe_direct_database_update") is None


def test_due_diligence_agent_role_registry_sets_boundaries():
    orchestrator = get_agent_role("orchestrator_agent")
    accounting_clerk = get_agent_role("accounting_clerk_agent")
    assert orchestrator is not None
    assert orchestrator["file_access"] == "read_only"
    assert orchestrator["can_execute_tools"] is False
    assert "重大问题定性" in orchestrator["prohibited_outputs"]
    assert accounting_clerk is not None
    assert accounting_clerk["file_access"] == "read_only"
    assert accounting_clerk["can_execute_tools"] is True
    assert "审计报告" in accounting_clerk["prohibited_outputs"]


def test_due_diligence_orchestration_plan_sets_agents_and_controls():
    plan = build_due_diligence_orchestration_plan("对目标公司做尽调审计", 1, None)
    assert plan["intent"] == "due_diligence_audit"
    assert plan["primary_agent_role"] == "orchestrator_agent"
    assert "accounting_clerk_agent" in plan["supporting_agent_roles"]
    assert "最终结论" in plan["human_confirmation_required_for"]
    assert "最终交付物" in plan["human_confirmation_required_for"]
    assert "重大问题定性" in plan["human_confirmation_required_for"]
    assert plan["file_access_policy"] == "read_only"
    assert plan["audit_trace_required"] is True
    assert all(step["audit_trace_required"] is True for step in plan["coordination_steps"])
    assert plan["coordination_steps"][0]["can_execute"] is False
    clerk_step = plan["coordination_steps"][1]
    assert clerk_step["agent_role"] == "accounting_clerk_agent"
    assert "collect_readonly_source_files" in clerk_step["allowed_tools"]


def test_due_diligence_case_template_sets_execution_and_draft_rules():
    template = build_due_diligence_case_template()
    assert template["template_code"] == "due_diligence_audit"
    assert "orchestrator_agent" in template["allowed_agent_roles"]
    assert "accounting_clerk_agent" in template["allowed_agent_roles"]
    assert "quality_reviewer_agent" in template["allowed_agent_roles"]
    assert "auditor_agent" in template["allowed_agent_roles"]
    assert template["audit_trace_required"] is True
    assert template["immutable_trace_required"] is True
    assert "草稿" in template["workpaper_policy"]
    assert "人工确认" in template["audit_draft_policy"]
    step_names = {step["name"] for step in template["execution_steps"]}
    assert "导入原始资料" in step_names
    assert "导入凭证并生成分录草稿" in step_names
    assert "向量库识别业务循环" in step_names
    all_tools = {tool for step in template["execution_steps"] for tool in step["allowed_tools"]}
    assert "identify_business_cycles_by_vector" in all_tools
    assert "generate_audit_draft" in all_tools


def test_internal_control_case_template_uses_management_trace_deliverables():
    template = build_due_diligence_case_template("internal_control")
    deliverables = template["deliverable_rule"]["allowed_deliverables"]
    assert template["scenario"] == "internal_control"
    assert "管理层复核记录" in deliverables
    assert "整改跟踪台账" in deliverables
    assert "企业自身管理痕迹" in template["deliverable_rule"]["deliverable_policy"]


def test_model_config_status_hides_api_key():
    settings = Settings(
        ai_provider="openai-compatible",
        ai_base_url="https://example.test/v1",
        ai_api_key="secret-api-key",
        ai_model="finance-agent-model",
        ai_local_model_enabled=True,
        ai_fallback_to_rules=True,
    )
    status = get_model_config_status(settings)

    assert status["provider"] == "openai-compatible"
    assert status["model_name"] == "finance-agent-model"
    assert status["api_key_configured"] is True
    assert status["remote_model_configured"] is True
    assert status["local_lightweight_model_enabled"] is True
    assert status["fallback_strategy"] == "rules_intent_recognition"
    assert status["active_mode"] == "remote_model"
    assert "ai_api_key" not in status
    assert "secret-api-key" not in str(status)


def test_agent_model_config_endpoint_requires_login_and_hides_key():
    response = client.get("/api/agent/model/config")
    assert response.status_code == 401

    headers = auth_headers("agent_model_config_user", "13800139014")
    authed_response = client.get("/api/agent/model/config", headers=headers)
    assert authed_response.status_code == 200
    data = authed_response.json()
    assert "api_key_configured" in data
    assert "ai_api_key" not in data


def test_agent_chat_without_token_returns_401():
    response = client.post("/api/agent/chat", json={"message": "我要导入原始凭证生成分录"})
    assert response.status_code == 401


def test_agent_chat_empty_message_returns_400():
    headers = auth_headers("agent_empty_user", "13800139001")
    response = client.post("/api/agent/chat", json={"message": "   "}, headers=headers)
    assert response.status_code == 400
    audit_log = latest_audit_log("agent_chat")
    assert audit_log is not None
    assert audit_log.execution_source == "agent_assisted"
    assert audit_log.status == "failed"
    assert audit_log.error_message == "message 不能为空"


def test_agent_chat_accounting_import():
    headers = auth_headers("agent_accounting_user", "13800139002")
    response = client.post("/api/agent/chat", json={"message": "我要导入原始凭证生成分录"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "accounting_import"
    assert data["suggested_path"] == "/accounting/step/1"
    assert data["steps"]
    assert data["task_plan"]["agent_role"] == "accounting_assistant_agent"
    assert data["task_plan"]["approval_required"] is True
    assert data["task_plan"]["audit_trace_required"] is True
    assert data["task_plan"]["user_id"] > 0
    assert "create_import_job" in data["task_plan"]["allowed_tools"]
    assert all(
        tool["tool_name"] in data["task_plan"]["allowed_tools"]
        for tool in data["task_plan"]["tool_details"]
    )
    audit_log = latest_audit_log("agent_chat")
    assert audit_log is not None
    assert audit_log.execution_source == "agent_assisted"
    assert audit_log.agent_role == "accounting_assistant_agent"
    assert audit_log.risk_level == "medium"
    assert audit_log.status == "success"
    assert audit_log.approval_required is True
    assert audit_log.input_summary["intent"] == "accounting_import"


def test_agent_chat_audit_workflow():
    headers = auth_headers("agent_audit_user", "13800139003")
    response = client.post("/api/agent/chat", json={"message": "执行审计测试并查看风险发现"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "audit_workflow"
    assert data["task_plan"]["agent_role"] == "audit_assistant_agent"


def test_agent_chat_report_export():
    headers = auth_headers("agent_report_user", "13800139004")
    response = client.post("/api/agent/chat", json={"message": "导出审计报告xlsx"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["intent"] == "report_export"


def test_agent_chat_basic_data():
    headers = auth_headers("agent_basic_user", "13800139005")
    response = client.post("/api/agent/chat", json={"message": "维护科目和供应商"}, headers=headers)
    assert response.status_code == 200
    assert response.json()["intent"] == "basic_data"


def test_agent_chat_period_close():
    headers = auth_headers("agent_period_user", "13800139006")
    response = client.post("/api/agent/chat", json={"message": "做期末损益结转"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "period_close"
    assert data["task_plan"]["risk_level"] == "high"


def test_agent_task_plan_endpoint_returns_same_plan_shape():
    headers = auth_headers("agent_plan_user", "13800139007")
    response = client.post("/api/agent/tasks/plan", json={"message": "维护科目和供应商"}, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "basic_data"
    assert data["task_plan"]["execution_source"] == "agent_assisted"
    assert data["task_plan"]["allowed_tools"]
    audit_log = latest_audit_log("agent_tasks_plan")
    assert audit_log is not None
    assert audit_log.execution_source == "agent_assisted"
    assert audit_log.business_object_type == "agent_task_plan"
    assert audit_log.status == "success"


def test_agent_orchestration_plan_endpoint_requires_login():
    response = client.post("/api/agent/orchestration/plan", json={"message": "做尽调审计"})
    assert response.status_code == 401


def test_due_diligence_case_template_endpoint_returns_internal_control_template():
    headers = auth_headers("agent_case_template_user", "13800139016")
    response = client.post(
        "/api/agent/case-templates/due-diligence",
        json={"scenario": "internal_control"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scenario"] == "internal_control"
    assert "quality_reviewer_agent" in data["allowed_agent_roles"]
    assert "auditor_agent" in data["allowed_agent_roles"]
    assert data["api_tool_policy"] == "所有工具必须在后端 API 白名单范围以内。"
    assert data["deliverable_rule"]["human_confirmation_required"] is True
    audit_log = latest_audit_log("due_diligence_case_template")
    assert audit_log is not None
    assert audit_log.business_object_type == "agent_case_template"
    assert audit_log.input_summary["scenario"] == "internal_control"


def test_agent_orchestration_plan_endpoint_returns_due_diligence_plan():
    headers = auth_headers("agent_orchestration_user", "13800139015")
    response = client.post(
        "/api/agent/orchestration/plan",
        json={"message": "以尽调审计任务为案例，收集材料并编制底稿"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["primary_agent_role"] == "orchestrator_agent"
    assert "accounting_clerk_agent" in data["supporting_agent_roles"]
    assert data["file_access_policy"] == "read_only"
    assert data["audit_trace_required"] is True
    assert all(step["audit_trace_required"] is True for step in data["coordination_steps"])
    assert any(step["approval_required"] is True for step in data["coordination_steps"])
    audit_log = latest_audit_log("agent_orchestration_plan")
    assert audit_log is not None
    assert audit_log.business_object_type == "agent_orchestration_plan"
    assert audit_log.agent_role == "orchestrator_agent"
    assert audit_log.approval_required is True
    assert audit_log.input_summary["intent"] == "due_diligence_audit"


def test_agent_low_risk_tool_call_lists_chart_of_accounts():
    suffix = uuid4().hex[:6]
    account_code = f"AG{suffix}"
    seed_agent_tool_basic_data(account_code, f"Agent客户{suffix}")
    headers = auth_headers("agent_tool_coa_user", "13800139009")
    response = client.post(
        "/api/agent/tools/run",
        json={
            "tool_name": "list_chart_of_accounts",
            "agent_role": "accounting_assistant_agent",
            "args": {"limit": 200},
        },
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tool"]["risk_level"] == "low"
    assert data["tool"]["approval_required"] is False
    assert any(item["code"] == account_code for item in data["result"]["items"])
    audit_log = latest_audit_log("list_chart_of_accounts")
    assert audit_log is not None
    assert audit_log.execution_source == "agent_auto"
    assert audit_log.status == "success"
    assert audit_log.business_object_type == "agent_tool_call"


def test_agent_tool_call_blocks_high_risk_tool():
    headers = auth_headers("agent_tool_block_user", "13800139010")
    response = client.post(
        "/api/agent/tools/run",
        json={
            "tool_name": "preview_profit_loss_transfer",
            "agent_role": "accounting_assistant_agent",
            "args": {},
        },
        headers=headers,
    )
    assert response.status_code == 403
    assert "不能自动执行" in response.json()["detail"]
    audit_log = latest_audit_log("preview_profit_loss_transfer")
    assert audit_log is not None
    assert audit_log.execution_source == "agent_auto"
    assert audit_log.status == "failed"
    assert audit_log.risk_level == "high"


def test_agent_tool_call_blocks_wrong_agent_role():
    headers = auth_headers("agent_tool_role_user", "13800139011")
    response = client.post(
        "/api/agent/tools/run",
        json={
            "tool_name": "list_chart_of_accounts",
            "agent_role": "audit_assistant_agent",
            "args": {},
        },
        headers=headers,
    )
    assert response.status_code == 403
    assert "无权调用" in response.json()["detail"]


def test_agent_approval_request_and_confirm_high_risk_tool():
    headers = auth_headers("agent_approval_user", "13800139012")
    request_response = client.post(
        "/api/agent/approvals/request",
        json={
            "tool_name": "preview_profit_loss_transfer",
            "agent_role": "accounting_assistant_agent",
            "args": {"period_code": "2026-06"},
        },
        headers=headers,
    )
    assert request_response.status_code == 200
    approval_data = request_response.json()
    assert approval_data["tool_name"] == "preview_profit_loss_transfer"
    assert approval_data["risk_level"] == "high"
    assert approval_data["status"] == "pending"
    approval = latest_agent_approval("preview_profit_loss_transfer")
    assert approval is not None
    assert approval.status == "pending"
    request_audit_log = latest_audit_log("preview_profit_loss_transfer")
    assert request_audit_log is not None
    assert request_audit_log.business_object_type == "agent_approval"
    assert request_audit_log.approval_required is True

    confirm_response = client.post(
        f"/api/agent/approvals/{approval_data['id']}/confirm",
        json={"comment": "已人工复核，同意后续进入执行前置检查。"},
        headers=headers,
    )
    assert confirm_response.status_code == 200
    confirmed_data = confirm_response.json()
    assert confirmed_data["status"] == "confirmed"
    assert confirmed_data["confirmed_by_user_id"] is not None
    confirm_audit_log = latest_audit_log("preview_profit_loss_transfer")
    assert confirm_audit_log is not None
    assert confirm_audit_log.approval_id == approval_data["id"]
    assert confirm_audit_log.status == "success"


def test_agent_approval_request_rejects_low_risk_tool():
    headers = auth_headers("agent_approval_low_user", "13800139013")
    response = client.post(
        "/api/agent/approvals/request",
        json={
            "tool_name": "list_chart_of_accounts",
            "agent_role": "accounting_assistant_agent",
            "args": {},
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert "不需要人工确认" in response.json()["detail"]


def test_confirmed_approval_can_execute_draft_only():
    headers = auth_headers("agent_draft_execution_user", "13800139017")
    request_response = client.post(
        "/api/agent/approvals/request",
        json={
            "tool_name": "generate_audit_draft",
            "agent_role": "auditor_agent",
            "args": {"source": "test", "scenario": "internal_control"},
        },
        headers=headers,
    )
    assert request_response.status_code == 200
    approval_id = request_response.json()["id"]

    pending_execute_response = client.post(
        f"/api/agent/approvals/{approval_id}/execute-draft",
        headers=headers,
    )
    assert pending_execute_response.status_code == 400
    assert "已确认" in pending_execute_response.json()["detail"]

    confirm_response = client.post(
        f"/api/agent/approvals/{approval_id}/confirm",
        json={"comment": "同意生成审计初稿草稿。"},
        headers=headers,
    )
    assert confirm_response.status_code == 200

    execute_response = client.post(
        f"/api/agent/approvals/{approval_id}/execute-draft",
        headers=headers,
    )
    assert execute_response.status_code == 200
    data = execute_response.json()
    assert data["execution_status"] == "success"
    assert data["output_type"] == "draft"
    assert data["result"]["review_required"] is True
    assert data["result"]["formal_delivery_allowed"] is False
    assert "正式报告" in data["result"]["notice"]
    audit_log = latest_audit_log("generate_audit_draft")
    assert audit_log is not None
    assert audit_log.business_object_type == "agent_controlled_draft_execution"
    assert audit_log.status == "success"
    assert audit_log.approval_id == approval_id


def test_agent_draft_review_create_and_submit_approved():
    headers = auth_headers("agent_draft_review_user", "13800139019")
    request_response = client.post(
        "/api/agent/approvals/request",
        json={
            "tool_name": "generate_audit_draft",
            "agent_role": "auditor_agent",
            "args": {"source": "test"},
        },
        headers=headers,
    )
    assert request_response.status_code == 200
    approval_id = request_response.json()["id"]
    assert client.post(
        f"/api/agent/approvals/{approval_id}/confirm",
        json={"comment": "同意生成草稿。"},
        headers=headers,
    ).status_code == 200
    assert client.post(f"/api/agent/approvals/{approval_id}/execute-draft", headers=headers).status_code == 200

    review_response = client.post(f"/api/agent/approvals/{approval_id}/draft-review", headers=headers)
    assert review_response.status_code == 200
    review_data = review_response.json()
    assert review_data["review_status"] == "pending"
    assert review_data["allow_formal_delivery_design"] is False

    submit_response = client.post(
        f"/api/agent/draft-reviews/{review_data['id']}/submit",
        json={
            "review_status": "approved",
            "review_comment": "已复核草稿内容，允许进入正式交付设计阶段。",
            "returned_for_rework": False,
            "allow_formal_delivery_design": True,
        },
        headers=headers,
    )
    assert submit_response.status_code == 200
    submitted = submit_response.json()
    assert submitted["review_status"] == "approved"
    assert submitted["reviewed_by_user_id"] is not None
    assert submitted["returned_for_rework"] is False
    assert submitted["allow_formal_delivery_design"] is True
    review = latest_draft_review(approval_id)
    assert review is not None
    assert review.review_status == "approved"
    audit_log = latest_audit_log("generate_audit_draft")
    assert audit_log is not None
    assert audit_log.business_object_type == "agent_draft_review"
    assert audit_log.input_summary["action"] == "submit"


def test_agent_draft_review_returned_cannot_allow_formal_delivery_design():
    headers = auth_headers("agent_draft_review_return_user", "13800139020")
    request_response = client.post(
        "/api/agent/approvals/request",
        json={"tool_name": "generate_audit_draft", "agent_role": "auditor_agent", "args": {}},
        headers=headers,
    )
    approval_id = request_response.json()["id"]
    client.post(
        f"/api/agent/approvals/{approval_id}/confirm",
        json={"comment": "同意生成草稿。"},
        headers=headers,
    )
    review_response = client.post(f"/api/agent/approvals/{approval_id}/draft-review", headers=headers)
    review_id = review_response.json()["id"]
    response = client.post(
        f"/api/agent/draft-reviews/{review_id}/submit",
        json={
            "review_status": "returned",
            "review_comment": "资料不完整，退回重做。",
            "returned_for_rework": True,
            "allow_formal_delivery_design": True,
        },
        headers=headers,
    )
    assert response.status_code == 400
    assert "退回重做" in response.json()["detail"]


def test_confirmed_approval_rejects_non_draft_controlled_execution():
    headers = auth_headers("agent_non_draft_execution_user", "13800139018")
    request_response = client.post(
        "/api/agent/approvals/request",
        json={
            "tool_name": "preview_profit_loss_transfer",
            "agent_role": "accounting_assistant_agent",
            "args": {"period_code": "2026-06"},
        },
        headers=headers,
    )
    assert request_response.status_code == 200
    approval_id = request_response.json()["id"]
    confirm_response = client.post(
        f"/api/agent/approvals/{approval_id}/confirm",
        json={"comment": "仅确认，不允许草稿执行。"},
        headers=headers,
    )
    assert confirm_response.status_code == 200

    execute_response = client.post(
        f"/api/agent/approvals/{approval_id}/execute-draft",
        headers=headers,
    )
    assert execute_response.status_code == 403
    assert "草稿或预览类" in execute_response.json()["detail"]
