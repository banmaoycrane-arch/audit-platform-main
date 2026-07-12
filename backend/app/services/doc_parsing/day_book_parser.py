"""
序时簿 / 结构化凭证表区域识别（场景 A 引擎前提步骤）。

识别顺序（所有结构化 Excel/CSV 导入应先走本模块）：
  1. header=None 读取全表
  2. 合并单元格横向填充（标题行常仅首格有值）
  3. 元数据区（表名、单位、期间、币种等，位于真表头之上）
  4. 表头行定位
  5. 表内容区（跳过空行/小计；连续空行或表尾合计后结束）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

# 扫描真表头的最大行数（传统序时簿标题区可达 4~8 行，留余量）
HEADER_SCAN_MAX_ROWS = 25

_HEADER_KEYWORDS = [
    "凭证", "日期", "摘要", "科目", "借方", "贷方", "余额", "金额",
    "序号", "年", "月", "日", "对方科目", "经办人", "审核人", "过账",
    "voucher", "date", "summary", "subject", "debit", "credit", "balance",
    "amount", "no", "serial",
]

_TITLE_ROW_KEYWORDS = [
    "序时簿", "序时账", "凭证序时簿", "凭证序时账", "日记账", "明细账", "核算单位", "单位：", "单位:",
    "年月", "报表", "台账", "科目余额", "余额表",
]

_METADATA_COMPANY_KEYWORDS = ["公司", "企业", "单位", "核算单位"]
_METADATA_PERIOD_KEYWORDS = ["202", "期间", "年度", "月份", "会计期间", "年月"]
_METADATA_CURRENCY_KEYWORDS = ["货币单位", "本位币", "币种", "人民币", "美元"]

_SUMMARY_KEYWORDS = ["合计", "小计", "总计", "汇总", "sum", "total", "subtotal"]
_FOOTER_KEYWORDS = ["制表人", "审核人", "复核人", "打印日期", "页码"]


@dataclass
class TableMetadata:
    """表头之上的说明区（标题、单位、期间、币种）。"""

    title: str | None = None
    company_name: str | None = None
    report_period: str | None = None
    currency_unit: str = "元"


@dataclass
class StructuredTableLayout:
    """结构化表区域解析结果。"""

    raw_frame: pd.DataFrame
    header_row_index: int
    metadata: TableMetadata
    data_frame: pd.DataFrame
    raw_headers: list[str] = field(default_factory=list)
    data_row_excel_indices: list[int] = field(default_factory=list)
    amount_color_grid: dict[tuple[int, int], str] = field(default_factory=dict)
    source_path: str | None = None


def _row_values(row: pd.Series) -> list[str]:
    return [str(v).strip() for v in row.values if pd.notna(v) and str(v).strip()]


def _row_text(row: pd.Series) -> str:
    return " ".join(v.lower() for v in _row_values(row))


def forward_fill_merged_row_values(frame: pd.DataFrame) -> pd.DataFrame:
    """横向填充合并单元格：仅对「仅首格有值的标题行」向右继承。"""
    if frame.empty:
        return frame
    filled = frame.copy()
    for idx in range(len(filled)):
        row = filled.iloc[idx]
        values = _row_values(row)
        if len(values) != 1:
            continue
        first_cell = values[0]
        if not (
            is_title_only_row(row)
            or any(kw in first_cell for kw in ("序时", "日记账", "明细账"))
        ):
            continue
        for col in filled.columns:
            cell = filled.iloc[idx, col]
            if pd.isna(cell) or not str(cell).strip():
                filled.iloc[idx, col] = first_cell
    return filled


def is_empty_row(row: pd.Series) -> bool:
    return len(_row_values(row)) == 0


def is_summary_row(row: pd.Series) -> bool:
    """小计/合计/汇总行。"""
    text = _row_text(row)
    if any(keyword in text for keyword in _SUMMARY_KEYWORDS):
        return True
    non_empty = _row_values(row)
    if len(non_empty) == 1 and any(k in non_empty[0].lower() for k in _SUMMARY_KEYWORDS):
        return True
    return False


def is_footer_metadata_row(row: pd.Series) -> bool:
    """表尾签字/页码等说明行。"""
    text = " ".join(_row_values(row))
    return any(kw in text for kw in _FOOTER_KEYWORDS)


def is_title_only_row(row: pd.Series) -> bool:
    """单行标题（表名、单位说明等），不应视为字段表头。"""
    values = _row_values(row)
    if len(values) != 1:
        return False
    cell = values[0]
    if len(cell) > 40:
        return False
    return any(kw in cell for kw in _TITLE_ROW_KEYWORDS)


def detect_header_row(frame: pd.DataFrame, *, max_scan_rows: int = HEADER_SCAN_MAX_ROWS) -> int:
    """
    定位真正字段表头行。

    财务序时簿常见前若干行为标题/单位/期间，真表头在下方 4~8 行。
    """
    if frame.empty:
        return 0

    best_score = -1.0
    best_index = 0

    for idx in range(min(len(frame), max_scan_rows)):
        row = frame.iloc[idx]
        row_values = _row_values(row)
        row_str = _row_text(row)

        if is_title_only_row(row):
            continue
        if not row_str:
            continue

        score = 0.0
        for keyword in _HEADER_KEYWORDS:
            if keyword in row_str:
                score += 1.0
        non_empty_count = len(row_values)
        if non_empty_count >= 4:
            score += non_empty_count * 0.5
        if score > best_score:
            best_score = score
            best_index = idx

    return best_index


def extract_table_metadata(frame: pd.DataFrame, header_row_index: int) -> TableMetadata:
    """从表头行之上的区域提取标题、单位、期间、币种。"""
    meta = TableMetadata()
    for idx in range(max(header_row_index, 0)):
        row_text = " ".join(_row_values(frame.iloc[idx]))
        if not row_text:
            continue
        if meta.title is None and any(kw in row_text for kw in ("序时簿", "序时账", "日记账", "明细账")):
            meta.title = row_text.strip()
        if meta.company_name is None and any(kw in row_text for kw in _METADATA_COMPANY_KEYWORDS):
            if "货币" not in row_text:
                meta.company_name = row_text.strip()
        if meta.report_period is None and any(kw in row_text for kw in _METADATA_PERIOD_KEYWORDS):
            meta.report_period = row_text.strip()
        if any(kw in row_text for kw in _METADATA_CURRENCY_KEYWORDS):
            meta.currency_unit = row_text.strip()
    return meta


def _make_unique_columns(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for index, header in enumerate(headers):
        name = str(header).strip() if header and str(header).strip().lower() != "nan" else ""
        if not name:
            name = f"col_{index}"
        if name in seen:
            seen[name] += 1
            result.append(f"{name}_{seen[name]}")
        else:
            seen[name] = 0
            result.append(name)
    return result


def iter_data_row_indices(
    frame: pd.DataFrame,
    header_row_index: int,
) -> Iterator[int]:
    """
    遍历表内容区行号：跳过中间小计；表尾合计或连续空行后结束。
    """
    consecutive_empty = 0
    saw_data = False

    for idx in range(header_row_index + 1, len(frame)):
        row = frame.iloc[idx]

        if is_empty_row(row):
            consecutive_empty += 1
            if saw_data and consecutive_empty >= 2:
                break
            continue

        consecutive_empty = 0

        if is_footer_metadata_row(row):
            if saw_data:
                break
            continue

        if is_summary_row(row):
            if saw_data:
                break
            continue

        saw_data = True
        yield idx


def _sniff_text_delimiter(file_path: Path) -> str:
    """检测 CSV/文本分隔符（财务软件常导出 Tab 分隔「伪 CSV」）。"""
    from app.services.doc_parsing.charset_detection_service import sniff_text_delimiter

    return sniff_text_delimiter(file_path)


def _read_csv_raw(file_path: Path, parse_options: StructuredParseOptions | None = None) -> pd.DataFrame:
    """读取 CSV/TSV 全表：标题区常少于数据列数，需按最大列宽补齐。"""
    import csv

    from app.services.doc_parsing.structured_parse_options import (
        StructuredParseOptions,
        get_parse_options,
        resolve_csv_delimiter,
        resolve_csv_encoding,
    )

    options = parse_options or get_parse_options()
    suffix = file_path.suffix.lower()
    encoding = resolve_csv_encoding(file_path, options)
    delimiter = resolve_csv_delimiter(file_path, encoding=encoding, suffix=suffix, options=options)

    rows: list[list[str]] = []
    with file_path.open("r", encoding=encoding, errors="replace", newline="") as handle:
        for line in csv.reader(handle, delimiter=delimiter):
            if not line or not any(str(cell).strip() for cell in line):
                rows.append([])
                continue
            rows.append([str(cell).strip() for cell in line])

    if not rows:
        return pd.DataFrame()

    max_cols = max(len(row) for row in rows)
    padded = [row + [""] * (max_cols - len(row)) for row in rows]
    return pd.DataFrame(padded, dtype=str)


def read_raw_frame(path: str, parse_options: StructuredParseOptions | None = None) -> pd.DataFrame | None:
    """以 header=None 读取全表，保留标题区与真表头之前的所有行。"""
    from app.services.doc_parsing.structured_parse_options import StructuredParseOptions

    file_path = Path(path)
    suffix = file_path.suffix.lower()
    if suffix not in {".xlsx", ".xls", ".csv", ".tsv"}:
        return None
    try:
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(file_path, header=None, dtype=str)
        return _read_csv_raw(file_path, parse_options=parse_options)
    except Exception:
        return None


def resolve_structured_table(
    path: str,
    parse_options: StructuredParseOptions | None = None,
) -> StructuredTableLayout | None:
    """
    完整结构化表区域识别：元数据区 → 表头 → 表内容。

    返回带列名的 data_frame，仅含数据行（不含表尾合计行）。
    """
    raw = read_raw_frame(path, parse_options=parse_options)
    if raw is None or raw.empty:
        return None

    header_row_index = detect_header_row(raw)
    metadata = extract_table_metadata(raw, header_row_index)
    raw = forward_fill_merged_row_values(raw)
    header_row_index = detect_header_row(raw)

    raw_headers = [
        str(v).strip() if pd.notna(v) and str(v).strip().lower() != "nan" else ""
        for v in raw.iloc[header_row_index].values
    ]
    columns = _make_unique_columns(raw_headers)

    data_rows: list[list[Any]] = []
    data_row_excel_indices: list[int] = []
    for idx in iter_data_row_indices(raw, header_row_index):
        row = raw.iloc[idx]
        data_row_excel_indices.append(idx)
        data_rows.append([row.iloc[col] if col < len(row) else None for col in range(len(columns))])

    data_frame = pd.DataFrame(data_rows, columns=columns) if data_rows else pd.DataFrame(columns=columns)

    amount_color_grid: dict[tuple[int, int], str] = {}
    if data_frame.empty is False and path.lower().endswith((".xlsx", ".xlsm")):
        from app.services.doc_parsing.excel_font_amount_service import build_amount_color_grid

        amount_color_grid = build_amount_color_grid(
            path,
            row_indices=data_row_excel_indices,
            column_count=len(columns),
        )

    if not data_frame.empty:
        from app.services.doc_parsing.voucher_no_resolution import forward_fill_voucher_columns

        data_frame = forward_fill_voucher_columns(data_frame, list(data_frame.columns))

    return StructuredTableLayout(
        raw_frame=raw,
        header_row_index=header_row_index,
        metadata=metadata,
        data_frame=data_frame,
        raw_headers=raw_headers,
        data_row_excel_indices=data_row_excel_indices,
        amount_color_grid=amount_color_grid,
        source_path=path,
    )


def load_accounting_frame(
    path: str,
    parse_options: StructuredParseOptions | None = None,
) -> tuple[pd.DataFrame | None, int]:
    """兼容 file_parser_service：返回 (数据区 DataFrame, 表头行索引)。"""
    layout = resolve_structured_table(path, parse_options=parse_options)
    if layout is None:
        return None, 0
    return layout.data_frame, layout.header_row_index
