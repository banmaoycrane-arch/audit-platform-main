"""Phase C：工作底稿索引与版本 API 测试。"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import ImportJob, Organization, SourceFile
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.project import Project
from app.models.project_ledger import ProjectLedger
from app.models.team import Team
from app.services.draft_archive_service import auto_archive_draft


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
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _auth_headers(client: TestClient, username: str) -> dict:
    register = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "phone": f"135{username[-7:]}",
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert register.status_code == 200
    return {"Authorization": f"Bearer {register.json()['access_token']}"}


def _create_ledger(client: TestClient, headers: dict) -> tuple[dict, int]:
    team = client.post("/api/teams", json={"name": "底稿团队", "type": "company"}, headers=headers)
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "底稿账套"},
        headers=headers,
    )
    ledger_id = ledger.json()["id"]
    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    return {**headers, "X-Ledger-Id": str(ledger_id)}, ledger_id


def _seed_archived_source_files(ledger_id: int) -> tuple[int, int]:
    with next(app.dependency_overrides[get_db]()) as db:
        team = Team(name="底稿项目团队")
        db.add(team)
        db.flush()
        project = Project(name="2025年度审计", team_id=team.id)
        db.add(project)
        db.flush()
        ledger = db.get(Ledger, ledger_id)
        db.add(ProjectLedger(project_id=project.id, ledger_id=ledger_id))
        org = Organization(name="底稿组织")
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, ledger_id=ledger_id)
        db.add(job)
        db.flush()

        file1 = SourceFile(
            organization_id=org.id,
            import_job_id=job.id,
            ledger_id=ledger_id,
            filename="采购合同.pdf",
            file_type="pdf",
            storage_path="/tmp/contract.pdf",
        )
        file2 = SourceFile(
            organization_id=org.id,
            import_job_id=job.id,
            ledger_id=ledger_id,
            filename="采购合同-修订.pdf",
            file_type="pdf",
            storage_path="/tmp/contract-v2.pdf",
        )
        db.add(file1)
        db.add(file2)
        db.flush()

        auto_archive_draft(
            db,
            file1,
            {
                "document_type": "contract",
                "document_type_label": "采购合同",
                "register_type": "contract",
                "voucher_date": "2025-06-15",
            },
            module_registrations=[{"module_key": "purchase", "semantic_only": False}],
            job=job,
        )
        db.commit()
        return file1.id, file2.id


def test_workpaper_auto_registered_on_archive(client):
    headers = _auth_headers(client, "wp_user1")
    ledger_headers, ledger_id = _create_ledger(client, headers)
    _seed_archived_source_files(ledger_id)

    listing = client.get("/api/workpapers/index", headers=ledger_headers)
    assert listing.status_code == 200
    rows = listing.json()
    assert len(rows) >= 1
    assert rows[0]["version_count"] >= 1
    assert rows[0]["index_no"]


def test_workpaper_revise_and_export_catalog(client):
    headers = _auth_headers(client, "wp_user2")
    ledger_headers, ledger_id = _create_ledger(client, headers)
    file1_id, file2_id = _seed_archived_source_files(ledger_id)

    index_id = client.get("/api/workpapers/index", headers=ledger_headers).json()[0]["id"]
    revised = client.post(
        f"/api/workpapers/index/{index_id}/revise",
        json={"source_file_id": file2_id, "change_reason": "补充签署页"},
        headers=ledger_headers,
    )
    assert revised.status_code == 200
    body = revised.json()
    assert len(body["versions"]) == 2
    assert body["versions"][-1]["version_no"] == "1.1"
    assert body["versions"][0]["status"] == "superseded"

    version_id = body["versions"][-1]["id"]
    reviewed = client.patch(
        f"/api/workpapers/versions/{version_id}",
        json={"status": "reviewed"},
        headers=ledger_headers,
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"

    export = client.get("/api/workpapers/export", headers=ledger_headers)
    assert export.status_code == 200
    catalog = export.json()
    assert catalog["index_count"] >= 1
    assert catalog["version_count"] >= 2
    assert catalog["items"][0]["versions"]


def test_sync_from_archive_is_idempotent(client):
    headers = _auth_headers(client, "wp_user3")
    ledger_headers, ledger_id = _create_ledger(client, headers)
    _seed_archived_source_files(ledger_id)

    first = client.post("/api/workpapers/sync-from-archive", headers=ledger_headers)
    second = client.post("/api/workpapers/sync-from-archive", headers=ledger_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    listing = client.get("/api/workpapers/index", headers=ledger_headers).json()
    assert len(listing) >= 1
