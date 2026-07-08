from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.main as app_main
from app.db.session import Base, get_db
from app.main import app


def test_root() -> None:
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_gateway_adds_request_id_and_security_headers() -> None:
    client = TestClient(app)
    response = client.get("/health", headers={"X-Request-ID": "test-request-001"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request-001"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"


def test_gateway_formats_not_found_errors() -> None:
    client = TestClient(app)
    response = client.get("/not-exists", headers={"X-Request-ID": "missing-path-001"})
    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"] == "Not Found"
    assert payload["error"]["code"] == "http_error"
    assert payload["error"]["message"] == "Not Found"
    assert payload["error"]["request_id"] == "missing-path-001"
    assert response.headers["X-Request-ID"] == "missing-path-001"


def test_ensure_local_sqlite_schema_adds_missing_user_columns(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "old_local.db"
    temporary_engine = create_engine(f"sqlite:///{database_path}")
    try:
        with temporary_engine.begin() as connection:
            connection.execute(text("CREATE TABLE users (id INTEGER NOT NULL, username VARCHAR(100))"))

        monkeypatch.setattr(app_main, "engine", temporary_engine)
        app_main._ensure_local_sqlite_schema()

        inspector = inspect(temporary_engine)
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        assert {
            "agreed_terms",
            "agreed_privacy",
            "team_id",
            "last_ledger_id",
            "updated_at",
        }.issubset(user_columns)
    finally:
        temporary_engine.dispose()


from tests.conftest import register_auth_headers


def _memory_test_client():
    """创建带内存数据库的测试客户端。"""
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
    return TestClient(app), engine


def test_create_import_job() -> None:
    client, engine = _memory_test_client()
    try:
        headers = register_auth_headers(client, username="import_job_user", phone="13800138001")
        response = client.post(
            "/api/import-jobs",
            json={"organization_name": "测试企业", "fiscal_year": 2026},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "created"
        assert response.json()["source_type"] == "voucher_import"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_upload_pdf_source_file() -> None:
    client, engine = _memory_test_client()
    try:
        headers = register_auth_headers(client, username="upload_pdf_user", phone="13800138002")
        job_response = client.post(
            "/api/import-jobs",
            json={"organization_name": "测试企业", "fiscal_year": 2026, "source_type": "ai_generated"},
            headers=headers,
        )
        job_id = job_response.json()["id"]

        response = client.post(
            f"/api/import-jobs/{job_id}/files",
            files={"file": ("山西春刚商贸有限公司_可搜索.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
        )

        assert response.status_code == 200
        assert response.json()["filename"] == "山西春刚商贸有限公司_可搜索.pdf"
        assert response.json()["file_type"] == "pdf"
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
