"""底稿资料自动归档测试。"""

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
from app.services.draft_archive_service import (
    auto_archive_draft,
    build_archive_context,
    build_archive_path,
    load_archive_metadata,
    resolve_project_for_ledger,
)


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


def test_build_archive_path_segments():
    path = build_archive_path("2025年度审计", "2025-03", "税务底稿", "发票")
    assert path == "2025年度审计/2025-03/税务底稿/发票"


def test_build_archive_context_from_invoice_feedback():
    project = Project(id=1, name="测试项目", team_id=1)
    feedback = {
        "document_type": "invoice",
        "document_type_label": "发票",
        "voucher_date": "2025-03-15",
        "counterparty": "供应商A",
        "register_type": "invoice",
    }
    module_regs = [
        {"module_key": "tax_invoice", "module_label": "税务模块-发票台账", "semantic_only": False},
    ]
    archive = build_archive_context(
        project=project,
        parse_feedback=feedback,
        module_registrations=module_regs,
    )
    assert archive["project_id"] == 1
    assert archive["period_code"] == "2025-03"
    assert archive["archive_category"] == "税务底稿"
    assert archive["archive_folder"] == "发票"
    assert archive["archive_path"].startswith("测试项目/2025-03/税务底稿/")


def test_auto_archive_persists_to_source_file_notes(client):
    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="归档测试组织")
        db.add(org)
        db.flush()

        team = Team(name="归档测试团队")
        db.add(team)
        db.flush()

        project = Project(name="归档项目", team_id=team.id)
        db.add(project)
        db.flush()

        ledger = Ledger(name="归档账套", team_id=team.id)
        db.add(ledger)
        db.flush()

        db.add(ProjectLedger(project_id=project.id, ledger_id=ledger.id))

        job = ImportJob(organization_id=org.id, ledger_id=ledger.id, source_type="ai_generated")
        db.add(job)
        db.flush()

        source_file = SourceFile(
            organization_id=org.id,
            import_job_id=job.id,
            ledger_id=ledger.id,
            filename="增值税发票.pdf",
            file_type="pdf",
            storage_path="/tmp/invoice.pdf",
            notes=json.dumps({"document_type_hints": ["invoice"]}, ensure_ascii=False),
        )
        db.add(source_file)
        db.commit()

        archive = auto_archive_draft(
            db,
            source_file,
            {
                "document_type": "invoice",
                "document_type_label": "发票",
                "voucher_date": "2025-04-02",
                "counterparty": "客户B",
            },
            module_registrations=[{"module_key": "tax_invoice", "semantic_only": False}],
            source_type="ai_generated",
            job=job,
        )
        db.commit()
        db.refresh(source_file)

        assert archive["project_id"] == project.id
        assert "归档项目" in archive["archive_path"]
        stored = load_archive_metadata(source_file)
        assert stored is not None
        assert stored["archive_path"] == archive["archive_path"]
        assert resolve_project_for_ledger(db, ledger.id).id == project.id


def test_project_files_api_returns_archived_files(client):
    project_id = None
    with next(app.dependency_overrides[get_db]()) as db:
        org = Organization(name="API归档组织")
        db.add(org)
        db.flush()
        team = Team(name="API团队")
        db.add(team)
        db.flush()
        project = Project(name="API归档项目", team_id=team.id)
        db.add(project)
        db.flush()
        project_id = project.id
        ledger = Ledger(name="API账套", team_id=team.id)
        db.add(ledger)
        db.flush()
        db.add(ProjectLedger(project_id=project.id, ledger_id=ledger.id))
        job = ImportJob(organization_id=org.id, ledger_id=ledger.id, source_type="ai_generated")
        db.add(job)
        db.flush()
        source_file = SourceFile(
            organization_id=org.id,
            import_job_id=job.id,
            ledger_id=ledger.id,
            filename="合同.pdf",
            file_type="pdf",
            storage_path="/tmp/contract.pdf",
            notes=json.dumps(
                {
                    "archive": {
                            "project_id": project_id,
                            "project_name": "API归档项目",
                            "archive_path": "API归档项目/2025-05/往来账款底稿/合同",
                        "archive_category": "往来账款底稿",
                        "archive_folder": "合同",
                        "period_code": "2025-05",
                        "status": "archived",
                    }
                },
                ensure_ascii=False,
            ),
        )
        db.add(source_file)
        db.commit()

    response = client.get(f"/api/files?project_id={project_id}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["archive_path"].endswith("往来账款底稿/合同")
    assert data[0]["project_id"] == project_id
