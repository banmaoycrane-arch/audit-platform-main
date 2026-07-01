from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.services.draft_archive_service import auto_archive_draft

from app.db.models import (
    AccountingEntry,
    BankAccount,
    BankStatement,
    BankTransaction,
    Contract,
    DocumentChunk,
    ImportJob,
    InventoryDocument,
    Invoice,
    SourceFile,
)

AUTO_REVIEW_CONFIDENCE_THRESHOLD = 0.85


DOCUMENT_ARCHIVE_TARGETS = {
    "invoice": "invoice_ledger",
    "contract": "contract_ledger",
    "inventory_receipt": "inventory_ledger",
    "expense_document": "business_document_ledger",
    "receipt": "business_document_ledger",
    "salary_table": "business_document_ledger",
    "bank_statement": "bank_ledger",
    "accounting_entry": "voucher_ledger",
    "general": "audit_document_library",
}


def _as_text(value: Any, default: str | None = None) -> str | None:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(Decimal(str(value).replace(",", "")))
    except (InvalidOperation, ValueError):
        return None


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("年", "-").replace("月", "-").replace("日", "")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _pick(data: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    lowered = {str(k).lower(): v for k, v in data.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value not in (None, ""):
            return value
    return None


def _json_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def _build_rule(name: str, passed: bool, message: str) -> dict[str, Any]:
    return {"name": name, "passed": passed, "message": message}


def auto_review_parser_result(parser_result: dict[str, Any]) -> dict[str, Any]:
    document_type = _as_text(parser_result.get("document_type"), "unknown") or "unknown"
    confidence = float(parser_result.get("confidence") or 0)
    data = parser_result.get("data") if isinstance(parser_result.get("data"), dict) else {}

    rules = [
        _build_rule(
            "confidence_threshold",
            confidence >= AUTO_REVIEW_CONFIDENCE_THRESHOLD,
            f"置信度 {confidence:.2f}，阈值 {AUTO_REVIEW_CONFIDENCE_THRESHOLD:.2f}",
        ),
        _build_rule(
            "no_parse_error",
            not bool(parser_result.get("error_message")),
            _as_text(parser_result.get("error_message"), "无解析错误") or "无解析错误",
        ),
        _build_rule(
            "document_type_supported",
            document_type in DOCUMENT_ARCHIVE_TARGETS,
            f"文档类型：{document_type}",
        ),
        _build_rule(
            "has_extracted_data_or_text",
            bool(data) or bool(parser_result.get("raw_text")),
            "解析结果包含结构化字段或原始文本",
        ),
    ]

    risk_level = "low" if all(rule["passed"] for rule in rules) else "medium"
    return {
        "passed": all(rule["passed"] for rule in rules),
        "confidence": confidence,
        "document_type": document_type,
        "risk_level": risk_level,
        "rules": rules,
        "reviewed_at": datetime.utcnow().isoformat(),
    }


def _archive_invoice(db: Session, job: ImportJob, source_file: SourceFile, parser_result: dict[str, Any]) -> tuple[str, int]:
    data = parser_result.get("data") if isinstance(parser_result.get("data"), dict) else {}
    invoice = Invoice(
        organization_id=job.organization_id,
        ledger_id=job.ledger_id,
        invoice_no=_as_text(_pick(data, "invoice_no", "发票号码", "发票号")),
        invoice_code=_as_text(_pick(data, "invoice_code", "发票代码")),
        invoice_type=_as_text(_pick(data, "invoice_type", "document_sub_type", "发票类型"), "电子发票") or "电子发票",
        invoice_status="normal",
        invoice_date=_as_date(_pick(data, "invoice_date", "issue_date", "开票日期", "日期")),
        buyer_name=_as_text(_pick(data, "buyer_name", "购买方名称", "购方名称")),
        buyer_tax_no=_as_text(_pick(data, "buyer_tax_no", "购买方税号", "购方税号")),
        seller_name=_as_text(_pick(data, "seller_name", "销售方名称", "销方名称")),
        seller_tax_no=_as_text(_pick(data, "seller_tax_no", "销售方税号", "销方税号")),
        amount_excluding_tax=_as_float(_pick(data, "amount_excluding_tax", "amount_excl_tax", "不含税金额", "金额")),
        tax_rate=_as_float(_pick(data, "tax_rate", "税率")),
        tax_amount=_as_float(_pick(data, "tax_amount", "税额")),
        total_amount=_as_float(_pick(data, "total_amount", "价税合计", "合计金额")),
        source_file_id=source_file.id,
        extracted_text=_json_text(parser_result),
        confidence_score=float(parser_result.get("confidence") or 0),
    )
    db.add(invoice)
    db.flush()
    return "invoice_ledger", invoice.id


def _archive_contract(db: Session, job: ImportJob, source_file: SourceFile, parser_result: dict[str, Any]) -> tuple[str, int]:
    data = parser_result.get("data") if isinstance(parser_result.get("data"), dict) else {}
    contract = Contract(
        organization_id=job.organization_id,
        ledger_id=job.ledger_id,
        contract_no=_as_text(_pick(data, "contract_no", "合同编号", "合同号")),
        contract_type=_as_text(_pick(data, "contract_type", "合同类型"), "service") or "service",
        contract_name=_as_text(_pick(data, "contract_name", "合同名称", "name"), source_file.filename),
        sign_date=_as_date(_pick(data, "sign_date", "signing_date", "签署日期", "签订日期")),
        start_date=_as_date(_pick(data, "start_date", "开始日期")),
        end_date=_as_date(_pick(data, "end_date", "结束日期")),
        contract_amount=_as_float(_pick(data, "contract_amount", "total_amount", "合同金额", "价税合计")),
        currency=_as_text(_pick(data, "currency", "币种"), "CNY") or "CNY",
        tax_rate=_as_float(_pick(data, "tax_rate", "税率")),
        tax_amount=_as_float(_pick(data, "tax_amount", "税额")),
        performance_obligations=data.get("performance_obligations") if isinstance(data.get("performance_obligations"), dict) else {},
        risk_flags={"auto_archived": True},
        source_file_id=source_file.id,
        extracted_text=_json_text(parser_result),
        confidence_score=float(parser_result.get("confidence") or 0),
    )
    db.add(contract)
    db.flush()
    return "contract_ledger", contract.id


def _archive_inventory(db: Session, job: ImportJob, source_file: SourceFile, parser_result: dict[str, Any]) -> tuple[str, int]:
    data = parser_result.get("data") if isinstance(parser_result.get("data"), dict) else {}
    document = InventoryDocument(
        organization_id=job.organization_id,
        ledger_id=job.ledger_id,
        document_no=_as_text(_pick(data, "document_no", "单据编号", "入库单号"), f"SF-{source_file.id}") or f"SF-{source_file.id}",
        document_type=_as_text(_pick(data, "document_type", "单据类型"), "inventory_in") or "inventory_in",
        document_date=_as_date(_pick(data, "document_date", "日期", "入库日期")),
        warehouse_name=_as_text(_pick(data, "warehouse_name", "仓库")),
        counterparty_name=_as_text(_pick(data, "counterparty_name", "供应商", "客户")),
        total_quantity=_as_float(_pick(data, "total_quantity", "数量")),
        total_amount=_as_float(_pick(data, "total_amount", "金额", "价税合计")),
        source_file_id=source_file.id,
        extracted_text=_json_text(parser_result),
        confidence_score=float(parser_result.get("confidence") or 0),
    )
    db.add(document)
    db.flush()
    return "inventory_ledger", document.id


def _archive_bank(db: Session, job: ImportJob, source_file: SourceFile, parser_result: dict[str, Any]) -> tuple[str, int]:
    data = parser_result.get("data") if isinstance(parser_result.get("data"), dict) else {}
    amount = _as_float(_pick(data, "amount", "金额", "交易金额", "收入金额", "支出金额")) or 0
    transaction_type = _as_text(_pick(data, "transaction_type", "direction", "收支方向"), "income") or "income"
    statement = BankStatement(
        organization_id=job.organization_id,
        ledger_id=job.ledger_id,
        transaction_no=_as_text(_pick(data, "transaction_no", "流水号", "回单编号")),
        transaction_date=_as_date(_pick(data, "transaction_date", "交易日期", "日期")),
        transaction_type="expense" if transaction_type in ("out", "支出", "付款", "expense") else "income",
        account_name=_as_text(_pick(data, "account_name", "户名", "本方户名")),
        account_no=_as_text(_pick(data, "account_no", "账号", "本方账号")),
        bank_name=_as_text(_pick(data, "bank_name", "开户行", "银行")),
        counterparty_name=_as_text(_pick(data, "counterparty_name", "对方户名", "对方名称")),
        counterparty_account=_as_text(_pick(data, "counterparty_account", "对方账号")),
        amount=amount,
        balance=_as_float(_pick(data, "balance", "余额")),
        summary=_as_text(_pick(data, "summary", "摘要", "用途")),
        purpose=_as_text(_pick(data, "purpose", "用途")),
        remark=_as_text(_pick(data, "remark", "备注")),
        source_file_id=source_file.id,
        extracted_text=_json_text(parser_result),
        confidence_score=float(parser_result.get("confidence") or 0),
    )
    db.add(statement)
    db.flush()

    if job.ledger_id:
        account_no = _as_text(_pick(data, "account_no", "账号", "本方账号"), "UNKNOWN") or "UNKNOWN"
        bank_name = _as_text(_pick(data, "bank_name", "开户行", "银行"), "未知银行") or "未知银行"
        account_name = _as_text(_pick(data, "account_name", "户名", "本方户名"), "未知户名") or "未知户名"
        account = (
            db.query(BankAccount)
            .filter(BankAccount.ledger_id == job.ledger_id, BankAccount.account_no == account_no)
            .first()
        )
        if account is None:
            account = BankAccount(
                ledger_id=job.ledger_id,
                bank_name=bank_name,
                account_no=account_no,
                account_name=account_name,
            )
            db.add(account)
            db.flush()
        db.add(BankTransaction(
            bank_account_id=account.id,
            ledger_id=job.ledger_id,
            transaction_date=statement.transaction_date or datetime.utcnow().date(),
            direction="out" if statement.transaction_type == "expense" else "in",
            amount=amount,
            summary=statement.summary,
            counterparty=statement.counterparty_name,
        ))
    return "bank_ledger", statement.id


def _archive_voucher(db: Session, job: ImportJob, source_file: SourceFile, parser_result: dict[str, Any]) -> tuple[str, int]:
    """归档 AI 识别出的凭证类原始文件。

    业务说明：
    - 此函数生成的是单条草稿分录行，用于保存 AI 对原始凭证/票据的初步识别结果。
    - 不保证借贷平衡，不生成 Voucher 主记录，不能作为正式记账凭证。
    - 正式凭证必须走 import_service._process_accounting_file 或 voucher_service.create_voucher。
    """
    data = parser_result.get("data") if isinstance(parser_result.get("data"), dict) else {}
    entry = AccountingEntry(
        organization_id=job.organization_id,
        ledger_id=job.ledger_id,
        import_job_id=job.id,
        voucher_no=_as_text(_pick(data, "voucher_no", "凭证号"), f"DRAFT-{job.id}-{source_file.id}"),
        voucher_date=_as_date(_pick(data, "voucher_date", "日期", "凭证日期")),
        summary=_as_text(_pick(data, "summary", "摘要"), f"自动归档解析文件：{source_file.filename}"),
        account_code=_as_text(_pick(data, "account_code", "科目编码")),
        account_name=_as_text(_pick(data, "account_name", "科目名称")),
        source_file_id=source_file.id,
        entry_source="auto",
        debit_amount=_as_float(_pick(data, "debit_amount", "借方金额")) or 0,
        credit_amount=_as_float(_pick(data, "credit_amount", "贷方金额")) or 0,
        counterparty=_as_text(_pick(data, "counterparty", "往来单位")),
        original_row=data,
        normalized_text=parser_result.get("raw_text") or source_file.filename,
        review_status="auto_reviewed",
        post_status="draft",
    )
    db.add(entry)
    db.flush()
    return "voucher_ledger", entry.id


def _archive_audit_document(db: Session, job: ImportJob, source_file: SourceFile, parser_result: dict[str, Any]) -> tuple[str, int]:
    raw_text = parser_result.get("raw_text") or _json_text(parser_result)
    digest = hashlib.sha256(f"{source_file.id}:{raw_text}".encode("utf-8")).hexdigest()
    chunk = DocumentChunk(
        organization_id=job.organization_id,
        ledger_id=job.ledger_id,
        source_type="parser_engine_archive",
        source_id=source_file.id,
        chunk_text=raw_text[:8000],
        chunk_hash=digest,
        vector_collection="audit_documents",
        vector_point_id=f"source-file-{source_file.id}",
    )
    db.add(chunk)
    db.flush()
    return "audit_document_library", chunk.id


def _archive_business_document(db: Session, job: ImportJob, source_file: SourceFile, parser_result: dict[str, Any]) -> tuple[str, int]:
    return _archive_audit_document(db, job, source_file, parser_result)


def archive_parser_result(db: Session, job: ImportJob, source_file: SourceFile, parser_result: dict[str, Any]) -> dict[str, Any]:
    document_type = _as_text(parser_result.get("document_type"), "unknown") or "unknown"
    archive_handlers = {
        "invoice": _archive_invoice,
        "contract": _archive_contract,
        "inventory_receipt": _archive_inventory,
        "bank_statement": _archive_bank,
        "accounting_entry": _archive_voucher,
        "general": _archive_audit_document,
        "expense_document": _archive_business_document,
        "receipt": _archive_business_document,
        "salary_table": _archive_business_document,
    }
    handler = archive_handlers.get(document_type)
    if handler is None:
        return {
            "archived": False,
            "status": "manual_review_required",
            "target": None,
            "record_id": None,
            "reason": f"文档类型 {document_type} 暂不支持自动归档",
        }

    target, record_id = handler(db, job, source_file, parser_result)
    workpaper_archive = auto_archive_draft(
        db,
        source_file,
        parser_result,
        source_type=job.source_type,
        job=job,
    )
    return {
        "archived": True,
        "status": "archived",
        "target": target,
        "record_id": record_id,
        "document_type": document_type,
        "project_id": job.project_id,
        "ledger_id": job.ledger_id or source_file.ledger_id,
        "workpaper_archive": workpaper_archive,
        "archived_at": datetime.utcnow().isoformat(),
    }


def auto_review_and_archive(db: Session, job: ImportJob, source_file: SourceFile, parser_result: dict[str, Any]) -> dict[str, Any]:
    review_result = auto_review_parser_result(parser_result)
    if not review_result["passed"]:
        return {
            "auto_review": review_result,
            "archive": {
                "archived": False,
                "status": "manual_review_required",
                "target": DOCUMENT_ARCHIVE_TARGETS.get(review_result["document_type"]),
                "record_id": None,
                "reason": "自动复核未通过",
            },
        }

    archive_result = archive_parser_result(db, job, source_file, parser_result)
    return {
        "auto_review": review_result,
        "archive": archive_result,
    }
