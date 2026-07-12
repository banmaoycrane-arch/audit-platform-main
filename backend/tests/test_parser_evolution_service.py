# -*- coding: utf-8 -*-
"""Parser Evolution Loop 单元测试。"""

import json

import pytest

from app.db.session import SessionLocal
from app.models.parse_correction import ParseCorrection, ParsingRulePatch
from app.services.doc_parsing.parser_engine.correction_loop_service import (
    create_correction_record,
)
from app.services.doc_parsing.parser_engine.parser_evolution_service import (
    PROPOSAL_STATUS_ACTIVE,
    PROPOSAL_STATUS_DRAFT,
    RULE_TYPE_PRODUCTION_FIELD,
    batch_approve_proposals,
    enqueue_proposals_from_correction,
    ensure_evolution_tables,
    get_active_column_header_aliases,
    proposal_to_dict,
    run_nightly_top3_regression,
)


@pytest.fixture
def db():
    ensure_evolution_tables()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_get_active_column_header_aliases(db):
    patch = ParsingRulePatch(
        rule_name="evo:test",
        document_type="bank_statement",
        rule_type="column_header",
        rule_pattern=json.dumps(
            {"source_header": "对方单位", "target_field": "counterparty_name"},
            ensure_ascii=False,
        ),
        target_field="counterparty_name",
        status=PROPOSAL_STATUS_ACTIVE,
    )
    db.add(patch)
    db.commit()

    aliases = get_active_column_header_aliases(db, "bank_statement")
    assert aliases.get("对方单位") == "counterparty_name"


def test_batch_approve_proposals(db):
    patch = ParsingRulePatch(
        rule_name="evo:draft",
        document_type="accounting_entry",
        rule_type="column_header",
        rule_pattern=json.dumps({"source_header": "制单人", "target_field": "preparer"}),
        target_field="preparer",
        status=PROPOSAL_STATUS_DRAFT,
    )
    db.add(patch)
    db.commit()
    db.refresh(patch)

    result = batch_approve_proposals(db, [patch.id], approved_by="test")
    assert result["approved_count"] == 1

    db.refresh(patch)
    assert patch.status == PROPOSAL_STATUS_ACTIVE


def test_proposal_to_dict(db):
    patch = ParsingRulePatch(
        rule_name="evo:x",
        document_type="bank_statement",
        rule_type="column_header",
        rule_pattern=json.dumps(
            {
                "source_header": "对方户名",
                "target_field": "counterparty_name",
                "evidence_file": "test.xls",
            }
        ),
        target_field="counterparty_name",
        status=PROPOSAL_STATUS_DRAFT,
    )
    d = proposal_to_dict(patch)
    assert d["source_header"] == "对方户名"
    assert d["evidence_file"] == "test.xls"


def test_enqueue_proposals_from_correction_mapping(db):
    correction = create_correction_record(
        db=db,
        task_id="t1",
        document_type="bank_statement",
        file_name="test.xlsx",
        original_result={"counterparty_name": "旧名"},
        corrected_result={"counterparty_name": "新名"},
        corrected_by="tester",
    )
    queued = enqueue_proposals_from_correction(db, correction)
    assert queued >= 1

    patches = (
        db.query(ParsingRulePatch)
        .filter(ParsingRulePatch.source_correction_id == correction.id)
        .all()
    )
    assert len(patches) >= 1
    assert any(p.rule_type in ("mapping", RULE_TYPE_PRODUCTION_FIELD) for p in patches)


def test_enqueue_idempotent(db):
    correction = create_correction_record(
        db=db,
        task_id="t2",
        document_type="invoice",
        file_name="inv.pdf",
        original_result={"amount": "100"},
        corrected_result={"amount": "1000"},
        corrected_by="tester",
    )
    first = enqueue_proposals_from_correction(db, correction)
    second = enqueue_proposals_from_correction(db, correction)
    assert second == first


def test_nightly_regression_runs_without_samples(db, tmp_path):
    (tmp_path / "journal").mkdir()
    (tmp_path / "bank").mkdir()
    summary = run_nightly_top3_regression(db, top3_root=tmp_path)
    assert summary["type"] == "nightly_regression"
    assert "categories" in summary
    assert (tmp_path / "evolution" / "latest_nightly.json").exists()
