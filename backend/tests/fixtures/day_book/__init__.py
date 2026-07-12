"""带 5 行标题区的序时簿样例（传统财务软件导出格式）。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures" / "day_book"

PREAMBLE_ROWS = [
    ["序时账"],
    ["核算单位：示例科技有限公司"],
    ["会计期间：2026年1月"],
    ["货币单位：人民币元"],
    ["制表日期：2026-01-31"],
]

HEADER_ROW = [
    "凭证号",
    "日期",
    "摘要",
    "科目编码",
    "科目名称",
    "借方",
    "贷方",
    "对方单位",
]

DATA_ROWS = [
    ["记-001", "2026-01-03", "收到客户货款", "1002", "银行存款", "12000", "0", "客户A"],
    ["记-001", "2026-01-03", "冲减应收账款", "1122", "应收账款", "0", "12000", "客户A"],
]

FOOTER_ROWS = [
    ["合计", "", "", "", "", "12000", "12000", ""],
    ["", "", "", "", "", "", "", ""],
    ["制表人：张三", "", "", "", "", "", "", ""],
]

VOUCHER_SERPENTINE_PREAMBLE = [
    ["凭证序时簿", "", "", "", "", "", ""],
    ["2022年05月至2026年03月", "", "", "", "", "", ""],
    ["核算单位：123", "", "", "", "单位：元", "", ""],
]

VOUCHER_SERPENTINE_HEADER = [
    "凭证日期", "凭证号", "摘要", "科目", "借方金额", "贷方金额", "制单人",
]

VOUCHER_SERPENTINE_DATA = [
    ["2022-05-31", "记-0001", "2022-05-06,现金存入", "100202 银行存款_农商行", "200.00", "", "吴林玉"],
    ["", "", "2022-05-06,现金存入", "1001 库存现金", "", "200.00", ""],
    ["", "", "2022-05-06,现金存入", "1001 库存现金", "200.00", "", ""],
    ["", "", "2022-05-06,现金存入", "20011108 短期借款_股东_王林阳", "", "200.00", ""],
    ["2022-05-31", "记-0002", "2022-05-10,小额普通贷记来账,李岩", "100202 银行存款_农商行", "1,000,000.00", "", "吴林玉"],
    ["", "", "2022-05-10,小额普通贷记来账,李岩", "100202 银行存款_农商行", "500,000.00", "", ""],
]


def build_daybook_rows() -> list[list[str]]:
    width = len(HEADER_ROW)
    padded_preamble = [row + [""] * (width - len(row)) for row in PREAMBLE_ROWS]
    padded_footer = [row + [""] * (width - len(row)) for row in FOOTER_ROWS]
    return [*padded_preamble, HEADER_ROW, *DATA_ROWS, *padded_footer]


def write_daybook_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_daybook_rows()
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8-sig")
    return path


def write_daybook_xlsx(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(build_daybook_rows())
    frame.to_excel(path, index=False, header=False)
    return path


def write_merged_title_xlsx(path: Path) -> Path:
    """模拟居中标题：首行仅第一格有「序时账」，其余为空（合并单元格效果）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_daybook_rows()
    rows[0] = ["序时账", "", "", "", "", "", "", ""]
    frame = pd.DataFrame(rows)
    frame.to_excel(path, index=False, header=False)
    return path


def build_voucher_serpentine_rows() -> list[list[str]]:
    return [*VOUCHER_SERPENTINE_PREAMBLE, VOUCHER_SERPENTINE_HEADER, *VOUCHER_SERPENTINE_DATA]


def write_voucher_serpentine_xlsx(path: Path) -> Path:
    """金蝶/用友常见「凭证序时簿」导出格式（含合并单元格续行）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(build_voucher_serpentine_rows()).to_excel(path, index=False, header=False)
    return path


def write_voucher_serpentine_tsv(path: Path) -> Path:
    """Tab 分隔文本（部分软件导出为 .csv 但实际为 TSV）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["\t".join(row) for row in build_voucher_serpentine_rows()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    return path
