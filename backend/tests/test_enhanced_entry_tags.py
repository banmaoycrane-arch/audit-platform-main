# -*- coding: utf-8 -*-
"""
增强型 EntryTag / TagCategory 系统测试。

覆盖范围：
1. TagCategory 的 CRUD 与层级树
2. EntryTag 的创建、更新、删除、历史记录
3. TagMappingRule 的匹配逻辑
4. LegacyTagImport 兼容层 PoC
"""
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import Base
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user import User
from app.services.entry_tag_service import (
    aggregate_tags_by_category,
    create_entry_tag,
    delete_entry_tag,
    list_entry_tags,
    list_tag_history,
    update_entry_tag,
)
from app.services.ledger_management_service import create_ledger
from app.services.legacy_tag_import_service import (
    LegacyTagRecord,
    detect_legacy_tag_format,
    import_legacy_tags,
)
from app.services.tag_category_service import (
    build_category_tree,
    create_category,
    delete_category,
    get_category_by_code,
    update_category,
)
from app.services.tag_mapping_rule_service import apply_mapping_rules, create_mapping_rule


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def ledger(db):
    team = Team(name="tag_test_team", type="virtual")
    db.add(team)
    db.flush()

    user = User(username="tag_test_user", phone="13800000003", team_id=team.id)
    db.add(user)
    db.flush()

    ledger = create_ledger(
        db,
        team_id=team.id,
        name="tag_test_ledger",
        accounting_start_date=date(2026, 1, 1),
    )
    db.commit()
    return ledger


def test_create_category(db, ledger):
    category = create_category(
        db,
        ledger_id=ledger.id,
        code="counterparty",
        name="往来单位",
        value_type="entity",
        source_table="counterparties",
    )
    assert category.code == "counterparty"
    assert category.ledger_id == ledger.id
    assert category.level == 1

    found = get_category_by_code(db, ledger.id, "counterparty")
    assert found is not None
    assert found.name == "往来单位"


def test_category_tree(db, ledger):
    parent = create_category(db, ledger.id, "entity", "主体")
    child = create_category(
        db,
        ledger.id,
        "entity_legal",
        "法律主体",
        parent_id=parent.id,
    )

    tree = build_category_tree(db, ledger.id)
    assert len(tree) == 1
    assert tree[0]["code"] == "entity"
    assert len(tree[0]["children"]) == 1
    assert tree[0]["children"][0]["code"] == "entity_legal"
    assert tree[0]["children"][0]["level"] == 2


def test_delete_category_with_children_fails(db, ledger):
    parent = create_category(db, ledger.id, "parent", "父分类")
    create_category(db, ledger.id, "child", "子分类", parent_id=parent.id)

    with pytest.raises(ValueError):
        delete_category(db, parent.id)


def test_entry_tag_crud_and_history(db, ledger):
    category = create_category(db, ledger.id, "project", "项目")

    entry_tag = create_entry_tag(
        db,
        entry_id=1,
        ledger_id=ledger.id,
        category_code="project",
        tag_value="审计项目2026",
        weight=1.5,
    )
    assert entry_tag.category_id == category.id
    assert entry_tag.weight == 1.5
    assert entry_tag.display_name == "审计项目2026"

    history = list_tag_history(db, entry_tag_id=entry_tag.id)
    assert len(history) == 1
    assert history[0].change_type == "create"

    updated = update_entry_tag(
        db,
        entry_tag_id=entry_tag.id,
        tag_value="审计项目2026-修订",
        weight=2.0,
    )
    assert updated.tag_value == "审计项目2026-修订"
    assert updated.weight == 2.0
    assert updated.vector_pending is True

    history = list_tag_history(db, entry_tag_id=entry_tag.id)
    assert len(history) == 2
    assert history[0].change_type == "update"

    delete_entry_tag(db, entry_tag.id)
    assert list_entry_tags(db, entry_id=1) == []

    history = list_tag_history(db, entry_id=1)
    assert any(h.change_type == "delete" for h in history)


def test_aggregate_tags_by_category(db, ledger):
    create_category(db, ledger.id, "counterparty", "往来单位")
    create_entry_tag(db, entry_id=1, ledger_id=ledger.id, category_code="counterparty", tag_value="A公司")
    create_entry_tag(db, entry_id=2, ledger_id=ledger.id, category_code="counterparty", tag_value="A公司")
    create_entry_tag(db, entry_id=3, ledger_id=ledger.id, category_code="counterparty", tag_value="B公司")

    result = aggregate_tags_by_category(db, ledger.id, "counterparty")
    assert len(result) == 2
    a_company = next(r for r in result if r["tag_value"] == "A公司")
    assert a_company["count"] == 2


def test_mapping_rule_apply(db, ledger):
    create_category(db, ledger.id, "bank_account", "银行账户")
    create_mapping_rule(
        db,
        ledger_id=ledger.id,
        source_pattern="100201",
        source_type="account_code",
        target_category_code="bank_account",
        target_value="招商银行",
        priority=10,
    )

    results = apply_mapping_rules(
        db,
        ledger_id=ledger.id,
        source_type="account_code",
        source_values=["100201", "100202"],
        fallback_category_code="bank_account",
    )

    assert results[0]["matched"] is True
    assert results[0]["category_code"] == "bank_account"
    assert results[0]["target_value"] == "招商银行"

    assert results[1]["matched"] is True
    assert results[1]["fallback"] is True


def test_legacy_tag_import(db, ledger):
    create_category(db, ledger.id, "counterparty", "往来单位")
    create_category(db, ledger.id, "project", "项目")

    records = [
        LegacyTagRecord(entry_id=1, raw_tag="counterparty:山西岚县尚德鑫"),
        LegacyTagRecord(entry_id=1, raw_tag="project:审计项目2026"),
        LegacyTagRecord(entry_id=2, raw_tag="未知标签值"),
        LegacyTagRecord(entry_id=3, raw_tag="", weight=2.0),
    ]

    report = import_legacy_tags(
        db,
        ledger_id=ledger.id,
        records=records,
        auto_create_category=True,
        default_category_code="legacy",
    )

    assert report.total == 4
    assert report.success == 2
    assert report.warning == 1
    assert report.failed == 1

    success_item = next(i for i in report.items if i.raw_tag == "counterparty:山西岚县尚德鑫")
    assert success_item.category_code == "counterparty"
    assert success_item.tag_value == "山西岚县尚德鑫"


def test_detect_legacy_tag_format():
    assert detect_legacy_tag_format(["a:1", "b:2", "c"]) == "colon_separated"
    assert detect_legacy_tag_format(["a", "b", "c"]) == "free_text"
    assert detect_legacy_tag_format([]) == "unknown"
