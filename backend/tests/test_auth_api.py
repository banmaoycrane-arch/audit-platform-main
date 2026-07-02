from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db.session import SessionLocal, engine
from app.db.session import Base
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user import User
from app.models.user_ledger_auth import UserLedgerAuth
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.db.models import Entity, Organization, SmsVerificationCode
from app.models.project_ledger import ProjectLedger
from app.core.config import get_settings
import app.core.security as security
from app.core.security import create_access_token, decode_token

client = TestClient(app)


def setup_module() -> None:
    Base.metadata.create_all(bind=engine)


def teardown_module() -> None:
    db = SessionLocal()
    try:
        test_phones = (
            "13800138000", "13800138001", "13800138002", "13800138003", "13800138004",
            "13800138005", "13800138013", "13800138014", "13800138020", "13800138021",
            "13800138022",
        )
        for phone in test_phones:
            db.execute(text("DELETE FROM sms_verification_codes WHERE phone = :phone"), {"phone": phone})
            user = db.execute(text("SELECT id FROM users WHERE phone = :phone"), {"phone": phone}).first()
            if user:
                user_id = user[0]
                db.execute(text("DELETE FROM user_ledger_auths WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM project_members WHERE user_id = :uid"), {"uid": user_id})
                db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        db.commit()
    finally:
        db.close()


def test_create_access_token_fails_without_secret_key(monkeypatch) -> None:
    monkeypatch.setattr(security, "get_settings", lambda: SimpleNamespace(secret_key=None))

    with pytest.raises(RuntimeError, match="JWT 密钥未配置"):
        create_access_token({"sub": "1"}, expires_delta=timedelta(minutes=5))


def test_configured_secret_key_signs_and_decodes_token() -> None:
    token = create_access_token({"sub": "1"}, expires_delta=timedelta(minutes=5))
    payload = decode_token(token)

    assert payload is not None
    assert payload["sub"] == "1"


def test_register_success_and_get_current_user() -> None:
    response = client.post("/api/auth/register", json={
        "username": "testuser",
        "phone": "13800138000",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    me_response = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["username"] == "testuser"
    assert me_data["phone"] == "13800138000"
    assert me_data["is_active"] is True


def test_register_rejects_duplicate_username() -> None:
    first_response = client.post("/api/auth/register", json={
        "username": "duplicate_username",
        "phone": "13800138010",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    assert first_response.status_code == 200

    duplicate_response = client.post("/api/auth/register", json={
        "username": "duplicate_username",
        "phone": "13800138011",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })

    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "Username already exists"


def test_register_rejects_duplicate_phone() -> None:
    first_response = client.post("/api/auth/register", json={
        "username": "duplicate_phone_user",
        "phone": "13800138012",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    assert first_response.status_code == 200

    duplicate_response = client.post("/api/auth/register", json={
        "username": "duplicate_phone_user_2",
        "phone": "13800138012",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })

    assert duplicate_response.status_code == 400
    assert duplicate_response.json()["detail"] == "Phone already exists"


def test_login_password_success() -> None:
    # register first
    client.post("/api/auth/register", json={
        "username": "loginuser",
        "phone": "13800138001",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    response = client.post("/api/auth/login/password", json={
        "username": "loginuser",
        "password": "password123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_login_password_fail() -> None:
    response = client.post("/api/auth/login/password", json={
        "username": "nonexistent",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


def test_sms_code() -> None:
    response = client.post("/api/auth/sms/code", json={"phone": "13800138002"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["code"]) == 6
    assert data["code"].isdigit()
    assert data["sms_code"] == data["code"]
    assert data["message"] in {"验证码已生成", "验证码已生成（开发模式）"}


def test_login_sms_success_and_auto_create() -> None:
    response = client.post("/api/auth/sms/code", json={"phone": "13800138003"})
    assert response.status_code == 200
    code_data = response.json()
    code = code_data["sms_code"]
    response = client.post("/api/auth/login/sms", json={
        "phone": "13800138003",
        "code": code,
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data


def test_sms_code_is_random_and_single_use() -> None:
    first_response = client.post("/api/auth/sms/code", json={"phone": "13800138004"})
    second_response = client.post("/api/auth/sms/code", json={"phone": "13800138004"})
    first_code = first_response.json()["sms_code"]
    second_code = second_response.json()["sms_code"]

    assert first_code != "123456"
    assert len(second_code) == 6

    stale_login = client.post("/api/auth/login/sms", json={
        "phone": "13800138004",
        "code": first_code,
    })
    assert stale_login.status_code == 401

    valid_login = client.post("/api/auth/login/sms", json={
        "phone": "13800138004",
        "code": second_code,
    })
    assert valid_login.status_code == 200

    reused_login = client.post("/api/auth/login/sms", json={
        "phone": "13800138004",
        "code": second_code,
    })
    assert reused_login.status_code == 401


def test_sms_user_can_set_password_and_login_with_password() -> None:
    code_response = client.post("/api/auth/sms/code", json={"phone": "13800138013"})
    code = code_response.json()["sms_code"]
    login_response = client.post("/api/auth/login/sms", json={
        "phone": "13800138013",
        "code": code,
    })
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    set_password_response = client.post(
        "/api/auth/password",
        json={"password": "newpass123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert set_password_response.status_code == 200
    assert set_password_response.json()["message"] == "密码已设置"

    password_login_response = client.post("/api/auth/login/password", json={
        "username": "13800138013",
        "password": "newpass123",
    })
    assert password_login_response.status_code == 200
    assert "access_token" in password_login_response.json()


def test_login_then_empty_team_and_ledger_lists_are_available() -> None:
    client.post("/api/auth/register", json={
        "username": "empty_init_user",
        "phone": "13800138005",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    login_response = client.post("/api/auth/login/password", json={
        "username": "empty_init_user",
        "password": "password123",
    })
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    teams_response = client.get("/api/teams", headers=headers)
    ledgers_response = client.get("/api/ledgers", headers=headers)

    assert teams_response.status_code == 200
    assert teams_response.json() == []
    assert ledgers_response.status_code == 200
    assert ledgers_response.json() == []


def test_me_with_token() -> None:
    # register and get token
    reg = client.post("/api/auth/register", json={
        "username": "meuser",
        "phone": "13800138014",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    token = reg.json()["access_token"]
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "meuser"
    assert data["phone"] == "13800138014"
    assert data["is_active"] is True


def test_me_without_token() -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_auth_context_for_unbound_user_requires_onboarding() -> None:
    response = client.post("/api/auth/register", json={
        "username": "context_unbound_user",
        "phone": "13800138020",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    assert response.status_code == 200
    token = response.json()["access_token"]

    context_response = client.get(
        "/api/auth/context",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert context_response.status_code == 200
    context = context_response.json()
    assert context["requires_onboarding"] is True
    assert context["next_action"] == "create_team"
    assert context["temporary_status"] == "onboarding_pending"
    assert context["teams"] == []
    assert context["ledgers"] == []
    assert context["projects"] == []
    assert context["current_ledger_id"] is None
    assert context["missing_bindings"] == ["team", "ledger", "project", "accounting_entity"]
    assert context["historical_candidates"] == []
    assert context["mock_boundaries"]["sms_code"] == "development_mock"
    assert context["mock_boundaries"]["onboarding_data"] == "real_api"


def test_sms_login_preserves_existing_user_context() -> None:
    response = client.post("/api/auth/register", json={
        "username": "sms_context_user",
        "phone": "13800138022",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    team_response = client.post(
        "/api/teams",
        json={"name": "短信上下文团队", "type": "firm"},
        headers=headers,
    )
    team_id = team_response.json()["id"]
    ledger_response = client.post(
        "/api/ledgers",
        json={"team_id": team_id, "name": "短信上下文账簿"},
        headers=headers,
    )
    ledger_id = ledger_response.json()["id"]

    db = SessionLocal()
    try:
        db.add(Entity(
            entity_name="短信上下文会计主体",
            entity_type="company",
            entity_category="parent",
            is_accounting_entity=True,
            ledger_id=ledger_id,
        ))
        db.commit()
    finally:
        db.close()

    sms_code_response = client.post("/api/auth/sms/code", json={"phone": "13800138022"})
    sms_login_response = client.post("/api/auth/login/sms", json={
        "phone": "13800138022",
        "code": sms_code_response.json()["sms_code"],
    })
    assert sms_login_response.status_code == 200
    sms_headers = {"Authorization": f"Bearer {sms_login_response.json()['access_token']}"}
    context_response = client.get("/api/auth/context", headers=sms_headers)
    assert context_response.status_code == 200
    context = context_response.json()
    assert len(context["teams"]) == 1
    assert len(context["ledgers"]) == 1
    assert "team" not in context["missing_bindings"]
    assert "ledger" not in context["missing_bindings"]
    assert "accounting_entity" not in context["missing_bindings"]



def test_auth_context_for_bound_user_can_enter_workspace() -> None:
    response = client.post("/api/auth/register", json={
        "username": "context_bound_user",
        "phone": "13800138021",
        "password": "password123",
        "agreed_terms": True,
        "agreed_privacy": True,
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    team_response = client.post(
        "/api/teams",
        json={"name": "上下文测试团队", "type": "firm"},
        headers=headers,
    )
    assert team_response.status_code == 200
    team_id = team_response.json()["id"]

    ledger_response = client.post(
        "/api/ledgers",
        json={"team_id": team_id, "name": "上下文测试账簿"},
        headers=headers,
    )
    assert ledger_response.status_code == 200
    ledger_id = ledger_response.json()["id"]

    project_response = client.post(
        "/api/projects",
        json={"team_id": team_id, "name": "上下文测试项目"},
        headers=headers,
    )
    assert project_response.status_code == 200

    db = SessionLocal()
    try:
        db.add(Entity(
            entity_name="上下文测试会计主体",
            entity_type="company",
            entity_category="parent",
            is_accounting_entity=True,
            ledger_id=ledger_id,
        ))
        db.commit()
    finally:
        db.close()

    switch_response = client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    assert switch_response.status_code == 200

    context_response = client.get("/api/auth/context", headers=headers)
    assert context_response.status_code == 200
    context = context_response.json()
    assert context["requires_onboarding"] is False
    assert context["next_action"] == "workspace"
    assert context["temporary_status"] == "ready"
    assert context["missing_bindings"] == []
    assert len(context["teams"]) == 1
    assert len(context["ledgers"]) == 1
    assert len(context["projects"]) == 1
    assert context["current_ledger_id"] == ledger_id
