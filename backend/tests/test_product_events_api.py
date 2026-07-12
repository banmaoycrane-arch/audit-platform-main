"""MVP 产品埋点 API 测试。"""
from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app

client: TestClient


@pytest.fixture(autouse=True)
def _isolated_product_events_client(tmp_path):
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

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            client = test_client
            yield
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _auth_headers() -> dict[str, str]:
    suffix = uuid4().hex[:8]
    response = client.post(
        "/api/auth/register",
        json={
            "username": f"mvp_metrics_{suffix}",
            "phone": f"1380013{suffix[:4]}",
            "password": "password123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_product_event_create_and_kpi_summary():
    headers = _auth_headers()
    response = client.post(
        "/api/product-events",
        json={
            "event_name": "task_bookkeeping_step_reached",
            "job_id": 101,
            "properties": {"step": "step1_select"},
        },
        headers=headers,
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True

    response = client.post(
        "/api/product-events",
        json={
            "event_name": "ai_voucher_draft_shown",
            "job_id": 101,
            "properties": {"fields_total": 10, "llm_used": True},
        },
        headers=headers,
    )
    assert response.status_code == 200

    response = client.post(
        "/api/product-events",
        json={
            "event_name": "ai_voucher_draft_saved",
            "job_id": 101,
            "properties": {
                "fields_total": 10,
                "fields_adopted_unchanged": 7,
                "fields_edited": 3,
                "time_to_save_seconds": 42,
            },
        },
        headers=headers,
    )
    assert response.status_code == 200

    summary = client.get("/api/product-events/mvp-kpi-summary?days=14", headers=headers)
    assert summary.status_code == 200
    data = summary.json()
    assert data["total_events"] >= 3
    adoption = next(item for item in data["kpis"] if item["key"] == "ai_adoption_rate")
    assert adoption["value"] == 0.7
