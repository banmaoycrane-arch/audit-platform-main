"""Regression: critical API routers must be registered in main.py.

Unmounted routers return 404; mounted routers reach auth or validation (non-404).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app as fastapi_app


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

    fastapi_app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(fastapi_app) as test_client:
            yield test_client
    finally:
        fastapi_app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _register_token(client: TestClient, username: str, phone: str) -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "phone": phone,
            "password": "password123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("POST", "/api/binding-requests", {"team_id": 1, "requested_role": "viewer"}),
        ("GET", "/api/workpapers/index", None),
        ("GET", "/api/audit/workflow/runs", None),
    ],
)
def test_critical_routers_are_mounted(
    client: TestClient,
    method: str,
    path: str,
    json_body: dict | None,
):
    token = _register_token(client, f"route_{path.split('/')[-1]}", "13900009999")
    headers = {"Authorization": f"Bearer {token}"}
    response = client.request(method, path, json=json_body, headers=headers)
    assert response.status_code != 404, f"{method} {path} returned 404 — router likely not mounted in main.py"
