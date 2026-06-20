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


def _check_evidence_sufficiency(files: list[SourceFile]) -> dict[str, Any]:
    context = _build_evidence_context(files)
    evidence_types = set(context["evidence_types"])
    has_invoice = "invoice" in evidence_types
    has_bank_or_receipt = bool({"bank", "receipt"} & evidence_types)
    has_business_document = bool({"contract", "order", "settlement"} & evidence_types)

    if has_invoice and not has_bank_or_receipt:
        return context | {
            "evidence_status": "insufficient",
            "is_blocked": True,
            "missing_evidence": ["银行流水", "收款回单/付款回单"],
            "missing_reason": "当前仅能识别到发票。发票可证明开票和税额，但不能证明款项已经收付，因此不得直接确认银行存款。",
            "suggested_actions": ["请补充银行流水", "请补充收款回单或付款回单", "如尚未收款，可人工改按应收/应付往来处理"],
        }

    if has_bank_or_receipt and not has_invoice and not has_business_document:
        return context | {
            "evidence_status": "insufficient",
            "is_blocked": True,
            "missing_evidence": ["合同", "订单", "结算单"],
            "missing_reason": "当前仅能识别到银行流水/回单。流水可证明资金收付，但不能单独证明业务性质、交易内容和收入成本归类。",
            "suggested_actions": ["请补充合同", "请补充订单", "请补充结算单"],
        }

    if (has_invoice and has_bank_or_receipt) or (has_bank_or_receipt and has_business_document):
        return context | {
            "evidence_status": "sufficient",
            "is_blocked": False,
            "missing_evidence": [],
            "missing_reason": "",
            "suggested_actions": [],
        }

    return context | {
        "evidence_status": "insufficient",
        "is_blocked": True,
        "missing_evidence": ["发票", "银行流水", "合同/订单/结算单"],
        "missing_reason": "当前原始资料不足以同时证明交易发生、业务性质和资金收付，AI 只能暂存草稿，不能直接落库。",
        "suggested_actions": ["请补充发票、银行流水或回单", "请补充合同、订单或结算单"],
    }


def _merge_evidence_metadata(metadata: dict[str, Any], evidence_check: dict[str, Any]) -> dict[str, Any]:
    return metadata | {
        "evidence_status": evidence_check["evidence_status"],
        "missing_evidence": evidence_check["missing_evidence"],
        "missing_reason": evidence_check["missing_reason"],
        "current_recognized_evidence": evidence_check["source_files"],
        "evidence_definitions": evidence_check["evidence_definitions"],
        "suggested_actions": evidence_check["suggested_actions"],
        "is_blocked": evidence_check["is_blocked"],
    }


def generate_drafts(
    db: Session,
    job: ImportJob,
    period: AccountingPeriod,
) -> list[dict[str, Any]]:
    """生成草稿分录（不落库）。"""
    drafts: list[dict[str, Any]] = []
    files: list[SourceFile] = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()
    evidence_check = _check_evidence_sufficiency(files)

    existing_entries: list[AccountingEntry] = (
        db.query(AccountingEntry)
        .filter(AccountingEntry.import_job_id == job.id)
        .order_by(AccountingEntry.voucher_no, AccountingEntry.entry_line_no)
        .all()
    )

    if existing_entries:
        # 基于既有分录应用规则进行"重写"：不修改原数据
        for entry in existing_entries:
            voucher_date, clamped = _clamp_date(entry.voucher_date, period)
            file_type = None
            prefix = _voucher_prefix(entry.account_name, entry.summary, file_type)
            if prefix == "收" and (entry.credit_amount or 0) > 0 and (entry.debit_amount or 0) == 0:
                prefix = "付"
            voucher_no = f"{prefix}-{(entry.voucher_no or str(entry.id))[-6:]}"
            counterparty = entry.counterparty if entry.counterparty else ""
            new_summary = _format_summary(prefix, entry.account_name, counterparty, entry.summary)
            metadata = _merge_evidence_metadata(
                {"date_clamped": clamped, "vector_pending": True, "source_entry_id": entry.id},
                evidence_check,
            )
            draft = {
                "source_entry_id": entry.id,
                "voucher_no": voucher_no,
                "voucher_date": voucher_date.isoformat(),
                "account_code": entry.account_code,
                "account_name": entry.account_name,
                "summary": new_summary,
                "debit_amount": float(entry.debit_amount or 0),
                "credit_amount": float(entry.credit_amount or 0),
                "counterparty": counterparty or None,
                "entry_line_no": entry.entry_line_no,
                "metadata": metadata,
                "tags": _extract_tags(
                    {
                        "summary": new_summary,
                        "account_code": entry.account_code,
                        "account_name": entry.account_name,
                        "counterparty": entry.counterparty,
                        "source_entry_id": entry.id,
                        "metadata": metadata,
                    }
                ),
            }
            drafts.append(draft)
        return drafts

    # 没有既有分录：基于 source_files 生成最小占位草稿（仅展示流程）
    seq = 1
    for f in files:
        ftype = (f.file_type or "").lower()
        evidence_type = _normalize_evidence_type(f)
        prefix = "银" if evidence_type in {"bank", "receipt"} or "bank" in ftype else "记"
        voucher_no = f"{prefix}-{seq:03d}"
        voucher_date, clamped = _clamp_date(period.start_date, period)
        account_code = "1002" if prefix == "银" and not evidence_check["is_blocked"] else ""
        account_name = "银行存款" if prefix == "银" and not evidence_check["is_blocked"] else "待补充资料确认"
        metadata = _merge_evidence_metadata(
            {
                "date_clamped": clamped,
                "vector_pending": True,
                "source_evidence_type": evidence_type,
                "source_file_id": f.id,
            },
            evidence_check,
        )
        summary = _format_summary(prefix, None, None, f.filename)
        drafts.append(
            {
                "source_file_id": f.id,
                "voucher_no": voucher_no,
                "voucher_date": voucher_date.isoformat(),
                "account_code": account_code,
                "account_name": account_name,
                "summary": summary,
                "debit_amount": 0.0,
                "credit_amount": 0.0,
                "counterparty": None,
                "entry_line_no": 1,
                "metadata": metadata,
                "tags": _extract_tags(
                    {
                        "summary": summary,
                        "account_code": account_code,
                        "account_name": account_name,
                        "source_file_id": f.id,
                        "metadata": metadata,
                    }
                ),
            }
        )
        seq += 1
    return drafts


def commit_drafts(
    db: Session,
    job: ImportJob,
    period: AccountingPeriod,
    drafts: list[dict[str, Any]],
) -> list[AccountingEntry]:
    """落库：把草稿写入 accounting_entries + entry_tags。"""
    persisted: list[AccountingEntry] = []
    voucher_line_counter: dict[str, int] = {}

    for draft in drafts:
        metadata = draft.get("metadata") or {}
        if metadata.get("is_blocked") is True or metadata.get("evidence_status") == "insufficient":
            missing_evidence = "、".join(metadata.get("missing_evidence") or [])
            missing_reason = metadata.get("missing_reason") or "原始资料不足，不能确认业务事实。"
            raise ValueError(f"AI 草稿证据不足，不能落库：{missing_reason} 需补充：{missing_evidence}")

        voucher_no = draft.get("voucher_no") or f"记-{job.id}"
        voucher_line_counter[voucher_no] = voucher_line_counter.get(voucher_no, 0) + 1
        line_no = voucher_line_counter[voucher_no]

        try:
            voucher_date = date.fromisoformat(draft["voucher_date"])
        except Exception:
            voucher_date = period.start_date
        voucher_date, _ = _clamp_date(voucher_date, period)

        entry = AccountingEntry(
            organization_id=job.organization_id,
            import_job_id=job.id,
            voucher_no=voucher_no,
            voucher_date=voucher_date,
            summary=draft.get("summary"),
            account_code=draft.get("account_code"),
            account_name=draft.get("account_name"),
            debit_amount=Decimal(str(draft.get("debit_amount", 0))),
            credit_amount=Decimal(str(draft.get("credit_amount", 0))),
            counterparty=draft.get("counterparty"),
            entry_line_no=line_no,
            normalized_text=draft.get("summary") or "",
        )
        db.add(entry)
        db.flush()

        input_source = metadata.get("source") or metadata.get("input_source") or "ai_generated"
        source_tag_value = f"source:{input_source}"
        db.add(
            EntryTag(
                entry_id=entry.id,
                tag_name=source_tag_value,
                tag_type="source",
                tag_value=source_tag_value,
                tag_value_normalized=source_tag_value,
                tag_source=input_source,
                confidence=1.0,
                vector_pending=True,
            )
        )

        tags = list(draft.get("tags", []) or [])
        tags.extend(
            _extract_tags(
                {
                    "summary": draft.get("summary"),
                    "account_code": draft.get("account_code"),
                    "account_name": draft.get("account_name"),
                    "counterparty": draft.get("counterparty"),
                    "source_file_id": draft.get("source_file_id"),
                    "source_entry_id": draft.get("source_entry_id"),
                    "metadata": metadata,
                }
            )
        )
        seen_persisted_tags: set[tuple[str | None, str]] = set()
        for tag in tags:
            tag_value = tag.get("tag_value") or ""
            tag_type = tag.get("tag_type")
            tag_key = (tag_type, tag_value)
            if not tag_value or tag_key in seen_persisted_tags:
                continue
            seen_persisted_tags.add(tag_key)
            db.add(
                EntryTag(
                    entry_id=entry.id,
                    tag_name=tag_value,
                    tag_type=tag_type,
                    tag_value=tag_value,
                    tag_value_normalized=tag_value.strip().lower(),
                    tag_source=tag.get("tag_source") or "rule",
                    confidence=float(tag.get("confidence", 0.8)),
                    vector_pending=True,
                )
            )
        persisted.append(entry)

    db.commit()
    for e in persisted:
        db.refresh(e)
    return persisted
