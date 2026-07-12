"""COA 缺口自动映射：将明细/异构科目编码 rollup 到账簿科目表。"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, ChartOfAccounts, OpeningBalance
from app.services.basic_data.coa_service import DEFAULT_ACCOUNTS

# 异构 ERP 常见权益科目前缀 → 准则口径一级科目
LEGACY_ROOT_ALIASES: dict[str, str] = {
    "3001": "4001",  # 实收资本
    "3002": "4002",  # 资本公积
    "3101": "4101",  # 盈余公积
    "3103": "4103",  # 本年利润（部分系统用 3103）
    "3104": "4104",  # 利润分配
}

_CANONICAL_BY_CODE = {item["code"]: item for item in DEFAULT_ACCOUNTS}


def _infer_account_meta(code: str) -> tuple[str, str]:
    """按科目编码首位推断类别与余额方向（用于 COA 缺口自动补全）。"""
    root = (code or "").strip()[:1]
    if root == "1":
        return "asset", "debit"
    if root == "2":
        return "liability", "credit"
    if root in {"3", "4"}:
        return "equity", "credit"
    if root == "5":
        return "cost", "debit"
    if root in {"6", "7"}:
        return "profit", "debit"
    return "asset", "debit"


def _normalize_account_token(code: str | None) -> str:
    return (code or "").strip().replace(".", "")


def _expand_numeric_code_segments(account_code: str) -> list[str]:
    normalized = account_code.strip()
    if not normalized:
        return []
    if "." in normalized:
        return [segment.strip() for segment in normalized.split(".") if segment.strip()]
    if not normalized.isdigit():
        return [normalized]
    if len(normalized) <= 4:
        return [normalized]
    segments = [normalized[:4]]
    rest = normalized[4:]
    while rest:
        segments.append(rest[:2])
        rest = rest[2:]
    return segments


def translate_legacy_code(code: str) -> str:
    """将异构编码翻译为准则口径编码（保留下级段）。"""
    normalized = _normalize_account_token(code)
    if not normalized:
        return ""
    segments = _expand_numeric_code_segments(normalized)
    if segments and segments[0] in LEGACY_ROOT_ALIASES:
        segments[0] = LEGACY_ROOT_ALIASES[segments[0]]
        return "".join(segments)
    return normalized


def _longest_prefix_match(code: str, coa_codes: set[str]) -> str | None:
    best: str | None = None
    for coa in coa_codes:
        if code.startswith(coa):
            if best is None or len(coa) > len(best):
                best = coa
    return best


def resolve_coa_mapping_target(code: str, coa_codes: set[str]) -> tuple[str | None, str]:
    """
    将分录/期初科目映射到 COA 汇总目标。

    返回 (target_code, mapping_source)。
    mapping_source: exact | prefix | legacy_prefix | legacy_root | unmapped
    """
    normalized = _normalize_account_token(code)
    if not normalized:
        return None, "unmapped"

    if normalized in coa_codes:
        return normalized, "exact"
    if code in coa_codes:
        return code, "exact"

    direct_prefix = _longest_prefix_match(normalized, coa_codes)
    if direct_prefix:
        return direct_prefix, "prefix"
    if code != normalized:
        legacy_direct = _longest_prefix_match(code, coa_codes)
        if legacy_direct:
            return legacy_direct, "prefix"

    translated = translate_legacy_code(normalized)
    if translated != normalized:
        if translated in coa_codes:
            return translated, "legacy_exact"
        legacy_prefix = _longest_prefix_match(translated, coa_codes)
        if legacy_prefix:
            return legacy_prefix, "legacy_prefix"

        segments = _expand_numeric_code_segments(translated)
        if segments:
            root = segments[0]
            if root in coa_codes:
                return root, "legacy_root"

    segments = _expand_numeric_code_segments(normalized)
    if segments:
        root = segments[0]
        if root in LEGACY_ROOT_ALIASES:
            canonical_root = LEGACY_ROOT_ALIASES[root]
            if canonical_root in coa_codes:
                return canonical_root, "legacy_root"

    return None, "unmapped"


def rollup_amount_map_with_gap_mapping(
    raw_map: dict[str, tuple[Decimal, Decimal]],
    coa_codes: set[str],
) -> tuple[dict[str, tuple[Decimal, Decimal]], Decimal, dict[str, Any]]:
    """按 COA 汇总借贷发生额，并返回映射元数据。"""
    rolled: dict[str, tuple[Decimal, Decimal]] = {}
    orphan_debit = Decimal("0")
    orphan_credit = Decimal("0")
    mapping_hits: dict[str, str] = {}
    unmapped_codes: list[str] = []

    for code, (debit, credit) in raw_map.items():
        target, source = resolve_coa_mapping_target(code, coa_codes)
        if not target:
            orphan_debit += debit
            orphan_credit += credit
            if debit != 0 or credit != 0:
                unmapped_codes.append(code)
            continue
        if source != "exact":
            mapping_hits[code] = f"{target} ({source})"
        prev_d, prev_c = rolled.get(target, (Decimal("0"), Decimal("0")))
        rolled[target] = (prev_d + debit, prev_c + credit)

    orphan_net = orphan_debit - orphan_credit
    meta = {
        "coa_gap_mapping_count": len(mapping_hits),
        "coa_gap_mappings": dict(sorted(mapping_hits.items())[:20]),
        "unmapped_codes": sorted(set(unmapped_codes))[:30],
    }
    return rolled, orphan_net, meta


def collect_orphan_account_codes(
    db: Session,
    ledger_id: int,
    *,
    period_id: int | None = None,
    as_of_date=None,
) -> dict[str, str | None]:
    """收集账簿中未能映射到 COA 的科目编码及代表性名称。"""
    coa_codes = {
        row.code
        for row in db.query(ChartOfAccounts.code)
        .filter(ChartOfAccounts.ledger_id == ledger_id)
        .all()
    }
    names: dict[str, str | None] = {}

    opening_query = db.query(OpeningBalance.account_code).filter(OpeningBalance.ledger_id == ledger_id)
    if period_id is not None:
        opening_query = opening_query.filter(OpeningBalance.period_id == period_id)
    for (code,) in opening_query.distinct().all():
        if code and resolve_coa_mapping_target(code, coa_codes)[0] is None:
            names.setdefault(code, None)

    entry_query = db.query(
        func.coalesce(
            func.nullif(AccountingEntry.resolved_account_code, ""),
            AccountingEntry.account_code,
        ).label("effective_code"),
        func.max(AccountingEntry.account_name).label("account_name"),
    ).filter(AccountingEntry.ledger_id == ledger_id)
    if period_id is not None and as_of_date is not None:
        from app.db.models import AccountingPeriod

        period = db.get(AccountingPeriod, period_id)
        if period:
            entry_query = entry_query.filter(
                AccountingEntry.voucher_date >= period.start_date,
                AccountingEntry.voucher_date <= as_of_date,
            )
    entry_query = entry_query.group_by("effective_code")
    for row in entry_query.all():
        code = str(row.effective_code or "")
        if not code:
            continue
        if resolve_coa_mapping_target(code, coa_codes)[0] is None:
            names[code] = row.account_name

    return names


def auto_provision_coa_gaps(
    db: Session,
    ledger_id: int,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    为账簿自动补全 COA 缺口：
    1. 确保异构映射的准则一级科目存在；
    2. 为仍无法 rollup 的明细编码创建子科目（翻译后的编码）。
    """
    existing_codes = {
        row.code
        for row in db.query(ChartOfAccounts.code)
        .filter(ChartOfAccounts.ledger_id == ledger_id)
        .all()
    }
    orphans = collect_orphan_account_codes(db, ledger_id)

    created: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    planned_roots: set[str] = set()

    for orphan_code, orphan_name in sorted(orphans.items()):
        translated = translate_legacy_code(orphan_code)
        segments = _expand_numeric_code_segments(translated or orphan_code)
        root = segments[0] if segments else translated or orphan_code

        if root not in existing_codes and root in _CANONICAL_BY_CODE:
            planned_roots.add(root)

        if translated and translated not in existing_codes:
            parent = _longest_prefix_match(translated, existing_codes | planned_roots)
            if parent is None and root in _CANONICAL_BY_CODE:
                parent = root
            if parent:
                template = _CANONICAL_BY_CODE.get(parent, _CANONICAL_BY_CODE.get(root, {}))
                payload = {
                    "ledger_id": ledger_id,
                    "code": translated,
                    "name": orphan_name or f"自动补全-{translated}",
                    "parent_code": parent if parent != translated else None,
                    "category": template.get("category", "equity"),
                    "direction": template.get("direction", "credit"),
                    "is_terminal": True,
                }
                if dry_run:
                    created.append({"action": "create", **payload, "source_code": orphan_code})
                else:
                    from app.services.basic_data import coa_service

                    try:
                        account = coa_service.create_account(db, payload)
                        created.append(
                            {
                                "action": "created",
                                "code": account.code,
                                "name": account.name,
                                "source_code": orphan_code,
                            }
                        )
                        existing_codes.add(account.code)
                    except ValueError as exc:
                        skipped.append({"code": translated, "reason": str(exc)})
                continue

        # 兜底：按编码规则推断类别，补全无法翻译/无准则模板的孤儿科目（如 1604、5602）
        target_code = translated or orphan_code
        if target_code and target_code not in existing_codes:
            category, direction = _infer_account_meta(target_code)
            parent = _longest_prefix_match(target_code, existing_codes | planned_roots)
            if parent == target_code:
                parent = None
            segments = _expand_numeric_code_segments(target_code)
            payload = {
                "ledger_id": ledger_id,
                "code": target_code,
                "name": orphan_name or f"自动补全-{target_code}",
                "parent_code": parent,
                "level": max(1, len(segments)),
                "category": category,
                "direction": direction,
                "is_terminal": True,
            }
            if dry_run:
                created.append({"action": "create_inferred", **payload, "source_code": orphan_code})
                existing_codes.add(target_code)
                continue
            from app.services.basic_data import coa_service

            try:
                account = coa_service.create_account(db, payload)
                created.append(
                    {
                        "action": "created_inferred",
                        "code": account.code,
                        "name": account.name,
                        "source_code": orphan_code,
                    }
                )
                existing_codes.add(account.code)
                continue
            except ValueError as exc:
                skipped.append({"code": target_code, "reason": str(exc)})
                continue

        skipped.append(
            {
                "code": orphan_code,
                "reason": "无法推断父级科目或翻译后编码已存在",
            }
        )

    for root in sorted(planned_roots):
        if root in existing_codes:
            continue
        template = _CANONICAL_BY_CODE[root]
        payload = {
            "ledger_id": ledger_id,
            "code": root,
            "name": template["name"],
            "parent_code": None,
            "level": 1,
            "category": template["category"],
            "direction": template["direction"],
            "is_terminal": False,
        }
        if dry_run:
            created.append({"action": "create_root", **payload})
        else:
            from app.services.basic_data import coa_service

            try:
                account = coa_service.create_account(db, payload)
                created.append({"action": "created_root", "code": account.code, "name": account.name})
                existing_codes.add(account.code)
            except ValueError as exc:
                skipped.append({"code": root, "reason": str(exc)})

    return {
        "ledger_id": ledger_id,
        "dry_run": dry_run,
        "orphan_code_count": len(orphans),
        "created_count": len(created),
        "created": created,
        "skipped": skipped,
    }
