# -*- coding: utf-8 -*-
"""
旧标签数据导入兼容层（Legacy Tag Import Compatibility Layer）。

业务场景：
    将历史 EntryTag 数据（扁平 tag_name:tag_value 格式）或外部 ERP 标签格式，
    转换为新的 Dimension 体系：TagCategory + EntryTag。

政策依据：
    项目采用"一级科目 + Dimension"核心模型，旧标签数据需经过映射、校验、转换后
    才能进入新系统，确保数据语义一致与审计可追溯。

输入数据：
    - ledger_id: 目标账簿
    - legacy_tags: 旧标签记录列表，每条包含 entry_id、原始 tag 表达等
    - mapping_rules: 可选的显式映射规则

输出结果：
    - LegacyTagImportReport：包含成功、失败、警告记录的导入报告
"""
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import EntryTag
from app.services.entry_tag_service import create_entry_tag
from app.services.tag_category_service import get_or_create_category
from app.services.tag_mapping_rule_service import apply_mapping_rules


@dataclass
class LegacyTagRecord:
    """单条旧标签记录。"""

    entry_id: int
    raw_tag: str
    raw_value: str | None = None
    weight: float = 1.0
    tag_source: str = "import"
    confidence: float = 0.8


@dataclass
class ImportReportItem:
    """导入报告单项。"""

    entry_id: int
    raw_tag: str
    status: str  # success / failed / warning
    category_code: str | None = None
    tag_value: str | None = None
    message: str = ""


@dataclass
class LegacyTagImportReport:
    """旧标签导入报告。"""

    total: int = 0
    success: int = 0
    failed: int = 0
    warning: int = 0
    items: list[ImportReportItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "warning": self.warning,
            "items": [
                {
                    "entry_id": item.entry_id,
                    "raw_tag": item.raw_tag,
                    "status": item.status,
                    "category_code": item.category_code,
                    "tag_value": item.tag_value,
                    "message": item.message,
                }
                for item in self.items
            ],
        }


def _parse_legacy_tag(raw_tag: str) -> tuple[str | None, str | None]:
    """
    解析旧标签字符串。

    支持的格式：
        - "category:value" 或 "category：value"
        - "value"（无分类，返回 category=None）

    Returns:
        (category, value) 元组
    """
    if not raw_tag:
        return None, None

    separators = [":", "：", "-", "_"]
    for sep in separators:
        if sep in raw_tag:
            parts = raw_tag.split(sep, 1)
            if len(parts) == 2:
                category = parts[0].strip().lower().replace(" ", "_")
                value = parts[1].strip()
                return category, value

    return None, raw_tag.strip()


def _validate_record(record: LegacyTagRecord) -> tuple[bool, str]:
    """
    校验单条旧标签记录的有效性。

    Returns:
        (是否有效, 错误信息)
    """
    if not record.entry_id:
        return False, "entry_id 不能为空"
    if not record.raw_tag:
        return False, "raw_tag 不能为空"
    if record.weight < 0 or record.weight > 10:
        return False, "weight 必须在 0-10 之间"
    return True, ""


def import_legacy_tags(
    db: Session,
    ledger_id: int,
    records: list[LegacyTagRecord],
    auto_create_category: bool = True,
    default_category_code: str = "legacy",
    changed_by: int | None = None,
) -> LegacyTagImportReport:
    """
    导入旧标签数据并转换为新 Dimension 体系。

    Args:
        db: 数据库会话
        ledger_id: 目标账簿 ID
        records: 旧标签记录列表
        auto_create_category: 是否自动创建不存在的分类
        default_category_code: 无法识别分类时的默认分类编码
        changed_by: 操作人 ID

    Returns:
        LegacyTagImportReport 导入报告
    """
    report = LegacyTagImportReport()

    # 自动准备默认分类
    if auto_create_category:
        get_or_create_category(
            db,
            ledger_id=ledger_id,
            code=default_category_code,
            name="历史遗留标签",
            description="从旧系统自动导入的未分类标签",
            value_type="text",
        )

    # 收集所有 raw_tag 用于映射规则匹配
    raw_tags = [r.raw_tag for r in records]
    mapping_results = apply_mapping_rules(
        db,
        ledger_id=ledger_id,
        source_type="tag",
        source_values=raw_tags,
        fallback_category_code=default_category_code,
    )
    mapping_lookup = {r["source_value"]: r for r in mapping_results}

    for record in records:
        report.total += 1

        valid, error_message = _validate_record(record)
        if not valid:
            report.failed += 1
            report.items.append(
                ImportReportItem(
                    entry_id=record.entry_id,
                    raw_tag=record.raw_tag,
                    status="failed",
                    message=error_message,
                )
            )
            continue

        category_code: str | None = None
        tag_value: str | None = None
        is_fallback = False

        # 1. 优先从 raw_tag 解析 category:value 格式
        parsed_category, parsed_value = _parse_legacy_tag(record.raw_tag)
        if parsed_category:
            category_code = parsed_category
            tag_value = record.raw_value or parsed_value
        else:
            # 2. 无法解析时，尝试映射规则
            mapped = mapping_lookup.get(record.raw_tag)
            if mapped and mapped.get("matched") and not mapped.get("fallback"):
                category_code = mapped["category_code"]
                tag_value = mapped["target_value"] or record.raw_value
            else:
                # 3. 仍未命中，使用默认分类兜底
                category_code = default_category_code
                tag_value = record.raw_value or record.raw_tag
                is_fallback = True

        if not tag_value:
            report.failed += 1
            report.items.append(
                ImportReportItem(
                    entry_id=record.entry_id,
                    raw_tag=record.raw_tag,
                    status="failed",
                    message="无法提取标签值",
                )
            )
            continue

        if auto_create_category:
            get_or_create_category(
                db,
                ledger_id=ledger_id,
                code=category_code,
                name=category_code,
                value_type="text",
            )

        try:
            create_entry_tag(
                db,
                entry_id=record.entry_id,
                ledger_id=ledger_id,
                category_code=category_code,
                tag_value=tag_value,
                weight=record.weight,
                tag_source=record.tag_source,
                confidence=record.confidence,
                changed_by=changed_by,
                change_reason="从旧标签系统自动导入",
            )

            if is_fallback:
                report.warning += 1
                status = "warning"
                message = f"使用默认分类 {default_category_code} 导入"
            else:
                report.success += 1
                status = "success"
                message = "导入成功"

            report.items.append(
                ImportReportItem(
                    entry_id=record.entry_id,
                    raw_tag=record.raw_tag,
                    status=status,
                    category_code=category_code,
                    tag_value=tag_value,
                    message=message,
                )
            )
        except ValueError as e:
            report.failed += 1
            report.items.append(
                ImportReportItem(
                    entry_id=record.entry_id,
                    raw_tag=record.raw_tag,
                    status="failed",
                    category_code=category_code,
                    tag_value=tag_value,
                    message=str(e),
                )
            )

    return report


def detect_legacy_tag_format(sample: list[str]) -> str:
    """
    根据样本检测旧标签数据格式。

    Returns:
        "colon_separated" | "free_text" | "unknown"
    """
    if not sample:
        return "unknown"

    colon_count = sum(1 for s in sample if ":" in s or "：" in s)
    if colon_count / len(sample) >= 0.5:
        return "colon_separated"

    return "free_text"
