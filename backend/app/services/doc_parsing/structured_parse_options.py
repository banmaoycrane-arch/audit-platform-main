"""结构化表格（CSV/TSV）解析兼容选项：字符集、分隔符。"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from pathlib import Path
from typing import Any

AUTO = "auto"

_DELIMITER_ALIASES = {
    "comma": ",",
    "tab": "\t",
    "semicolon": ";",
    ",": ",",
    "\t": "\t",
    ";": ";",
}


@dataclass(frozen=True)
class StructuredParseOptions:
    charset: str | None = None
    delimiter: str | None = None


_current_parse_options: ContextVar[StructuredParseOptions | None] = ContextVar(
    "structured_parse_options",
    default=None,
)


def normalize_charset(value: str | None) -> str | None:
    if not value or value == AUTO:
        return None
    return value


def normalize_delimiter(value: str | None) -> str | None:
    if not value or value == AUTO:
        return None
    return _DELIMITER_ALIASES.get(value, value)


def parse_options_from_mapping(data: dict[str, Any] | None) -> StructuredParseOptions:
    if not data:
        return StructuredParseOptions()
    return StructuredParseOptions(
        charset=normalize_charset(data.get("charset")),
        delimiter=normalize_delimiter(data.get("delimiter")),
    )


def parse_options_from_job_draft(draft_data: dict[str, Any] | None) -> StructuredParseOptions:
    if not draft_data:
        return StructuredParseOptions()
    return parse_options_from_mapping(draft_data.get("parse_options"))


def parse_options_to_mapping(options: StructuredParseOptions) -> dict[str, str]:
    charset = options.charset or AUTO
    delimiter = AUTO
    if options.delimiter == ",":
        delimiter = "comma"
    elif options.delimiter == "\t":
        delimiter = "tab"
    elif options.delimiter == ";":
        delimiter = "semicolon"
    return {"charset": charset, "delimiter": delimiter}


def set_parse_options(options: StructuredParseOptions | None) -> Token:
    return _current_parse_options.set(options)


def reset_parse_options(token: Token) -> None:
    _current_parse_options.reset(token)


def get_parse_options() -> StructuredParseOptions:
    return _current_parse_options.get() or StructuredParseOptions()


def resolve_csv_encoding(file_path: Path, options: StructuredParseOptions | None = None) -> str:
    opts = options or get_parse_options()
    if opts.charset:
        return opts.charset
    from app.services.doc_parsing.charset_detection_service import detect_text_encoding

    return detect_text_encoding(file_path).get("encoding") or "utf-8"


def resolve_csv_delimiter(
    file_path: Path,
    *,
    encoding: str,
    suffix: str,
    options: StructuredParseOptions | None = None,
) -> str:
    if suffix == ".tsv":
        return "\t"
    opts = options or get_parse_options()
    if opts.delimiter:
        return opts.delimiter
    from app.services.doc_parsing.charset_detection_service import sniff_text_delimiter

    return sniff_text_delimiter(file_path, encoding=encoding)
