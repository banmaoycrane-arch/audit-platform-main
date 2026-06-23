"""模块台账持久化查询服务（Phase A）。

从数据库按 ledger_id 查询各 Register 子数据集，替代仅依赖内存 module_ledgers 的方式。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import BankStatement, Contract, Counterparty, InventoryDocument, Invoice
from app.services.register_ingestion_service import MODULE_DEFINITIONS

VALID_MODULE_KEYS = set(MODULE_DEFINITIONS.keys()) - {"general"}

EXECUTION_STATUS_LABELS = {
    "pending": "待执行",
    "executing": "执行中",
    "completed": "已完成",
    "not_executed": "未执行",
    "cancelled": "已取消",
}

BALANCE_TYPE_LABELS = {
    "receivable": "应收",
    "payable": "应付",
    "prepaid": "预付",
    "advance_received": "预收",
}


def _iso(value: date | datetime | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value.isoformat()


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _contract_to_dict(contract: Contract, db: Session) -> dict[str, Any]:
    counterparty = db.get(Counterparty, contract.counterparty_id) if contract.counterparty_id else None
    return {
        "id": contract.id,
        "module_key": "contract_register",
        "ledger_id": contract.ledger_id,
        "counterparty_id": contract.counterparty_id,
        "counterparty_name": counterparty.name if counterparty else None,
        "contract_no": contract.contract_no,
        "contract_type": contract.contract_type,
        "contract_name": contract.contract_name,
        "sign_date": _iso(contract.sign_date),
        "contract_amount": _float(contract.contract_amount),
        "execution_status": contract.execution_status,
        "execution_status_label": EXECUTION_STATUS_LABELS.get(contract.execution_status, contract.execution_status),
        "source_file_id": contract.source_file_id,
        "confidence_score": contract.confidence_score,
        "created_at": _iso(contract.created_at),
    }


def _invoice_to_dict(invoice: Invoice, db: Session) -> dict[str, Any]:
    counterparty = db.get(Counterparty, invoice.counterparty_id) if invoice.counterparty_id else None
    return {
        "id": invoice.id,
        "module_key": "tax_invoice",
        "ledger_id": invoice.ledger_id,
        "counterparty_id": invoice.counterparty_id,
        "counterparty_name": counterparty.name if counterparty else None,
        "invoice_no": invoice.invoice_no,
        "invoice_type": invoice.invoice_type,
        "invoice_date": _iso(invoice.invoice_date),
        "buyer_name": invoice.buyer_name,
        "seller_name": invoice.seller_name,
        "total_amount": _float(invoice.total_amount),
        "related_contract_id": invoice.related_contract_id,
        "source_file_id": invoice.source_file_id,
        "confidence_score": invoice.confidence_score,
        "created_at": _iso(invoice.created_at),
    }


def _bank_to_dict(statement: BankStatement, db: Session) -> dict[str, Any]:
    counterparty = db.get(Counterparty, statement.counterparty_id) if statement.counterparty_id else None
    return {
        "id": statement.id,
        "module_key": "bank_cash_flow",
        "ledger_id": statement.ledger_id,
        "counterparty_id": statement.counterparty_id,
        "counterparty_name": counterparty.name if counterparty else statement.counterparty_name,
        "transaction_no": statement.transaction_no,
        "transaction_date": _iso(statement.transaction_date),
        "transaction_type": statement.transaction_type,
        "amount": _float(statement.amount),
        "balance": _float(statement.balance),
        "summary": statement.summary,
        "related_contract_id": statement.related_contract_id,
        "related_invoice_id": statement.related_invoice_id,
        "source_file_id": statement.source_file_id,
        "confidence_score": statement.confidence_score,
        "created_at": _iso(statement.created_at),
    }


def _inventory_to_dict(document: InventoryDocument, db: Session) -> dict[str, Any]:
    counterparty = db.get(Counterparty, document.counterparty_id) if document.counterparty_id else None
    return {
        "id": document.id,
        "module_key": "inventory_receipt",
        "ledger_id": document.ledger_id,
        "counterparty_id": document.counterparty_id,
        "counterparty_name": counterparty.name if counterparty else document.counterparty_name,
        "document_no": document.document_no,
        "document_type": document.document_type,
        "document_date": _iso(document.document_date),
        "total_amount": _float(document.total_amount),
        "related_contract_id": document.related_contract_id,
        "related_invoice_id": document.related_invoice_id,
        "source_file_id": document.source_file_id,
        "confidence_score": document.confidence_score,
        "created_at": _iso(document.created_at),
    }


def _infer_invoice_balance(invoice: Invoice, db: Session) -> tuple[str, str | None, int | None]:
    contract = db.get(Contract, invoice.related_contract_id) if invoice.related_contract_id else None
    if contract and contract.contract_type == "purchase":
        return "payable", invoice.seller_name, invoice.counterparty_id
    if contract and contract.contract_type == "sales":
        return "receivable", invoice.buyer_name, invoice.counterparty_id
    if invoice.seller_name and not invoice.buyer_name:
        return "receivable", invoice.buyer_name, invoice.counterparty_id
    if invoice.buyer_name and not invoice.seller_name:
        return "payable", invoice.seller_name, invoice.counterparty_id
    return "receivable", invoice.buyer_name or invoice.seller_name, invoice.counterparty_id


def list_counterparty_balances(db: Session, ledger_id: int) -> list[dict[str, Any]]:
    """往来款项台账：按单位+余额方向汇总（来自已登记发票等余额事实）。"""
    invoices = (
        db.query(Invoice)
        .filter(Invoice.ledger_id == ledger_id)
        .order_by(Invoice.id.desc())
        .all()
    )
    buckets: dict[tuple[int | None, str | None, str], dict[str, Any]] = {}
    for invoice in invoices:
        balance_type, counterparty_name, counterparty_id = _infer_invoice_balance(invoice, db)
        key = (counterparty_id, counterparty_name, balance_type)
        bucket = buckets.setdefault(
            key,
            {
                "module_key": "counterparty_ledger",
                "ledger_id": ledger_id,
                "counterparty_id": counterparty_id,
                "counterparty_name": counterparty_name,
                "balance_type": balance_type,
                "balance_type_label": BALANCE_TYPE_LABELS.get(balance_type, balance_type),
                "total_amount": 0.0,
                "document_count": 0,
                "invoice_ids": [],
            },
        )
        amount = _float(invoice.total_amount) or 0.0
        bucket["total_amount"] += amount
        bucket["document_count"] += 1
        bucket["invoice_ids"].append(invoice.id)

    return sorted(
        buckets.values(),
        key=lambda item: (item["counterparty_name"] or "", item["balance_type"]),
    )


def list_module_registers(
    db: Session,
    module_key: str,
    ledger_id: int,
    *,
    execution_status: str | None = None,
    contract_type: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    if module_key not in VALID_MODULE_KEYS:
        raise ValueError(f"未知模块台账: {module_key}")

    if module_key == "counterparty_ledger":
        return list_counterparty_balances(db, ledger_id)

    if module_key in {"contract_register", "purchase", "sales"}:
        query = db.query(Contract).filter(Contract.ledger_id == ledger_id)
        if module_key == "purchase":
            query = query.filter(Contract.contract_type == "purchase")
        elif module_key == "sales":
            query = query.filter(Contract.contract_type == "sales")
        if execution_status:
            query = query.filter(Contract.execution_status == execution_status)
        if contract_type:
            query = query.filter(Contract.contract_type == contract_type)
        contracts = query.order_by(Contract.id.desc()).limit(limit).all()
        rows = [_contract_to_dict(item, db) for item in contracts]
        for row in rows:
            row["module_key"] = module_key
        return rows

    if module_key == "tax_invoice":
        invoices = (
            db.query(Invoice)
            .filter(Invoice.ledger_id == ledger_id)
            .order_by(Invoice.id.desc())
            .limit(limit)
            .all()
        )
        return [_invoice_to_dict(item, db) for item in invoices]

    if module_key == "bank_cash_flow":
        statements = (
            db.query(BankStatement)
            .filter(BankStatement.ledger_id == ledger_id)
            .order_by(BankStatement.id.desc())
            .limit(limit)
            .all()
        )
        return [_bank_to_dict(item, db) for item in statements]

    if module_key == "inventory_receipt":
        documents = (
            db.query(InventoryDocument)
            .filter(InventoryDocument.ledger_id == ledger_id)
            .order_by(InventoryDocument.id.desc())
            .limit(limit)
            .all()
        )
        return [_inventory_to_dict(item, db) for item in documents]

    return []


def get_module_register_summary(db: Session, ledger_id: int) -> dict[str, Any]:
    summary: dict[str, Any] = {"ledger_id": ledger_id, "modules": {}}
    for module_key in sorted(VALID_MODULE_KEYS):
        if module_key == "counterparty_ledger":
            rows = list_counterparty_balances(db, ledger_id)
            summary["modules"][module_key] = {
                "module_key": module_key,
                "module_label": MODULE_DEFINITIONS[module_key]["label"],
                "module_path": MODULE_DEFINITIONS[module_key]["module_path"],
                "count": len(rows),
            }
            continue

        if module_key in {"contract_register", "purchase", "sales", "tax_invoice", "bank_cash_flow", "inventory_receipt"}:
            if module_key == "contract_register":
                count = db.query(Contract).filter(Contract.ledger_id == ledger_id).count()
            elif module_key == "purchase":
                count = (
                    db.query(Contract)
                    .filter(Contract.ledger_id == ledger_id, Contract.contract_type == "purchase")
                    .count()
                )
            elif module_key == "sales":
                count = (
                    db.query(Contract)
                    .filter(Contract.ledger_id == ledger_id, Contract.contract_type == "sales")
                    .count()
                )
            elif module_key == "tax_invoice":
                count = db.query(Invoice).filter(Invoice.ledger_id == ledger_id).count()
            elif module_key == "bank_cash_flow":
                count = db.query(BankStatement).filter(BankStatement.ledger_id == ledger_id).count()
            else:
                count = db.query(InventoryDocument).filter(InventoryDocument.ledger_id == ledger_id).count()
            summary["modules"][module_key] = {
                "module_key": module_key,
                "module_label": MODULE_DEFINITIONS[module_key]["label"],
                "module_path": MODULE_DEFINITIONS[module_key]["module_path"],
                "count": count,
            }
    return summary
