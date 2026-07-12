# -*- coding: utf-8 -*-
"""
账簿维度就绪检查：结构化导入（序时簿）前，确认解析映射与维度分类已审阅。

业务场景：
    不同公司/行业的维度叫法不同，须先在本账簿确认 tag 规则，再导入结构性文件；
    向量检索亦按 ledger 隔离，就绪检查与审阅确认写入 LedgerSettings。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import ImportJob, TagCategory
from app.models.scope_settings import LedgerSettings


def _coerce_settings_dict(raw: Any) -> dict[str, Any]:
    """将 LedgerSettings.settings 规范为 dict，避免历史脏数据导致 dict(str) 抛错。"""
    if isinstance(raw, dict):
        return dict(raw)
    return {}


def _ledger_settings(db: Session, ledger_id: int) -> tuple[LedgerSettings, dict[str, Any]]:
    row = db.query(LedgerSettings).filter(LedgerSettings.ledger_id == ledger_id).first()
    if row is None:
        row = LedgerSettings(ledger_id=ledger_id, settings={})
        db.add(row)
        db.flush()
        return row, {}
    settings = _coerce_settings_dict(row.settings)
    if row.settings is not None and not isinstance(row.settings, dict):
        row.settings = settings
        flag_modified(row, "settings")
        db.flush()
    return row, settings


def acknowledge_tag_rules_reviewed(
    db: Session,
    ledger_id: int,
    *,
    reviewed_by: int | None = None,
) -> dict[str, Any]:
    """标记本账簿 tag 解析规则与维度分类已审阅，允许结构化导入。"""
    row, settings = _ledger_settings(db, ledger_id)
    now = datetime.now(timezone.utc).isoformat()
    merged = dict(settings)
    merged["tag_rules_reviewed_at"] = now
    if reviewed_by is not None:
        merged["tag_rules_reviewed_by"] = reviewed_by
    row.settings = merged
    row.updated_at = datetime.now(timezone.utc)
    flag_modified(row, "settings")
    db.flush()
    return {"ledger_id": ledger_id, "tag_rules_reviewed_at": now}


def assess_ledger_dimension_readiness(db: Session, ledger_id: int) -> dict[str, Any]:
    """
    评估账簿是否已完成维度规则审阅，可否进行序时簿等结构化导入。

    阻塞条件（须先处理）：
        - 解析映射无法加载
        - 本账簿从未审阅过 tag 规则（首次结构化导入）

    警告（可继续但建议处理）：
        - 解析配置中的 category 在分类表缺失
        - 曾导入过但审阅标记过期（无，仅首次强制）
    """
    from app.config.account_tag_config import load_account_tag_config
    from app.services.audit.audit_day_book_service import _ensure_tag_categories

    row, settings = _ledger_settings(db, ledger_id)
    tag_rules_reviewed_at = settings.get("tag_rules_reviewed_at")

    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    try:
        config = load_account_tag_config(db, ledger_id=ledger_id)
        parse_config_ok = True
    except Exception as exc:
        config = None
        parse_config_ok = False
        blockers.append(
            {
                "code": "parse_config_unavailable",
                "message": f"无法加载本账簿解析映射：{exc}",
                "action_tab": "parse-mapping",
            }
        )

    config_categories: set[str] = set()
    if config is not None:
        config_categories |= set(config.account_code_tag_category.values())
        config_categories |= set(config.account_name_tag_category.values())
        config_categories |= set(config.auxiliary_keywords.keys())
        if config_categories:
            try:
                _ensure_tag_categories(db, ledger_id, config_categories)
                db.flush()
            except Exception as exc:
                warnings.append(
                    {
                        "code": "tag_category_bootstrap_failed",
                        "message": f"自动补全维度分类失败（可继续在维度分类页手工维护）：{exc}",
                        "action_tab": "categories",
                    }
                )

    categories = (
        db.query(TagCategory)
        .filter(TagCategory.ledger_id == ledger_id, TagCategory.status == "active")
        .all()
    )
    category_codes = {cat.code for cat in categories}
    missing_categories = sorted(config_categories - category_codes)
    if missing_categories:
        warnings.append(
            {
                "code": "missing_tag_categories",
                "message": f"解析映射引用的分类尚未登记：{', '.join(missing_categories)}",
                "categories": missing_categories,
                "action_tab": "categories",
            }
        )

    prior_day_book_imports = (
        db.query(ImportJob)
        .filter(
            ImportJob.ledger_id == ledger_id,
            ImportJob.source_type == "ledger_day_book",
            ImportJob.status.notin_(["created", "cancelled"]),
        )
        .count()
    )

    if not tag_rules_reviewed_at:
        blockers.append(
            {
                "code": "tag_rules_not_reviewed",
                "message": (
                    "请先在「账簿维度管理」审阅本账簿的解析映射与维度分类。"
                    "不同公司/行业的维度叫法不同，须按账簿确认后再导入序时簿。"
                ),
                "action_tab": "parse-mapping",
                "is_first_import": prior_day_book_imports == 0,
            }
        )

    ready = len(blockers) == 0
    return {
        "ledger_id": ledger_id,
        "ready_for_structured_import": ready,
        "tag_rules_reviewed_at": tag_rules_reviewed_at,
        "parse_config_ok": parse_config_ok,
        "category_count": len(categories),
        "prior_structured_import_count": prior_day_book_imports,
        "blockers": blockers,
        "warnings": warnings,
        "vector_scope_note": "向量检索仅在本账簿（ledger_id）范围内匹配，避免跨公司映射串库。",
    }
