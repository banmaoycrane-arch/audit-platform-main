"""parser-engine 路由 async 修复与结构化快速路径回归。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Organization
from app.db.session import Base, get_db
from app.main import app
from app.services.doc_parsing.parser_engine.parse_result import (
    DocumentType,
    EngineType,
    FileFormat,
    ParseResult,
)
from tests.conftest import register_auth_headers
from tests.fixtures.day_book import write_daybook_csv


@pytest.fixture
def client(monkeypatch, tmp_path):
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

    monkeypatch.setattr("app.storage.local_storage.get_settings", lambda: SimpleNamespace(upload_dir=str(tmp_path)))
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    db.add(Organization(name="测试组织"))
    db.commit()
    db.close()

    try:
        with TestClient(app) as test_client:
            test_client._auth_headers = register_auth_headers(test_client)
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_detect_format_endpoint(client, tmp_path: Path) -> None:
    test_client, _ = client
    csv_path = write_daybook_csv(tmp_path / "sample.csv")
    with csv_path.open("rb") as handle:
        response = test_client.post(
            "/api/import-jobs/detect-format",
            files={"file": ("sample.csv", handle, "text/csv")},
            headers=test_client._auth_headers,
        )
    assert response.status_code == 200
    data = response.json()
    assert data["is_structured_tabular"] is True
    assert data["parseable"] is True
    assert len(data["detected_headers"]) > 0


def test_parse_file_endpoint_uses_async_dispatch(client, tmp_path: Path) -> None:
    test_client, _ = client
    csv_path = write_daybook_csv(tmp_path / "parse.csv")
    mock_result = ParseResult(
        document_type=DocumentType.ACCOUNTING_ENTRY,
        file_format=FileFormat.CSV,
        confidence=0.9,
        engine=EngineType.RULE,
        engine_name="rule_engine",
        data={"entries": [], "entry_count": 0},
    )

    with patch(
        "app.services.doc_parsing.parser_engine.parser_engine_dispatcher.ParserEngineDispatcher.parse",
        new_callable=AsyncMock,
        return_value=mock_result,
    ) as mocked_parse:
        with csv_path.open("rb") as handle:
            response = test_client.post(
                "/api/parser-engine/parse-file",
                data={"organization_id": "1"},
                files={"file": ("parse.csv", handle, "text/csv")},
                headers=test_client._auth_headers,
            )

    assert response.status_code == 200
    mocked_parse.assert_awaited_once()
    body = response.json()
    assert body["document_type"] == "accounting_entry"
    assert body["engine_type"] == "rule"
