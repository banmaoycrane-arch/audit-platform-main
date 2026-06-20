import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Transaction, TransactionOperation
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


def _seed_transaction(
    TestingSessionLocal,
    transaction_id: str,
    status: str = "pending",
    transaction_type: str = "import",
    context_type: str | None = None,
    context_id: int | None = None,
    operation_count: int = 0,
    succeeded_count: int = 0,
) -> int:
    db = TestingSessionLocal()
    try:
        tx = Transaction(
            transaction_id=transaction_id,
            transaction_type=transaction_type,
            context_type=context_type,
            context_id=context_id,
            status=status,
            operation_count=operation_count,
            succeeded_count=succeeded_count,
        )
        db.add(tx)
        db.commit()
        db.refresh(tx)
        return tx.id
    finally:
        db.close()


def _seed_operation(
    TestingSessionLocal,
    transaction_db_id: int,
    operation_order: int,
    operation_type: str = "create",
    entity_type: str = "accounting_entry",
    entity_id: int | None = None,
    status: str = "pending",
) -> int:
    db = TestingSessionLocal()
    try:
        op = TransactionOperation(
            transaction_id=transaction_db_id,
            operation_order=operation_order,
            operation_type=operation_type,
            entity_type=entity_type,
            entity_id=entity_id,
            operation_details={"foo": "bar"},
            status=status,
        )
        db.add(op)
        db.commit()
        db.refresh(op)
        return op.id
    finally:
        db.close()


def test_list_transactions_empty(client):
    test_client, _ = client
    resp = test_client.get("/api/transactions/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_transaction_404(client):
    test_client, _ = client
    resp = test_client.get("/api/transactions/9999")
    assert resp.status_code == 404


def test_create_via_manager_then_list_returns_one(client):
    test_client, TestingSessionLocal = client
    _seed_transaction(TestingSessionLocal, transaction_id="test-uuid-1", status="pending")

    resp = test_client.get("/api/transactions/")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "pending"
    assert items[0]["transaction_id"] == "test-uuid-1"


def test_get_transaction_detail_with_operations(client):
    test_client, TestingSessionLocal = client
    tx_id = _seed_transaction(
        TestingSessionLocal, transaction_id="test-uuid-2", status="pending", operation_count=2
    )
    _seed_operation(TestingSessionLocal, tx_id, operation_order=1)
    _seed_operation(TestingSessionLocal, tx_id, operation_order=2, operation_type="update")

    detail = test_client.get(f"/api/transactions/{tx_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == tx_id
    assert body["summary"]["operation_count"] == 2

    resp = test_client.get(f"/api/transactions/{tx_id}/operations")
    assert resp.status_code == 200
    ops = resp.json()
    assert len(ops) == 2
    assert ops[0]["operation_order"] == 1
    assert ops[1]["operation_order"] == 2


def test_operations_unknown_transaction_404(client):
    test_client, _ = client
    resp = test_client.get("/api/transactions/9999/operations")
    assert resp.status_code == 404


def test_manual_rollback_pending_transaction(client):
    test_client, TestingSessionLocal = client
    tx_id = _seed_transaction(TestingSessionLocal, transaction_id="test-uuid-3", status="pending")

    resp = test_client.post(f"/api/transactions/{tx_id}/rollback")
    assert resp.status_code == 200
    assert resp.json()["status"] == "rolled_back"

    detail = test_client.get(f"/api/transactions/{tx_id}").json()
    assert detail["status"] == "rolled_back"


def test_rollback_already_committed_returns_400(client):
    test_client, TestingSessionLocal = client
    tx_id = _seed_transaction(TestingSessionLocal, transaction_id="test-uuid-4", status="committed")

    resp = test_client.post(f"/api/transactions/{tx_id}/rollback")
    assert resp.status_code == 400
    assert "committed" in resp.json()["detail"]


def test_rollback_unknown_404(client):
    test_client, _ = client
    resp = test_client.post("/api/transactions/9999/rollback")
    assert resp.status_code == 404


def test_summary_returns_status_counts(client):
    test_client, TestingSessionLocal = client
    _seed_transaction(TestingSessionLocal, transaction_id="t-pending", status="pending")
    _seed_transaction(TestingSessionLocal, transaction_id="t-committed", status="committed")
    _seed_transaction(TestingSessionLocal, transaction_id="t-rolled", status="rolled_back")

    resp = test_client.get("/api/transactions/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "pending": 1,
        "committed": 1,
        "rolled_back": 1,
        "failed": 0,
        "total": 3,
    }


def test_summary_filter_by_context(client):
    test_client, TestingSessionLocal = client
    _seed_transaction(
        TestingSessionLocal,
        transaction_id="t-ctx-1",
        status="pending",
        context_type="import_job",
        context_id=10,
    )
    _seed_transaction(
        TestingSessionLocal,
        transaction_id="t-ctx-2",
        status="committed",
        context_type="import_job",
        context_id=20,
    )

    resp = test_client.get(
        "/api/transactions/summary",
        params={"context_type": "import_job", "context_id": 10},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["pending"] == 1
    assert body["committed"] == 0
