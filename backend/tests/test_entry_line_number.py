# -*- coding: utf-8 -*-
"""
模块功能：凭证分录行号生成逻辑测试。
业务场景：验证导入凭证时，系统自动为同一凭证的分录分配连续行号。
政策依据：会计准则对凭证分录顺序的要求。
输入数据：CSV导入的凭证数据。
输出结果：带行号的分录记录。
创建日期：2026-07-02
"""

from io import BytesIO
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_imports import _import_reports
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user_ledger_auth import UserLedgerAuth

from tests.conftest import register_auth_headers


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
    monkeypatch.setattr("app.services.doc_parsing.import_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.audit.risk_case_library.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.audit.risk_rule_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.audit.audit_day_book_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.accounting.entry_tag_vector_service.safe_vector_store", lambda: None)
    _import_reports.clear()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            test_client._auth_headers = register_auth_headers(test_client)
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        _import_reports.clear()
        Base.metadata.drop_all(bind=engine)


def _seed_ledger(TestingSessionLocal, test_client) -> int:
    """创建测试账簿，并默认给当前测试用户授权管理员权限。"""
    from app.core.security import decode_token

    token = test_client._auth_headers.get("Authorization", "").replace("Bearer ", "")
    payload = decode_token(token)
    user_id = int(payload["sub"])

    db = TestingSessionLocal()
    try:
        team = Team(name="行号测试团队")
        db.add(team)
        db.flush()
        ledger = Ledger(name="行号测试账簿", team_id=team.id)
        db.add(ledger)
        db.flush()
        auth = UserLedgerAuth(user_id=user_id, ledger_id=ledger.id, role="admin")
        db.add(auth)
        db.commit()
        return ledger.id
    finally:
        db.close()


def _acknowledge_dimension_readiness(test_client, ledger_id: int) -> None:
    """确认账簿维度规则已审阅，允许结构化导入。"""
    ack_response = test_client.post(
        f"/api/config/ledgers/{ledger_id}/dimension-readiness/acknowledge",
        headers=test_client._auth_headers,
    )
    assert ack_response.status_code == 200


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


def _create_job(test_client: TestClient, ledger_id: int, auth_headers: dict) -> int:
    response = test_client.post(
        "/api/import-jobs",
        json={
            "organization_name": "行号测试企业",
            "ledger_id": ledger_id,
            "industry": "general",
            "fiscal_year": 2026,
            "source_type": "ledger_day_book",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()["id"]


def _upload_csv(test_client: TestClient, job_id: int, csv_bytes: bytes, auth_headers: dict, filename: str = "entries.csv") -> None:
    response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": (filename, BytesIO(csv_bytes), "text/csv")},
        headers=auth_headers,
    )
    assert response.status_code == 200


def _list_entries(test_client: TestClient, job_id: int, auth_headers: dict) -> list[dict]:
    response = test_client.get(f"/api/entries?import_job_id={job_id}", headers=auth_headers)
    payload = response.json()
    if isinstance(payload, dict):
        return payload.get("items", [])
    return payload


def _process(test_client: TestClient, job_id: int, auth_headers: dict) -> None:
    # 通过 API 触发处理，确保与真实调用路径一致（含维度就绪检查）
    process_response = test_client.post(
        f"/api/import-jobs/{job_id}/process/sync",
        headers=auth_headers,
    )
    assert process_response.status_code == 200
    assert process_response.json()["job"]["status"] == "preview"
    # 复核后确认入账，生成正式 AccountingEntry
    review_response = test_client.post(
        f"/api/import-jobs/{job_id}/preview-entries/review-all",
        json={"review_status": "verified"},
        headers=auth_headers,
    )
    assert review_response.status_code == 200
    confirm_response = test_client.post(
        f"/api/import-jobs/{job_id}/confirm",
        headers=auth_headers,
    )
    assert confirm_response.status_code == 200


def test_same_voucher_assigns_continuous_line_numbers(client):
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal, test_client)
    _acknowledge_dimension_readiness(test_client, ledger_id)
    auth_headers = test_client._auth_headers

    job_id = _create_job(test_client, ledger_id, auth_headers)
    csv_bytes = _build_csv([
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购原材料", "account_code": "1403", "account_name": "原材料", "debit_amount": 1000, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "进项税额", "account_code": "2221", "account_name": "应交税费", "debit_amount": 130, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "应付货款", "account_code": "2202", "account_name": "应付账款", "debit_amount": 0, "credit_amount": 1130, "counterparty": "供应商A"},
    ])
    _upload_csv(test_client, job_id, csv_bytes, auth_headers)

    _process(test_client, job_id, auth_headers)

    entries = _list_entries(test_client, job_id, auth_headers)
    line_nos = [e["entry_line_no"] for e in entries if e["voucher_no"] == "记-001"]
    assert sorted(line_nos) == [1, 2, 3]


def test_different_vouchers_have_independent_line_numbers(client):
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal, test_client)
    _acknowledge_dimension_readiness(test_client, ledger_id)
    auth_headers = test_client._auth_headers

    job_id = _create_job(test_client, ledger_id, auth_headers)
    csv_bytes = _build_csv([
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购", "account_code": "1403", "account_name": "原材料", "debit_amount": 1000, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购", "account_code": "2202", "account_name": "应付账款", "debit_amount": 0, "credit_amount": 1000, "counterparty": "供应商A"},
        {"voucher_no": "记-002", "voucher_date": "2026-01-02", "summary": "付款", "account_code": "2202", "account_name": "应付账款", "debit_amount": 1000, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-002", "voucher_date": "2026-01-02", "summary": "付款", "account_code": "1002", "account_name": "银行存款", "debit_amount": 0, "credit_amount": 1000, "counterparty": "供应商A"},
    ])
    _upload_csv(test_client, job_id, csv_bytes, auth_headers)
    _process(test_client, job_id, auth_headers)

    entries = _list_entries(test_client, job_id, auth_headers)
    by_voucher: dict[str, list[int]] = {}
    for entry in entries:
        by_voucher.setdefault(entry["voucher_no"], []).append(entry["entry_line_no"])
    assert sorted(by_voucher["记-001"]) == [1, 2]
    assert sorted(by_voucher["记-002"]) == [1, 2]


def test_single_entry_voucher_line_number(client):
    test_client, TestingSessionLocal = client
    ledger_id = _seed_ledger(TestingSessionLocal, test_client)
    _acknowledge_dimension_readiness(test_client, ledger_id)
    auth_headers = test_client._auth_headers

    job_id = _create_job(test_client, ledger_id, auth_headers)
    csv_bytes = _build_csv([
        {"voucher_no": "记-003", "voucher_date": "2026-01-03", "summary": "提现", "account_code": "1001", "account_name": "库存现金", "debit_amount": 500, "credit_amount": 0, "counterparty": ""},
        {"voucher_no": "记-003", "voucher_date": "2026-01-03", "summary": "提现", "account_code": "1002", "account_name": "银行存款", "debit_amount": 0, "credit_amount": 500, "counterparty": ""},
    ])
    _upload_csv(test_client, job_id, csv_bytes, auth_headers)
    _process(test_client, job_id, auth_headers)

    entries = _list_entries(test_client, job_id, auth_headers)
    line_nos = [e["entry_line_no"] for e in entries if e["voucher_no"] == "记-003"]
    assert sorted(line_nos) == [1, 2]
