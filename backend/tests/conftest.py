import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def configure_test_secret_key(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-jwt-secret-key")
    monkeypatch.setenv("SMS_RETURN_CODE_IN_DEV", "true")
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


def register_auth_headers(
    client: TestClient,
    *,
    username: str | None = None,
    phone: str | None = None,
) -> dict[str, str]:
    """注册测试用户并返回 Bearer 鉴权头。"""
    suffix = uuid.uuid4().hex[:8]
    username = username or f"user_{suffix}"
    phone = phone or f"138{int(suffix, 16) % 10 ** 8:08d}"
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "phone": phone,
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
