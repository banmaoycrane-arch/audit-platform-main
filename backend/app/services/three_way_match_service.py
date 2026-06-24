"""采购三单匹配服务（Phase B3）：合同 ↔ 入库单 ↔ 发票。"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Contract, Counterparty, InventoryDocument, Invoice

AMOUNT_TOLERANCE = Decimal("0.01")
INVENTORY_IN_TYPES = {"inventory_in", "purchase_in", "purchase"}

EXCEPTION_LABELS = {
    "missing_invoice": "缺发票",
    "missing_inventory": "缺入库单",
    "amount_mismatch": "金额不一致",
}

MATCH_STATUS_LABELS = {
    "matched": "已匹配",
    "exception": "有异常",
    "incomplete": "单据不全",
}


def _round_amount(value: Any) -> float:
    if value is None:
        return 0.0
    return float(Decimal(str(value)).quantize(Decimal("0.01")))


def _amounts_close(left: float, right: float) -> bool:
    return abs(Decimal(str(left)) - Decimal(str(right))) <= AMOUNT_TOLERANCE


def _contract_dict(contract: Contract, db: Session) -> dict[str, Any]:
    counterparty = db.get(Counterparty, contract.counterparty_id) if contract.counterparty_id else None
    return {
        "id": contract.id,
        "contract_no": contract.contract_no,
        "contract_name": contract.contract_name,
        "contract_amount": _round_amount(contract.contract_amount),
        "execution_status": contract.execution_status,
        "counterparty_name": counterparty.name if counterparty else None,
    }


def _invoice_dict(invoice: Invoice) -> dict[str, Any]:
    return {
        "id": invoice.id,
        "invoice_no": invoice.invoice_no,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "total_amount": _round_amount(invoice.total_amount),
        "seller_name": invoice.seller_name,
        "buyer_name": invoice.buyer_name,
    }


def _inventory_dict(document: InventoryDocument) -> dict[str, Any]:
    return {
        "id": document.id,
        "document_no": document.document_no,
        "document_type": document.document_type,
        "document_date": document.document_date.isoformat() if document.document_date else None,
        "total_amount": _round_amount(document.total_amount),
        "counterparty_name": document.counterparty_name,
    }


def _linked_invoices(db: Session, ledger_id: int, contract_id: int) -> list[Invoice]:
    return (
        db.query(Invoice)
        .filter(Invoice.ledger_id == ledger_id, Invoice.related_contract_id == contract_id)
        .order_by(Invoice.id.asc())
        .all()
    )


def _linked_inventory(db: Session, ledger_id: int, contract_id: int) -> list[InventoryDocument]:
    return (
        db.query(InventoryDocument)
        .filter(
            InventoryDocument.ledger_id == ledger_id,
            InventoryDocument.related_contract_id == contract_id,
        )
        .order_by(InventoryDocument.id.asc())
        .all()
    )


def _sum_amounts(items: list[Any], attr: str = "total_amount") -> float:
    return _round_amount(sum(_round_amount(getattr(item, attr, 0)) for item in items))


def _build_checks(
    contract_amount: float,
    invoice_total: float,
    inventory_total: float,
    has_invoice: bool,
    has_inventory: bool,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    if has_invoice:
        checks.append(
            {
                "check_key": "contract_vs_invoice",
                "label": "合同金额 vs 发票合计",
                "left_amount": contract_amount,
                "right_amount": invoice_total,
                "passed": _amounts_close(contract_amount, invoice_total) if contract_amount > 0 else True,
            }
        )
    if has_inventory:
        checks.append(
            {
                "check_key": "contract_vs_inventory",
                "label": "合同金额 vs 入库合计",
                "left_amount": contract_amount,
                "right_amount": inventory_total,
                "passed": _amounts_close(contract_amount, inventory_total) if contract_amount > 0 else True,
            }
        )
    if has_invoice and has_inventory:
        checks.append(
            {
                "check_key": "invoice_vs_inventory",
                "label": "发票合计 vs 入库合计",
                "left_amount": invoice_total,
                "right_amount": inventory_total,
                "passed": _amounts_close(invoice_total, inventory_total),
            }
        )
    return checks


def _build_exceptions(
    *,
    has_invoice: bool,
    has_inventory: bool,
    contract_amount: float,
    invoice_total: float,
    inventory_total: float,
) -> list[dict[str, Any]]:
    exceptions: list[dict[str, Any]] = []

    if not has_invoice:
        exceptions.append(
            {
                "exception_type": "missing_invoice",
                "exception_label": EXCEPTION_LABELS["missing_invoice"],
                "message": "采购合同下未找到关联发票",
            }
        )
    if not has_inventory:
        exceptions.append(
            {
                "exception_type": "missing_inventory",
                "exception_label": EXCEPTION_LABELS["missing_inventory"],
                "message": "采购合同下未找到关联入库单",
            }
        )

    if has_invoice and contract_amount > 0 and not _amounts_close(contract_amount, invoice_total):
        exceptions.append(
            {
                "exception_type": "amount_mismatch",
                "exception_label": EXCEPTION_LABELS["amount_mismatch"],
                "message": f"合同金额 {contract_amount} 与发票合计 {invoice_total} 不一致",
                "left_amount": contract_amount,
                "right_amount": invoice_total,
            }
        )
    if has_inventory and contract_amount > 0 and not _amounts_close(contract_amount, inventory_total):
        exceptions.append(
            {
                "exception_type": "amount_mismatch",
                "exception_label": EXCEPTION_LABELS["amount_mismatch"],
                "message": f"合同金额 {contract_amount} 与入库合计 {inventory_total} 不一致",
                "left_amount": contract_amount,
                "right_amount": inventory_total,
            }
        )
    if has_invoice and has_inventory and not _amounts_close(invoice_total, inventory_total):
        exceptions.append(
            {
                "exception_type": "amount_mismatch",
                "exception_label": EXCEPTION_LABELS["amount_mismatch"],
                "message": f"发票合计 {invoice_total} 与入库合计 {inventory_total} 不一致",
                "left_amount": invoice_total,
                "right_amount": inventory_total,
            }
        )

    return exceptions


def _resolve_match_status(exceptions: list[dict[str, Any]]) -> str:
    if not exceptions:
        return "matched"
    missing_only = all(exc["exception_type"] in {"missing_invoice", "missing_inventory"} for exc in exceptions)
    return "incomplete" if missing_only and len(exceptions) > 0 else "exception"


def match_purchase_contract(db: Session, ledger_id: int, contract_id: int) -> dict[str, Any]:
    contract = (
        db.query(Contract)
        .filter(
            Contract.id == contract_id,
            Contract.ledger_id == ledger_id,
            Contract.contract_type == "purchase",
        )
        .first()
    )
    if contract is None:
        raise ValueError("purchase contract not found for ledger")

    invoices = _linked_invoices(db, ledger_id, contract_id)
    inventory_docs = [
        doc for doc in _linked_inventory(db, ledger_id, contract_id) if doc.document_type in INVENTORY_IN_TYPES
    ]
    if not inventory_docs:
        inventory_docs = _linked_inventory(db, ledger_id, contract_id)

    contract_amount = _round_amount(contract.contract_amount)
    invoice_total = _sum_amounts(invoices)
    inventory_total = _sum_amounts(inventory_docs)
    has_invoice = len(invoices) > 0
    has_inventory = len(inventory_docs) > 0

    checks = _build_checks(contract_amount, invoice_total, inventory_total, has_invoice, has_inventory)
    exceptions = _build_exceptions(
        has_invoice=has_invoice,
        has_inventory=has_inventory,
        contract_amount=contract_amount,
        invoice_total=invoice_total,
        inventory_total=inventory_total,
    )
    match_status = _resolve_match_status(exceptions)

    result = {
        "ledger_id": ledger_id,
        "contract": _contract_dict(contract, db),
        "invoices": [_invoice_dict(item) for item in invoices],
        "inventory_documents": [_inventory_dict(item) for item in inventory_docs],
        "totals": {
            "contract_amount": contract_amount,
            "invoice_total": invoice_total,
            "inventory_total": inventory_total,
        },
        "checks": checks,
        "exceptions": exceptions,
        "match_status": match_status,
        "match_status_label": MATCH_STATUS_LABELS.get(match_status, match_status),
    }
    try:
        from app.services import audit_workflow_service

        audit_workflow_service.sync_purchase_match_procedure(
            db,
            ledger_id,
            contract_id,
            match_status,
            title=contract.contract_name or contract.contract_no,
        )
    except Exception:
        pass
    return result


def match_purchase_cycle(db: Session, ledger_id: int, contract_id: int | None = None) -> list[dict[str, Any]]:
    if contract_id is not None:
        return [match_purchase_contract(db, ledger_id, contract_id)]

    contracts = (
        db.query(Contract)
        .filter(Contract.ledger_id == ledger_id, Contract.contract_type == "purchase")
        .order_by(Contract.id.asc())
        .all()
    )
    return [match_purchase_contract(db, ledger_id, contract.id) for contract in contracts]


def summarize_purchase_matches(db: Session, ledger_id: int) -> dict[str, Any]:
    results = match_purchase_cycle(db, ledger_id)
    matched = [item for item in results if item["match_status"] == "matched"]
    incomplete = [item for item in results if item["match_status"] == "incomplete"]
    exceptions = [item for item in results if item["match_status"] == "exception"]

    flat_exceptions: list[dict[str, Any]] = []
    for result in results:
        for exc in result["exceptions"]:
            flat_exceptions.append(
                {
                    "contract_id": result["contract"]["id"],
                    "contract_no": result["contract"]["contract_no"],
                    "contract_name": result["contract"]["contract_name"],
                    "match_status": result["match_status"],
                    **exc,
                }
            )

    return {
        "ledger_id": ledger_id,
        "contract_count": len(results),
        "matched_count": len(matched),
        "incomplete_count": len(incomplete),
        "exception_count": len(exceptions),
        "exception_items": flat_exceptions,
        "results": results,
    }
