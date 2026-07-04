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
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ImportJob, SourceFile, AccountingPeriod, Organization
from app.db.session import Base, engine
from app.main import app
from app.services.doc_parsing.import_service import process_import_job
from app.services.basic_data.coa_service import init_default_accounts
from app.models.user import User
from app.models.ledger import Ledger
from app.models.user_ledger_auth import UserLedgerAuth
from app.models.team import Team
from app.core.security import create_access_token


client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    user = User(
        username="line_no_test_user",
        phone="13800000001",
        email="line_no_test@example.com",
        hashed_password="fake_hash",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_team(db_session):
    team = Team(name="行号测试团队", type="enterprise")
    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)
    return team


@pytest.fixture
def test_organization(db_session):
    org = Organization(name="行号测试企业")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_ledger(db_session, test_team, test_user, test_organization):
    ledger = Ledger(
        team_id=test_team.id,
        name="行号测试账簿",
        status="active",
        accounting_start_date=date(2026, 1, 1),
    )
    db_session.add(ledger)
    db_session.commit()
    db_session.refresh(ledger)

    auth = UserLedgerAuth(
        user_id=test_user.id,
        ledger_id=ledger.id,
        role="accountant",
    )
    db_session.add(auth)
    db_session.flush()

    init_default_accounts(db_session, ledger.id)

    return ledger


@pytest.fixture
def test_period(db_session, test_organization, test_ledger):
    period = AccountingPeriod(
        organization_id=test_organization.id,
        ledger_id=test_ledger.id,
        period_code="2026-01",
        period_type="monthly",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status="open",
    )
    db_session.add(period)
    db_session.commit()
    return period


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
        json={"organization_name": "行号测试企业", "ledger_id": ledger_id, "industry": "general", "fiscal_year": 2026},
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()["id"]


def _upload_csv(test_client: TestClient, job_id: int, csv_bytes: bytes, filename: str = "entries.csv") -> None:
    response = test_client.post(
        f"/api/import-jobs/{job_id}/files",
        files={"file": (filename, BytesIO(csv_bytes), "text/csv")},
    )
    assert response.status_code == 200


def _list_entries(test_client: TestClient, job_id: int) -> list[dict]:
    payload = test_client.get(f"/api/entries?import_job_id={job_id}").json()
    if isinstance(payload, dict):
        return payload.get("items", [])
    return payload


def _process(db_session: Session, job_id: int) -> None:
    for source_file in db_session.query(SourceFile).filter(SourceFile.import_job_id == job_id).all():
        if not source_file.file_type.startswith("."):
            source_file.file_type = f".{source_file.file_type}"
    db_session.commit()
    job = db_session.get(ImportJob, job_id)
    process_import_job(db_session, job)


def test_same_voucher_assigns_continuous_line_numbers(db_session, test_user, test_team, test_organization, test_ledger, test_period):
    auth_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(test_user.id)})}"}

    job_id = _create_job(client, test_ledger.id, auth_headers)
    csv_bytes = _build_csv([
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购原材料", "account_code": "1403", "account_name": "原材料", "debit_amount": 1000, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "进项税额", "account_code": "2221", "account_name": "应交税费", "debit_amount": 130, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "应付货款", "account_code": "2202", "account_name": "应付账款", "debit_amount": 0, "credit_amount": 1130, "counterparty": "供应商A"},
    ])
    _upload_csv(client, job_id, csv_bytes)
    
    _process(db_session, job_id)

    entries = _list_entries(client, job_id)
    line_nos = [e["entry_line_no"] for e in entries if e["voucher_no"] == "记-001"]
    assert sorted(line_nos) == [1, 2, 3]


def test_different_vouchers_have_independent_line_numbers(db_session, test_user, test_team, test_organization, test_ledger, test_period):
    auth_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(test_user.id)})}"}

    job_id = _create_job(client, test_ledger.id, auth_headers)
    csv_bytes = _build_csv([
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购", "account_code": "1403", "account_name": "原材料", "debit_amount": 1000, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-001", "voucher_date": "2026-01-01", "summary": "采购", "account_code": "2202", "account_name": "应付账款", "debit_amount": 0, "credit_amount": 1000, "counterparty": "供应商A"},
        {"voucher_no": "记-002", "voucher_date": "2026-01-02", "summary": "付款", "account_code": "2202", "account_name": "应付账款", "debit_amount": 1000, "credit_amount": 0, "counterparty": "供应商A"},
        {"voucher_no": "记-002", "voucher_date": "2026-01-02", "summary": "付款", "account_code": "1002", "account_name": "银行存款", "debit_amount": 0, "credit_amount": 1000, "counterparty": "供应商A"},
    ])
    _upload_csv(client, job_id, csv_bytes)
    _process(db_session, job_id)

    entries = _list_entries(client, job_id)
    by_voucher: dict[str, list[int]] = {}
    for entry in entries:
        by_voucher.setdefault(entry["voucher_no"], []).append(entry["entry_line_no"])
    assert sorted(by_voucher["记-001"]) == [1, 2]
    assert sorted(by_voucher["记-002"]) == [1, 2]


def test_single_entry_voucher_line_number(db_session, test_user, test_team, test_organization, test_ledger, test_period):
    auth_headers = {"Authorization": f"Bearer {create_access_token({'sub': str(test_user.id)})}"}

    job_id = _create_job(client, test_ledger.id, auth_headers)
    csv_bytes = _build_csv([
        {"voucher_no": "记-003", "voucher_date": "2026-01-03", "summary": "提现", "account_code": "1001", "account_name": "库存现金", "debit_amount": 500, "credit_amount": 0, "counterparty": ""},
        {"voucher_no": "记-003", "voucher_date": "2026-01-03", "summary": "提现", "account_code": "1002", "account_name": "银行存款", "debit_amount": 0, "credit_amount": 500, "counterparty": ""},
    ])
    _upload_csv(client, job_id, csv_bytes)
    _process(db_session, job_id)

    entries = _list_entries(client, job_id)
    line_nos = [e["entry_line_no"] for e in entries if e["voucher_no"] == "记-003"]
    assert sorted(line_nos) == [1, 2]