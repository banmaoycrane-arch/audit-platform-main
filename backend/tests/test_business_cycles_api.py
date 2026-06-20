"""业务循环 API 集成测试。

财务视角说明：业务循环（采购→入库→发票→付款 等）是审计中证据链完整性
的核心检查对象；这里通过 HTTP 接口验证服务能否：
  1. 创建/查询/更新业务循环
  2. 检测证据链断裂（如缺少入库单步骤）
  3. 在循环完成后给出后续风险延伸（如采购循环→付款循环）
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Organization
from app.db.session import Base, get_db
from app.main import app


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


def _seed_org(TestingSessionLocal, name: str = "测试公司") -> int:
    db = TestingSessionLocal()
    try:
        org = Organization(name=name, fiscal_year=2026)
        db.add(org)
        db.commit()
        db.refresh(org)
        return org.id
    finally:
        db.close()


def _create_cycle(test_client, organization_id: int, cycle_type: str = "purchase",
                  cycle_name: str = "2026-Q1 采购循环") -> dict:
    resp = test_client.post(
        "/api/business-cycles/",
        json={
            "organization_id": organization_id,
            "cycle_type": cycle_type,
            "cycle_name": cycle_name,
        },
    )
    assert resp.status_code == 200
    return resp.json()


def test_create_cycle_returns_201_or_200_with_id(client):
    test_client, TestingSessionLocal = client
    org_id = _seed_org(TestingSessionLocal)

    resp = test_client.post(
        "/api/business-cycles/",
        json={
            "organization_id": org_id,
            "cycle_type": "purchase",
            "cycle_name": "采购循环-001",
            "start_date": "2026-01-01",
        },
    )
    assert resp.status_code in (200, 201)
    body = resp.json()
    assert "id" in body and isinstance(body["id"], int)
    assert body["organization_id"] == org_id
    assert body["cycle_type"] == "purchase"
    assert body["status"] == "in_progress"


def test_list_cycles_filtered_by_org(client):
    test_client, TestingSessionLocal = client
    org_a = _seed_org(TestingSessionLocal, "公司A")
    org_b = _seed_org(TestingSessionLocal, "公司B")

    _create_cycle(test_client, org_a, "purchase", "A-采购")
    _create_cycle(test_client, org_a, "sales", "A-销售")
    _create_cycle(test_client, org_b, "purchase", "B-采购")

    # org_a 全部
    resp = test_client.get("/api/business-cycles/", params={"organization_id": org_a})
    assert resp.status_code == 200
    cycles = resp.json()
    assert len(cycles) == 2
    assert all(c["organization_id"] == org_a for c in cycles)

    # org_a 仅 purchase
    resp = test_client.get(
        "/api/business-cycles/",
        params={"organization_id": org_a, "cycle_type": "purchase"},
    )
    assert resp.status_code == 200
    cycles = resp.json()
    assert len(cycles) == 1
    assert cycles[0]["cycle_type"] == "purchase"


def test_get_cycle_with_steps_and_breaks(client):
    test_client, TestingSessionLocal = client
    org_id = _seed_org(TestingSessionLocal)
    cycle = _create_cycle(test_client, org_id)
    cycle_id = cycle["id"]

    # 添加步骤
    test_client.post(
        f"/api/business-cycles/{cycle_id}/steps",
        json={"step_order": 1, "step_type": "contract", "step_name": "采购合同"},
    )
    test_client.post(
        f"/api/business-cycles/{cycle_id}/steps",
        json={"step_order": 2, "step_type": "inventory", "step_name": "入库单"},
    )

    resp = test_client.get(f"/api/business-cycles/{cycle_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == cycle_id
    assert "steps" in body and len(body["steps"]) == 2
    assert "breaks" in body and body["breaks"] == []
    # steps 按 step_order 升序
    assert body["steps"][0]["step_order"] == 1
    assert body["steps"][1]["step_order"] == 2


def test_get_cycle_404(client):
    test_client, _ = client
    resp = test_client.get("/api/business-cycles/9999")
    assert resp.status_code == 404


def test_add_step_then_detect_break_for_missing_step(client):
    test_client, TestingSessionLocal = client
    org_id = _seed_org(TestingSessionLocal)
    cycle = _create_cycle(test_client, org_id)
    cycle_id = cycle["id"]

    # 添加 3 个步骤
    s1 = test_client.post(
        f"/api/business-cycles/{cycle_id}/steps",
        json={"step_order": 1, "step_type": "contract", "step_name": "采购合同"},
    ).json()
    s2 = test_client.post(
        f"/api/business-cycles/{cycle_id}/steps",
        json={"step_order": 2, "step_type": "inventory", "step_name": "入库单"},
    ).json()
    test_client.post(
        f"/api/business-cycles/{cycle_id}/steps",
        json={"step_order": 3, "step_type": "invoice", "step_name": "采购发票"},
    )

    # 标记 step1 完成、step2 缺失 — 应触发证据链断裂
    test_client.patch(
        f"/api/business-cycles/steps/{s1['id']}",
        json={"status": "completed", "actual_date": "2026-01-05"},
    )
    test_client.patch(
        f"/api/business-cycles/steps/{s2['id']}",
        json={"status": "missing"},
    )

    resp = test_client.post(
        "/api/business-cycles/detect-breaks",
        json={"cycle_id": cycle_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cycle_id"] == cycle_id
    assert len(body["breaks"]) >= 1
    # 至少存在一个 evidence_break，对应 step_order=2
    evidence_breaks = [b for b in body["breaks"] if b["break_type"] == "evidence_break"]
    assert len(evidence_breaks) >= 1
    assert any(b["break_point"] == 2 for b in evidence_breaks)

    # 持久化校验：再次 GET 详情应包含 breaks
    detail = test_client.get(f"/api/business-cycles/{cycle_id}").json()
    assert len(detail["breaks"]) == len(body["breaks"])


def test_get_risk_extension_for_completed_purchase_cycle(client):
    test_client, TestingSessionLocal = client
    org_id = _seed_org(TestingSessionLocal)
    cycle = _create_cycle(test_client, org_id, "purchase")
    cycle_id = cycle["id"]

    # 添加并完成步骤
    s = test_client.post(
        f"/api/business-cycles/{cycle_id}/steps",
        json={"step_order": 1, "step_type": "contract", "step_name": "采购合同"},
    ).json()
    test_client.patch(
        f"/api/business-cycles/steps/{s['id']}",
        json={"status": "completed", "actual_date": "2026-01-10"},
    )

    # 标记循环完成
    upd = test_client.patch(
        f"/api/business-cycles/{cycle_id}/status",
        json={"status": "completed"},
    )
    assert upd.status_code == 200

    resp = test_client.get(f"/api/business-cycles/{cycle_id}/risks")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("next_cycle") == "payment"
    assert "risk_factors" in body and len(body["risk_factors"]) > 0


def test_detect_breaks_returns_breaks_list(client):
    test_client, TestingSessionLocal = client
    org_id = _seed_org(TestingSessionLocal)
    cycle = _create_cycle(test_client, org_id)
    cycle_id = cycle["id"]

    # 无步骤的循环 — 检测应返回空列表
    resp = test_client.post(
        "/api/business-cycles/detect-breaks",
        json={"cycle_id": cycle_id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["cycle_id"] == cycle_id
    assert isinstance(body["breaks"], list)
    assert body["breaks"] == []

    # 不存在的循环 → 404
    resp_404 = test_client.post(
        "/api/business-cycles/detect-breaks",
        json={"cycle_id": 99999},
    )
    assert resp_404.status_code == 404
