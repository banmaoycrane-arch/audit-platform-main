"""结构化分录导入：preview → staging → confirm → 正式凭证。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ImportJob, StagingAccountingEntry


def _invalidate_staging_preview_cache(job_id: int) -> None:
    try:
        from app.services.audit.staging_preview_cache import invalidate_staging_preview_cache

        invalidate_staging_preview_cache(job_id)
    except Exception:
        pass
from app.services.audit.audit_day_book_service import (
    DayBookProcessingResult,
    _ensure_tag_categories,
    cancel_day_book_import,
    confirm_day_book_import,
    preview_day_book_import,
)
from app.services.audit.audit_snapshot_import_service import (
    cancel_snapshot_import,
    confirm_snapshot_import,
    preview_snapshot_import,
)
from app.services.audit.staging_review_service import (
    apply_voucher_review_status,
    assert_voucher_editable,
    compute_review_stats,
    group_staging_rows,
    query_staging_rows_by_group_key,
    rows_in_same_voucher,
    staging_rows_for_group_key,
    summarize_preview_vouchers,
    voucher_group_key,
    VERIFIED_REVIEW_STATUSES,
)
from app.services.audit.staging_voucher_query_service import (
    compute_review_stats_sql,
    paginate_preview_vouchers_sql,
)
from app.services.doc_parsing.import_routing_service import get_structured_kind


def _stamp_dimension_mapping_trace(
    tag: dict[str, Any],
    new_display_name: str,
    *,
    mapped_by_user_id: int | None = None,
) -> None:
    """写入维度映射痕迹：保留导入原名/改前名称，便于待处理队列还原对照。"""
    normalized = new_display_name.strip()
    if not normalized:
        return
    prior_display = str(tag.get("display_name") or tag.get("tag_value") or "").strip()
    tag_value = str(tag.get("tag_value") or "").strip()
    if not tag.get("original_display_name"):
        tag["original_display_name"] = prior_display or tag_value
    tag["display_name"] = normalized
    tag["name_standardized"] = True
    tag["mapped_at"] = datetime.now(timezone.utc).isoformat()
    if mapped_by_user_id is not None:
        tag["mapped_by_user_id"] = mapped_by_user_id


def preview_structured_import(db: Session, job: ImportJob) -> DayBookProcessingResult:
    kind = get_structured_kind(job.source_type)
    if kind == "entries":
        return preview_day_book_import(db, job)
    if kind in {"balances", "general_ledger", "general_ledger_summary"}:
        return preview_snapshot_import(db, job)
    return DayBookProcessingResult(
        success=False,
        error_message=f"暂不支持的结构化类型: {job.source_type}",
    )


def confirm_structured_import(
    db: Session,
    job: ImportJob,
    *,
    approved_by_user_id: int | None = None,
) -> DayBookProcessingResult:
    kind = get_structured_kind(job.source_type)
    if kind == "entries":
        return confirm_day_book_import(db, job, approved_by_user_id=approved_by_user_id)
    if kind in {"balances", "general_ledger", "general_ledger_summary"}:
        return confirm_snapshot_import(db, job)
    return DayBookProcessingResult(
        success=False,
        error_message=f"暂不支持的结构化类型: {job.source_type}",
    )


def cancel_structured_import(db: Session, job: ImportJob) -> None:
    kind = get_structured_kind(job.source_type)
    if kind == "entries":
        cancel_day_book_import(db, job)
        return
    if kind in {"balances", "general_ledger", "general_ledger_summary"}:
        cancel_snapshot_import(db, job)
        return
    job.status = "cancelled"
    db.commit()


def list_preview_entries(
    db: Session,
    job_id: int,
    *,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[StagingAccountingEntry], int, dict[str, Any]]:
    query = db.query(StagingAccountingEntry).filter(StagingAccountingEntry.import_job_id == job_id)
    total = query.count()
    all_rows = (
        query.order_by(
            StagingAccountingEntry.voucher_no,
            StagingAccountingEntry.entry_line_no,
        )
        .all()
    )
    review_stats = compute_review_stats(all_rows)
    rows = all_rows[offset : offset + limit]
    return rows, total, review_stats


def get_preview_voucher_review_stats(db: Session, job_id: int) -> dict[str, Any]:
    """凭证复核统计（维度 Tab 用，不返回凭证列表）。"""
    from app.services.audit.staging_preview_cache import (
        get_cached_review_stats,
        set_cached_review_stats,
    )

    cached = get_cached_review_stats(job_id)
    if cached is not None:
        return cached
    stats = compute_review_stats_sql(db, job_id)
    set_cached_review_stats(job_id, stats)
    return stats


def list_preview_vouchers(
    db: Session,
    job_id: int,
    *,
    review_filter: str = "all",
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    from app.services.audit.staging_preview_cache import (
        get_cached_voucher_page,
        set_cached_voucher_page,
    )
    from app.services.audit.staging_voucher_query_service import (
        _build_voucher_groups_subquery,
        _stats_from_groups_subquery,
    )

    cached_page = get_cached_voucher_page(
        job_id,
        review_filter=review_filter,
        search=search,
        limit=limit,
        offset=offset,
    )
    if cached_page is not None:
        return cached_page

    groups = _build_voucher_groups_subquery(db, job_id)
    review_stats = _stats_from_groups_subquery(db, job_id, groups)
    page_items, total = paginate_preview_vouchers_sql(
        db,
        job_id,
        review_filter=review_filter,
        search=search,
        limit=limit,
        offset=offset,
        groups=groups,
    )
    from app.services.audit.voucher_signature_service import enrich_voucher_summaries_with_signature_names

    enrich_voucher_summaries_with_signature_names(db, page_items)
    set_cached_voucher_page(
        job_id,
        review_filter=review_filter,
        search=search,
        limit=limit,
        offset=offset,
        page_items=page_items,
        total=total,
        review_stats=review_stats,
    )
    return page_items, total, review_stats


def get_preview_voucher_lines(
    db: Session,
    job_id: int,
    group_key: str,
) -> list[StagingAccountingEntry] | None:
    group = query_staging_rows_by_group_key(db, job_id, group_key)
    if not group:
        return None
    return group


def _sync_tag_updates_to_master(
    db: Session,
    row: StagingAccountingEntry,
    tag_updates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from app.services.audit.dimension_sync_service import sync_dimension_value_to_master

    if not row.ledger_id:
        return []
    tags = row.entry_tags_payload or []
    results: list[dict[str, Any]] = []
    for update in tag_updates:
        if not isinstance(update, dict):
            continue
        idx = update.get("tag_index")
        if idx is None or not (0 <= int(idx) < len(tags)):
            continue
        tag = tags[int(idx)]
        if not isinstance(tag, dict):
            continue
        results.append(
            sync_dimension_value_to_master(
                db,
                row.ledger_id,
                category_code=str(tag.get("category_code") or ""),
                display_name=str(tag.get("display_name") or update.get("display_name") or ""),
                tag_value=str(tag.get("tag_value") or ""),
                source_sub_code=tag.get("source_sub_code"),
                account_code=row.resolved_account_code or row.account_code,
            )
        )
    return results


def update_preview_entry(
    db: Session,
    job_id: int,
    staging_id: int,
    patch: dict[str, Any],
    *,
    reviewed_by_user_id: int | None = None,
) -> tuple[StagingAccountingEntry | None, list[dict[str, Any]]]:
    row = (
        db.query(StagingAccountingEntry)
        .filter(
            StagingAccountingEntry.import_job_id == job_id,
            StagingAccountingEntry.id == staging_id,
        )
        .first()
    )
    if not row:
        return None, []

    if "review_status" in patch and patch["review_status"] is not None:
        apply_voucher_review_status(
            db,
            row,
            str(patch["review_status"]),
            reviewed_by_user_id=reviewed_by_user_id,
        )
        db.commit()
        _invalidate_staging_preview_cache(row.import_job_id)
        db.refresh(row)
        return row, []

    if patch.get("tag_updates"):
        _apply_staging_tag_updates(row, patch["tag_updates"])
        master_sync_results: list[dict[str, Any]] = []
        if patch.get("sync_to_master"):
            master_sync_results = _sync_tag_updates_to_master(db, row, patch["tag_updates"])
        _resolve_matching_control_findings(db, row.import_job_id, row.entry_tags_payload or [])
        db.commit()
        db.refresh(row)
        return row, master_sync_results

    editable_fields = {
        "summary",
        "account_code",
        "account_name",
        "debit_amount",
        "credit_amount",
        "counterparty",
    }
    if editable_fields.intersection(patch.keys()):
        assert_voucher_editable(rows_in_same_voucher(db, row))

    allowed = editable_fields
    for key, value in patch.items():
        if key not in allowed:
            continue
        if key in {"debit_amount", "credit_amount"} and value is not None:
            value = Decimal(str(value))
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row, []


def _apply_staging_tag_updates(row: StagingAccountingEntry, tag_updates: list[dict[str, Any]]) -> None:
    tags = [dict(tag) for tag in (row.entry_tags_payload or []) if isinstance(tag, dict)]
    if not tags:
        return
    for update in tag_updates:
        if not isinstance(update, dict):
            continue
        idx = update.get("tag_index")
        display_name = str(update.get("display_name") or "").strip()
        if idx is None or not display_name:
            continue
        if not (0 <= int(idx) < len(tags)):
            continue
        if update.get("name_standardized") is True or display_name != str(tags[int(idx)].get("tag_value") or ""):
            _stamp_dimension_mapping_trace(tags[int(idx)], display_name)
        else:
            tags[int(idx)]["display_name"] = display_name
    row.entry_tags_payload = tags


def _resolve_matching_control_findings(
    db: Session,
    job_id: int,
    tags: list[dict[str, Any]],
) -> int:
    from app.db.models import AuditFinding

    resolved = 0
    for tag in tags:
        if not isinstance(tag, dict) or not tag.get("name_standardized"):
            continue
        sub = str(tag.get("source_sub_code") or "")
        display = str(tag.get("display_name") or "")
        if not sub or not display:
            continue
        findings = (
            db.query(AuditFinding)
            .filter(
                AuditFinding.job_id == job_id,
                AuditFinding.finding_type == "internal_control",
                AuditFinding.status == "pending",
            )
            .all()
        )
        for finding in findings:
            meta = finding.finding_metadata or {}
            if meta.get("source_sub_code") == sub and meta.get("control_defect") == "bank_name_not_standardized":
                finding.status = "resolved"
                finding.audit_conclusion = f"已补全规范户名：{display}"
                finding.updated_at = datetime.utcnow()
                resolved += 1
    return resolved


def bulk_update_dimension_display_name(
    db: Session,
    job_id: int,
    *,
    account_code: str,
    category_code: str,
    tag_value: str,
    display_name: str,
    source_sub_code: str | None = None,
    name_standardized: bool = True,
    sync_to_master: bool = False,
    mapped_by_user_id: int | None = None,
) -> dict[str, Any]:
    """批量更新本 job 下匹配维度的 Tag display_name（Step4 注册表行编辑）。"""
    from app.db.models import AuditFinding

    normalized_display = display_name.strip()
    if not normalized_display:
        raise ValueError("规范全称不能为空")

    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    updated_lines = 0
    for row in rows:
        base_code = row.resolved_account_code or row.account_code or ""
        if base_code != account_code:
            continue
        tags = [dict(tag) for tag in (row.entry_tags_payload or []) if isinstance(tag, dict)]
        changed = False
        for tag in tags:
            if str(tag.get("category_code") or "") != category_code:
                continue
            if str(tag.get("tag_value") or "") != tag_value:
                continue
            tag_sub = str(tag.get("source_sub_code") or "")
            if source_sub_code and tag_sub != source_sub_code:
                continue
            if name_standardized or normalized_display != str(tag.get("tag_value") or ""):
                _stamp_dimension_mapping_trace(
                    tag,
                    normalized_display,
                    mapped_by_user_id=mapped_by_user_id,
                )
            else:
                tag["display_name"] = normalized_display
            changed = True
        if changed:
            row.entry_tags_payload = tags
            updated_lines += 1

    resolved_findings = 0
    if name_standardized and source_sub_code:
        findings = (
            db.query(AuditFinding)
            .filter(
                AuditFinding.job_id == job_id,
                AuditFinding.finding_type == "internal_control",
                AuditFinding.status == "pending",
            )
            .all()
        )
        for finding in findings:
            meta = finding.finding_metadata or {}
            if meta.get("source_sub_code") == source_sub_code and meta.get("control_defect") == "bank_name_not_standardized":
                finding.status = "resolved"
                finding.audit_conclusion = f"已补全规范户名：{normalized_display}"
                finding.updated_at = datetime.utcnow()
                resolved_findings += 1

    db.commit()

    master_sync: dict[str, Any] | None = None
    if sync_to_master:
        job = db.get(ImportJob, job_id)
        from app.services.audit.dimension_sync_service import sync_dimension_value_to_master

        master_sync = sync_dimension_value_to_master(
            db,
            job.ledger_id if job else None,
            category_code=category_code,
            display_name=normalized_display,
            tag_value=tag_value,
            source_sub_code=source_sub_code,
            account_code=account_code,
        )

    return {
        "updated_lines": updated_lines,
        "resolved_findings": resolved_findings,
        "display_name": normalized_display,
        "master_sync": master_sync,
    }


def batch_update_preview_review(
    db: Session,
    job_id: int,
    entry_ids: list[int],
    review_status: str,
    *,
    reviewed_by_user_id: int | None = None,
) -> dict[str, Any]:
    if not entry_ids:
        return {"updated_vouchers": 0, "updated_lines": 0}

    anchors = (
        db.query(StagingAccountingEntry)
        .filter(
            StagingAccountingEntry.import_job_id == job_id,
            StagingAccountingEntry.id.in_(entry_ids),
        )
        .all()
    )
    seen_keys: set[str] = set()
    updated_lines = 0
    for anchor in anchors:
        key = voucher_group_key(anchor)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        group_rows = apply_voucher_review_status(
            db, anchor, review_status, reviewed_by_user_id=reviewed_by_user_id
        )
        updated_lines += len(group_rows)

    db.commit()
    _invalidate_staging_preview_cache(job_id)
    return {"updated_vouchers": len(seen_keys), "updated_lines": updated_lines}


def review_all_preview_entries(
    db: Session,
    job_id: int,
    review_status: str,
    *,
    reviewed_by_user_id: int | None = None,
) -> dict[str, Any]:
    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    groups = group_staging_rows(rows)
    now = datetime.now(timezone.utc)
    for group in groups.values():
        for row in group:
            row.review_status = review_status
            if review_status in VERIFIED_REVIEW_STATUSES and reviewed_by_user_id is not None:
                row.cross_reviewed_by_user_id = reviewed_by_user_id
                row.cross_reviewed_at = now
            elif review_status == "draft":
                row.cross_reviewed_by_user_id = None
                row.cross_reviewed_at = None
    db.commit()
    _invalidate_staging_preview_cache(job_id)
    return {
        "updated_vouchers": len(groups),
        "updated_lines": len(rows),
    }


def apply_compliance_spot_check(
    db: Session,
    job_id: int,
    amount_threshold: Decimal,
) -> dict[str, Any]:
    from app.services.audit.staging_review_service import group_staging_rows, voucher_group_key

    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    for row in rows:
        row.spot_check_flag = False

    flagged_group_keys: set[str] = set()
    flagged_vouchers: set[str] = set()
    for row in rows:
        amount = max(row.debit_amount or Decimal("0"), row.credit_amount or Decimal("0"))
        if amount >= amount_threshold:
            row.spot_check_flag = True
            flagged_group_keys.add(voucher_group_key(row))
            if row.voucher_no:
                flagged_vouchers.add(row.voucher_no)
    db.commit()
    return {
        "flagged_count": sum(1 for row in rows if row.spot_check_flag),
        "flagged_voucher_nos": sorted(flagged_vouchers),
        "flagged_group_keys": sorted(flagged_group_keys),
    }


def apply_compliance_random_sample(
    db: Session,
    job_id: int,
    *,
    sample_rate: float | None = None,
    sample_count: int | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """按凭证组随机抽样，标记 spot_check_flag 供后续合规审查。"""
    import random

    from app.services.audit.staging_review_service import group_staging_rows, voucher_group_key

    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    for row in rows:
        row.spot_check_flag = False

    groups = group_staging_rows(rows)
    group_keys = list(groups.keys())
    if not group_keys:
        db.commit()
        return {"flagged_count": 0, "flagged_voucher_nos": [], "flagged_group_keys": [], "sampled_vouchers": 0}

    if sample_count is not None and sample_count > 0:
        pick_count = min(sample_count, len(group_keys))
    elif sample_rate is not None and sample_rate > 0:
        pick_count = max(1, min(len(group_keys), int(len(group_keys) * sample_rate)))
    else:
        pick_count = max(1, min(len(group_keys), int(len(group_keys) * 0.1)))

    rng = random.Random(seed)
    selected_keys = rng.sample(group_keys, pick_count)
    flagged_vouchers: set[str] = set()
    for key in selected_keys:
        for row in groups[key]:
            row.spot_check_flag = True
            if row.voucher_no:
                flagged_vouchers.add(row.voucher_no)
    db.commit()
    return {
        "flagged_count": sum(1 for row in rows if row.spot_check_flag),
        "flagged_voucher_nos": sorted(flagged_vouchers),
        "flagged_group_keys": sorted(selected_keys),
        "sampled_vouchers": len(selected_keys),
    }


def build_staging_dimension_registry(db: Session, job_id: int) -> dict[str, Any]:
    """汇总 staging 中的维度实例（S2：一级科目 + source_sub_code + Tag），并做完整性提示。"""
    from app.db.models import ChartOfAccounts
    from app.services.doc_parsing.name_standardization_service import resolve_name_standardized

    job = db.get(ImportJob, job_id)
    if not job:
        raise ValueError("导入任务不存在")

    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    ledger_id = job.ledger_id

    registry: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        base_code = row.resolved_account_code or row.account_code or ""
        base_name = row.resolved_account_name or row.account_name or ""
        tags = row.entry_tags_payload or []
        if not tags and row.account_code and row.resolved_account_code and row.account_code != row.resolved_account_code:
            from app.config.account_tag_config import load_account_tag_config

            config = load_account_tag_config(db, ledger_id=ledger_id)
            base_root = (base_code or "").strip().split(".")[0]
            fallback_category = config.account_code_tag_category.get(base_root)
            if not fallback_category and base_root in {"1001", "1002"}:
                fallback_category = "bank_account"
            if fallback_category and fallback_category != "unknown":
                tags = [
                    {
                        "category_code": fallback_category,
                        "tag_value": row.account_name or "",
                        "display_name": row.account_name or "",
                    }
                ]
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            category = str(tag.get("category_code") or "unknown")
            tag_value = str(tag.get("tag_value") or "")
            display_name = str(tag.get("display_name") or tag_value)
            source_sub_code = str(tag.get("source_sub_code") or "")
            key = (base_code, category, source_sub_code, tag_value)
            if key not in registry:
                registry[key] = {
                    "account_code": base_code,
                    "account_name": base_name,
                    "category_code": category,
                    "source_sub_code": source_sub_code or None,
                    "tag_value": tag_value,
                    "display_name": display_name,
                    "name_standardized": resolve_name_standardized(
                        db,
                        ledger_id,
                        {
                            "category_code": category,
                            "tag_value": tag_value,
                            "display_name": display_name,
                            "source_sub_code": source_sub_code or None,
                            "name_standardized": tag.get("name_standardized"),
                        },
                        account_code=base_code,
                    ),
                    "line_count": 0,
                    "voucher_count": set(),
                }
            registry[key]["line_count"] += 1
            if row.voucher_no:
                registry[key]["voucher_count"].add(voucher_group_key(row))
            if tag.get("original_display_name"):
                registry[key]["original_display_name"] = str(tag.get("original_display_name"))
            if tag.get("mapped_at"):
                registry[key]["mapped_at"] = str(tag.get("mapped_at"))
            if tag.get("mapped_by_user_id") is not None:
                registry[key]["mapped_by_user_id"] = tag.get("mapped_by_user_id")

    items: list[dict[str, Any]] = []
    for item in registry.values():
        item["voucher_count"] = len(item["voucher_count"])
        items.append(item)
    items.sort(key=lambda x: (x["account_code"], x["source_sub_code"] or "", x["tag_value"]))

    coa_children: dict[str, list[str]] = {}
    if ledger_id:
        accounts = (
            db.query(ChartOfAccounts)
            .filter(ChartOfAccounts.ledger_id == ledger_id)
            .order_by(ChartOfAccounts.code)
            .all()
        )
        for account in accounts:
            parent = account.parent_code or (account.code[:4] if len(account.code or "") > 4 else None)
            if parent and parent != account.code:
                coa_children.setdefault(parent, []).append(account.code)

    warnings: list[dict[str, Any]] = []
    by_account: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        by_account.setdefault(item["account_code"], []).append(item)

    for account_code, dims in by_account.items():
        used_sub_codes = {d["source_sub_code"] for d in dims if d.get("source_sub_code")}
        coa_subs = set()
        for code in coa_children.get(account_code, []):
            if code.startswith(account_code) and len(code) > len(account_code):
                tail = code[len(account_code):].lstrip(".")
                if tail:
                    coa_subs.add(tail.split(".")[0] if "." in tail else tail)

        if coa_subs and used_sub_codes and coa_subs - used_sub_codes:
            warnings.append(
                {
                    "severity": "warning",
                    "code": "coa_unused_sub_accounts",
                    "account_code": account_code,
                    "message": f"科目 {account_code}：科目表里有 {len(coa_subs)} 个下级户，但这批序时簿只用了其中 {len(used_sub_codes)} 个，请核对是否漏导或科目表有多余户。",
                    "coa_sub_codes": sorted(coa_subs),
                    "used_sub_codes": sorted(used_sub_codes),
                    "missing_in_import": sorted(coa_subs - used_sub_codes),
                }
            )

        non_standard = [d for d in dims if not d.get("name_standardized")]
        if non_standard and account_code in {"1001", "1002"}:
            warnings.append(
                {
                    "severity": "info",
                    "code": "bank_name_not_standardized",
                    "account_code": account_code,
                    "message": f"银行存款还有 {len(non_standard)} 个户名是简称（不是开户时的规范全称）；若直接入账，系统会记一条内控提醒，建议先在维度主数据里补全。",
                    "items": [
                        {
                            "source_sub_code": d.get("source_sub_code"),
                            "display_name": d.get("display_name"),
                            "tag_value": d.get("tag_value"),
                        }
                        for d in non_standard
                    ],
                }
            )

    return {
        "job_id": job_id,
        "ledger_id": ledger_id,
        "dimension_count": len(items),
        "items": items,
        "warnings": warnings,
        "blocking": False,
        "layers": _build_dimension_layers(db, ledger_id, items, coa_children),
        "comparison": _build_dimension_comparison(db, ledger_id, items, coa_children),
    }


def _build_dimension_layers(
    db: Session,
    ledger_id: int | None,
    items: list[dict[str, Any]],
    coa_children: dict[str, list[str]],
) -> dict[str, Any]:
    from app.db.models import BankAccount

    bank_evidence: list[dict[str, Any]] = []
    if ledger_id:
        accounts = (
            db.query(BankAccount)
            .filter(BankAccount.ledger_id == ledger_id, BankAccount.is_active.is_(True))
            .order_by(BankAccount.source_sub_code, BankAccount.id)
            .all()
        )
        bank_evidence = [
            {
                "bank_name": account.bank_name,
                "account_no": account.account_no,
                "account_name": account.account_name,
                "coa_account_code": account.coa_account_code,
                "source_sub_code": account.source_sub_code,
            }
            for account in accounts
        ]

    coa_defined: list[dict[str, Any]] = []
    for parent_code, children in sorted(coa_children.items()):
        for child_code in children:
            coa_defined.append({"parent_code": parent_code, "account_code": child_code})

    return {
        "config_coa": coa_defined,
        "config_bank_evidence": bank_evidence,
        "import_used": items,
    }


def _normalize_bank_label(value: str) -> str:
    return value.replace("银行", "").replace("存款", "").strip().lower()


def _build_dimension_comparison(
    db: Session,
    ledger_id: int | None,
    items: list[dict[str, Any]],
    coa_children: dict[str, list[str]],
) -> dict[str, Any]:
    from app.db.models import BankAccount

    bank_items = [item for item in items if item.get("account_code") in {"1001", "1002"}]
    evidence_rows: list[BankAccount] = []
    if ledger_id:
        evidence_rows = (
            db.query(BankAccount)
            .filter(BankAccount.ledger_id == ledger_id, BankAccount.is_active.is_(True))
            .all()
        )

    evidence_by_sub: dict[str, BankAccount] = {}
    evidence_by_name: dict[str, BankAccount] = {}
    for row in evidence_rows:
        if row.source_sub_code:
            evidence_by_sub[row.source_sub_code] = row
        evidence_by_name[_normalize_bank_label(row.bank_name)] = row

    in_import_not_in_evidence: list[dict[str, Any]] = []
    matched: list[dict[str, Any]] = []
    for item in bank_items:
        sub = item.get("source_sub_code") or ""
        label = _normalize_bank_label(str(item.get("display_name") or item.get("tag_value") or ""))
        evidence = evidence_by_sub.get(sub) if sub else None
        if evidence is None and label:
            evidence = evidence_by_name.get(label)
        if evidence:
            matched.append({**item, "evidence_bank_name": evidence.bank_name, "evidence_account_no": evidence.account_no})
        else:
            in_import_not_in_evidence.append(item)

    used_subs = {item.get("source_sub_code") for item in bank_items if item.get("source_sub_code")}
    in_evidence_not_in_import: list[dict[str, Any]] = []
    for row in evidence_rows:
        if row.source_sub_code and row.source_sub_code not in used_subs:
            in_evidence_not_in_import.append(
                {
                    "source_sub_code": row.source_sub_code,
                    "bank_name": row.bank_name,
                    "account_no": row.account_no,
                }
            )

    coa_subs_by_parent: dict[str, set[str]] = {}
    for parent_code, children in coa_children.items():
        subs: set[str] = set()
        for code in children:
            if code.startswith(parent_code) and len(code) > len(parent_code):
                tail = code[len(parent_code):].lstrip(".")
                if tail:
                    subs.add(tail.split(".")[0])
        if subs:
            coa_subs_by_parent[parent_code] = subs

    coa_gaps: list[dict[str, Any]] = []
    for account_code, dims in _group_items_by_account(bank_items).items():
        used = {d.get("source_sub_code") for d in dims if d.get("source_sub_code")}
        defined = coa_subs_by_parent.get(account_code, set())
        if defined and used and defined - used:
            coa_gaps.append(
                {
                    "account_code": account_code,
                    "missing_in_import": sorted(defined - used),
                    "defined_sub_codes": sorted(defined),
                    "used_sub_codes": sorted(used),
                }
            )

    return {
        "matched": matched,
        "in_import_not_in_evidence": in_import_not_in_evidence,
        "in_evidence_not_in_import": in_evidence_not_in_import,
        "coa_gaps": coa_gaps,
    }


def _group_items_by_account(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        grouped.setdefault(str(item.get("account_code") or ""), []).append(item)
    return grouped


def create_bank_name_control_findings(db: Session, job: ImportJob, rows: list[StagingAccountingEntry]) -> int:
    """确认入账后：银行户名为简称时写入内控提示（AuditFinding）。"""
    import uuid

    from app.db.models import AuditFinding

    created = 0
    seen: set[tuple[str, str]] = set()
    for row in rows:
        base_code = row.resolved_account_code or row.account_code or ""
        if base_code not in {"1001", "1002"}:
            continue
        for tag in row.entry_tags_payload or []:
            if not isinstance(tag, dict):
                continue
            if tag.get("name_standardized"):
                continue
            sub = str(tag.get("source_sub_code") or "")
            display = str(tag.get("display_name") or tag.get("tag_value") or "")
            key = (sub, display)
            if not display or key in seen:
                continue
            seen.add(key)
            finding = AuditFinding(
                job_id=job.id,
                ledger_id=job.ledger_id,
                finding_uuid=str(uuid.uuid4()),
                finding_type="internal_control",
                severity="info",
                business_type="bank_account",
                finding_title=f"银行户名未规范：{sub or '-'} · {display}",
                finding_description=(
                    f"序时簿导入分录中银行存款维度仍使用简称「{display}」。"
                    f"建议在账簿维度管理中对照开户清单补全规范全称，并更新 display_name。"
                ),
                audit_procedure="核对银行开户清单/询证函，确认户名全称与科目明细一致。",
                audit_conclusion="待补充规范户名后关闭。",
                risk_statement="户名不规范可能导致银行账户识别错误，影响货币资金审计完整性。",
                recommendation="在「账簿维度管理」中维护开户清单，并将 Tag display_name 更新为银行全称。",
                related_entries=[{"staging_entry_id": row.id, "voucher_no": row.voucher_no}],
                finding_metadata={
                    "source_sub_code": sub or None,
                    "display_name": display,
                    "tag_value": str(tag.get("tag_value") or display),
                    "account_code": base_code,
                    "category_code": str(tag.get("category_code") or "bank_account"),
                    "control_defect": "bank_name_not_standardized",
                },
                status="pending",
            )
            db.add(finding)
            created += 1
    if created:
        db.flush()
    return created


def build_dimension_pending_queue(db: Session, job_id: int) -> dict[str, Any]:
    """汇总本批导入待处理的维度问题：简称、主数据缺口、待 LLM、未知分类、内控提醒。"""
    from app.db.models import AuditFinding, TagCategory
    from app.services.doc_parsing.name_standardization_service import name_standardization_queue_message

    registry = build_staging_dimension_registry(db, job_id)
    job = db.get(ImportJob, job_id)
    ledger_id = job.ledger_id if job else None

    known_categories: set[str] = set()
    if ledger_id:
        used_codes = {
            str(item.get("category_code"))
            for item in registry.get("items", [])
            if item.get("category_code") and item.get("category_code") != "unknown"
        }
        if used_codes:
            _ensure_tag_categories(db, ledger_id, used_codes)
            db.flush()
        categories = (
            db.query(TagCategory)
            .filter(TagCategory.ledger_id == ledger_id, TagCategory.status == "active")
            .all()
        )
        known_categories = {cat.code for cat in categories}

    items: list[dict[str, Any]] = []

    for reg_item in registry.get("items", []):
        if not reg_item.get("name_standardized"):
            items.append(
                {
                    "queue_type": "non_standardized",
                    "priority": "medium",
                    "account_code": reg_item.get("account_code"),
                    "account_name": reg_item.get("account_name"),
                    "category_code": reg_item.get("category_code"),
                    "source_sub_code": reg_item.get("source_sub_code"),
                    "tag_value": reg_item.get("tag_value"),
                    "display_name": reg_item.get("display_name"),
                    "line_count": reg_item.get("line_count", 0),
                    "voucher_count": reg_item.get("voucher_count", 0),
                    "message": name_standardization_queue_message(
                        str(reg_item.get("display_name") or reg_item.get("tag_value") or ""),
                        category_code=str(reg_item.get("category_code") or "") or None,
                        account_code=str(reg_item.get("account_code") or "") or None,
                    ),
                }
            )
        category_code = str(reg_item.get("category_code") or "")
        if category_code and category_code not in known_categories and category_code != "unknown":
            items.append(
                {
                    "queue_type": "unknown_category",
                    "priority": "high",
                    "account_code": reg_item.get("account_code"),
                    "category_code": category_code,
                    "source_sub_code": reg_item.get("source_sub_code"),
                    "tag_value": reg_item.get("tag_value"),
                    "display_name": reg_item.get("display_name"),
                    "line_count": reg_item.get("line_count", 0),
                    "message": f"维度分类「{category_code}」还没在这本账里登记，请先去「维度分类」新建",
                }
            )

    mapped_keys: set[tuple[str, str, str, str]] = set()
    for reg_item in registry.get("items", []):
        tag_value = str(reg_item.get("tag_value") or "")
        display_name = str(reg_item.get("display_name") or tag_value)
        original_name = str(reg_item.get("original_display_name") or tag_value)
        if not tag_value:
            continue
        if display_name == tag_value and not reg_item.get("original_display_name"):
            continue
        if not reg_item.get("name_standardized") and display_name == original_name:
            continue
        map_key = (
            str(reg_item.get("account_code") or ""),
            str(reg_item.get("category_code") or ""),
            str(reg_item.get("source_sub_code") or ""),
            tag_value,
        )
        if map_key in mapped_keys:
            continue
        mapped_keys.add(map_key)
        items.append(
            {
                "queue_type": "mapped",
                "priority": "low",
                "account_code": reg_item.get("account_code"),
                "account_name": reg_item.get("account_name"),
                "category_code": reg_item.get("category_code"),
                "source_sub_code": reg_item.get("source_sub_code"),
                "tag_value": tag_value,
                "original_display_name": original_name,
                "display_name": display_name,
                "mapped_at": reg_item.get("mapped_at"),
                "mapped_by_user_id": reg_item.get("mapped_by_user_id"),
                "line_count": reg_item.get("line_count", 0),
                "voucher_count": reg_item.get("voucher_count", 0),
                "message": "已人工映射：下列为导入原名与当前映射值，入账前可再改",
            }
        )

    comparison = registry.get("comparison") or {}
    for gap_item in comparison.get("in_import_not_in_evidence", []):
        items.append(
            {
                "queue_type": "missing_in_master",
                "priority": "high",
                "account_code": gap_item.get("account_code"),
                "category_code": gap_item.get("category_code") or "bank_account",
                "source_sub_code": gap_item.get("source_sub_code"),
                "tag_value": gap_item.get("tag_value"),
                "display_name": gap_item.get("display_name"),
                "line_count": gap_item.get("line_count", 0),
                "message": "账里用到了，但开户清单/往来单位等主数据里还没有，请先补登记",
            }
        )

    staging_rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .order_by(StagingAccountingEntry.voucher_no, StagingAccountingEntry.entry_line_no)
        .all()
    )
    for row in staging_rows:
        if (row.original_row or {}).get("_requires_llm_resolution"):
            base_code = row.resolved_account_code or row.account_code or ""
            items.append(
                {
                    "queue_type": "requires_llm",
                    "priority": "medium",
                    "staging_id": row.id,
                    "voucher_no": row.voucher_no,
                    "account_code": base_code,
                    "summary": row.summary,
                    "line_count": 1,
                    "message": "系统没从摘要里识别出辅助核算，请用 LLM 识别或人工补",
                }
            )
        tags = row.entry_tags_payload or []
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            category_code = str(tag.get("category_code") or "")
            if not category_code or category_code == "unknown":
                items.append(
                    {
                        "queue_type": "unknown_category",
                        "priority": "high",
                        "staging_id": row.id,
                        "voucher_no": row.voucher_no,
                        "account_code": row.resolved_account_code or row.account_code,
                        "category_code": category_code or None,
                        "tag_value": str(tag.get("tag_value") or ""),
                        "display_name": str(tag.get("display_name") or tag.get("tag_value") or ""),
                        "line_count": 1,
                        "message": "这条分录的维度缺少有效分类，请检查解析映射规则",
                    }
                )

    findings = (
        db.query(AuditFinding)
        .filter(
            AuditFinding.job_id == job_id,
            AuditFinding.finding_type == "internal_control",
            AuditFinding.status == "pending",
        )
        .order_by(AuditFinding.id)
        .all()
    )
    for finding in findings:
        meta = finding.finding_metadata or {}
        items.append(
            {
                "queue_type": "internal_control",
                "priority": "low",
                "finding_id": finding.id,
                "account_code": meta.get("account_code"),
                "category_code": meta.get("category_code"),
                "source_sub_code": meta.get("source_sub_code"),
                "tag_value": meta.get("tag_value"),
                "display_name": meta.get("display_name"),
                "message": finding.finding_title or "内控维度提醒待处理",
            }
        )

    summary_counts = {
        "non_standardized": sum(1 for i in items if i["queue_type"] == "non_standardized"),
        "missing_in_master": sum(1 for i in items if i["queue_type"] == "missing_in_master"),
        "requires_llm": sum(1 for i in items if i["queue_type"] == "requires_llm"),
        "unknown_category": sum(1 for i in items if i["queue_type"] == "unknown_category"),
        "internal_control": sum(1 for i in items if i["queue_type"] == "internal_control"),
        "mapped": sum(1 for i in items if i["queue_type"] == "mapped"),
    }
    summary_counts["total"] = sum(1 for i in items if i["queue_type"] != "mapped")

    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda x: (priority_order.get(str(x.get("priority")), 9), str(x.get("queue_type"))))

    return {
        "job_id": job_id,
        "ledger_id": ledger_id,
        "summary": summary_counts,
        "items": items,
        "registry_warnings": registry.get("warnings", []),
    }
