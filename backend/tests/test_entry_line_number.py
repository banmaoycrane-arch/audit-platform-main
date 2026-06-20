from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import ImportJob, SourceFile
from app.db.session import Base, get_db
from app.main import app
from app.services.import_service import process_import_job


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
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _build_csv(rows: list[dict]) -> bytes:
    header = "voucher_no,voucher_date,summary,account_code,account_name,debit_amount,credit_amount,counterparty\n"
    body = "\n".join(
        ",".join(
            str(row.get(col, ""))
            for col in [
                "voucher_no",
                "voucher_date",
                "summary",
                "account_code",
                "account_name",
                "debit_amount",
                "credit_amount",
                "counterparty",
            ]
        )
        for row in rows
    )
    return (header + body + "\n").encode("utf-8-sig")


def _create_job(test_client: TestClient) -> int:
    response = test_client.post(
        "/api/import-jobs",
        json={"organization_name": "行号测试企业", "industry": "general", "fiscal_year": 2026},
    )
    assert response.status_code == 200
    return response.json()["id"]


def _upload_csv(test_client: TestClient, job_id: int, csv_bytes: bytes, filename: str = "entries.csv") -> None:
    response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": (filename, BytesIO(csv_bytes), "text/csv")},
    )
    assert response.status_code == 200


def _process(SessionLocal, job_id: int) -> None:
    db = SessionLocal()
    try:
        # 修正 file_type 以兼容 _is_accounting_file 校验
        for source_file in db.query(SourceFile).filter(SourceFile.import_job_id == job_id).all():
            if not source_file.file_type.startswith("."):
                source_file.file_type = f".{source_file.file_type}"
        db.commit()
        job = db.get(ImportJob, job_id)
        process_import_job(db, job)
    finally:
        db.close()


def test_same_voucher_assigns_continuous_line_numbers(client):
    test_client, SessionLocal = client
    job_id = _create_job(test_client)
    csv_bytes = _build_csv([
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购", "account_code": "1403", "account_name": "原材料", "debit_amount": 1000, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购", "account_code": "2202", "account_name": "应付账款", "debit_amount": 0, "credit_amount": 1000, "counterparty": "供应商A"},
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "进项税", "account_code": "2221", "account_name": "应交税费", "debit_amount": 130, "credit_amount": 0, "counterparty": "供应商A"},
    ])
    _upload_csv(test_client, job_id, csv_bytes)
    _process(SessionLocal, job_id)

    entries = test_client.get(f"/api/entries?import_job_id={job_id}").json()
    line_nos = [e["entry_line_no"] for e in entries if e["voucher_no"] == "记-001"]
    assert sorted(line_nos) == [1, 2, 3]


def test_different_vouchers_have_independent_line_numbers(client):
    test_client, SessionLocal = client
    job_id = _create_job(test_client)
    csv_bytes = _build_csv([
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购", "account_code": "1403", "account_name": "原材料", "debit_amount": 1000, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购", "account_code": "2202", "account_name": "应付账款", "debit_amount": 0, "credit_amount": 1000, "counterparty": "供应商A"},
        {"voucher_no": "记-002", "voucher_date": "2026-01-02", "summary": "付款", "account_code": "2202", "account_name": "应付账款", "debit_amount": 1000, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-002", "voucher_date": "2026-01-02", "summary": "付款", "account_code": "1002", "account_name": "银行存款", "debit_amount": 0, "credit_amount": 1000, "counterparty": "供应商A"},
    ])
    _upload_csv(test_client, job_id, csv_bytes)
    _process(SessionLocal, job_id)

    entries = test_client.get(f"/api/entries?import_job_id={job_id}").json()
    by_voucher: dict[str, list[int]] = {}
    for entry in entries:
        by_voucher.setdefault(entry["voucher_no"], []).append(entry["entry_line_no"])
    assert sorted(by_voucher["记-001"]) == [1, 2]
    assert sorted(by_voucher["记-002"]) == [1, 2]


def test_missing_voucher_no_defaults_to_one(client):
    test_client, SessionLocal = client
    job_id = _create_job(test_client)
    csv_bytes = _build_csv([
        {"voucher_no": "", "voucher_date": "2026-01-03", "summary": "无凭证号A", "account_code": "1001", "account_name": "库存现金", "debit_amount": 100, "credit_amount": 0, "counterparty": ""},
        {"voucher_no": "", "voucher_date": "2026-01-03", "summary": "无凭证号B", "account_code": "1001", "account_name": "库存现金", "debit_amount": 200, "credit_amount": 0, "counterparty": ""},
    ])
    _upload_csv(test_client, job_id, csv_bytes)
    _process(SessionLocal, job_id)

    entries = test_client.get(f"/api/entries?import_job_id={job_id}").json()
    line_nos = [e["entry_line_no"] for e in entries]
    assert line_nos and all(no == 1 for no in line_nos)
