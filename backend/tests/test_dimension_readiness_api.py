"""维度就绪 API：确认规则已审阅 / 查询就绪状态。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import application
from app.models.scope_settings import LedgerSettings

from tests.conftest import register_auth_headers


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    application.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(application) as test_client:
            yield test_client, SessionLocal
    finally:
        application.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _bootstrap_ledger(client: TestClient) -> tuple[dict, int]:
    headers = register_auth_headers(client)
    team = client.post(
        "/api/teams",
        json={"name": "维度就绪测试团队", "type": "firm"},
        headers=headers,
    ).json()
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "维度就绪测试账簿"},
        headers=headers,
    ).json()
    return headers, ledger["id"]


def test_dimension_readiness_acknowledge_api(client):
    test_client, SessionLocal = client
    headers, ledger_id = _bootstrap_ledger(test_client)

    readiness = test_client.get(
        f"/api/config/ledgers/{ledger_id}/dimension-readiness",
        headers=headers,
    )
    assert readiness.status_code == 200
    body = readiness.json()
    assert body["ready_for_structured_import"] is False
    assert any(item["code"] == "tag_rules_not_reviewed" for item in body["blockers"])

    ack = test_client.post(
        f"/api/config/ledgers/{ledger_id}/dimension-readiness/acknowledge",
        headers=headers,
    )
    assert ack.status_code == 200, ack.text
    ack_body = ack.json()
    assert ack_body["success"] is True
    assert ack_body["tag_rules_reviewed_at"]

    readiness2 = test_client.get(
        f"/api/config/ledgers/{ledger_id}/dimension-readiness",
        headers=headers,
    )
    assert readiness2.status_code == 200
    assert readiness2.json()["ready_for_structured_import"] is True


def test_dimension_readiness_acknowledge_survives_corrupt_settings(client):
    """历史脏 settings（非 dict）不应导致 500。"""
    test_client, SessionLocal = client
    headers, ledger_id = _bootstrap_ledger(test_client)

    db = SessionLocal()
    try:
        row = db.query(LedgerSettings).filter(LedgerSettings.ledger_id == ledger_id).first()
        if row is None:
            row = LedgerSettings(ledger_id=ledger_id, settings="corrupt-string")
            db.add(row)
        else:
            row.settings = "corrupt-string"
        db.commit()
    finally:
        db.close()

    ack = test_client.post(
        f"/api/config/ledgers/{ledger_id}/dimension-readiness/acknowledge",
        headers=headers,
    )
    assert ack.status_code == 200, ack.text
    assert ack.json()["success"] is True


def test_dimension_readiness_unknown_ledger_returns_404(client):
    test_client, _ = client
    headers, ledger_id = _bootstrap_ledger(test_client)
    missing_id = ledger_id + 9999

    ack = test_client.post(
        f"/api/config/ledgers/{missing_id}/dimension-readiness/acknowledge",
        headers=headers,
    )
    assert ack.status_code == 404
