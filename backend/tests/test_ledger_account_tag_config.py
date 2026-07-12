"""账簿级解析映射覆盖测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config.account_tag_config import (
    AccountTagConfig,
    clear_ledger_account_tag_override,
    load_ledger_account_tag_override,
    merge_account_tag_configs,
    save_ledger_account_tag_override,
    _default_config,
)
from app.db.session import Base
from app.db.models import Ledger, Team
from app.models.scope_settings import LedgerSettings  # noqa: F401


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


def _seed_ledger(db) -> int:
    team = Team(name="测试团队")
    db.add(team)
    db.flush()
    ledger = Ledger(name="测试账簿", team_id=team.id)
    db.add(ledger)
    db.commit()
    return ledger.id


def test_merge_account_tag_configs_overlays_code_mapping():
    base = _default_config()
    merged = merge_account_tag_configs(
        base,
        {"account_code_tag_category": {"1002": "bank_account", "9999": "product"}},
    )
    assert merged.account_code_tag_category["1002"] == "bank_account"
    assert merged.account_code_tag_category["9999"] == "product"
    assert merged.account_code_tag_category["1122"] == base.account_code_tag_category["1122"]


def test_ledger_override_roundtrip(db):
    ledger_id = _seed_ledger(db)
    override = AccountTagConfig(
        version="ledger-1",
        mandatory_hierarchical_accounts=set(),
        mandatory_hierarchical_keywords=set(),
        account_code_tag_category={"1002": "bank_account", "9999": "product"},
        account_name_tag_category={},
        auxiliary_keywords={"department": ["财务部"]},
    )
    save_ledger_account_tag_override(db, ledger_id, override)
    loaded_override = load_ledger_account_tag_override(db, ledger_id)
    loaded = merge_account_tag_configs(_default_config(), loaded_override)
    assert loaded.account_code_tag_category["9999"] == "product"
    assert loaded.auxiliary_keywords["department"] == ["财务部"]
    assert clear_ledger_account_tag_override(db, ledger_id) is True
    after_clear = merge_account_tag_configs(
        _default_config(),
        load_ledger_account_tag_override(db, ledger_id),
    )
    assert "9999" not in after_clear.account_code_tag_category
