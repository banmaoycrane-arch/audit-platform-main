"""往来单位 API 测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Counterparty
from app.db.session import Base


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()


def test_batch_update_counterparty_role(db):
    from app.api.routes_counterparties import batch_update_counterparty_role, CounterpartyBatchRoleUpdate

    cp1 = Counterparty(name="甲公司", role="other")
    cp2 = Counterparty(name="乙个人", role="other")
    db.add_all([cp1, cp2])
    db.commit()

    result = batch_update_counterparty_role(
        CounterpartyBatchRoleUpdate(ids=[cp1.id, cp2.id], role="customer"),
        db=db,
    )
    assert result["updated"] == 2
    assert result["role"] == "customer"
    db.refresh(cp1)
    db.refresh(cp2)
    assert cp1.role == "customer"
    assert cp2.role == "customer"


def test_batch_update_related_party_sets_flag(db):
    from app.api.routes_counterparties import batch_update_counterparty_role, CounterpartyBatchRoleUpdate

    cp = Counterparty(name="关联公司", role="other", is_related_party=False)
    db.add(cp)
    db.commit()

    batch_update_counterparty_role(
        CounterpartyBatchRoleUpdate(ids=[cp.id], role="related_party"),
        db=db,
    )
    db.refresh(cp)
    assert cp.role == "related_party"
    assert cp.is_related_party is True
