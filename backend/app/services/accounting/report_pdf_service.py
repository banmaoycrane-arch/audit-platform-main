"""财务报表正式 PDF 导出（含编制/复核/审核签章栏）。"""
from __future__ import annotations

import io
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from app.services.accounting.report_format_standard import (
    append_trial_balance_body,
    append_balance_sheet_body,
    append_income_statement_body,
    append_cash_flow_body,
    format_money,
)

_REPORT_TITLE = {
    "trial_balance": "科目余额表",
    "balance_sheet": "资产负债表",
    "income_statement": "损益表",
    "cash_flow": "现金流量表",
}

_REVENUE_LABEL = {
    "main_business_revenue": "主营业务收入",
    "other_business_revenue": "其他业务收入",
    "investment_income": "投资收益",
    "non_operating_income": "营业外收入",
}
_EXPENSE_LABEL = {
    "main_business_cost": "主营业务成本",
    "other_business_cost": "其他业务成本",
    "selling_expenses": "销售费用",
    "admin_expenses": "管理费用",
    "financial_expenses": "财务费用",
    "asset_impairment_loss": "资产减值损失",
    "non_operating_expense": "营业外支出",
    "income_tax_expense": "所得税费用",
}


@dataclass
class ReportSignature:
    preparer_name: str = ""
    reviewer_name: str = ""
    approver_name: str = ""
    export_date: str = ""

    @classmethod
    def from_params(
        cls,
        *,
        preparer_name: str | None = None,
        reviewer_name: str | None = None,
        approver_name: str | None = None,
    ) -> ReportSignature:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return cls(
            preparer_name=(preparer_name or "").strip(),
            reviewer_name=(reviewer_name or "").strip(),
            approver_name=(approver_name or "").strip(),
            export_date=today,
        )


def _register_cjk_font() -> str:
    candidates = [
        os.environ.get("REPORT_PDF_FONT_PATH", ""),
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            try:
                pdfmetrics.registerFont(TTFont("ReportCJK", path))
                return "ReportCJK"
            except Exception:
                continue
    return "Helvetica"


def _pdf_styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle",
            parent=base["Title"],
            fontName=font_name,
            fontSize=16,
            alignment=1,
            spaceAfter=8,
        ),
        "meta": ParagraphStyle(
            "ReportMeta",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=10,
            textColor=colors.grey,
            spaceAfter=6,
        ),
        "normal": ParagraphStyle(
            "ReportNormal",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=9,
        ),
    }


def _table_style(font_name: str) -> TableStyle:
    return TableStyle([
        ("FONT", (0, 0), (-1, -1), font_name, 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
    ])


def _signature_table(signature: ReportSignature, font_name: str) -> Table:
    data = [
        ["制表人", signature.preparer_name or "____________", "", ""],
        ["负责人", signature.approver_name or "____________", "", ""],
        ["复核", signature.reviewer_name or "____________", "", ""],
    ]
    table = Table(data, colWidths=[22 * mm, 50 * mm, 20 * mm, 40 * mm])
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font_name, 9),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f5f5f5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def _paragraph_cell(text: str, font_name: str, *, font_size: int = 8, align: str = "left") -> Paragraph:
    safe = str(text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    style = ParagraphStyle(
        "ReportCell",
        fontName=font_name,
        fontSize=font_size,
        leading=font_size + 2,
        alignment={"left": 0, "center": 1, "right": 2}.get(align, 0),
    )
    return Paragraph(safe or " ", style)


def _prepare_wrapped_table(
    table_data: list[list[str]],
    font_name: str,
    *,
    wrap_cols: set[int] | None = None,
    align_right_cols: set[int] | None = None,
) -> list[list[Any]]:
    if not table_data:
        return []
    wrap_cols = wrap_cols or set()
    align_right_cols = align_right_cols or set()
    prepared: list[list[Any]] = []
    for row_idx, row in enumerate(table_data):
        prepared_row: list[Any] = []
        for col_idx, cell in enumerate(row):
            if row_idx > 0 and col_idx in wrap_cols:
                align = "right" if col_idx in align_right_cols else "left"
                prepared_row.append(_paragraph_cell(cell, font_name, align=align))
            else:
                prepared_row.append(str(cell))
        prepared.append(prepared_row)
    return prepared


def _usable_page_width(page_size: tuple[float, float], *, margin_mm: float = 36) -> float:
    return page_size[0] - margin_mm * mm


def _meta_info_table(meta_cells: list[str], font_name: str, usable_width: float) -> Table:
    cells = (meta_cells + ["", "", ""])[:3]
    table = Table([cells], colWidths=[usable_width * 0.45, usable_width * 0.35, usable_width * 0.20])
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, -1), font_name, 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.grey),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def _build_pdf(
    title: str,
    meta_lines: list[str],
    table_data: list[list[str]],
    signature: ReportSignature,
    *,
    landscape_mode: bool = False,
    col_widths: list[float] | None = None,
    meta_cells: list[str] | None = None,
    chunk_size: int | None = None,
    wrap_cols: set[int] | None = None,
    align_right_cols: set[int] | None = None,
) -> bytes:
    font_name = _register_cjk_font()
    styles = _pdf_styles(font_name)
    buffer = io.BytesIO()
    page_size = landscape(A4) if landscape_mode else A4
    usable_width = _usable_page_width(page_size)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    story: list[Any] = []
    if title:
        story.append(Paragraph(title, styles["title"]))
    if meta_cells:
        story.append(_meta_info_table(meta_cells, font_name, usable_width))
    else:
        for line in meta_lines:
            if line:
                story.append(Paragraph(line, styles["meta"]))
    story.append(Spacer(1, 6))
    if table_data:
        header = table_data[0]
        data_rows = table_data[1:]
        prepared = _prepare_wrapped_table(
            [header, *data_rows],
            font_name,
            wrap_cols=wrap_cols,
            align_right_cols=align_right_cols,
        )
        chunks = [prepared[1:]]
        if chunk_size and len(prepared) > chunk_size + 1:
            body = prepared[1:]
            chunks = [body[i : i + chunk_size] for i in range(0, len(body), chunk_size)]
        for idx, chunk in enumerate(chunks):
            if idx > 0:
                story.append(Spacer(1, 8))
                story.append(Paragraph(f"（续表 {idx + 1}）", styles["meta"]))
            table = Table([prepared[0], *chunk], colWidths=col_widths, repeatRows=1)
            style_cmds = list(_table_style(font_name).getCommands())
            if align_right_cols:
                for col in align_right_cols:
                    style_cmds.append(("ALIGN", (col, 1), (col, -1), "RIGHT"))
            if landscape_mode and len(header) >= 6:
                style_cmds.extend([
                    ("ALIGN", (1, 0), (2, -1), "RIGHT"),
                    ("ALIGN", (4, 0), (5, -1), "RIGHT"),
                ])
            table.setStyle(TableStyle(style_cmds))
            story.append(table)
    story.append(Spacer(1, 14))
    story.append(Paragraph("签章确认", styles["normal"]))
    story.append(Spacer(1, 4))
    story.append(_signature_table(signature, font_name))
    doc.build(story)
    return buffer.getvalue()


def _classic_pdf_meta(report_kind: str, report: dict[str, Any], *, ledger_name: str | None = None) -> list[str]:
    from app.services.accounting.classic_report_layout_service import classic_report_header_rows

    payload = {**report, "ledger_name": ledger_name or report.get("ledger_name")}
    rows = classic_report_header_rows(report_kind, payload)
    lines: list[str] = []
    for row in rows:
        if not row:
            continue
        if len(row) == 1:
            lines.append(row[0])
        else:
            lines.append("　　".join(str(c) for c in row))
    return lines


def _attach_signature(report: dict[str, Any], signature: ReportSignature) -> dict[str, Any]:
    payload = dict(report)
    payload["signature"] = {
        "preparer_name": signature.preparer_name,
        "reviewer_name": signature.reviewer_name,
        "approver_name": signature.approver_name,
    }
    return payload


def _pdf_meta_lines(
    report: dict[str, Any],
    *,
    ledger_name: str | None = None,
    period_code: str = "",
    extra: list[str] | None = None,
) -> list[str]:
    lines = [
        f"编制单位：{ledger_name or report.get('ledger_name') or '—'}",
        f"会计期间：{period_code or report.get('period_code') or '—'}",
        f"截止日：{report.get('as_of_date') or '—'}",
        "币种：人民币    金额单位：元",
    ]
    if extra:
        lines.extend(extra)
    return lines


def _report_pdf_meta(report_kind: str, report: dict[str, Any], *, ledger_name: str | None = None, period_code: str = "") -> list[str]:
    if report.get("format", "").startswith("classic"):
        return _classic_pdf_meta(report_kind, report, ledger_name=ledger_name)
    return _pdf_meta_lines(report, ledger_name=ledger_name, period_code=period_code)


def _build_trial_balance_pdf(
    title: str,
    meta_lines: list[str],
    table_data: list[list[str]],
    signature: ReportSignature,
) -> bytes:
    """科目余额表 PDF：横向 A4 + 分页表格，适配十列数据。"""
    font_name = _register_cjk_font()
    styles = _pdf_styles(font_name)
    buffer = io.BytesIO()
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
    )
    story: list[Any] = [Paragraph(title, styles["title"])]
    for line in meta_lines:
        story.append(Paragraph(line, styles["meta"]))
    story.append(Spacer(1, 4))

    if table_data:
        header = table_data[0]
        data_rows = table_data[1:]
        chunk_size = 32
        col_count = len(header)
        usable = page_size[0] - 24 * mm
        code_w, name_w = 16 * mm, 34 * mm
        cat_w = 14 * mm
        amount_cols = max(col_count - 3, 1)
        amount_w = (usable - code_w - name_w - cat_w) / amount_cols
        col_widths = [code_w, name_w, cat_w] + [amount_w] * amount_cols

        for i in range(0, max(len(data_rows), 1), chunk_size):
            chunk = data_rows[i : i + chunk_size]
            if i > 0:
                story.append(Spacer(1, 8))
                story.append(Paragraph(f"（续表 {i // chunk_size + 1}）", styles["meta"]))
            table = Table([header, *chunk], colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                ("FONT", (0, 0), (-1, -1), font_name, 7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
            ]))
            story.append(table)

    story.append(Spacer(1, 10))
    story.append(Paragraph("签章确认", styles["normal"]))
    story.append(Spacer(1, 4))
    story.append(_signature_table(signature, font_name))
    doc.build(story)
    return buffer.getvalue()


def trial_balance_to_pdf(report: dict[str, Any], signature: ReportSignature, *, ledger_name: str | None = None) -> bytes:
    body_rows: list[list[Any]] = []
    append_trial_balance_body(body_rows, report)
    rows = [body_rows[0]] + [[str(c) for c in row] for row in body_rows[1:]]
    meta = _pdf_meta_lines(
        report,
        ledger_name=ledger_name,
        extra=[f"平衡校验：{'通过' if report.get('is_balanced') else '未通过'}"],
    )
    return _build_trial_balance_pdf(_REPORT_TITLE["trial_balance"], meta, rows, signature)


def _classic_pdf_title_and_meta(report_kind: str, report: dict[str, Any], *, ledger_name: str | None = None) -> tuple[str, list[str]]:
    from app.services.accounting.classic_report_layout_service import classic_report_header_rows

    payload = {**report, "ledger_name": ledger_name or report.get("ledger_name")}
    rows = classic_report_header_rows(report_kind, payload)
    title = rows[0][0] if rows and rows[0] else _REPORT_TITLE.get(report_kind, "财务报表")
    meta_cells = list(rows[1]) if len(rows) > 1 and rows[1] else []
    return title, meta_cells


def _portrait_col_widths(col_count: int, ratios: list[float], page_size: tuple[float, float] | None = None) -> list[float]:
    page_size = page_size or A4
    usable = _usable_page_width(page_size)
    total = sum(ratios[:col_count]) or 1
    return [usable * (ratio / total) for ratio in ratios[:col_count]]


def balance_sheet_to_pdf(report: dict[str, Any], signature: ReportSignature, *, ledger_name: str | None = None) -> bytes:
    payload = _attach_signature(report, signature)
    body_rows: list[list[Any]] = []
    append_balance_sheet_body(body_rows, payload)
    rows = [body_rows[0]] + [[str(c) for c in row] for row in body_rows[1:]]
    if payload.get("format", "").startswith("classic"):
        title, meta_cells = _classic_pdf_title_and_meta("balance_sheet", payload, ledger_name=ledger_name)
        col_widths = _portrait_col_widths(6, [0.22, 0.11, 0.11, 0.22, 0.11, 0.11], landscape(A4))
        return _build_pdf(
            title,
            [],
            rows,
            signature,
            landscape_mode=True,
            col_widths=col_widths,
            meta_cells=meta_cells,
            chunk_size=26,
            wrap_cols={0, 3},
            align_right_cols={1, 2, 4, 5},
        )
    meta = _pdf_meta_lines(
        payload,
        ledger_name=ledger_name,
        extra=[
            f"资产合计 {payload.get('assets_total', '')} = 负债 {payload.get('liabilities_total', '')} + 权益 {payload.get('equity_total', '')}",
        ],
    )
    return _build_pdf(_REPORT_TITLE["balance_sheet"], meta, rows, signature)


def income_statement_to_pdf(
    report: dict[str, Any],
    signature: ReportSignature,
    *,
    period_code: str = "",
    ledger_name: str | None = None,
) -> bytes:
    payload = _attach_signature(report, signature)
    body_rows: list[list[Any]] = []
    append_income_statement_body(body_rows, payload)
    rows = [body_rows[0]] + [[str(c) for c in row] for row in body_rows[1:]]
    if payload.get("format", "").startswith("classic"):
        title, meta_cells = _classic_pdf_title_and_meta("income_statement", payload, ledger_name=ledger_name)
        col_widths = _portrait_col_widths(4, [0.48, 0.10, 0.21, 0.21])
        return _build_pdf(
            title,
            [],
            rows,
            signature,
            col_widths=col_widths,
            meta_cells=meta_cells,
            wrap_cols={0},
            align_right_cols={2, 3},
        )
    meta = _pdf_meta_lines(payload, ledger_name=ledger_name, period_code=period_code, extra=[f"净利润：{format_money(payload.get('net_profit'))}"])
    return _build_pdf(_REPORT_TITLE["income_statement"], meta, rows, signature)


def cash_flow_to_pdf(
    report: dict[str, Any],
    signature: ReportSignature,
    *,
    period_code: str = "",
    ledger_name: str | None = None,
) -> bytes:
    payload = _attach_signature(report, signature)
    body_rows: list[list[Any]] = []
    append_cash_flow_body(body_rows, payload)
    rows = [body_rows[0]] + [[str(c) for c in row] for row in body_rows[1:]]
    if payload.get("format", "").startswith("classic"):
        title, meta_cells = _classic_pdf_title_and_meta("cash_flow", payload, ledger_name=ledger_name)
        col_widths = _portrait_col_widths(4, [0.48, 0.10, 0.21, 0.21])
        return _build_pdf(
            title,
            [],
            rows,
            signature,
            col_widths=col_widths,
            meta_cells=meta_cells,
            chunk_size=30,
            wrap_cols={0},
            align_right_cols={2, 3},
        )
    meta = _pdf_meta_lines(payload, ledger_name=ledger_name, period_code=period_code, extra=["口径：简化直接法"])
    return _build_pdf(_REPORT_TITLE["cash_flow"], meta, rows, signature)


PDF_BUILDERS = {
    "trial_balance": trial_balance_to_pdf,
    "balance_sheet": balance_sheet_to_pdf,
    "income_statement": income_statement_to_pdf,
    "cash_flow": cash_flow_to_pdf,
}
