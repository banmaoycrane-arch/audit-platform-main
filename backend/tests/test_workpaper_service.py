# -*- coding: utf-8 -*-
"""
模块功能：审计工作底稿服务层单元测试。
业务场景：验证底稿索引创建、版本管理、状态流转、目录导出等核心业务逻辑。
创建日期：2026-07-03
"""

import os
import tempfile
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Organization, SourceFile, WorkpaperIndex, WorkpaperVersion
from app.db.session import Base, get_db
from app.main import app
from app.services.audit.workpaper_service import (
    create_index_node,
    export_workpaper_catalog,
    get_workpaper_index,
    list_workpaper_indexes,
    register_source_file,
    revise_workpaper,
    sync_from_archived_files,
    update_version_status,
)


@pytest.fixture
def db_session():
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
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def seed_ledger_and_files(db_session):
    from app.db.models import ImportJob

    org = Organization(name="测试组织")
    db_session.add(org)
    db_session.flush()

    job = ImportJob(organization_id=org.id)
    db_session.add(job)
    db_session.flush()

    file1 = SourceFile(
        organization_id=org.id,
        import_job_id=job.id,
        filename="采购合同.pdf",
        file_type="pdf",
        storage_path="/tmp/test_contract.pdf",
        text_extract_status="completed",
        extracted_text="测试合同内容",
    )
    db_session.add(file1)
    db_session.commit()

    return {"org": org, "job": job, "file1": file1}


class TestWorkpaperIndex:
    """工作底稿索引测试。"""

    def test_create_index_node(self, db_session):
        result = create_index_node(
            db_session,
            ledger_id=1,
            title="货币资金底稿",
            audit_area="货币资金",
            project_id=1,
        )
        assert result["id"] is not None
        assert result["title"] == "货币资金底稿"
        assert result["audit_area"] == "货币资金"
        assert result["index_no"] == "A1"
        assert result["version_count"] == 0

    def test_create_index_node_auto_index_no(self, db_session):
        create_index_node(db_session, ledger_id=1, title="货币资金底稿1", audit_area="货币资金")
        create_index_node(db_session, ledger_id=1, title="货币资金底稿2", audit_area="货币资金")
        result = create_index_node(db_session, ledger_id=1, title="往来底稿", audit_area="往来款项")
        assert result["index_no"] == "B1"

    def test_list_workpaper_indexes(self, db_session):
        create_index_node(db_session, ledger_id=1, title="底稿A", audit_area="货币资金")
        create_index_node(db_session, ledger_id=1, title="底稿B", audit_area="往来款项")
        create_index_node(db_session, ledger_id=2, title="其他账簿底稿", audit_area="货币资金")

        indexes = list_workpaper_indexes(db_session, ledger_id=1)
        assert len(indexes) == 2
        assert indexes[0]["index_no"] == "A1"
        assert indexes[1]["index_no"] == "B1"

    def test_get_workpaper_index(self, db_session):
        created = create_index_node(db_session, ledger_id=1, title="测试底稿", audit_area="综合")
        fetched = get_workpaper_index(db_session, created["id"], ledger_id=1)
        assert fetched is not None
        assert fetched["title"] == "测试底稿"
        assert len(fetched["versions"]) == 0

    def test_get_workpaper_index_not_found(self, db_session):
        result = get_workpaper_index(db_session, index_id=999, ledger_id=1)
        assert result is None


class TestWorkpaperVersion:
    """工作底稿版本管理测试。"""

    def test_register_source_file_creates_index_and_version(self, db_session, seed_ledger_and_files):
        file1 = seed_ledger_and_files["file1"]
        file1.ledger_id = 1
        db_session.commit()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write("test content")
            temp_path = f.name
        try:
            file1.storage_path = temp_path
            db_session.commit()

            result = register_source_file(db_session, ledger_id=1, source_file_id=file1.id)
            assert result["id"] is not None
            assert result["version_count"] == 1
            assert result["versions"][0]["version_no"] == "1.0"
            assert result["versions"][0]["status"] == "draft"
        finally:
            os.unlink(temp_path)

    def test_revise_workpaper_creates_new_version(self, db_session, seed_ledger_and_files):
        file1 = seed_ledger_and_files["file1"]
        file1.ledger_id = 1
        db_session.commit()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write("test content")
            temp_path = f.name
        try:
            file1.storage_path = temp_path
            db_session.commit()

            index = register_source_file(db_session, ledger_id=1, source_file_id=file1.id)
            index_id = index["id"]

            revised = revise_workpaper(
                db_session,
                index_id=index_id,
                ledger_id=1,
                source_file_id=file1.id,
                change_reason="内容修订",
            )
            assert len(revised["versions"]) == 2
            assert revised["versions"][0]["status"] == "superseded"
            assert revised["versions"][1]["version_no"] == "1.1"
            assert revised["versions"][1]["status"] == "draft"
            assert revised["versions"][1]["change_reason"] == "内容修订"
        finally:
            os.unlink(temp_path)

    def test_version_number_increment_logic(self, db_session, seed_ledger_and_files):
        file1 = seed_ledger_and_files["file1"]
        file1.ledger_id = 1
        db_session.commit()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write("test content")
            temp_path = f.name
        try:
            file1.storage_path = temp_path
            db_session.commit()

            index = register_source_file(db_session, ledger_id=1, source_file_id=file1.id)
            index_id = index["id"]

            revise_workpaper(db_session, index_id=index_id, ledger_id=1, source_file_id=file1.id, change_reason="v1")
            revise_workpaper(db_session, index_id=index_id, ledger_id=1, source_file_id=file1.id, change_reason="v2")
            revised = revise_workpaper(db_session, index_id=index_id, ledger_id=1, source_file_id=file1.id, change_reason="v3")

            assert len(revised["versions"]) == 4
            assert revised["versions"][-1]["version_no"] == "1.3"
        finally:
            os.unlink(temp_path)

    def test_update_version_status(self, db_session, seed_ledger_and_files):
        file1 = seed_ledger_and_files["file1"]
        file1.ledger_id = 1
        db_session.commit()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write("test content")
            temp_path = f.name
        try:
            file1.storage_path = temp_path
            db_session.commit()

            index = register_source_file(db_session, ledger_id=1, source_file_id=file1.id)
            version_id = index["versions"][0]["id"]

            submitted = update_version_status(db_session, version_id=version_id, ledger_id=1, status="submitted")
            assert submitted["status"] == "submitted"

            reviewed = update_version_status(db_session, version_id=version_id, ledger_id=1, status="reviewed", reviewed_by=1)
            assert reviewed["status"] == "reviewed"
            assert reviewed["reviewed_by"] == 1
        finally:
            os.unlink(temp_path)

    def test_update_version_status_invalid(self, db_session):
        with pytest.raises(ValueError, match="invalid status"):
            update_version_status(db_session, version_id=1, ledger_id=1, status="invalid")


class TestWorkpaperExport:
    """工作底稿导出测试。"""

    def test_export_workpaper_catalog(self, db_session):
        create_index_node(db_session, ledger_id=1, title="底稿A", audit_area="货币资金")
        create_index_node(db_session, ledger_id=1, title="底稿B", audit_area="往来款项")

        catalog = export_workpaper_catalog(db_session, ledger_id=1)
        assert catalog["ledger_id"] == 1
        assert catalog["index_count"] == 2
        assert catalog["version_count"] == 0
        assert len(catalog["items"]) == 2
        assert "exported_at" in catalog


class TestWorkpaperSync:
    """工作底稿同步测试。"""

    def test_sync_from_archived_files(self, db_session, seed_ledger_and_files):
        file1 = seed_ledger_and_files["file1"]
        file1.ledger_id = 1
        db_session.commit()

        result = sync_from_archived_files(db_session, ledger_id=1)
        assert isinstance(result, list)


class TestWorkpaperPermissions:
    """工作底稿权限测试。"""

    def test_revise_rejects_wrong_ledger(self, db_session, seed_ledger_and_files):
        file1 = seed_ledger_and_files["file1"]
        file1.ledger_id = 2
        db_session.commit()

        create_index_node(db_session, ledger_id=1, title="底稿", audit_area="综合")

        with pytest.raises(ValueError, match="source file does not belong to ledger"):
            revise_workpaper(
                db_session,
                index_id=1,
                ledger_id=1,
                source_file_id=file1.id,
                change_reason="测试",
            )