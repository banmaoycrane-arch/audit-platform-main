"""税务城市出口 IP 池 API 测试。"""
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
def _isolated_tax_egress_client(tmp_path):
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
            "username": f"tax_egress_{suffix}",
            "phone": f"1380023{suffix[:4]}",
            "password": "password123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_tax_egress_pools_seed_and_binding_rotate():
    headers = _auth_headers()
    pools = client.get("/api/tax/egress/pools?city_code=330100", headers=headers)
    assert pools.status_code == 200
    body = pools.json()
    assert body["pool_policy"] == "sticky_with_failover"
    assert len(body["cities"]) == 1
    assert len(body["cities"][0]["nodes"]) >= 2

    create = client.post(
        "/api/tax/egress/bindings",
        json={
            "taxpayer_id": "91330100MA2XXXX099",
            "taxpayer_name": "杭州测试科技有限公司",
            "city_code": "330100",
        },
        headers=headers,
    )
    assert create.status_code == 200
    binding = create.json()
    assert binding["taxpayer_id"] == "91330100MA2XXXX099"
    first_ip = binding["egress_ip"]
    binding_id = binding["id"]

    rotate = client.post(
        f"/api/tax/egress/bindings/{binding_id}/rotate",
        json={"reason": "测试手动轮换"},
        headers=headers,
    )
    assert rotate.status_code == 200
    rotated = rotate.json()
    assert rotated["egress_ip"] != first_ip
    assert rotated["session_state"] == "need_qr"

    events = client.get("/api/tax/egress/rotation-events", headers=headers)
    assert events.status_code == 200
    assert len(events.json()["items"]) >= 2
