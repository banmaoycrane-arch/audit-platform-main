# -*- coding: utf-8 -*-
"""经济事件工单 E3/E4 测试。

覆盖：
- E3：Agent 开草稿工单、Tool steps 留痕、禁止 Agent 过账
- E4：vector-sync / similar 接口在无向量库时优雅降级
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AgentApproval, EconomicEvent, EconomicEventStep
from app.db.session import Base, get_db
from app.main import app
from app.services.agent.agent_controlled_execution_service import (
    execute_confirmed_agent_draft,
)
from app.services.shared import economic_event_service as event_svc
from app.services.shared.economic_event_agent_service import (
    advance_event_from_agent,
    create_draft_event_from_agent,
)


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _auth_headers(client: TestClient) -> dict:
    suffix = uuid.uuid4().hex[:8]
    register = client.post(
        "/api/auth/register",
        json={
            "username": f"e34_{suffix}",
            "password": "TestPass123!",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert register.status_code == 200
    return {"Authorization": f"Bearer {register.json()['access_token']}"}


def _create_ledger(client: TestClient, headers: dict) -> tuple[dict, int]:
    team = client.post("/api/teams", json={"name": "E34团队", "type": "company"}, headers=headers)
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "E34账簿"},
        headers=headers,
    )
    ledger_id = ledger.json()["id"]
    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    return {**headers, "X-Ledger-Id": str(ledger_id)}, ledger_id


def test_agent_create_draft_writes_tool_steps(client):
    test_client, SessionLocal = client
    headers = _auth_headers(test_client)
    headers, ledger_id = _create_ledger(test_client, headers)

    with SessionLocal() as db:
        event = create_draft_event_from_agent(
            db,
            ledger_id=ledger_id,
            title="办合同入账准备",
            summary="上传销售合同并准备权责发生制草稿",
            actor_user_id=1,
            model_name="test-model",
        )
        assert event.status == "draft"
        assert event.source == "agent"
        steps = (
            db.query(EconomicEventStep)
            .filter(EconomicEventStep.event_id == event.id)
            .order_by(EconomicEventStep.sequence.asc())
            .all()
        )
        assert any(s.step_code == "create" for s in steps)
        tool_steps = [s for s in steps if s.step_code == "agent_tool"]
        assert len(tool_steps) >= 1
        assert tool_steps[0].api_name == "create_economic_event_draft"
        assert tool_steps[0].actor_type == "agent"


def test_agent_cannot_transition_to_posted(client):
    test_client, SessionLocal = client
    headers = _auth_headers(test_client)
    headers, ledger_id = _create_ledger(test_client, headers)

    with SessionLocal() as db:
        event = create_draft_event_from_agent(
            db,
            ledger_id=ledger_id,
            title="待入账事件",
            actor_user_id=1,
        )
        # 人工推进到 pending_post
        for to_status in ("collecting", "pending_review", "pending_post"):
            event = event_svc.transition(
                db, event.id, to_status, actor_user_id=1, actor_type="user"
            )

        with pytest.raises(ValueError, match="过账|人工"):
            advance_event_from_agent(
                db,
                event_id=event.id,
                to_status="posted",
                actor_user_id=1,
            )

        with pytest.raises(ValueError, match="Agent 不得|人工"):
            event_svc.transition(
                db, event.id, "posted", actor_user_id=1, actor_type="agent"
            )

        # 人工可以过账
        posted = event_svc.transition(
            db, event.id, "posted", actor_user_id=1, actor_type="user", reason="人工确认入账"
        )
        assert posted.status == "posted"


def test_confirmed_approval_creates_economic_event_draft(client):
    test_client, SessionLocal = client
    headers = _auth_headers(test_client)
    headers, ledger_id = _create_ledger(test_client, headers)

    with SessionLocal() as db:
        approval = AgentApproval(
            tool_name="create_economic_event_draft",
            agent_role="accounting_assistant_agent",
            risk_level="medium",
            status="confirmed",
            requested_by_user_id=1,
            confirmed_by_user_id=1,
            request_args_summary={
                "ledger_id": ledger_id,
                "title": "Agent 确认后开草稿",
                "summary": "合同办理",
            },
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)

        result = execute_confirmed_agent_draft(db, approval.id)
        assert result["execution_status"] == "success"
        assert result["result"]["formal_delivery_allowed"] is False
        event_brief = result["result"]["economic_event"]
        assert event_brief is not None
        assert event_brief["status"] == "draft"
        assert event_brief["title"] == "Agent 确认后开草稿"

        stored = db.query(EconomicEvent).filter(EconomicEvent.id == event_brief["id"]).one()
        assert stored.source == "agent"


def test_vector_sync_and_similar_graceful_without_qdrant(client):
    test_client, _SessionLocal = client
    headers = _auth_headers(test_client)
    headers, _ledger_id = _create_ledger(test_client, headers)

    create = test_client.post(
        "/api/economic-events/",
        headers=headers,
        json={
            "title": "销售收款样例",
            "summary": "收到客户货款并确认收入",
            "event_type": "revenue_recognition",
        },
    )
    assert create.status_code == 201
    event_id = create.json()["id"]

    with patch(
        "app.services.shared.economic_event_vector_service.safe_vector_store",
        return_value=None,
    ):
        sync = test_client.post("/api/economic-events/vector-sync", headers=headers)
        assert sync.status_code == 200
        assert sync.json()["vector_available"] is False

        similar = test_client.get(
            f"/api/economic-events/{event_id}/similar",
            headers=headers,
        )
        assert similar.status_code == 200
        body = similar.json()
        assert body["vector_available"] is False
        assert body["results"] == []


def test_similar_events_with_mocked_vector_store(client):
    test_client, SessionLocal = client
    headers = _auth_headers(test_client)
    headers, ledger_id = _create_ledger(test_client, headers)

    first = test_client.post(
        "/api/economic-events/",
        headers=headers,
        json={"title": "销售A", "summary": "销售收款"},
    )
    second = test_client.post(
        "/api/economic-events/",
        headers=headers,
        json={"title": "销售B", "summary": "销售收款相似"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    target_id = first.json()["id"]
    similar_id = second.json()["id"]

    mock_store = MagicMock()
    mock_store.search.return_value = [
        {
            "id": f"economic_event_{similar_id}",
            "score": 0.91,
            "payload": {
                "ledger_id": ledger_id,
                "event_id": similar_id,
                "source": "economic_event",
            },
        }
    ]

    with patch(
        "app.services.shared.economic_event_vector_service.safe_vector_store",
        return_value=mock_store,
    ):
        similar = test_client.get(
            f"/api/economic-events/{target_id}/similar?limit=5",
            headers=headers,
        )
    assert similar.status_code == 200
    results = similar.json()["results"]
    assert len(results) == 1
    assert results[0]["event_id"] == similar_id
    assert results[0]["score"] == 0.91


def test_list_economic_events_low_risk_tool(client):
    test_client, SessionLocal = client
    headers = _auth_headers(test_client)
    headers, ledger_id = _create_ledger(test_client, headers)

    test_client.post(
        "/api/economic-events/",
        headers=headers,
        json={"title": "只读列表事件", "summary": "x"},
    )

    run = test_client.post(
        "/api/agent/tools/run",
        headers=headers,
        json={
            "tool_name": "list_economic_events",
            "agent_role": "accounting_assistant_agent",
            "args": {"ledger_id": ledger_id, "limit": 10},
        },
    )
    assert run.status_code == 200, run.text
    payload = run.json()
    assert payload["result"]["count"] >= 1
