# -*- coding: utf-8 -*-
"""
Parser Evolution Loop — 生产机制

- 主信号：每次 ParseCorrection 自动入 draft 提案队列
- 标尺：nightly TOP3 回归（只测不退化，不自动激活规则）
- 人工：审批台批量采纳 → active 规则加载到解析引擎
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.models.parse_correction import ParseCorrection, ParsingRulePatch
from app.services.doc_parsing.file_parser_service import parse_entries
from app.services.doc_parsing.format_template import match_header, normalize_header
from app.services.doc_parsing.parser_engine.field_alias_catalog import get_field_aliases
from app.services.doc_parsing.parser_engine.rule_parsers import _parse_bank_statement_excel

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TOP3_ROOT = BACKEND_ROOT / "samples" / "top3"


def ensure_evolution_tables() -> None:
    """确保进化环依赖表存在（parse_correction / parsing_rule_patch）。"""
    from app.db.session import engine

    ParseCorrection.__table__.create(bind=engine, checkfirst=True)
    ParsingRulePatch.__table__.create(bind=engine, checkfirst=True)

CATEGORY_DOC_TYPE = {
    "journal": "accounting_entry",
    "invoice": "invoice",
    "bank": "bank_statement",
    "contract": "contract",
}

RULE_TYPE_COLUMN_HEADER = "column_header"
RULE_TYPE_PRODUCTION_FIELD = "production_field"
PROPOSAL_STATUS_DRAFT = "draft"
PROPOSAL_STATUS_ACTIVE = "active"
PROPOSAL_STATUS_REJECTED = "rejected"
SOURCE_PRODUCTION = "production_correction"
SOURCE_TOP3_SCAN = "parser_evolution_loop"


def get_active_column_header_aliases(db: Session, document_type: str) -> dict[str, str]:
    """
    返回 normalized_header -> target_field，供 journal/bank 解析加载。
    """
    try:
        patches = (
            db.query(ParsingRulePatch)
            .filter(
                ParsingRulePatch.document_type == document_type,
                ParsingRulePatch.rule_type == RULE_TYPE_COLUMN_HEADER,
                ParsingRulePatch.status == PROPOSAL_STATUS_ACTIVE,
            )
            .order_by(ParsingRulePatch.priority)
            .all()
        )
    except Exception as exc:
        logger.debug("column_header aliases unavailable: %s", exc)
        return {}
    aliases: dict[str, str] = {}
    for patch in patches:
        try:
            meta = json.loads(patch.rule_pattern)
        except json.JSONDecodeError:
            continue
        source = meta.get("source_header", "")
        target = meta.get("target_field") or patch.target_field
        if source and target:
            aliases[normalize_header(source)] = target
    return aliases


def _guess_target_field(document_type: str, header: str) -> str | None:
    """用内置别名表猜测未映射表头应对应的标准字段。"""
    matched = match_header(header)
    if matched:
        return matched
    norm = normalize_header(header)
    aliases = get_field_aliases(document_type)
    best_field: str | None = None
    best_len = 0
    for field_name, alias_list in aliases.items():
        for alias in alias_list:
            alias_norm = normalize_header(alias)
            if norm == alias_norm or alias_norm in norm or norm in alias_norm:
                if len(alias_norm) > best_len:
                    best_len = len(alias_norm)
                    best_field = field_name
    return best_field


def _proposal_exists(db: Session, document_type: str, source_header: str, target_field: str) -> bool:
    norm = normalize_header(source_header)
    existing = (
        db.query(ParsingRulePatch)
        .filter(
            ParsingRulePatch.document_type == document_type,
            ParsingRulePatch.rule_type == RULE_TYPE_COLUMN_HEADER,
            ParsingRulePatch.status.in_([PROPOSAL_STATUS_DRAFT, PROPOSAL_STATUS_ACTIVE]),
        )
        .all()
    )
    for patch in existing:
        try:
            meta = json.loads(patch.rule_pattern)
        except json.JSONDecodeError:
            continue
        if normalize_header(meta.get("source_header", "")) == norm and (
            meta.get("target_field") == target_field or patch.target_field == target_field
        ):
            return True
    return False


def _create_proposal(
    db: Session,
    *,
    document_type: str,
    source_header: str,
    target_field: str,
    evidence_file: str,
    category: str,
    run_id: str,
    shadow_note: str = "",
) -> ParsingRulePatch | None:
    if _proposal_exists(db, document_type, source_header, target_field):
        return None

    meta = {
        "source_header": source_header,
        "target_field": target_field,
        "category": category,
        "evidence_file": evidence_file,
        "run_id": run_id,
        "shadow_note": shadow_note,
        "proposed_at": datetime.now().isoformat(),
        "source": SOURCE_TOP3_SCAN,
    }
    rule_name = f"evo:{document_type}:{normalize_header(source_header)}:{target_field}"

    patch = ParsingRulePatch(
        rule_name=rule_name,
        document_type=document_type,
        rule_type=RULE_TYPE_COLUMN_HEADER,
        rule_pattern=json.dumps(meta, ensure_ascii=False),
        target_field=target_field,
        priority=45,
        confidence_boost=5,
        status=PROPOSAL_STATUS_DRAFT,
        source_correction_id=None,
    )
    db.add(patch)
    return patch


def _scan_journal_proposals(db: Session, folder: Path, run_id: str) -> list[ParsingRulePatch]:
    proposals: list[ParsingRulePatch] = []
    for path in sorted(folder.glob("*")):
        if path.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
            continue
        result = parse_entries(str(path), db=db)
        for header in result.unmatched_headers:
            target = _guess_target_field("accounting_entry", header)
            if not target:
                continue
            patch = _create_proposal(
                db,
                document_type="accounting_entry",
                source_header=header,
                target_field=target,
                evidence_file=path.name,
                category="journal",
                run_id=run_id,
                shadow_note=f"序时簿未映射表头；质量分 {result.quality_score:.1f}%",
            )
            if patch:
                proposals.append(patch)
    return proposals


def _scan_bank_proposals(db: Session, folder: Path, run_id: str) -> list[ParsingRulePatch]:
    proposals: list[ParsingRulePatch] = []
    active = get_active_column_header_aliases(db, "bank_statement")

    for path in sorted(folder.glob("*")):
        if path.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
            continue
        try:
            raw = pd.read_excel(path, header=None) if path.suffix.lower() != ".csv" else pd.read_csv(path, header=None)
        except Exception:
            continue
        headers = [str(c).strip() for c in raw.iloc[0].values if str(c).strip() and str(c) != "nan"]
        before = _parse_bank_statement_excel(str(path), header_aliases=active)
        before_count = (before or {}).get("transaction_count", 0)

        for header in headers:
            if normalize_header(header) in active:
                continue
            target = _guess_target_field("bank_statement", header)
            if not target:
                continue
            trial = dict(active)
            trial[normalize_header(header)] = target
            after = _parse_bank_statement_excel(str(path), header_aliases=trial)
            after_count = (after or {}).get("transaction_count", 0)
            if after_count <= before_count and before_count > 0:
                continue
            patch = _create_proposal(
                db,
                document_type="bank_statement",
                source_header=header,
                target_field=target,
                evidence_file=path.name,
                category="bank",
                run_id=run_id,
                shadow_note=f"影子试跑：交易行 {before_count}→{after_count}",
            )
            if patch:
                proposals.append(patch)
    return proposals


def _summarize_category(folder: Path, category: str) -> dict[str, Any]:
    files = [p for p in folder.glob("*") if p.is_file() and not p.name.startswith(".")]
    return {"category": category, "file_count": len(files)}


def run_evolution_cycle(
    db: Session,
    top3_root: Path | None = None,
) -> dict[str, Any]:
    """
    执行一轮进化：扫描 TOP3 → 生成 draft 规则提案（不自动激活）。
    """
    root = top3_root or DEFAULT_TOP3_ROOT
    ensure_evolution_tables()
    run_id = datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:8]
    all_proposals: list[ParsingRulePatch] = []

    journal_dir = root / "journal"
    bank_dir = root / "bank"
    if journal_dir.exists():
        all_proposals.extend(_scan_journal_proposals(db, journal_dir, run_id))
    if bank_dir.exists():
        all_proposals.extend(_scan_bank_proposals(db, bank_dir, run_id))

    db.commit()

    summary = {
        "run_id": run_id,
        "started_at": datetime.now().isoformat(),
        "top3_root": str(root),
        "categories": {
            "journal": _summarize_category(journal_dir, "journal") if journal_dir.exists() else None,
            "bank": _summarize_category(bank_dir, "bank") if bank_dir.exists() else None,
        },
        "new_proposals": len(all_proposals),
        "proposal_ids": [p.id for p in all_proposals if p.id],
    }

    out_dir = root / "evolution"
    out_dir.mkdir(parents=True, exist_ok=True)
    latest = out_dir / "latest_run.json"
    latest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Evolution run %s: %s new proposals", run_id, len(all_proposals))
    return summary


def _proposal_exists_for_correction(
    db: Session,
    correction_id: int,
    field: str,
) -> bool:
    return (
        db.query(ParsingRulePatch)
        .filter(
            ParsingRulePatch.source_correction_id == correction_id,
            ParsingRulePatch.target_field == field,
            ParsingRulePatch.status.in_([PROPOSAL_STATUS_DRAFT, PROPOSAL_STATUS_ACTIVE]),
        )
        .first()
        is not None
    )


def _create_production_field_proposal(
    db: Session,
    correction: ParseCorrection,
    field: str,
    original_val: Any,
    corrected_val: Any,
) -> ParsingRulePatch | None:
    if _proposal_exists_for_correction(db, correction.id, field):
        return None

    meta = {
        "source": SOURCE_PRODUCTION,
        "file_name": correction.file_name,
        "document_type": correction.document_type,
        "field": field,
        "original_value": original_val,
        "corrected_value": corrected_val,
        "correction_id": correction.id,
        "proposed_at": datetime.now().isoformat(),
        "shadow_note": f"生产改错：{field} → {corrected_val}",
    }
    rule_name = f"prod:{correction.document_type}:{field}:{correction.id}"

    patch = ParsingRulePatch(
        rule_name=rule_name,
        document_type=correction.document_type,
        rule_type=RULE_TYPE_PRODUCTION_FIELD,
        rule_pattern=json.dumps(meta, ensure_ascii=False),
        target_field=field,
        priority=30,
        confidence_boost=3,
        status=PROPOSAL_STATUS_DRAFT,
        source_correction_id=correction.id,
    )
    db.add(patch)
    return patch


def enqueue_proposals_from_correction(
    db: Session,
    correction: ParseCorrection,
    original_text: str = "",
) -> int:
    """
    生产机制主入口：ParseCorrection 创建后自动入提案队列（draft，待批量采纳）。

    1. extract_rules_from_correction → regex / mapping 提案
    2. 未能自动提取的 diff 字段 → production_field 兜底提案
    """
    ensure_evolution_tables()

    from app.services.doc_parsing.parser_engine.correction_loop_service import (
        extract_rules_from_correction,
    )

    existing = (
        db.query(ParsingRulePatch)
        .filter(ParsingRulePatch.source_correction_id == correction.id)
        .count()
    )
    if existing > 0:
        return existing

    patches = extract_rules_from_correction(db, correction.id, original_text=original_text)
    created = len(patches)
    extracted_fields = {p.target_field for p in patches}

    for field in correction.diff_fields or []:
        if field in extracted_fields:
            continue
        corrected_val = (correction.corrected_result or {}).get(field)
        if corrected_val is None or corrected_val == "":
            continue
        original_val = (correction.original_result or {}).get(field)
        fallback = _create_production_field_proposal(
            db, correction, field, original_val, corrected_val
        )
        if fallback:
            created += 1

    if created > 0:
        db.commit()
        db.refresh(correction)
        correction.rule_extracted = True
        correction.extracted_rule = {
            "patches_queued": created,
            "source": SOURCE_PRODUCTION,
        }
        correction.status = "analyzed"
        db.commit()
        logger.info(
            "Correction %s enqueued %s proposals (production)",
            correction.id,
            created,
        )

    return created


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _run_journal_regression(db: Session, folder: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*")):
        if not path.is_file() or path.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
            continue
        try:
            result = parse_entries(str(path), db=db)
            files.append(
                {
                    "file": path.name,
                    "quality_score": round(result.quality_score, 2),
                    "success_rows": result.success_rows,
                    "total_rows": result.total_rows,
                    "unmatched_headers": len(result.unmatched_headers or []),
                }
            )
        except Exception as exc:
            files.append({"file": path.name, "error": str(exc)})

    scores = [f["quality_score"] for f in files if "quality_score" in f]
    return {
        "file_count": len(files),
        "avg_quality": round(_avg(scores), 2),
        "min_quality": round(min(scores), 2) if scores else 0.0,
        "files": files,
    }


def _run_bank_regression(db: Session, folder: Path) -> dict[str, Any]:
    active = get_active_column_header_aliases(db, "bank_statement")
    files: list[dict[str, Any]] = []
    for path in sorted(folder.glob("*")):
        if not path.is_file() or path.suffix.lower() not in {".xlsx", ".xls", ".csv"}:
            continue
        try:
            parsed = _parse_bank_statement_excel(str(path), header_aliases=active)
            tx_count = (parsed or {}).get("transaction_count", 0)
            sample_cp = None
            txs = (parsed or {}).get("transactions") or []
            if txs:
                sample_cp = txs[0].get("counterparty_name") or txs[0].get("counterparty")
            files.append(
                {
                    "file": path.name,
                    "transaction_count": tx_count,
                    "has_counterparty_sample": bool(sample_cp),
                }
            )
        except Exception as exc:
            files.append({"file": path.name, "error": str(exc)})

    counts = [f["transaction_count"] for f in files if "transaction_count" in f]
    return {
        "file_count": len(files),
        "total_transactions": sum(counts),
        "files_with_rows": sum(1 for c in counts if c > 0),
        "files": files,
    }


def _run_folder_file_count(folder: Path, category: str) -> dict[str, Any]:
    if not folder.exists():
        return {"category": category, "file_count": 0, "note": "目录不存在"}
    files = [p.name for p in folder.glob("*") if p.is_file() and not p.name.startswith(".")]
    return {"category": category, "file_count": len(files), "files": files[:20]}


def _compute_regression_delta(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    prev_cats = previous.get("categories") or {}
    curr_cats = current.get("categories") or {}

    prev_j = prev_cats.get("journal") or {}
    curr_j = curr_cats.get("journal") or {}
    if "avg_quality" in prev_j and "avg_quality" in curr_j:
        delta["journal_avg_quality"] = round(
            curr_j["avg_quality"] - prev_j["avg_quality"], 2
        )

    prev_b = prev_cats.get("bank") or {}
    curr_b = curr_cats.get("bank") or {}
    if "files_with_rows" in prev_b and "files_with_rows" in curr_b:
        delta["bank_files_with_rows"] = curr_b["files_with_rows"] - prev_b["files_with_rows"]

    return delta


def run_nightly_top3_regression(
    db: Session,
    top3_root: Path | None = None,
) -> dict[str, Any]:
    """
    Nightly 标尺：重跑 TOP3 样本集，记录质量指标，**不**自动生成或激活规则。
    """
    root = top3_root or DEFAULT_TOP3_ROOT
    ensure_evolution_tables()
    run_id = datetime.now().strftime("%Y%m%d") + "-nightly-" + uuid.uuid4().hex[:6]

    categories: dict[str, Any] = {}
    journal_dir = root / "journal"
    bank_dir = root / "bank"
    invoice_dir = root / "invoice"
    contract_dir = root / "contract"

    if journal_dir.exists():
        categories["journal"] = _run_journal_regression(db, journal_dir)
    if bank_dir.exists():
        categories["bank"] = _run_bank_regression(db, bank_dir)
    if invoice_dir.exists():
        categories["invoice"] = _run_folder_file_count(invoice_dir, "invoice")
    if contract_dir.exists():
        categories["contract"] = _run_folder_file_count(contract_dir, "contract")

    summary: dict[str, Any] = {
        "run_id": run_id,
        "started_at": datetime.now().isoformat(),
        "type": "nightly_regression",
        "top3_root": str(root),
        "categories": categories,
        "note": "TOP3 回归标尺；不自动激活规则；主信号来自生产 ParseCorrection",
    }

    out_dir = root / "evolution"
    out_dir.mkdir(parents=True, exist_ok=True)
    prev_path = out_dir / "nightly_regression.json"
    if prev_path.exists():
        try:
            previous = json.loads(prev_path.read_text(encoding="utf-8"))
            summary["delta_vs_previous"] = _compute_regression_delta(previous, summary)
        except json.JSONDecodeError:
            pass

    prev_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    latest = out_dir / "latest_nightly.json"
    latest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info("Nightly TOP3 regression %s completed", run_id)
    return summary


def get_latest_nightly_summary(top3_root: Path | None = None) -> dict[str, Any] | None:
    root = top3_root or DEFAULT_TOP3_ROOT
    latest = root / "evolution" / "latest_nightly.json"
    if not latest.exists():
        return None
    return json.loads(latest.read_text(encoding="utf-8"))


def list_proposals(
    db: Session,
    status: str = PROPOSAL_STATUS_DRAFT,
    document_type: str | None = None,
    rule_type: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> list[ParsingRulePatch]:
    query = db.query(ParsingRulePatch).filter(ParsingRulePatch.status == status)
    if document_type:
        query = query.filter(ParsingRulePatch.document_type == document_type)
    if rule_type:
        query = query.filter(ParsingRulePatch.rule_type == rule_type)

    fetch_limit = limit * 3 if source else limit
    patches = (
        query.order_by(ParsingRulePatch.created_at.desc()).limit(fetch_limit).all()
    )

    if not source:
        return patches

    filtered: list[ParsingRulePatch] = []
    for patch in patches:
        meta: dict[str, Any] = {}
        try:
            meta = json.loads(patch.rule_pattern)
        except json.JSONDecodeError:
            pass
        meta_source = meta.get("source", "")
        if source == "production" and (
            patch.source_correction_id or meta_source == SOURCE_PRODUCTION
        ):
            filtered.append(patch)
        elif source == "top3" and meta_source == SOURCE_TOP3_SCAN:
            filtered.append(patch)
        if len(filtered) >= limit:
            break
    return filtered


def proposal_to_dict(patch: ParsingRulePatch) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    try:
        meta = json.loads(patch.rule_pattern)
    except json.JSONDecodeError:
        pass

    meta_source = meta.get("source")
    if patch.source_correction_id:
        display_source = meta_source or SOURCE_PRODUCTION
    elif meta_source == SOURCE_TOP3_SCAN:
        display_source = "top3_scan"
    else:
        display_source = meta_source

    return {
        "id": patch.id,
        "rule_name": patch.rule_name,
        "document_type": patch.document_type,
        "rule_type": patch.rule_type,
        "target_field": patch.target_field,
        "status": patch.status,
        "priority": patch.priority,
        "source": display_source,
        "source_correction_id": patch.source_correction_id,
        "source_header": meta.get("source_header"),
        "evidence_file": meta.get("evidence_file") or meta.get("file_name"),
        "file_name": meta.get("file_name") or meta.get("evidence_file"),
        "category": meta.get("category"),
        "shadow_note": meta.get("shadow_note"),
        "run_id": meta.get("run_id"),
        "original_value": meta.get("original_value"),
        "corrected_value": meta.get("corrected_value"),
        "created_at": patch.created_at.isoformat() if patch.created_at else None,
    }


def batch_approve_proposals(
    db: Session,
    patch_ids: list[int],
    approved_by: str = "",
) -> dict[str, Any]:
    approved = 0
    for pid in patch_ids:
        patch = db.query(ParsingRulePatch).filter(ParsingRulePatch.id == pid).first()
        if not patch or patch.status != PROPOSAL_STATUS_DRAFT:
            continue
        patch.status = PROPOSAL_STATUS_ACTIVE
        approved += 1
        logger.info("Evolution approved patch %s by %s", pid, approved_by)
    db.commit()
    return {"approved_count": approved, "requested": len(patch_ids)}


def batch_reject_proposals(
    db: Session,
    patch_ids: list[int],
    reason: str = "",
) -> dict[str, Any]:
    rejected = 0
    for pid in patch_ids:
        patch = db.query(ParsingRulePatch).filter(ParsingRulePatch.id == pid).first()
        if not patch or patch.status != PROPOSAL_STATUS_DRAFT:
            continue
        patch.status = PROPOSAL_STATUS_REJECTED
        try:
            meta = json.loads(patch.rule_pattern)
            meta["reject_reason"] = reason
            patch.rule_pattern = json.dumps(meta, ensure_ascii=False)
        except json.JSONDecodeError:
            pass
        rejected += 1
    db.commit()
    return {"rejected_count": rejected, "requested": len(patch_ids)}


def get_latest_run_summary(top3_root: Path | None = None) -> dict[str, Any] | None:
    root = top3_root or DEFAULT_TOP3_ROOT
    latest = root / "evolution" / "latest_run.json"
    if not latest.exists():
        return None
    return json.loads(latest.read_text(encoding="utf-8"))
