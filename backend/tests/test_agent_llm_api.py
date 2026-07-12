from uuid import uuid4

from app.services.agent.agent_service import chat_with_agent
from app.services.agent.llm_client_service import LLMResult


class FakeLLMClient:
    def __init__(self, configured: bool, result: LLMResult | None = None):
        self.configured = configured
        self.result = result

    def is_configured(self) -> bool:
        return self.configured

    def chat(self, messages: list[dict], temperature: float = 0.2) -> LLMResult:
        return self.result or LLMResult(available=False, error="fake failure")


def test_agent_chat_without_llm_config_uses_rules():
    result = chat_with_agent("我要导入原始凭证生成分录", llm_client=FakeLLMClient(False))

    assert result["source"] == "rules"
    assert result["model_available"] is False
    assert result["intent"] == "accounting_import"


def test_agent_chat_with_llm_json_response():
    client = FakeLLMClient(
        True,
        LLMResult(
            available=True,
            content=(
                '{"intent":"audit_workflow","confidence":0.88,"reply":"建议先进入审计资料导入。",'
                '"suggested_path":"/audit/step/3","steps":["导入序时簿","执行审计测试"]}'
            ),
            model="fake-model",
        ),
    )

    result = chat_with_agent("我想先导入序时簿再审计", llm_client=client)

    assert result["source"] == "llm"
    assert result["model_available"] is True
    assert result["intent"] == "audit_workflow"
    assert result["suggested_path"] == "/audit/step/3"
    assert result["steps"] == ["导入序时簿", "执行审计测试"]


def test_agent_chat_with_llm_plain_text_uses_fallback_path():
    client = FakeLLMClient(True, LLMResult(available=True, content="请先进入记账导入页面。"))

    result = chat_with_agent("我要导入原始凭证生成分录", llm_client=client)

    assert result["source"] == "llm"
    assert result["model_available"] is True
    assert result["reply"] == "请先进入记账导入页面。"
    assert result["suggested_path"] == "/accounting/step/1"
    assert result["steps"]


def test_agent_chat_llm_failure_falls_back_to_rules():
    client = FakeLLMClient(True, LLMResult(available=False, error="timeout"))

    result = chat_with_agent("执行审计测试并查看风险发现", llm_client=client)

    assert result["source"] == "rules"
    assert result["model_available"] is False
    assert result["intent"] == "audit_workflow"


def test_agent_chat_empty_message_returns_400(monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.db.session import Base, get_db
    from app.main import app

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
    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        suffix = uuid4().hex[:8]
        phone_suffix = str(uuid4().int % 100).zfill(2)
        register_response = client.post("/api/auth/register", json={
            "username": f"agent_llm_empty_user_{suffix}",
            "phone": f"13800139008{phone_suffix}",
            "password": "password123",
            "agreed_terms": True,
            "agreed_privacy": True,
        })
        assert register_response.status_code == 200
        token = register_response.json()["access_token"]
        response = client.post(
            "/api/agent/chat",
            json={"message": "   "},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
