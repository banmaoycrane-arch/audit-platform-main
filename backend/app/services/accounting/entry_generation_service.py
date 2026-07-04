"""自动生成会计分录引擎。

关键规则：
- 凭证字（银/收/付/工/转/记）来自原始证据类型 + 摘要关键词。
- 凭证日期被夹紧到所选会计期间内。
- 摘要根据「凭证字 + 主科目 + 对方单位 + 业务关键词」拼装。
- 对方单位语义：借方记账 = 来源方；贷方记账 = 去向方；多行不复制。
- 二级科目（如增值税进项/销项）改为 EntryTag 表达。
"""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.services.accounting import voucher_service
from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    EntryTag,
    ImportJob,
    SourceFile,
)


EVIDENCE_TYPE_DEFINITIONS: dict[str, dict[str, str]] = {
    "invoice": {"label": "发票", "role": "证明开票事实、税额和应收/应付金额"},
    "bank": {"label": "银行流水", "role": "证明资金收付事实和银行账户变动"},
    "receipt": {"label": "收款/付款回单", "role": "证明单笔资金收付已发生"},
    "contract": {"label": "合同", "role": "证明交易背景、业务性质和权利义务"},
    "order": {"label": "订单", "role": "证明交易发起、客户/供应商和商品服务内容"},
    "settlement": {"label": "结算单", "role": "证明双方确认的结算金额和结算期间"},
    "inventory_in": {"label": "入库单", "role": "证明采购或生产入库事实"},
    "inventory_out": {"label": "出库单", "role": "证明销售或领用出库事实"},
}

EVIDENCE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "invoice": ("invoice", "发票", "开票", "增值税"),
    "bank": ("bank_statement", "bank", "银行流水", "流水", "对账单", "银行对账", "网银"),
    "receipt": ("receipt", "回单", "收款回单", "付款回单", "银行回单", "收据"),
    "contract": ("contract", "合同", "协议"),
    "order": ("order", "订单", "采购单", "销售单"),
    "settlement": ("settlement", "结算单", "结算"),
    "inventory_in": ("inventory_in", "入库单", "入库"),
    "inventory_out": ("inventory_out", "出库单", "出库"),
}

ACCOUNTING_JUDGMENT_POLICIES: dict[str, str] = {
    "compliant_default": "默认合规（谨慎）：有出库单先确认收入，发票主要确认销项税",
    "revenue_first": "收入确认优先：出库/履约时点优先确认收入，发票补齐税额",
    "counterparty_first": "往来确认优先：发票优先挂应收/冲预收，再匹配收款与出库",
}

OUTPUT_VAT_ACCOUNT = ("22210107", "应交税费-应交增值税-销项税额")
REVENUE_ACCOUNT = ("6001", "主营业务收入")
AR_ACCOUNT = ("1122", "应收账款")
PREPAID_REVENUE_ACCOUNT = ("2203", "预收账款")


ACCOUNT_RECOGNITION_RULES: list[dict[str, Any]] = [
    {"keywords": ("收入", "销售", "服务费", "服务费收入", "咨询费"), "code": "6001", "name": "主营业务收入", "category": "profit"},
    {"keywords": ("采购", "进货", "供应商", "应付"), "code": "2202", "name": "应付账款", "category": "liability"},
    {"keywords": ("应收", "客户", "应收账款"), "code": "1122", "name": "应收账款", "category": "asset"},
    {"keywords": ("工资", "薪酬", "社保", "公积金"), "code": "2211", "name": "应付职工薪酬", "category": "liability"},
    {"keywords": ("税", "增值税", "销项", "进项", "税额"), "code": "2221", "name": "应交税费", "category": "liability"},
    {"keywords": ("费用", "报销", "差旅费", "办公费"), "code": "6602", "name": "管理费用", "category": "profit"},
    {"keywords": ("销售费用", "广告费", "促销"), "code": "6601", "name": "销售费用", "category": "profit"},
    {"keywords": ("成本", "主营业务成本"), "code": "6401", "name": "主营业务成本", "category": "profit"},
    {"keywords": ("利息", "财务费用"), "code": "6603", "name": "财务费用", "category": "profit"},
    {"keywords": ("现金", "库存现金"), "code": "1001", "name": "库存现金", "category": "asset"},
    {"keywords": ("银行", "银行存款"), "code": "1002", "name": "银行存款", "category": "asset"},
    {"keywords": ("固定资产", "设备", "机器"), "code": "1601", "name": "固定资产", "category": "asset"},
    {"keywords": ("折旧", "累计折旧"), "code": "1602", "name": "累计折旧", "category": "asset"},
    {"keywords": ("借款", "贷款"), "code": "2001", "name": "短期借款", "category": "liability"},
    {"keywords": ("预收", "预收账款"), "code": "2203", "name": "预收账款", "category": "liability"},
    {"keywords": ("预付", "预付账款"), "code": "1123", "name": "预付账款", "category": "asset"},
    {"keywords": ("其他应收", "备用金"), "code": "1221", "name": "其他应收款", "category": "asset"},
    {"keywords": ("其他应付", "押金", "保证金"), "code": "2241", "name": "其他应付款", "category": "liability"},
    {"keywords": ("投资", "投资收益"), "code": "6111", "name": "投资收益", "category": "profit"},
    {"keywords": ("营业外", "捐赠"), "code": "6301", "name": "营业外收入", "category": "profit"},
]


def _recognize_account_from_text(text: str) -> tuple[str, str] | tuple[None, None]:
    """
    功能描述：从提取的文本中识别会计科目
    业务逻辑：按优先级匹配关键词，返回第一个匹配的科目代码和名称
    会计口径：基于常见业务关键词与一级科目的映射规则

    Args:
        text: 提取的文本内容

    Returns:
        tuple[str, str] | tuple[None, None]: (科目代码, 科目名称) 或 (None, None)

    注意事项：
        1. 匹配顺序按优先级排列，先匹配更具体的关键词
        2. 匹配是大小写不敏感的
    """
    if not text:
        return None, None
    text_lower = text.lower()
    for rule in ACCOUNT_RECOGNITION_RULES:
        if any(keyword.lower() in text_lower for keyword in rule["keywords"]):
            return rule["code"], rule["name"]
    return None, None


def _voucher_prefix(account_name: str | None, summary: str | None, file_type: str | None) -> str:
    """按规则推荐凭证字。"""
    text = f"{summary or ''} {file_type or ''} {account_name or ''}"
    if any(k in text for k in ("银行", "回单", "对账", "汇款")) or (file_type or "").lower() in {
        "bank_statement",
        "bank",
    }:
        return "银"
    if any(k in (account_name or "") for k in ("库存现金",)):
        return "收"  # 默认借方收，贷方调用方覆盖
    if any(k in (summary or "") for k in ("工资", "薪酬", "社保")):
        return "工"
    if any(k in (summary or "") for k in ("计提", "折旧", "摊销", "结转", "内部转账")):
        return "转"
    return "记"


def _clamp_date(target: date | None, period: AccountingPeriod) -> tuple[date, bool]:
    if target is None:
        return period.start_date, True
    if target < period.start_date:
        return period.start_date, True
    if target > period.end_date:
        return period.end_date, True
    return target, False


def _format_summary(prefix: str, account_name: str | None, counterparty: str | None, original: str | None) -> str:
    parts: list[str] = []
    action_map = {"银": "银行收付", "收": "现金收讫", "付": "现金支付", "工": "工资计提", "转": "结转", "记": "记账"}
    parts.append(action_map.get(prefix, "记账"))
    if counterparty:
        parts.append(counterparty)
    if account_name:
        parts.append(account_name)
    if original and original.strip():
        parts.append(original.strip())
    return " ".join(p for p in parts if p)


def _add_tag(
    tags: list[dict[str, Any]],
    seen: set[tuple[str, str]],
    tag_type: str,
    tag_value: Any,
    tag_source: str = "rule",
    confidence: float = 0.8,
) -> None:
    value = str(tag_value).strip() if tag_value is not None else ""
    if not value:
        return
    key = (tag_type, value)
    if key in seen:
        return
    seen.add(key)
    tags.append(
        {
            "tag_type": tag_type,
            "tag_value": value,
            "tag_source": tag_source,
            "confidence": confidence,
        }
    )


def _extract_tags(entry_data: dict[str, Any]) -> list[dict[str, Any]]:
    """从分录数据中识别二级语义 → EntryTag 候选。"""
    tags: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    summary = (entry_data.get("summary") or "")
    account = (entry_data.get("account_name") or "")
    account_code = (entry_data.get("account_code") or "")
    counterparty = entry_data.get("counterparty")
    metadata = entry_data.get("metadata") or {}

    if "应交税费" in account:
        if "销项" in summary or "销项" in account:
            _add_tag(tags, seen, "tax_subitem", "销项税额")
        elif "进项" in summary or "进项" in account:
            _add_tag(tags, seen, "tax_subitem", "进项税额")
    if "应付职工薪酬" in account:
        if "社保" in summary or "社保" in account:
            _add_tag(tags, seen, "payroll_subitem", "社保")
        elif "工资" in summary or "工资" in account:
            _add_tag(tags, seen, "payroll_subitem", "工资")
    if counterparty:
        _add_tag(tags, seen, "counterparty", counterparty, confidence=0.9)

    for keyword in ("工资", "薪酬", "社保", "公积金", "货款", "采购", "销售", "服务费", "租金", "报销", "差旅", "合同", "订单", "结算", "增值税", "销项", "进项"):
        if keyword in summary:
            _add_tag(tags, seen, "summary_keyword", keyword, confidence=0.7)

    for separator in ("-", "—", "_", "/", "\\", "·", ":", "："):
        if separator in account:
            account_parts = [part.strip() for part in account.split(separator) if part.strip()]
            for detail in account_parts[1:]:
                _add_tag(tags, seen, "account_detail_semantic", detail, confidence=0.85)
            break
    if account_code and len(account_code.strip()) > 4:
        _add_tag(tags, seen, "account_detail_semantic", f"{account}:{account_code}", confidence=0.75)

    for key in ("department", "project", "customer", "supplier", "employee"):
        auxiliary_value = entry_data.get(key) or metadata.get(key)
        if auxiliary_value:
            _add_tag(tags, seen, "auxiliary_accounting", f"{key}:{auxiliary_value}", confidence=0.85)

    source_file_id = entry_data.get("source_file_id") or metadata.get("source_file_id")
    if source_file_id:
        _add_tag(tags, seen, "source_file", f"source_file:{source_file_id}", confidence=1.0)
    source_entry_id = entry_data.get("source_entry_id") or metadata.get("source_entry_id")
    if source_entry_id:
        _add_tag(tags, seen, "source_document", f"source_entry:{source_entry_id}", confidence=1.0)

    evidence_type = metadata.get("source_evidence_type") or entry_data.get("evidence_type")
    if evidence_type:
        _add_tag(tags, seen, "evidence_type", evidence_type, confidence=0.9)
    for evidence in metadata.get("current_recognized_evidence") or []:
        if not isinstance(evidence, dict):
            continue
        if evidence.get("id"):
            _add_tag(tags, seen, "source_file", f"source_file:{evidence['id']}", confidence=1.0)
        if evidence.get("filename"):
            _add_tag(tags, seen, "source_document", evidence["filename"], confidence=0.9)
        if evidence.get("evidence_type") and evidence.get("evidence_type") != "unknown":
            _add_tag(tags, seen, "evidence_type", evidence["evidence_type"], confidence=0.9)
    return tags


def _normalize_evidence_type(source_file: SourceFile) -> str | None:
    extracted_text = source_file.extracted_text or ""
    try:
        parsed_text = json.loads(extracted_text)
        if isinstance(parsed_text, dict):
            parse_feedback = parsed_text.get("parse_feedback")
            if isinstance(parse_feedback, dict):
                document_type = parse_feedback.get("document_type")
                if document_type == "bank_statement":
                    return "bank"
                if document_type == "inventory":
                    return "inventory_in"
                if document_type and document_type != "unknown":
                    return str(document_type)
    except json.JSONDecodeError:
        pass

    text = f"{source_file.file_type or ''} {source_file.filename or ''} {extracted_text}".lower()
    for evidence_type, keywords in EVIDENCE_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            return evidence_type
    return None


def _build_evidence_context(files: list[SourceFile]) -> dict[str, Any]:
    evidence_types: set[str] = set()
    source_files: list[dict[str, Any]] = []
    for source_file in files:
        evidence_type = _normalize_evidence_type(source_file)
        if evidence_type:
            evidence_types.add(evidence_type)
        source_files.append(
            {
                "id": source_file.id,
                "filename": source_file.filename,
                "file_type": source_file.file_type,
                "evidence_type": evidence_type or "unknown",
            }
        )
    return {
        "evidence_types": sorted(evidence_types),
        "source_files": source_files,
        "evidence_definitions": EVIDENCE_TYPE_DEFINITIONS,
    }


def _normalize_accounting_judgment_policy(policy: str | None) -> str:
    normalized = (policy or "compliant_default").strip()
    if normalized not in ACCOUNTING_JUDGMENT_POLICIES:
        return "compliant_default"
    return normalized


def _invoice_is_purchase(combined_text: str) -> bool:
    return any(keyword in combined_text for keyword in ("采购", "进项", "应付", "供应商"))


def _invoice_has_prepaid_signal(combined_text: str) -> bool:
    return any(keyword in combined_text for keyword in ("预收", "预收款", "预收账款", "冲预收"))


def _should_invoice_confirm_vat_only(
    *,
    has_outbound: bool,
    policy: str,
) -> bool:
    """有出库单时，收入可能已在出库确认，发票默认仅补销项税（谨慎合规）。"""
    if not has_outbound:
        return False
    return policy in {"compliant_default", "revenue_first"}


def _resolve_invoice_debit_account(combined_text: str, policy: str) -> tuple[str, str, str]:
    """确定发票借方科目：应收或冲减预收。"""
    if _invoice_is_purchase(combined_text):
        return "2202", "应付账款", "确认应付"
    if policy == "counterparty_first":
        return AR_ACCOUNT[0], AR_ACCOUNT[1], "确认应收"
    if _invoice_has_prepaid_signal(combined_text):
        return PREPAID_REVENUE_ACCOUNT[0], PREPAID_REVENUE_ACCOUNT[1], "冲减预收"
    return AR_ACCOUNT[0], AR_ACCOUNT[1], "确认应收"


def _check_evidence_sufficiency(
    files: list[SourceFile],
    accounting_judgment_policy: str = "compliant_default",
) -> dict[str, Any]:
    """判断导入任务级证据状态。

    会计口径：
    - 仅有发票：权责发生制暂存（应收 + 收入），收款未确认，允许落库为 draft。
    - 发票 + 银行流水：先走开票挂应收，再走收款核销应收（不得发票直连银行存款）。
    - 仅有流水：仍须补充合同/订单等业务单据。
    """
    context = _build_evidence_context(files)
    evidence_types = set(context["evidence_types"])
    has_invoice = "invoice" in evidence_types
    has_outbound = "inventory_out" in evidence_types
    has_bank_or_receipt = bool({"bank", "receipt"} & evidence_types)
    has_business_document = bool({"contract", "order", "settlement"} & evidence_types)
    policy = _normalize_accounting_judgment_policy(accounting_judgment_policy)
    policy_note = ACCOUNTING_JUDGMENT_POLICIES[policy]

    base = context | {
        "accounting_judgment_policy": policy,
        "accounting_judgment_note": policy_note,
        "has_outbound": has_outbound,
    }

    if has_invoice and has_outbound and not has_bank_or_receipt:
        return base | {
            "evidence_status": "partial",
            "is_blocked": False,
            "accounting_flow": "outbound_revenue_then_invoice_tax",
            "missing_evidence": ["银行流水", "收款回单/付款回单"],
            "missing_reason": (
                "已识别出库单与发票。按所选会计判断原则，收入可能在出库确认、发票补销项税；"
                "收款尚未确认，不得直接确认银行存款。"
            ),
            "suggested_actions": [
                "请确认会计判断原则（合规/收入优先/往来优先）",
                "请补充银行流水以核销应收",
                "如收入已在出库确认，请复核发票是否仅需补销项税",
            ],
        }

    if has_invoice and not has_bank_or_receipt:
        return base | {
            "evidence_status": "partial",
            "is_blocked": False,
            "accounting_flow": "accrual_only",
            "missing_evidence": ["银行流水", "收款回单/付款回单"],
            "missing_reason": (
                "当前识别到发票。系统将按原则生成收入/销项税/应收（或冲减预收）草案，"
                "收款尚未确认，不得直接确认银行存款。"
            ),
            "suggested_actions": [
                "请确认会计判断原则（合规/收入优先/往来优先）",
                "请补充银行流水以确认收款并核销应收",
                "如有出库单请一并上传，以区分收入与销项税确认时点",
            ],
        }

    if has_bank_or_receipt and not has_invoice and not has_business_document:
        return base | {
            "evidence_status": "insufficient",
            "is_blocked": True,
            "accounting_flow": "blocked",
            "missing_evidence": ["合同", "订单", "结算单"],
            "missing_reason": "当前仅能识别到银行流水/回单。流水可证明资金收付，但不能单独证明业务性质、交易内容和收入成本归类。",
            "suggested_actions": ["请补充合同", "请补充订单", "请补充结算单"],
        }

    if has_invoice and has_bank_or_receipt:
        return base | {
            "evidence_status": "sufficient",
            "is_blocked": False,
            "accounting_flow": "accrual_then_collection",
            "missing_evidence": [],
            "missing_reason": "",
            "suggested_actions": [],
        }

    if has_bank_or_receipt and has_business_document:
        return base | {
            "evidence_status": "sufficient",
            "is_blocked": False,
            "accounting_flow": "business_then_cash",
            "missing_evidence": [],
            "missing_reason": "",
            "suggested_actions": [],
        }

    return base | {
        "evidence_status": "insufficient",
        "is_blocked": True,
        "accounting_flow": "blocked",
        "missing_evidence": ["发票", "银行流水", "合同/订单/结算单"],
        "missing_reason": "当前原始资料不足以同时证明交易发生、业务性质和资金收付，AI 只能暂存草稿，不能直接落库。",
        "suggested_actions": ["请补充发票、银行流水或回单", "请补充合同、订单或结算单"],
    }


def _merge_evidence_metadata(metadata: dict[str, Any], evidence_check: dict[str, Any]) -> dict[str, Any]:
    return metadata | {
        "evidence_status": evidence_check["evidence_status"],
        "accounting_flow": evidence_check.get("accounting_flow"),
        "missing_evidence": evidence_check["missing_evidence"],
        "missing_reason": evidence_check["missing_reason"],
        "current_recognized_evidence": evidence_check["source_files"],
        "evidence_definitions": evidence_check["evidence_definitions"],
        "suggested_actions": evidence_check["suggested_actions"],
        "is_blocked": evidence_check["is_blocked"],
    }


def _draft_line(
    *,
    voucher_no: str,
    entry_line_no: int,
    voucher_date: date,
    account_code: str,
    account_name: str,
    summary: str,
    debit_amount: float = 0.0,
    credit_amount: float = 0.0,
    counterparty: str | None = None,
    source_file_id: int | None = None,
    evidence_type: str | None = None,
    metadata: dict[str, Any],
    posting_phase: str | None = None,
) -> dict[str, Any]:
    line_metadata = dict(metadata)
    if posting_phase:
        line_metadata["posting_phase"] = posting_phase
    tags = _extract_tags(
        {
            "summary": summary,
            "account_code": account_code,
            "account_name": account_name,
            "counterparty": counterparty,
            "source_file_id": source_file_id,
            "metadata": line_metadata,
            "evidence_type": evidence_type,
        }
    )
    if posting_phase:
        tags.append(
            {
                "tag_type": "posting_phase",
                "tag_value": posting_phase,
                "tag_source": "rule",
                "confidence": 0.95,
            }
        )
    draft: dict[str, Any] = {
        "source_file_id": source_file_id,
        "voucher_no": voucher_no,
        "voucher_date": voucher_date.isoformat(),
        "account_code": account_code,
        "account_name": account_name,
        "summary": summary,
        "debit_amount": debit_amount,
        "credit_amount": credit_amount,
        "counterparty": counterparty,
        "entry_line_no": entry_line_no,
        "metadata": line_metadata,
        "tags": tags,
    }
    return draft


def _extract_amount_from_text(text: str) -> tuple[Decimal, Decimal]:
    """从文本中提取金额和税额。"""
    import re
    amount = Decimal("0.00")
    tax_amount = Decimal("0.00")

    amount_match = re.search(r"金额[：:]?\s*([\d,]+(?:\.\d+)?)", text)
    if amount_match:
        amount = Decimal(amount_match.group(1).replace(",", ""))

    tax_match = re.search(r"税额[：:]?\s*([\d,]+(?:\.\d+)?)", text)
    if tax_match:
        tax_amount = Decimal(tax_match.group(1).replace(",", ""))

    total_match = re.search(r"(?:价税合计|合计)[：:]?\s*([\d,]+(?:\.\d+)?)", text)
    if total_match and amount == Decimal("0.00"):
        amount = Decimal(total_match.group(1).replace(",", ""))

    return amount, tax_amount


def _build_invoice_sales_drafts(
    source_file: SourceFile,
    seq: int,
    period: AccountingPeriod,
    evidence_check: dict[str, Any],
    policy: str,
) -> list[dict[str, Any]]:
    """销售发票：借应收/冲预收 + 贷收入 + 贷销项税。"""
    voucher_date, clamped = _clamp_date(period.start_date, period)
    voucher_no = f"转-{seq:03d}"
    combined_text = f"{source_file.filename or ''} {source_file.extracted_text or ''}"
    if _invoice_is_purchase(combined_text):
        return _build_invoice_purchase_drafts(source_file, seq, period, evidence_check, policy)

    revenue_amount, tax_amount = _extract_amount_from_text(combined_text)
    if revenue_amount == Decimal("0.00"):
        revenue_amount = Decimal("1000.00")
        tax_amount = Decimal("130.00")

    debit_code, debit_name, debit_action = _resolve_invoice_debit_account(combined_text, policy)
    base_metadata = _merge_evidence_metadata(
        {
            "date_clamped": clamped,
            "vector_pending": True,
            "source_evidence_type": "invoice",
            "source_file_id": source_file.id,
            "accounting_judgment_policy": policy,
            "revenue_recognition_point": "invoice",
        },
        evidence_check,
    )
    summary_base = _format_summary("转", REVENUE_ACCOUNT[1], None, source_file.filename)
    return [
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=1,
            voucher_date=voucher_date,
            account_code=debit_code,
            account_name=debit_name,
            summary=f"{summary_base} {debit_action}",
            debit_amount=float(revenue_amount + tax_amount),
            source_file_id=source_file.id,
            evidence_type="invoice",
            metadata=base_metadata,
            posting_phase="accrual",
        ),
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=2,
            voucher_date=voucher_date,
            account_code=REVENUE_ACCOUNT[0],
            account_name=REVENUE_ACCOUNT[1],
            summary=f"{summary_base} 确认收入",
            credit_amount=float(revenue_amount),
            source_file_id=source_file.id,
            evidence_type="invoice",
            metadata=base_metadata,
            posting_phase="accrual",
        ),
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=3,
            voucher_date=voucher_date,
            account_code=OUTPUT_VAT_ACCOUNT[0],
            account_name=OUTPUT_VAT_ACCOUNT[1],
            summary=f"{summary_base} 确认销项税额",
            credit_amount=float(tax_amount),
            source_file_id=source_file.id,
            evidence_type="invoice",
            metadata=base_metadata,
            posting_phase="tax_invoice",
        ),
    ]


def _build_invoice_purchase_drafts(
    source_file: SourceFile,
    seq: int,
    period: AccountingPeriod,
    evidence_check: dict[str, Any],
    policy: str,
) -> list[dict[str, Any]]:
    """采购发票：借成本/费用 + 进项税 + 贷应付。"""
    voucher_date, clamped = _clamp_date(period.start_date, period)
    voucher_no = f"转-{seq:03d}"
    base_metadata = _merge_evidence_metadata(
        {
            "date_clamped": clamped,
            "vector_pending": True,
            "source_evidence_type": "invoice",
            "source_file_id": source_file.id,
            "accounting_judgment_policy": policy,
            "revenue_recognition_point": "invoice",
        },
        evidence_check,
    )
    summary_base = _format_summary("转", "应付账款", None, source_file.filename)
    return [
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=1,
            voucher_date=voucher_date,
            account_code="6401",
            account_name="主营业务成本",
            summary=f"{summary_base} 确认采购成本",
            source_file_id=source_file.id,
            evidence_type="invoice",
            metadata=base_metadata,
            posting_phase="accrual",
        ),
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=2,
            voucher_date=voucher_date,
            account_code="22210101",
            account_name="应交税费-应交增值税-进项税额",
            summary=f"{summary_base} 确认进项税额",
            source_file_id=source_file.id,
            evidence_type="invoice",
            metadata=base_metadata,
            posting_phase="tax_invoice",
        ),
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=3,
            voucher_date=voucher_date,
            account_code="2202",
            account_name="应付账款",
            summary=f"{summary_base} 确认应付",
            source_file_id=source_file.id,
            evidence_type="invoice",
            metadata=base_metadata,
            posting_phase="accrual",
        ),
    ]


def _build_invoice_vat_only_drafts(
    source_file: SourceFile,
    seq: int,
    period: AccountingPeriod,
    evidence_check: dict[str, Any],
    policy: str,
) -> list[dict[str, Any]]:
    """发票在出库后补开：默认仅确认销项税，收入已在出库确认。"""
    voucher_date, clamped = _clamp_date(period.start_date, period)
    voucher_no = f"转-{seq:03d}"
    debit_code, debit_name, debit_action = _resolve_invoice_debit_account(
        f"{source_file.filename or ''} {source_file.extracted_text or ''}",
        policy,
    )
    base_metadata = _merge_evidence_metadata(
        {
            "date_clamped": clamped,
            "vector_pending": True,
            "source_evidence_type": "invoice",
            "source_file_id": source_file.id,
            "accounting_judgment_policy": policy,
            "revenue_recognition_point": "outbound",
            "invoice_role": "vat_only_after_outbound",
        },
        evidence_check,
    )
    summary_base = _format_summary("转", OUTPUT_VAT_ACCOUNT[1], None, source_file.filename)
    return [
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=1,
            voucher_date=voucher_date,
            account_code=debit_code,
            account_name=debit_name,
            summary=f"{summary_base} {debit_action}（价税分离-税额部分）",
            source_file_id=source_file.id,
            evidence_type="invoice",
            metadata=base_metadata,
            posting_phase="tax_invoice",
        ),
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=2,
            voucher_date=voucher_date,
            account_code=OUTPUT_VAT_ACCOUNT[0],
            account_name=OUTPUT_VAT_ACCOUNT[1],
            summary=f"{summary_base} 补确认销项税额",
            source_file_id=source_file.id,
            evidence_type="invoice",
            metadata=base_metadata,
            posting_phase="tax_invoice",
        ),
    ]


def _build_outbound_revenue_drafts(
    source_file: SourceFile,
    seq: int,
    period: AccountingPeriod,
    evidence_check: dict[str, Any],
    policy: str,
) -> list[dict[str, Any]]:
    """出库单：按收入确认优先/合规原则，在出库时点确认收入与应收。"""
    voucher_date, clamped = _clamp_date(period.start_date, period)
    voucher_no = f"转-{seq:03d}"
    base_metadata = _merge_evidence_metadata(
        {
            "date_clamped": clamped,
            "vector_pending": True,
            "source_evidence_type": "inventory_out",
            "source_file_id": source_file.id,
            "accounting_judgment_policy": policy,
            "revenue_recognition_point": "outbound",
        },
        evidence_check,
    )
    summary_base = _format_summary("转", REVENUE_ACCOUNT[1], None, source_file.filename)
    lines = [
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=1,
            voucher_date=voucher_date,
            account_code=AR_ACCOUNT[0],
            account_name=AR_ACCOUNT[1],
            summary=f"{summary_base} 出库确认应收",
            source_file_id=source_file.id,
            evidence_type="inventory_out",
            metadata=base_metadata,
            posting_phase="revenue_recognition",
        ),
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=2,
            voucher_date=voucher_date,
            account_code=REVENUE_ACCOUNT[0],
            account_name=REVENUE_ACCOUNT[1],
            summary=f"{summary_base} 出库确认收入",
            source_file_id=source_file.id,
            evidence_type="inventory_out",
            metadata=base_metadata,
            posting_phase="revenue_recognition",
        ),
    ]
    if policy in {"compliant_default", "revenue_first"}:
        lines.append(
            _draft_line(
                voucher_no=voucher_no,
                entry_line_no=3,
                voucher_date=voucher_date,
                account_code="6401",
                account_name="主营业务成本",
                summary=f"{summary_base} 结转销售成本",
                source_file_id=source_file.id,
                evidence_type="inventory_out",
                metadata=base_metadata,
                posting_phase="cost_matching",
            )
        )
        lines.append(
            _draft_line(
                voucher_no=voucher_no,
                entry_line_no=4,
                voucher_date=voucher_date,
                account_code="1405",
                account_name="库存商品",
                summary=f"{summary_base} 出库减库存",
                source_file_id=source_file.id,
                evidence_type="inventory_out",
                metadata=base_metadata,
                posting_phase="cost_matching",
            )
        )
    return lines


def _build_invoice_accrual_drafts(
    source_file: SourceFile,
    seq: int,
    period: AccountingPeriod,
    evidence_check: dict[str, Any],
    policy: str = "compliant_default",
    *,
    vat_only: bool = False,
) -> list[dict[str, Any]]:
    if vat_only:
        return _build_invoice_vat_only_drafts(source_file, seq, period, evidence_check, policy)
    return _build_invoice_sales_drafts(source_file, seq, period, evidence_check, policy)


def _build_bank_collection_drafts(
    source_file: SourceFile,
    seq: int,
    period: AccountingPeriod,
    evidence_check: dict[str, Any],
) -> list[dict[str, Any]]:
    """有发票时的银行流水：借银行存款、贷应收（收款核销），不直接贷收入。"""
    voucher_date, clamped = _clamp_date(period.start_date, period)
    voucher_no = f"银-{seq:03d}"
    base_metadata = _merge_evidence_metadata(
        {
            "date_clamped": clamped,
            "vector_pending": True,
            "source_evidence_type": _normalize_evidence_type(source_file) or "bank",
            "source_file_id": source_file.id,
        },
        evidence_check,
    )
    summary_base = _format_summary("银", "银行存款", None, source_file.filename)
    return [
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=1,
            voucher_date=voucher_date,
            account_code="1002",
            account_name="银行存款",
            summary=f"{summary_base} 收款入账",
            source_file_id=source_file.id,
            evidence_type="bank",
            metadata=base_metadata,
            posting_phase="collection",
        ),
        _draft_line(
            voucher_no=voucher_no,
            entry_line_no=2,
            voucher_date=voucher_date,
            account_code="1122",
            account_name="应收账款",
            summary=f"{summary_base} 核销应收",
            source_file_id=source_file.id,
            evidence_type="bank",
            metadata=base_metadata,
            posting_phase="collection",
        ),
    ]


def _build_single_file_draft(
    source_file: SourceFile,
    seq: int,
    period: AccountingPeriod,
    evidence_check: dict[str, Any],
) -> dict[str, Any]:
    """非发票/非「发票+流水」场景下的单文件草稿（如合同+流水）。"""
    ftype = (source_file.file_type or "").lower()
    evidence_type = _normalize_evidence_type(source_file)
    prefix = "银" if evidence_type in {"bank", "receipt"} or "bank" in ftype else "记"
    voucher_no = f"{prefix}-{seq:03d}"
    voucher_date, clamped = _clamp_date(period.start_date, period)

    combined_text = f"{source_file.filename or ''} {source_file.file_type or ''} {source_file.extracted_text or ''}"
    recognized_code, recognized_name = _recognize_account_from_text(combined_text)

    if evidence_check["is_blocked"]:
        account_code = ""
        account_name = "待补充资料确认"
    elif recognized_code and recognized_name:
        account_code = recognized_code
        account_name = recognized_name
    elif prefix == "银" and not evidence_check["is_blocked"]:
        account_code = "1002"
        account_name = "银行存款"
    else:
        account_code = ""
        account_name = "待补充资料确认"

    metadata = _merge_evidence_metadata(
        {
            "date_clamped": clamped,
            "vector_pending": True,
            "source_evidence_type": evidence_type,
            "source_file_id": source_file.id,
        },
        evidence_check,
    )
    summary = _format_summary(prefix, account_name, None, source_file.filename)
    return _draft_line(
        voucher_no=voucher_no,
        entry_line_no=1,
        voucher_date=voucher_date,
        account_code=account_code,
        account_name=account_name,
        summary=summary,
        source_file_id=source_file.id,
        evidence_type=evidence_type,
        metadata=metadata,
    )


def generate_drafts(
    db: Session,
    job: ImportJob,
    period: AccountingPeriod,
    accounting_judgment_policy: str = "compliant_default",
) -> list[dict[str, Any]]:
    """生成草稿分录（不落库）。"""
    drafts: list[dict[str, Any]] = []
    files: list[SourceFile] = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()
    policy = _normalize_accounting_judgment_policy(accounting_judgment_policy)
    evidence_check = _check_evidence_sufficiency(files, policy)

    # 只查数据库中实际存在的列，避免 SQLAlchemy 映射缺失字段
    from sqlalchemy import select
    existing_rows = (
        db.execute(
            select(
                AccountingEntry.id,
                AccountingEntry.voucher_no,
                AccountingEntry.voucher_date,
                AccountingEntry.summary,
                AccountingEntry.account_code,
                AccountingEntry.account_name,
                AccountingEntry.debit_amount,
                AccountingEntry.credit_amount,
                AccountingEntry.counterparty,
                AccountingEntry.entry_line_no,
            ).where(AccountingEntry.import_job_id == job.id)
        )
        .fetchall()
    )

    if existing_rows:
        # 序时簿/已入账结构化分录本身就是会计凭证来源，不再套用原始证据充分性阻断规则。
        evidence_check = evidence_check | {
            "evidence_status": "sufficient",
            "is_blocked": False,
            "accounting_flow": "imported_day_book",
            "missing_evidence": [],
            "missing_reason": "",
            "suggested_actions": [],
        }
        # 已导入的序时簿应保留原凭证号、摘要和行号；只附带最小证据状态，避免大批量草稿返回过重。
        for row in existing_rows:
            row_id, voucher_no_raw, voucher_date, summary, account_code, account_name, debit_amount, credit_amount, counterparty, entry_line_no = row
            voucher_date_text = voucher_date.isoformat() if voucher_date else period.start_date.isoformat()
            date_outside_selected_period = bool(
                voucher_date and (voucher_date < period.start_date or voucher_date > period.end_date)
            )
            counterparty_str = counterparty if counterparty else ""
            metadata = {
                "evidence_status": "sufficient",
                "is_blocked": False,
                "accounting_flow": "imported_day_book",
                "date_outside_selected_period": date_outside_selected_period,
                "source_entry_id": row_id,
            }
            draft = {
                "source_entry_id": row_id,
                "voucher_no": voucher_no_raw or str(row_id),
                "voucher_date": voucher_date_text,
                "account_code": account_code,
                "account_name": account_name,
                "summary": summary or "",
                "debit_amount": Decimal(str(debit_amount or 0)).quantize(Decimal("0.00")),
                "credit_amount": Decimal(str(credit_amount or 0)).quantize(Decimal("0.00")),
                "counterparty": counterparty_str or None,
                "entry_line_no": entry_line_no or 1,
                "metadata": metadata,
                "tags": [],
            }
            drafts.append(draft)
        return drafts

    seq = 1
    accounting_flow = evidence_check.get("accounting_flow")
    evidence_types = set(evidence_check.get("evidence_types") or [])
    has_invoice = "invoice" in evidence_types
    has_outbound = evidence_check.get("has_outbound") is True

    outbound_files = [f for f in files if _normalize_evidence_type(f) == "inventory_out"]
    invoice_files = [f for f in files if _normalize_evidence_type(f) == "invoice"]
    bank_files = [
        f
        for f in files
        if _normalize_evidence_type(f) in {"bank", "receipt"}
    ]
    other_files = [
        f
        for f in files
        if f not in outbound_files and f not in invoice_files and f not in bank_files
    ]

    for f in outbound_files:
        if has_invoice and policy == "counterparty_first":
            continue
        drafts.extend(_build_outbound_revenue_drafts(f, seq, period, evidence_check, policy))
        seq += 1

    for f in invoice_files:
        vat_only = _should_invoice_confirm_vat_only(has_outbound=has_outbound, policy=policy)
        if policy == "counterparty_first":
            vat_only = False
        drafts.extend(
            _build_invoice_accrual_drafts(
                f,
                seq,
                period,
                evidence_check,
                policy,
                vat_only=vat_only,
            )
        )
        seq += 1

    for f in bank_files:
        if has_invoice and accounting_flow == "accrual_then_collection":
            drafts.extend(_build_bank_collection_drafts(f, seq, period, evidence_check))
            seq += 1
            continue
        drafts.append(_build_single_file_draft(f, seq, period, evidence_check))
        seq += 1

    for f in other_files:
        drafts.append(_build_single_file_draft(f, seq, period, evidence_check))
        seq += 1
    return drafts


def commit_drafts(
    db: Session,
    job: ImportJob,
    period: AccountingPeriod,
    drafts: list[dict[str, Any]],
) -> list[AccountingEntry]:
    """
    落库：把草稿写入 vouchers + accounting_entries + entry_tags。

    改造要点：
    - 统一通过 voucher_service 创建凭证，强制事务级借贷平衡校验。
    - 同一 voucher_no 的多条 draft 会被归并为一张凭证。
    - 任一张凭证借贷不平衡，整体回滚，避免部分落库。
    """
    if not drafts:
        return []

    # 1. 检查 evidence 阻断（保持原有逻辑）
    for draft in drafts:
        metadata = draft.get("metadata") or {}
        if metadata.get("is_blocked") is True or metadata.get("evidence_status") == "insufficient":
            missing_evidence = "、".join(metadata.get("missing_evidence") or [])
            missing_reason = metadata.get("missing_reason") or "原始资料不足，不能确认业务事实。"
            raise ValueError(f"AI 草稿证据不足，不能落库：{missing_reason} 需补充：{missing_evidence}")

    # 2. 准备 voucher_service 所需的数据
    # 按 voucher_no 分组，保留每组原始 drafts
    voucher_groups: dict[str, dict[str, Any]] = {}
    for draft in drafts:
        voucher_no = str(draft.get("voucher_no") or f"记-{job.id}").strip()
        draft["voucher_no"] = voucher_no

        if voucher_no not in voucher_groups:
            try:
                voucher_date = date.fromisoformat(draft["voucher_date"])
            except Exception:
                voucher_date = period.start_date
            voucher_date, _ = _clamp_date(voucher_date, period)
            voucher_groups[voucher_no] = {
                "voucher_date": voucher_date,
                "summary": draft.get("summary"),
                "drafts": [],
            }
        voucher_groups[voucher_no]["drafts"].append(draft)

    # 3. 批量创建 vouchers，所有创建在共享 session 中，失败统一回滚
    all_entries: list[AccountingEntry] = []
    for voucher_no, group in voucher_groups.items():
        lines = []
        for draft in group["drafts"]:
            metadata = draft.get("metadata") or {}
            input_source = metadata.get("source") or metadata.get("input_source") or "ai_generated"
            source_tag_value = f"source:{input_source}"

            # 自动标签
            auto_tags = [
                {
                    "tag_type": "source",
                    "tag_value": source_tag_value,
                    "tag_source": input_source,
                    "confidence": 1.0,
                }
            ]
            evidence_status = metadata.get("evidence_status")
            if evidence_status:
                auto_tags.append(
                    {
                        "tag_type": "evidence_status",
                        "tag_value": str(evidence_status),
                        "tag_source": "rule",
                        "confidence": 1.0,
                    }
                )
            posting_phase = metadata.get("posting_phase")
            if posting_phase:
                auto_tags.append(
                    {
                        "tag_type": "posting_phase",
                        "tag_value": str(posting_phase),
                        "tag_source": "rule",
                        "confidence": 0.95,
                    }
                )
            accounting_judgment_policy = metadata.get("accounting_judgment_policy")
            if accounting_judgment_policy:
                auto_tags.append(
                    {
                        "tag_type": "accounting_judgment_policy",
                        "tag_value": str(accounting_judgment_policy),
                        "tag_source": "rule",
                        "confidence": 1.0,
                    }
                )

            # 合并 draft 自带的 tags
            draft_tags = list(draft.get("tags", []) or [])
            seen_tag_values: set[tuple[str, str]] = set()
            combined_tags = []
            for tag in auto_tags + draft_tags:
                tag_type = tag.get("tag_type")
                tag_value = tag.get("tag_value") or tag.get("tag_name") or ""
                if not tag_value:
                    continue
                key = (tag_type, tag_value)
                if key in seen_tag_values:
                    continue
                seen_tag_values.add(key)
                combined_tags.append(tag)

            lines.append(
                voucher_service.VoucherEntryLine(
                    account_code=draft.get("account_code"),
                    account_name=draft.get("account_name"),
                    summary=draft.get("summary"),
                    debit_amount=Decimal(str(draft.get("debit_amount", 0))),
                    credit_amount=Decimal(str(draft.get("credit_amount", 0))),
                    counterparty=draft.get("counterparty"),
                    source_file_id=draft.get("source_file_id"),
                    original_row=draft.get("original_row"),
                    normalized_text=draft.get("summary") or "",
                    entity_id=draft.get("entity_id"),
                    original_entity_name=draft.get("original_entity_name"),
                    tags=combined_tags,
                )
            )

        # 4. 使用 voucher_service 创建凭证，事务内强制校验借贷平衡
        try:
            ledger_id_value = job.ledger_id or period.ledger_id or 0
            voucher = voucher_service.create_voucher(
                db,
                ledger_id=ledger_id_value,
                organization_id=job.organization_id,
                voucher_no=voucher_no,
                voucher_date=group["voucher_date"],
                summary=group["summary"],
                lines=lines,
                source_type=job.source_type or voucher_service.VoucherSourceType.AI_GENERATED,
                source_id=job.id,
                import_job_id=job.id,
                status=voucher_service.VoucherStatus.DRAFT,
                auto_commit=False,
            )
        except voucher_service.VoucherValidationError as exc:
            db.rollback()
            raise ValueError(f"凭证落库失败：{exc}") from exc

        # 5. 收集 entries
        entries = voucher_service.get_voucher_lines(db, voucher.id)
        all_entries.extend(entries)

    db.commit()
    for e in all_entries:
        db.refresh(e)
    return all_entries
