"""注册接口配置与健壮性测试。"""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app.core.security as security
from app.core.security import AuthConfigurationError, create_access_token
from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_create_access_token_raises_auth_configuration_error_without_secret(monkeypatch):
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(secret_key=None),
    )

    with pytest.raises(AuthConfigurationError, match="JWT 密钥未配置"):
        create_access_token({"sub": "1"})


def test_register_returns_503_when_secret_key_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(secret_key=""),
    )

    response = client.post(
        "/api/auth/register",
        json={
            "username": "missing_secret_user",
            "phone": "13800138111",
            "password": "password123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )

    assert response.status_code == 503
    body = response.json()
    assert "JWT 密钥未配置" in body["detail"]
    assert body["error"]["code"] == "auth_not_configured"
