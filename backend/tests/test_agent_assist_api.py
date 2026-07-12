from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import ChartOfAccounts, ExecutionAuditLog
from app.db.session import Base, get_db
from app.main import app
from app.services.agent.llm_client_service import LLMResult

client: TestClient


class FakeUnconfiguredLLMClient:
    def is_configured(self) -> bool:
        return False

    def chat(self, messages: list[dict], temperature: float = 0.2) -> LLMResult:
        return LLMResult(available=False, error="fake unconfigured")


@pytest.fixture(autouse=True)
def _isolated_agent_assist_client(monkeypatch, tmp_path):
    global client
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr("app.db.session.SessionLocal", testing_session_local)
    monkeypatch.setattr(
        "app.services.agent.agent_assist_service.build_agent_llm_client",
        lambda db: FakeUnconfiguredLLMClient(),
    )
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            client = test_client
            yield
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def auth_headers(username: str, phone: str) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    phone_suffix = str(uuid4().int % 100).zfill(2)
    response = client.post(
        "/api/auth/register",
        json={
            "username": f"{username}_{suffix}",
            "phone": f"{phone}{phone_suffix}",
            "password": "password123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def latest_audit_log(tool_name: str) -> ExecutionAuditLog | None:
    from app.db.session import SessionLocal

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


def seed_chart_of_accounts(account_code: str) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        db.add(
            ChartOfAccounts(
                code=account_code,
                name="Agent Assist 测试科目",
                category="asset",
                direction="debit",
            )
        )
        db.commit()
    finally:
        db.close()


def test_agent_assist_without_token_returns_401():
    response = client.post("/api/agent/assist", json={"message": "列出科目表"})
    assert response.status_code == 401


def test_agent_assist_empty_message_returns_400():
    headers = auth_headers("agent_assist_empty_user", "13800139101")
    response = client.post("/api/agent/assist", json={"message": "   "}, headers=headers)
    assert response.status_code == 400
    audit_log = latest_audit_log("agent_assist")
    assert audit_log is not None
    assert audit_log.status == "failed"


def test_agent_assist_lists_chart_of_accounts_via_rules():
    suffix = uuid4().hex[:6]
    account_code = f"AS{suffix}"
    seed_chart_of_accounts(account_code)
    headers = auth_headers("agent_assist_coa_user", "13800139102")
    response = client.post(
        "/api/agent/assist",
        json={"message": "帮我列出科目表"},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["reply"]
    assert data["source"] == "rules"
    assert data["intent"] == "basic_data"
    assert data["model_config"]["config_source"] in {"env", "parser_engine_db"}
    assert isinstance(data["tool_executions"], list)
    assert any(
        item["tool_name"] == "list_chart_of_accounts" and item["status"] == "success"
        for item in data["tool_executions"]
    )
    coa_result = next(
        item for item in data["tool_executions"] if item["tool_name"] == "list_chart_of_accounts"
    )
    assert any(row["code"] == account_code for row in coa_result["result"]["items"])
    audit_log = latest_audit_log("agent_assist")
    assert audit_log is not None
    assert audit_log.status == "success"
    assert audit_log.execution_source == "agent_assisted"


def test_agent_assist_model_config_endpoint_includes_assist_fields():
    headers = auth_headers("agent_assist_model_user", "13800139103")
    response = client.get("/api/agent/model/config", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["agent_mode"] == "conversational_assist"
    assert "config_source" in data
    assert "is_ollama" in data


def test_agent_assist_can_disable_auto_execute_tools():
    headers = auth_headers("agent_assist_no_exec_user", "13800139104")
    response = client.post(
        "/api/agent/assist",
        json={"message": "维护科目和供应商", "auto_execute_tools": False},
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tool_executions"] == []
