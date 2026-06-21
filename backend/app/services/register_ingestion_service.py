"""AI 导入路径：原始资料 → 功能模块台账登记。

底稿（SourceFile）保留文件载体；本服务将 AI/规则识别结果写入各模块台账表，
并同步内存台账服务，不生成会计分录（AccountingEntry）。

模块映射规则：
- 发票 → 税务模块台账
- 银行流水 → 银行模块台账
- 合同 → 往来账款台账；若为采购/销售合同，同时登记采购/销售模块台账
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import SourceFile
from app.services.document_parsing_service import DocumentParsingService
from app.services.ledger_service import BusinessType, ContractLedger, LedgerEntry, ledger_service
from app.services.source_document_service import SourceDocumentResult, classify_document

# 功能模块台账定义（非会计分录）
MODULE_DEFINITIONS: dict[str, dict[str, str]] = {
    "tax_invoice": {
        "label": "税务模块-发票台账",
        "module_path": "/tax/invoices",
    },
    "bank_cash_flow": {
        "label": "银行模块-资金收支台账",
        "module_path": "/bank/cash-flow-ledger",
    },
    "counterparty_ledger": {
        "label": "往来账款台账",
        "module_path": "/basic/counterparties",
    },
    "purchase": {
        "label": "采购模块-采购合同台账",
        "module_path": "/inventory/purchase-in",
    },
    "sales": {
        "label": "销售模块-销售合同台账",
        "module_path": "/inventory/sale-out",
    },
    "inventory_receipt": {
        "label": "库存模块-收发台账",
        "module_path": "/inventory/stock-receipt-ledger",
    },
    "payroll": {
        "label": "薪酬模块-工资台账",
        "module_path": "/payroll/ledger",
    },
    "general": {
        "label": "通用底稿资料",
        "module_path": "/ledger/files",
    },
}

HINT_TO_DOCUMENT_TYPE: dict[str, str] = {
    "invoice": "invoice",
    "bank_statement": "bank_statement",
    "bank": "bank_statement",
    "contract": "contract",
    "inventory": "inventory_receipt",
    "receipt": "bank_statement",
    "payroll": "payroll",
    "expense": "general",
    "other": "general",
}

PURCHASE_KEYWORDS = ("采购", "购买", "进货", "供应", "purchase", "procurement", "买方", "购入")
SALES_KEYWORDS = ("销售", "出售", "经销", "客户", "sales", "sell", "卖方", "销货")


@dataclass
class ModuleRegistration:
    module_key: str
    module_label: str
    module_path: str
    register_ids: list[int] = field(default_factory=list)
    register_count: int = 0


@dataclass
class RegisterIngestionResult:
    success: bool
    document_type: str
    module_label: str
    module_path: str
    register_ids: list[int] = field(default_factory=list)
    register_count: int = 0
    confidence: float = 0.0
    summary: str = ""
    error_message: str | None = None
    draft_only: bool = False
    module_registrations: list[ModuleRegistration] = field(default_factory=list)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _normalize_document_type(document_type: str) -> str:
    if document_type in {"bank", "bank_statement"}:
        return "bank_statement"
    if document_type in {"inventory", "inventory_receipt"}:
        return "inventory_receipt"
    return document_type


def _apply_type_hints(result: SourceDocumentResult, hints: list[str] | None) -> SourceDocumentResult:
    if not hints or result.confidence >= 0.55:
        return result

    for hint in hints:
        mapped = HINT_TO_DOCUMENT_TYPE.get(hint)
        if not mapped:
            continue
        return SourceDocumentResult(
            document_type=mapped,
            confidence=max(result.confidence, 0.55),
            data=result.data,
            raw_text=result.raw_text,
            file_name=result.file_name,
        )
    return result


def _detect_contract_modules(data: dict[str, Any], raw_text: str | None, filename: str) -> list[str]:
    """识别合同应登记到的功能模块台账（可多模块）。"""
    text = f"{filename} {raw_text or ''} {data.get('content') or ''}"
    contract_type = str(data.get("contract_type") or "").lower()

    modules: list[str] = []
    if data.get("party_a") or data.get("party_b"):
        modules.append("counterparty_ledger")

    is_purchase = contract_type == "purchase" or any(keyword in text for keyword in PURCHASE_KEYWORDS)
    is_sales = contract_type == "sales" or any(keyword in text for keyword in SALES_KEYWORDS)

    if is_purchase:
        modules.append("purchase")
    if is_sales:
        modules.append("sales")

    if not modules:
        modules.append("counterparty_ledger")

    # 去重并保持顺序
    seen: set[str] = set()
    ordered: list[str] = []
    for module_key in modules:
        if module_key not in seen:
            seen.add(module_key)
            ordered.append(module_key)
    return ordered


def _map_bank_transaction_type(value: str | None) -> str:
    if not value:
        return "income"
    text = str(value)
    if any(token in text for token in ("支", "付", "借", "debit", "expense", "out")):
        return "expense"
    return "income"


def _register_to_module(module_key: str, entry: LedgerEntry) -> None:
    bucket = ledger_service.module_ledgers.setdefault(module_key, {})
    bucket[entry.id] = entry


def _build_module_registration(module_key: str, register_ids: list[int] | None = None) -> ModuleRegistration:
    meta = MODULE_DEFINITIONS[module_key]
    ids = register_ids or []
    return ModuleRegistration(
        module_key=module_key,
        module_label=meta["label"],
        module_path=meta["module_path"],
        register_ids=ids,
        register_count=len(ids),
    )


def _persist_invoice(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
    raw_text: str | None,
) -> tuple[list[int], list[ModuleRegistration]]:
    service = DocumentParsingService(db)
    payload = {
        "invoice_no": data.get("invoice_number") or data.get("invoice_no"),
        "invoice_date": _parse_date(data.get("invoice_date")),
        "buyer_name": data.get("buyer_name"),
        "seller_name": data.get("seller_name"),
        "tax_amount": data.get("tax_amount"),
        "tax_rate": data.get("tax_rate"),
        "total_amount": data.get("total_amount"),
        "items": data.get("items") or [],
        "extracted_text": raw_text,
        "confidence_score": confidence,
    }
    invoice = service.parse_invoice(organization_id, payload)
    invoice.source_file_id = source_file.id
    db.commit()

    invoice_entry = ledger_service.add_invoice(data, source_file.filename)
    invoice_entry.metadata["module_key"] = "tax_invoice"
    invoice_entry.metadata["module_path"] = MODULE_DEFINITIONS["tax_invoice"]["module_path"]
    _register_to_module("tax_invoice", invoice_entry)

    module_regs = [_build_module_registration("tax_invoice", [invoice.id])]
    return [invoice.id], module_regs


def _persist_contract(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
    raw_text: str | None,
    filename: str,
) -> tuple[list[int], list[ModuleRegistration]]:
    service = DocumentParsingService(db)
    parties = []
    if data.get("party_a"):
        parties.append({"party_role": "party_a", "party_name": data.get("party_a")})
    if data.get("party_b"):
        parties.append({"party_role": "party_b", "party_name": data.get("party_b")})

    module_keys = _detect_contract_modules(data, raw_text, filename)
    contract_type = "purchase" if "purchase" in module_keys else "sales" if "sales" in module_keys else "service"

    payload = {
        "contract_no": data.get("contract_number") or data.get("contract_no"),
        "contract_type": contract_type,
        "contract_name": data.get("contract_name") or data.get("content", "")[:80] or source_file.filename,
        "sign_date": _parse_date(data.get("sign_date")),
        "contract_amount": data.get("amount") or data.get("contract_amount"),
        "parties": parties,
        "extracted_text": raw_text,
        "confidence_score": confidence,
    }
    contract = service.parse_contract(organization_id, payload)
    contract.source_file_id = source_file.id
    db.commit()

    base_entry = ledger_service.add_contract(data, source_file.filename)
    module_regs: list[ModuleRegistration] = []

    for module_key in module_keys:
        module_entry = ContractLedger(
            source_file=source_file.filename,
            source_type="contract",
            contract_number=base_entry.contract_number,
            party_a=base_entry.party_a,
            party_b=base_entry.party_b,
            sign_date=base_entry.sign_date,
            contract_amount=base_entry.contract_amount,
            counterparty=base_entry.counterparty,
            amount=base_entry.amount,
            date=base_entry.date,
            confidence=confidence,
            business_type=BusinessType.PURCHASE if module_key == "purchase" else BusinessType.SALES if module_key == "sales" else BusinessType.OTHER,
            metadata={
                **data,
                "module_key": module_key,
                "module_path": MODULE_DEFINITIONS[module_key]["module_path"],
                "contract_db_id": contract.id,
            },
        )
        _register_to_module(module_key, module_entry)
        module_regs.append(_build_module_registration(module_key, [contract.id]))

    return [contract.id], module_regs


def _persist_bank_statements(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
    raw_text: str | None,
) -> tuple[list[int], list[ModuleRegistration]]:
    service = DocumentParsingService(db)
    register_ids: list[int] = []
    transactions = data.get("transactions") or []
    if not transactions and data.get("transaction_date"):
        transactions = [data]

    for index, transaction in enumerate(transactions, start=1):
        payload = {
            "transaction_no": transaction.get("transaction_no") or f"{source_file.id}-{index}",
            "transaction_date": _parse_date(transaction.get("transaction_date") or transaction.get("date")),
            "transaction_type": _map_bank_transaction_type(transaction.get("transaction_type")),
            "counterparty_name": transaction.get("counterparty"),
            "amount": abs(float(transaction.get("amount") or 0)),
            "summary": transaction.get("summary"),
            "extracted_text": raw_text,
            "confidence_score": confidence,
        }
        statement = service.parse_bank_statement(organization_id, payload)
        statement.source_file_id = source_file.id
        db.commit()
        register_ids.append(statement.id)

        bank_entry = ledger_service.add_bank_statement(transaction, source_file.filename)
        bank_entry.metadata["module_key"] = "bank_cash_flow"
        bank_entry.metadata["module_path"] = MODULE_DEFINITIONS["bank_cash_flow"]["module_path"]
        _register_to_module("bank_cash_flow", bank_entry)

    module_regs = [_build_module_registration("bank_cash_flow", register_ids)]
    return register_ids, module_regs


def _persist_inventory(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
    raw_text: str | None,
) -> tuple[list[int], list[ModuleRegistration]]:
    service = DocumentParsingService(db)
    payload = {
        "document_no": data.get("receipt_number") or data.get("document_no") or f"INV-{source_file.id}",
        "document_type": data.get("document_type") or "inventory_in",
        "document_date": _parse_date(data.get("receipt_date") or data.get("document_date")),
        "counterparty_name": data.get("supplier") or data.get("counterparty_name"),
        "counterparty_type": "supplier",
        "total_amount": data.get("total_amount"),
        "items": data.get("items") or [],
        "extracted_text": raw_text,
        "confidence_score": confidence,
    }
    document = service.parse_inventory_document(organization_id, payload)
    document.source_file_id = source_file.id
    db.commit()

    inventory_entry = ledger_service.add_inventory(data, source_file.filename)
    inventory_entry.metadata["module_key"] = "inventory_receipt"
    inventory_entry.metadata["module_path"] = MODULE_DEFINITIONS["inventory_receipt"]["module_path"]
    _register_to_module("inventory_receipt", inventory_entry)

    module_regs = [_build_module_registration("inventory_receipt", [document.id])]
    return [document.id], module_regs


def _persist_payroll(
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
) -> tuple[list[int], list[ModuleRegistration]]:
    from app.services.ledger_service import PayrollLedger

    entry = PayrollLedger(
        source_file=source_file.filename,
        source_type="payroll",
        period=data.get("period"),
        total_amount=data.get("total_amount"),
        employee_count=data.get("employee_count"),
        amount=data.get("total_amount"),
        date=data.get("period"),
        confidence=confidence,
        metadata={
            **data,
            "module_key": "payroll",
            "module_path": MODULE_DEFINITIONS["payroll"]["module_path"],
        },
    )
    ledger_service.payroll_ledger[entry.id] = entry
    _register_to_module("payroll", entry)
    return [], [_build_module_registration("payroll", [])]


def _summarize_modules(module_regs: list[ModuleRegistration]) -> str:
    if not module_regs:
        return "已保存为底稿资料"
    parts = [f"{item.module_label} {item.register_count or 1} 条" for item in module_regs]
    return "已登记：" + "；".join(parts)


def ingest_register_from_document(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    classification: SourceDocumentResult,
    document_type_hints: list[str] | None = None,
) -> RegisterIngestionResult:
    """将已分类原始资料登记到功能模块台账（非会计分录）。"""
    result = _apply_type_hints(classification, document_type_hints)
    document_type = _normalize_document_type(result.document_type)

    if document_type == "general" or result.confidence < 0.35:
        general = _build_module_registration("general", [])
        return RegisterIngestionResult(
            success=True,
            document_type="general",
            module_label=general.module_label,
            module_path=general.module_path,
            confidence=result.confidence,
            summary="已保存为底稿资料，待补充类型说明或人工确认后登记台账",
            draft_only=True,
            module_registrations=[general],
        )

    try:
        data = result.data or {}
        raw_text = result.raw_text
        module_regs: list[ModuleRegistration] = []
        register_ids: list[int] = []

        if document_type == "invoice":
            register_ids, module_regs = _persist_invoice(db, organization_id, source_file, data, result.confidence, raw_text)
        elif document_type == "contract":
            register_ids, module_regs = _persist_contract(
                db, organization_id, source_file, data, result.confidence, raw_text, source_file.filename
            )
        elif document_type == "bank_statement":
            register_ids, module_regs = _persist_bank_statements(db, organization_id, source_file, data, result.confidence, raw_text)
        elif document_type == "inventory_receipt":
            register_ids, module_regs = _persist_inventory(db, organization_id, source_file, data, result.confidence, raw_text)
        elif document_type == "payroll":
            register_ids, module_regs = _persist_payroll(source_file, data, result.confidence)
        else:
            general = _build_module_registration("general", [])
            return RegisterIngestionResult(
                success=True,
                document_type=document_type,
                module_label=general.module_label,
                module_path=general.module_path,
                confidence=result.confidence,
                summary="已保存底稿，暂未匹配到可落库的模块台账结构",
                draft_only=True,
                module_registrations=[general],
            )

        primary = module_regs[0]
        return RegisterIngestionResult(
            success=True,
            document_type=document_type,
            module_label=primary.module_label,
            module_path=primary.module_path,
            register_ids=register_ids,
            register_count=len(register_ids),
            confidence=result.confidence,
            summary=_summarize_modules(module_regs),
            module_registrations=module_regs,
        )
    except Exception as exc:
        general = MODULE_DEFINITIONS.get(document_type, MODULE_DEFINITIONS["general"])
        return RegisterIngestionResult(
            success=False,
            document_type=document_type,
            module_label=general["label"],
            module_path=general["module_path"],
            confidence=result.confidence,
            summary="底稿已保存，但台账登记失败",
            error_message=str(exc),
            draft_only=True,
            module_registrations=[],
        )


def classify_and_ingest_register(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    document_type_hints: list[str] | None = None,
) -> tuple[SourceDocumentResult, RegisterIngestionResult]:
    classification = classify_document(source_file.storage_path, source_file.filename)
    ingestion = ingest_register_from_document(
        db,
        organization_id,
        source_file,
        classification,
        document_type_hints=document_type_hints,
    )
    return classification, ingestion
