"""结构化导入路由：按 source_type 区分 kind 与归属模式。"""

from __future__ import annotations

# 序时簿/日记账/凭证类（借贷分录）
ENTRY_SOURCE_TYPES = frozenset({
    "audit_day_book",
    "ledger_day_book",
    "voucher_import",
    "manual_entry",
    "ledger_voucher",
    "audit_voucher",
})

# 科目余额表
BALANCE_SOURCE_TYPES = frozenset({
    "ledger_balance_sheet",
    "audit_balance_sheet",
})

# 明细账
GENERAL_LEDGER_SOURCE_TYPES = frozenset({
    "ledger_general_ledger",
    "audit_general_ledger",
})

# 总账
GENERAL_LEDGER_SUMMARY_SOURCE_TYPES = frozenset({
    "ledger_general_ledger_summary",
    "audit_general_ledger_summary",
})

DAY_BOOK_SOURCE_TYPES = frozenset({"audit_day_book", "ledger_day_book"})

DIRECT_ENTRY_SOURCE_TYPES = frozenset(ENTRY_SOURCE_TYPES)

AI_EVIDENCE_SOURCE_TYPES = frozenset({"ai_generated", "evidence_inbox"})

STRUCTURED_SOURCE_TYPES = (
    ENTRY_SOURCE_TYPES
    | BALANCE_SOURCE_TYPES
    | GENERAL_LEDGER_SOURCE_TYPES
    | GENERAL_LEDGER_SUMMARY_SOURCE_TYPES
)

# 记账模式（进正式 ledger）
LEDGER_MODE_SOURCE_TYPES = frozenset({
    "ledger_day_book",
    "ledger_voucher",
    "voucher_import",
    "manual_entry",
})

# 审计模式凭证类（进工作底稿账套）
AUDIT_ENTRY_MODE_SOURCE_TYPES = frozenset({
    "audit_day_book",
    "audit_voucher",
})

# 审计模式快照类（进审计域表，无 ledger）
AUDIT_SNAPSHOT_MODE_SOURCE_TYPES = (
    BALANCE_SOURCE_TYPES
    | GENERAL_LEDGER_SOURCE_TYPES
    | GENERAL_LEDGER_SUMMARY_SOURCE_TYPES
)


def is_day_book_source_type(source_type: str) -> bool:
    return source_type in DAY_BOOK_SOURCE_TYPES or source_type in {
        "ledger_voucher",
        "audit_voucher",
        "voucher_import",
    }


def is_structured_source_type(source_type: str) -> bool:
    return source_type in STRUCTURED_SOURCE_TYPES


def get_structured_kind(source_type: str) -> str | None:
    if source_type in ENTRY_SOURCE_TYPES:
        return "entries"
    if source_type in BALANCE_SOURCE_TYPES:
        return "balances"
    if source_type in GENERAL_LEDGER_SOURCE_TYPES:
        return "general_ledger"
    if source_type in GENERAL_LEDGER_SUMMARY_SOURCE_TYPES:
        return "general_ledger_summary"
    return None


def get_import_mode(source_type: str) -> str:
    """A=记账模式, B1=审计凭证工作底稿, B2=审计快照。"""
    if source_type in LEDGER_MODE_SOURCE_TYPES:
        return "A"
    if source_type in AUDIT_ENTRY_MODE_SOURCE_TYPES:
        return "B1"
    if source_type in AUDIT_SNAPSHOT_MODE_SOURCE_TYPES:
        return "B2"
    return "A"


def get_import_output_path(source_type: str) -> str:
    if source_type in DIRECT_ENTRY_SOURCE_TYPES or source_type in STRUCTURED_SOURCE_TYPES:
        return "direct_entries"
    if source_type in AI_EVIDENCE_SOURCE_TYPES:
        return "register_ledger"
    return "ai_draft"


def should_persist_structured_entries(source_type: str) -> bool:
    return source_type not in AI_EVIDENCE_SOURCE_TYPES
