# -*- coding: utf-8 -*-
"""经济事件工单 E1 API 测试。

覆盖 spec §8 验收标准：
- 创建事件工单
- 关联分录与文件
- 状态迁移（合法/非法）
- 步骤日志写入
- 查询不创建事件
- 金额展示与分录汇总一致
"""
import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    AccountingEntry,
    EconomicEvent,
    EconomicEventEntry,
    EconomicEventFile,
    EconomicEventStep,
    ImportJob,
    Organization,
    SourceFile,
)
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team


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


def _auth_headers(client: TestClient) -> dict:
    suffix = uuid.uuid4().hex[:8]
    register = client.post(
        "/api/auth/register",
        json={
            "username": f"evt_{suffix}",
            "password": "TestPass123!",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert register.status_code == 200
    return {"Authorization": f"Bearer {register.json()['access_token']}"}


def _create_ledger(client: TestClient, headers: dict) -> tuple[dict, int]:
    team = client.post("/api/teams", json={"name": "事件团队", "type": "company"}, headers=headers)
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "事件账簿"},
        headers=headers,
    )
    ledger_id = ledger.json()["id"]
    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    return {**headers, "X-Ledger-Id": str(ledger_id)}, ledger_id


def _seed_entry_and_file(ledger_id: int) -> tuple[int, int]:
    """直接在 DB 插入一条分录和源文件供关联测试用。"""
    with next(app.dependency_overrides[get_db]()) as db:
        team = Team(name="种子团队")
        db.add(team)
        db.flush()
        ledger = db.get(Ledger, ledger_id)
        org = Organization(name="种子企业")
        db.add(org)
        db.flush()
        import_job = ImportJob(organization_id=org.id, ledger_id=ledger_id, status="completed")
        db.add(import_job)
        db.flush()
        sf = SourceFile(
            organization_id=org.id,
            import_job_id=import_job.id,
            filename="invoice.pdf",
            file_type="invoice",
            storage_path="/tmp/invoice.pdf",
        )
        db.add(sf)
        db.flush()
        entry = AccountingEntry(
            organization_id=org.id,
            ledger_id=ledger_id,
            import_job_id=import_job.id,
            voucher_no="V-001",
            account_code="1002",
            account_name="银行存款",
            debit_amount=Decimal("500.00"),
            credit_amount=Decimal("0.00"),
            entry_source="manual",
        )
        db.add(entry)
        db.flush()
        db.commit()
        return entry.id, sf.id


# ---------- Tests ----------

def test_create_event(client: TestClient):
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    resp = client.post(
        "/api/economic-events/",
        headers=headers,
        json={"title": "收到客户货款", "event_type": "revenue_recognition", "summary": "1月收入"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "收到客户货款"
    assert data["status"] == "draft"
    assert data["event_no"].startswith(f"E-{ledger_id}-")
    assert data["entry_count"] == 0


def test_list_events(client: TestClient):
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    for i in range(3):
        client.post(
            "/api/economic-events/",
            headers=headers,
            json={"title": f"事件{i}", "event_type": "manual"},
        )
    resp = client.get("/api/economic-events/", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_get_event_detail(client: TestClient):
    headers, _ = _create_ledger(client, _auth_headers(client))
    create = client.post(
        "/api/economic-events/", headers=headers, json={"title": "详情测试"}
    )
    event_id = create.json()["id"]
    resp = client.get(f"/api/economic-events/{event_id}", headers=headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["id"] == event_id
    assert len(detail["steps"]) >= 1  # 至少有 create 步骤
    assert detail["steps"][0]["step_code"] == "create"


def test_attach_entry_and_file(client: TestClient):
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    entry_id, file_id = _seed_entry_and_file(ledger_id)

    create = client.post(
        "/api/economic-events/", headers=headers, json={"title": "关联测试"}
    )
    event_id = create.json()["id"]

    # 挂分录
    resp_e = client.post(
        f"/api/economic-events/{event_id}/entries",
        headers=headers,
        json={"accounting_entry_id": entry_id},
    )
    assert resp_e.status_code == 201
    assert resp_e.json()["accounting_entry_id"] == entry_id

    # 挂文件
    resp_f = client.post(
        f"/api/economic-events/{event_id}/files",
        headers=headers,
        json={"source_file_id": file_id},
    )
    assert resp_f.status_code == 201
    assert resp_f.json()["source_file_id"] == file_id

    # 验证详情计数
    detail = client.get(f"/api/economic-events/{event_id}", headers=headers).json()
    assert detail["entry_count"] == 1
    assert detail["file_count"] == 1

    # E1 收尾验收：从分录侧反查所属事件（event_id + event_no 闭环）
    event_no = create.json()["event_no"]
    lines = client.get(
        "/api/entries/vouchers/lines",
        headers=headers,
        params={"ledger_id": ledger_id, "voucher_no": "V-001"},
    )
    assert lines.status_code == 200
    line_items = lines.json()["items"]
    assert len(line_items) >= 1
    assert line_items[0]["event_id"] == event_id
    assert line_items[0]["event_no"] == event_no


def test_transition_valid(client: TestClient):
    headers, _ = _create_ledger(client, _auth_headers(client))
    create = client.post(
        "/api/economic-events/", headers=headers, json={"title": "状态推进"}
    )
    event_id = create.json()["id"]

    # draft → collecting
    resp = client.post(
        f"/api/economic-events/{event_id}/transition",
        headers=headers,
        json={"to_status": "collecting", "reason": "开始归集"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "collecting"

    # collecting → pending_review
    resp = client.post(
        f"/api/economic-events/{event_id}/transition",
        headers=headers,
        json={"to_status": "pending_review"},
    )
    assert resp.json()["status"] == "pending_review"


def test_transition_invalid_rejected(client: TestClient):
    headers, _ = _create_ledger(client, _auth_headers(client))
    create = client.post(
        "/api/economic-events/", headers=headers, json={"title": "非法迁移"}
    )
    event_id = create.json()["id"]

    # draft → posted 是非法跳转
    resp = client.post(
        f"/api/economic-events/{event_id}/transition",
        headers=headers,
        json={"to_status": "posted"},
    )
    assert resp.status_code == 400
    assert "不允许" in resp.json()["detail"]


def test_steps_logged(client: TestClient):
    headers, _ = _create_ledger(client, _auth_headers(client))
    create = client.post(
        "/api/economic-events/", headers=headers, json={"title": "步骤日志"}
    )
    event_id = create.json()["id"]

    # 推进两次状态
    client.post(
        f"/api/economic-events/{event_id}/transition",
        headers=headers,
        json={"to_status": "collecting"},
    )
    client.post(
        f"/api/economic-events/{event_id}/transition",
        headers=headers,
        json={"to_status": "pending_review"},
    )

    resp = client.get(f"/api/economic-events/{event_id}/steps", headers=headers)
    assert resp.status_code == 200
    steps = resp.json()
    # create + transition × 2 = 至少 3 条
    assert len(steps) >= 3
    assert steps[0]["step_code"] == "create"
    assert steps[-1]["to_status"] == "pending_review"


def test_query_does_not_create_event(client: TestClient):
    """查询接口不应自动创建事件。"""
    headers, _ = _create_ledger(client, _auth_headers(client))
    # 先查询空列表
    resp = client.get("/api/economic-events/", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 0
    # 再查一次
    resp2 = client.get("/api/economic-events/", headers=headers)
    assert len(resp2.json()) == 0


def test_display_amount_matches_entries(client: TestClient):
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    entry_id, _ = _seed_entry_and_file(ledger_id)

    create = client.post(
        "/api/economic-events/", headers=headers, json={"title": "金额一致性"}
    )
    event_id = create.json()["id"]
    client.post(
        f"/api/economic-events/{event_id}/entries",
        headers=headers,
        json={"accounting_entry_id": entry_id},
    )

    detail = client.get(f"/api/economic-events/{event_id}", headers=headers).json()
    # display_amount 应等于关联分录借方合计 500.00
    assert detail["display_amount"] == "500.00"


def test_no_event_amount_in_db(client: TestClient):
    """库内事件表不应存储借贷金额作为核算事实。"""
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    client.post(
        "/api/economic-events/", headers=headers, json={"title": "金额字段检查"}
    )
    with next(app.dependency_overrides[get_db]()) as db:
        events = db.query(EconomicEvent).all()
        assert len(events) == 1
        # display_amount 可为 NULL（派生自关联分录）
        assert events[0].display_amount is None
