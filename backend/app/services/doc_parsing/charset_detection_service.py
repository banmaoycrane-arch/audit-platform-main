"""文本文件编码检测（CSV/TSV 等结构化导入前置步骤）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_COMMON_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "gb2312", "big5")


def detect_text_encoding(file_path: str | Path, *, sample_size: int = 65536) -> dict[str, Any]:
    """
    检测文本文件最可能的字符集。

    优先使用 charset-normalizer；不可用时回退到常见中文/UTF 编码试探。
    """
    path = Path(file_path)
    if not path.exists() or not path.is_file():
        return {"encoding": "utf-8", "confidence": 0.0, "source": "default"}

    sample = path.read_bytes()[:sample_size]
    if not sample:
        return {"encoding": "utf-8", "confidence": 1.0, "source": "empty"}

    try:
        from charset_normalizer import from_bytes

        matches = from_bytes(sample)
        best = matches.best()
        if best and best.encoding:
            return {
                "encoding": best.encoding,
                "confidence": float(best.coherence or best.chaos or 0.0),
                "language": best.language,
                "source": "charset-normalizer",
            }
    except ImportError:
        pass

    for encoding in _COMMON_ENCODINGS:
        try:
            sample.decode(encoding)
            return {"encoding": encoding, "confidence": 0.6, "source": "fallback"}
        except UnicodeDecodeError:
            continue

    return {"encoding": "utf-8", "confidence": 0.0, "source": "fallback-default"}


def sniff_text_delimiter(
    file_path: str | Path,
    *,
    encoding: str | None = None,
    sample_size: int = 8192,
) -> str:
    """检测 CSV/文本分隔符（逗号 / Tab / 分号）。"""
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".tsv":
        return "\t"

    enc = encoding or detect_text_encoding(path).get("encoding") or "utf-8"
    sample = path.read_text(encoding=enc, errors="ignore")[:sample_size]
    lines = [line for line in sample.splitlines() if line.strip()][:15]
    tab_count = sum(line.count("\t") for line in lines)
    comma_count = sum(line.count(",") for line in lines)
    semicolon_count = sum(line.count(";") for line in lines)
    if tab_count >= max(comma_count, semicolon_count) and tab_count > 0:
        return "\t"
    if semicolon_count > comma_count and semicolon_count > 0:
        return ";"
    return ","


def delimiter_label(delimiter: str) -> str:
    return {"\t": "Tab", ",": "逗号", ";": "分号"}.get(delimiter, delimiter)
