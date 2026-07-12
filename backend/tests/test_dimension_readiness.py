"""账簿维度就绪检查与向量 ledger 隔离。"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Ledger, Organization, Team
from app.db.session import Base
from app.services.accounting.entry_tag_vector_service import EntryTagVectorService
from app.services.doc_parsing.dimension_readiness_service import (
    acknowledge_tag_rules_reviewed,
    assess_ledger_dimension_readiness,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _seed_ledger(db) -> int:
    org = Organization(name="测试组织")
    db.add(org)
    db.flush()
    team = Team(name="测试团队")
    db.add(team)
    db.flush()
    ledger = Ledger(name="测试账簿", team_id=team.id)
    db.add(ledger)
    db.commit()
    return ledger.id


def test_readiness_blocks_until_tag_rules_acknowledged(db):
    ledger_id = _seed_ledger(db)
    assessment = assess_ledger_dimension_readiness(db, ledger_id)
    assert assessment["ready_for_structured_import"] is False
    assert any(item["code"] == "tag_rules_not_reviewed" for item in assessment["blockers"])

    acknowledge_tag_rules_reviewed(db, ledger_id, reviewed_by=1)
    db.commit()

    assessment = assess_ledger_dimension_readiness(db, ledger_id)
    assert assessment["ready_for_structured_import"] is True
    assert assessment["tag_rules_reviewed_at"]


def test_entry_tag_vector_search_requires_ledger_id(db):
    service = EntryTagVectorService(db)
    result = service.search("支付办公费", ledger_id=None)
    assert result["results"] == []
    assert "ledger_id" in (result.get("message") or "")
