"""导入任务输出路径路由。

为不同 source_type 定义稳定的下游处理路径，避免多类型资料导入后结果不可预期。
"""

from __future__ import annotations

# 序时簿类导入：解析为正式分录，跳过 AI 草稿生成
DAY_BOOK_SOURCE_TYPES = frozenset({"audit_day_book", "ledger_day_book"})

# 直接落库分录的路径（复核/导出，不经 Step3 AI 生成）
DIRECT_ENTRY_SOURCE_TYPES = frozenset(
    {"voucher_import", "audit_day_book", "ledger_day_book", "manual_entry"}
)

# AI 证据路径：原始资料 → Step3 生成草稿
AI_EVIDENCE_SOURCE_TYPES = frozenset({"ai_generated"})


def is_day_book_source_type(source_type: str) -> bool:
    return source_type in DAY_BOOK_SOURCE_TYPES


def get_import_output_path(source_type: str) -> str:
    """返回导入任务的稳定输出路径标识。

    - ``direct_entries``：结构化分录已生成，进入复核（Step4）
    - ``register_ledger``：原始资料已登记功能模块台账，进入 AI 凭证草稿（Step3）
    - ``ai_draft``：兼容旧路径别名，等同 register_ledger
    """
    if source_type in DIRECT_ENTRY_SOURCE_TYPES:
        return "direct_entries"
    if source_type in AI_EVIDENCE_SOURCE_TYPES:
        return "register_ledger"
    return "ai_draft"


def should_persist_structured_entries(source_type: str) -> bool:
    """结构化 Excel/CSV 是否应直接写入 accounting_entries。"""
    return source_type not in AI_EVIDENCE_SOURCE_TYPES
