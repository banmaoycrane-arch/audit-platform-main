"""
会计凭证文件解析服务

支持多种格式的自适应字段映射
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.format_template import (
    STANDARD_FIELDS,
    detect_template,
    get_required_fields,
    is_valid_template,
    match_header,
)


@dataclass
class ParseResult:
    """解析结果"""
    entries: list[dict[str, Any]]
    template_name: str | None
    matched_fields: dict[str, str]
    unmatched_headers: list[str]
    total_rows: int
    success_rows: int
    error_rows: int
    quality_score: float = 0.0


@dataclass
class RowParseResult:
    """单行解析结果"""
    data: dict[str, Any]
    success: bool
    error_message: str | None = None
    missing_fields: list[str] = field(default_factory=list)


def _normalize_key(key: str) -> str:
    """标准化键名"""
    return str(key).strip().lower()


def _amount(value: Any) -> float:
    """解析金额"""
    if value is None or pd.isna(value):
        return 0.0
    try:
        s = str(value).replace(",", "").replace("¥", "").replace("$", "").strip()
        return float(s)
    except ValueError:
        return 0.0


def _date(value: Any) -> date | None:
    """解析日期"""
    if value is None or pd.isna(value):
        return None
    try:
        if isinstance(value, (datetime, date)):
            return value.date() if isinstance(value, datetime) else value
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


def _normalize_text(value: Any) -> str:
    """标准化文本"""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _detect_header_row(frame: pd.DataFrame) -> int:
    """
    检测表头行

    策略：
    1. 查找包含多个标准字段关键词的行（如"凭证"、"摘要"、"金额"）
    2. 跳过标题行（如"凭证序时簿"、"核算单位"等）
    3. 查找与其他行格式明显不同的行
    """
    for i, row in frame.iterrows():
        row_values = [str(v) for v in row.values if pd.notna(v)]
        row_str = " ".join(v.lower() for v in row_values)
        
        # 跳过明显的标题行（只包含一个值且是标题）
        if len(row_values) == 1 and len(row_values[0]) < 20:
            title_keywords = ["序时簿", "核算单位", "单位：", "年月", "报表", "台账"]
            if any(kw in row_values[0] for kw in title_keywords):
                continue
        
        # 检查是否包含多个标准字段关键词
        header_keywords = ["凭证", "摘要", "科目", "金额", "voucher", "summary", "account", "amount"]
        matched_keywords = sum(1 for kw in header_keywords if kw in row_str)
        if matched_keywords >= 2:
            return i
        
        # 检查是否为表头格式（文本较短且非空值较多）
        non_null_count = len(row_values)
        if non_null_count >= 3:
            avg_len = sum(len(v) for v in row_values) / max(non_null_count, 1)
            if avg_len < 20:
                return i
    return 0  # 默认第一行


def _parse_amount_with_sign(value: Any, debit_default: bool = True) -> tuple[float, float]:
    """解析带符号的金额"""
    amount = _amount(value)
    if amount == 0:
        return 0.0, 0.0
    if amount > 0:
        return (amount, 0.0) if debit_default else (0.0, amount)
    else:
        return (0.0, abs(amount)) if debit_default else (abs(amount), 0.0)


def _has_amount_field(headers: list[str]) -> tuple[bool, bool]:
    """检测是否有借方/贷方字段"""
    debit_keywords = ["借方", "借", "debit", "dr"]
    credit_keywords = ["贷方", "贷", "credit", "cr"]

    has_debit = any(any(kw in h.lower() for kw in debit_keywords) for h in headers)
    has_credit = any(any(kw in h.lower() for kw in credit_keywords) for h in headers)

    return has_debit, has_credit


def _infer_amount_direction(row: dict[str, Any], has_debit: bool, has_credit: bool) -> tuple[float, float]:
    """推断借贷方向"""
    debit_amount = _amount(row.get("debit_amount") or row.get("debit") or 0)
    credit_amount = _amount(row.get("credit_amount") or row.get("credit") or 0)

    # 如果有明确的借贷字段
    if has_debit or has_credit:
        return debit_amount, credit_amount

    # 从单个金额字段推断
    amount = debit_amount + credit_amount
    if amount == 0:
        return 0.0, 0.0

    # 检查是否有借或贷标记
    for key, value in row.items():
        if pd.isna(value) or _amount(value) == 0:
            continue
        key_lower = key.lower()
        if "借" in key_lower or "dr" in key_lower:
            return _amount(value), 0.0
        if "贷" in key_lower or "cr" in key_lower:
            return 0.0, _amount(value)

    return amount, 0.0  # 默认借方


def _build_mapping(frame: pd.DataFrame) -> tuple[dict[str, str], list[str]]:
    """
    构建字段映射

    Returns:
        (header_to_field, unmatched_headers)
    """
    headers = [str(h) for h in frame.columns]
    template_name, detected_mapping = detect_template(headers)

    # 构建完整映射
    mapping: dict[str, str] = {}
    unmatched: list[str] = []

    for header in headers:
        normalized = _normalize_key(header)
        matched = match_header(header)

        if matched:
            mapping[normalized] = matched
        else:
            unmatched.append(header)

    return mapping, unmatched


def _map_row(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any]:
    """映射单行数据"""
    result: dict[str, Any] = {}

    for header, value in row.items():
        normalized = _normalize_key(header)
        if normalized in mapping:
            field_name = mapping[normalized]
            result[field_name] = value

    return result


def _transform_row(row: dict[str, Any], has_debit: bool, has_credit: bool) -> dict[str, Any]:
    """转换行数据"""
    # 处理金额
    debit_amount, credit_amount = _infer_amount_direction(row, has_debit, has_credit)

    # 处理日期
    voucher_date = _date(row.get("voucher_date"))

    # 构建 normalized_text
    parts = [
        _normalize_text(row.get("summary", "")),
        _normalize_text(row.get("account_name", "")),
        _normalize_text(row.get("account_code", "")),
    ]
    if debit_amount > 0:
        parts.append(f"借{debit_amount}")
    if credit_amount > 0:
        parts.append(f"贷{credit_amount}")
    parts.append(_normalize_text(row.get("counterparty", "")))

    normalized_text = " ".join(p for p in parts if p)

    return {
        "voucher_no": _normalize_text(row.get("voucher_no")),
        "voucher_date": voucher_date,
        "summary": _normalize_text(row.get("summary", "")),
        "account_code": _normalize_text(row.get("account_code", "")),
        "account_name": _normalize_text(row.get("account_name", "")),
        "debit_amount": debit_amount,
        "credit_amount": credit_amount,
        "counterparty": _normalize_text(row.get("counterparty", "")),
        "original_row": dict(row),
        "normalized_text": normalized_text,
    }


def _validate_row(row: dict[str, Any], required_fields: list[str]) -> tuple[bool, list[str]]:
    """验证行数据"""
    missing = []
    for field_name in required_fields:
        value = row.get(field_name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field_name)
    return len(missing) == 0, missing


def parse_entries(path: str) -> ParseResult:
    """
    解析会计分录文件

    支持格式：
    - Excel (.xlsx, .xls)
    - CSV (.csv)

    Returns:
        ParseResult 包含解析结果和元数据
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix not in {".xlsx", ".xls", ".csv"}:
        return ParseResult(
            entries=[],
            template_name=None,
            matched_fields={},
            unmatched_headers=[],
            total_rows=0,
            success_rows=0,
            error_rows=0,
            quality_score=0.0,
        )

    # 读取文件
    try:
        if suffix in {".xlsx", ".xls"}:
            # 尝试自动检测表头行
            frame = pd.read_excel(file_path, header=None)
            header_row = _detect_header_row(frame)
            frame = pd.read_excel(file_path, header=header_row)
        else:
            frame = pd.read_csv(file_path, header=None)
            header_row = _detect_header_row(frame)
            frame = pd.read_csv(file_path, header=header_row)
    except Exception as e:
        return ParseResult(
            entries=[],
            template_name=None,
            matched_fields={},
            unmatched_headers=[],
            total_rows=0,
            success_rows=0,
            error_rows=0,
            quality_score=0.0,
        )

    # 构建映射
    headers = list(frame.columns)
    mapping, unmatched = _build_mapping(frame)
    template_name, _ = detect_template(headers)

    # 检测借贷字段
    has_debit, has_credit = _has_amount_field(headers)

    # 获取必填字段
    required_fields = get_required_fields(template_name or "") if template_name else ["summary", "account_name"]

    # 解析每行
    entries: list[dict[str, Any]] = []
    success_rows = 0
    error_rows = 0

    for idx, row in frame.iterrows():
        try:
            # 映射原始数据
            mapped = _map_row(row, mapping)

            # 转换格式
            transformed = _transform_row(mapped, has_debit, has_credit)

            # 验证必填字段
            is_valid, missing = _validate_row(transformed, required_fields)

            if is_valid:
                entries.append(transformed)
                success_rows += 1
            else:
                error_rows += 1
        except Exception:
            error_rows += 1

    # 计算质量分数
    total_rows = len(frame)
    quality_score = (success_rows / max(total_rows, 1)) * 100

    return ParseResult(
        entries=entries,
        template_name=template_name,
        matched_fields={v: k for k, v in mapping.items()},
        unmatched_headers=unmatched,
        total_rows=total_rows,
        success_rows=success_rows,
        error_rows=error_rows,
        quality_score=quality_score,
    )


def extract_text(path: str) -> str:
    """提取文本内容（用于原始文件）"""
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    if suffix in {".txt", ".csv"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")

    if suffix == ".pdf":
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    # 图片 OCR 支持
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
        from app.services.ocr_service import extract_text_from_image

        return extract_text_from_image(path)

    return ""
