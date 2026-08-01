# -*- coding: utf-8 -*-
"""经济事件工单 E2 导入聚类 API 测试。

覆盖 spec §7 E2 验收标准：
- 空聚类（无分录 / 无导入任务匹配）返回空列表
- 正常聚类（同往来 + 同月 ≥2 分录）返回 1 个候选
- 阈值过滤（<2 分录的组不出现）
- confirm 幂等：已挂在 import_cluster 事件上的分录不会被二次聚类
- confirm 后事件状态推进到 collecting，关联分录正确
"""
import uuid
from datetime import date
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
    ImportJob,
    Organization,
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
            "username": f"cluster_{suffix}",
            "password": "TestPass123!",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert register.status_code == 200
    return {"Authorization": f"Bearer {register.json()['access_token']}"}


def _create_ledger(client: TestClient, headers: dict) -> tuple[dict, int]:
    team = client.post("/api/teams", json={"name": "聚类团队", "type": "company"}, headers=headers)
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "聚类账簿"},
        headers=headers,
    )
    ledger_id = ledger.json()["id"]
    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    return {**headers, "X-Ledger-Id": str(ledger_id)}, ledger_id


def _seed_entries(
    ledger_id: int,
    *,
    import_job_id: int | None = None,
    entries: list[dict],
) -> list[int]:
    """直接在 DB 插入若干分录，每条 dict 含 voucher_date/counterparty_id/original_entity_name/counterparty/debit_amount。"""
    with next(app.dependency_overrides[get_db]()) as db:
        ledger = db.get(Ledger, ledger_id)
        assert ledger is not None
        org = Organization(name=f"聚类企业-{uuid.uuid4().hex[:6]}")
        db.add(org)
        db.flush()
        ij_id = import_job_id
        if ij_id is None:
            ij = ImportJob(organization_id=org.id, ledger_id=ledger_id, status="completed")
            db.add(ij)
            db.flush()
            ij_id = ij.id
        entry_ids: list[int] = []
        for spec in entries:
            entry = AccountingEntry(
                organization_id=org.id,
                ledger_id=ledger_id,
                import_job_id=ij_id,
                voucher_no=spec.get("voucher_no", f"V-{len(entry_ids)+1:03d}"),
                voucher_date=spec["voucher_date"],
                account_code="1002",
                account_name="银行存款",
                counterparty_id=spec.get("counterparty_id"),
                counterparty=spec.get("counterparty"),
                original_entity_name=spec.get("original_entity_name"),
                debit_amount=Decimal(str(spec.get("debit_amount", "100.00"))),
                credit_amount=Decimal("0.00"),
                entry_source="manual",
            )
            db.add(entry)
            db.flush()
            entry_ids.append(entry.id)
        db.commit()
        return entry_ids


# ---------- Tests ----------

def test_cluster_suggest_empty_when_no_entries(client: TestClient):
    """空聚类：账簿无分录时返回空列表。"""
    headers, _ = _create_ledger(client, _auth_headers(client))
    resp = client.post(
        "/api/economic-events/cluster-suggest",
        headers=headers,
        json={"min_entries": 2},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_cluster_suggest_normal_grouping(client: TestClient):
    """正常聚类：同往来 + 同月 ≥2 分录 → 1 个候选。"""
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    _seed_entries(
        ledger_id,
        entries=[
            {
                "voucher_date": date(2026, 7, 5),
                "counterparty_id": 1001,
                "counterparty": "甲客户",
                "debit_amount": "500.00",
            },
            {
                "voucher_date": date(2026, 7, 20),
                "counterparty_id": 1001,
                "counterparty": "甲客户",
                "debit_amount": "300.00",
            },
        ],
    )
    resp = client.post(
        "/api/economic-events/cluster-suggest",
        headers=headers,
        json={"min_entries": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    cluster = data[0]
    assert cluster["counterparty_name"] == "甲客户"
    assert cluster["occurred_on"] == "2026-07-05"
    assert cluster["entry_count"] == 2
    assert cluster["display_amount"] == "800.00"
    assert cluster["title"].startswith("甲客户 2026-07")
    assert cluster["event_type"] == "manual"
    assert len(cluster["entry_ids"]) == 2


def test_cluster_suggest_threshold_filter(client: TestClient):
    """阈值过滤：单条分录的组不出现。"""
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    # 往来 A：2 条同月（应聚成 1 组）
    # 往来 B：1 条同月（<2，应被过滤）
    # 往来 C：2 条但跨月（应被分到 2 个不同组，每组 1 条，<2，都应被过滤）
    _seed_entries(
        ledger_id,
        entries=[
            {"voucher_date": date(2026, 7, 5), "counterparty_id": 1, "counterparty": "A", "debit_amount": "100.00"},
            {"voucher_date": date(2026, 7, 10), "counterparty_id": 1, "counterparty": "A", "debit_amount": "200.00"},
            {"voucher_date": date(2026, 7, 15), "counterparty_id": 2, "counterparty": "B", "debit_amount": "50.00"},
            {"voucher_date": date(2026, 7, 20), "counterparty_id": 3, "counterparty": "C", "debit_amount": "10.00"},
            {"voucher_date": date(2026, 8, 5), "counterparty_id": 3, "counterparty": "C", "debit_amount": "20.00"},
        ],
    )
    resp = client.post(
        "/api/economic-events/cluster-suggest",
        headers=headers,
        json={"min_entries": 2},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 只应有 1 个候选：往来 A 7月
    assert len(data) == 1
    assert data[0]["counterparty_name"] == "A"


def test_cluster_confirm_creates_events_and_attaches_entries(client: TestClient):
    """confirm 后事件状态推进到 collecting，关联分录正确。"""
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    entry_ids = _seed_entries(
        ledger_id,
        entries=[
            {"voucher_date": date(2026, 7, 5), "counterparty_id": 1001, "counterparty": "甲客户", "debit_amount": "500.00"},
            {"voucher_date": date(2026, 7, 20), "counterparty_id": 1001, "counterparty": "甲客户", "debit_amount": "300.00"},
        ],
    )

    # 1. suggest 拿候选
    suggest_resp = client.post(
        "/api/economic-events/cluster-suggest",
        headers=headers,
        json={"min_entries": 2},
    )
    assert suggest_resp.status_code == 200
    cluster = suggest_resp.json()[0]

    # 2. confirm 创建事件
    confirm_resp = client.post(
        "/api/economic-events/cluster-confirm",
        headers=headers,
        json={
            "clusters": [
                {
                    "title": cluster["title"],
                    "event_type": "import_cluster",
                    "occurred_on": cluster["occurred_on"],
                    "entry_ids": cluster["entry_ids"],
                }
            ]
        },
    )
    assert confirm_resp.status_code == 201
    events = confirm_resp.json()
    assert len(events) == 1
    event = events[0]
    assert event["status"] == "collecting"
    assert event["event_type"] == "import_cluster"
    assert event["source"] == "import"
    assert event["entry_count"] == 2
    assert event["display_amount"] == "800.00"

    # 3. DB 校验：事件状态 + 关联分录
    with next(app.dependency_overrides[get_db]()) as db:
        ev = db.query(EconomicEvent).filter(EconomicEvent.id == event["id"]).one()
        assert ev.status == "collecting"
        assert ev.event_type == "import_cluster"
        links = (
            db.query(EconomicEventEntry)
            .filter(EconomicEventEntry.event_id == event["id"])
            .all()
        )
        assert {l.accounting_entry_id for l in links} == set(entry_ids)


def test_cluster_suggest_idempotent_after_confirm(client: TestClient):
    """幂等：confirm 后再次 suggest，已挂载分录不应再出现。"""
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    _seed_entries(
        ledger_id,
        entries=[
            {"voucher_date": date(2026, 7, 5), "counterparty_id": 1001, "counterparty": "甲客户", "debit_amount": "500.00"},
            {"voucher_date": date(2026, 7, 20), "counterparty_id": 1001, "counterparty": "甲客户", "debit_amount": "300.00"},
        ],
    )

    # 1. 第一次 suggest → 1 个候选
    r1 = client.post("/api/economic-events/cluster-suggest", headers=headers, json={"min_entries": 2})
    assert r1.status_code == 200
    assert len(r1.json()) == 1
    cluster = r1.json()[0]

    # 2. confirm
    r2 = client.post(
        "/api/economic-events/cluster-confirm",
        headers=headers,
        json={
            "clusters": [
                {
                    "title": cluster["title"],
                    "entry_ids": cluster["entry_ids"],
                }
            ]
        },
    )
    assert r2.status_code == 201

    # 3. 再次 suggest → 应为空（已聚类分录被排除）
    r3 = client.post("/api/economic-events/cluster-suggest", headers=headers, json={"min_entries": 2})
    assert r3.status_code == 200
    assert r3.json() == [], f"幂等失败：再次 suggest 不应返回候选，实际={r3.json()}"


def test_cluster_suggest_filters_by_import_job(client: TestClient):
    """按 import_job_id 过滤：只聚类指定导入批次的分录。"""
    headers, ledger_id = _create_ledger(client, _auth_headers(client))
    # 第一批导入：往来 A 2 条
    _seed_entries(
        ledger_id,
        entries=[
            {"voucher_date": date(2026, 7, 5), "counterparty_id": 1, "counterparty": "A", "debit_amount": "100.00"},
            {"voucher_date": date(2026, 7, 10), "counterparty_id": 1, "counterparty": "A", "debit_amount": "200.00"},
        ],
    )
    # 第二批导入：往来 B 2 条（用不同 import_job_id）
    with next(app.dependency_overrides[get_db]()) as db:
        ledger = db.get(Ledger, ledger_id)
        org = Organization(name=f"第二批企业-{uuid.uuid4().hex[:6]}")
        db.add(org)
        db.flush()
        ij2 = ImportJob(organization_id=org.id, ledger_id=ledger_id, status="completed")
        db.add(ij2)
        db.flush()
        for amt in ("400.00", "600.00"):
            db.add(AccountingEntry(
                organization_id=org.id,
                ledger_id=ledger_id,
                import_job_id=ij2.id,
                voucher_no=f"V-B-{amt}",
                voucher_date=date(2026, 7, 15),
                account_code="1002",
                account_name="银行存款",
                counterparty_id=2,
                counterparty="B",
                debit_amount=Decimal(amt),
                credit_amount=Decimal("0.00"),
                entry_source="manual",
            ))
        db.commit()
        ij2_id = ij2.id

    # 不带过滤：应返回 2 个候选（A + B）
    r_all = client.post("/api/economic-events/cluster-suggest", headers=headers, json={"min_entries": 2})
    assert r_all.status_code == 200
    assert len(r_all.json()) == 2

    # 过滤指定 import_job_id：只返回 B
    r_filter = client.post(
        "/api/economic-events/cluster-suggest",
        headers=headers,
        json={"import_job_id": ij2_id, "min_entries": 2},
    )
    assert r_filter.status_code == 200
    data = r_filter.json()
    assert len(data) == 1
    assert data[0]["counterparty_name"] == "B"
