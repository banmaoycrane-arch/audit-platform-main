from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from sqlalchemy.orm import Session

from app.db.models import BankStatement, Contract, InventoryDocument, Invoice
from app.db.session import get_db
from app.services.module_register_service import (
    EXECUTION_STATUS_LABELS,
    VALID_MODULE_KEYS,
    get_module_register_summary,
    list_module_registers,
)
from app.services.register_ingestion_service import MODULE_DEFINITIONS

router = APIRouter(prefix="/api/module-registers", tags=["module-registers"])


class ModuleRegisterUpdateRequest(BaseModel):
    fields: dict[str, Any]
    correction_reason: str | None = None


class ModuleRegisterArchiveRequest(BaseModel):
    archive_reason: str | None = None


REGISTER_MODEL_MAP = {
    "contract_register": Contract,
    "purchase": Contract,
    "sales": Contract,
    "tax_invoice": Invoice,
    "bank_cash_flow": BankStatement,
    "inventory_receipt": InventoryDocument,
}

REGISTER_EDITABLE_FIELDS = {
    "contract_register": {
        "contract_no", "contract_name", "contract_type", "sign_date", "start_date", "end_date",
        "contract_amount", "currency", "tax_rate", "tax_amount", "execution_status",
    },
    "purchase": {
        "contract_no", "contract_name", "contract_type", "sign_date", "start_date", "end_date",
        "contract_amount", "currency", "tax_rate", "tax_amount", "execution_status",
    },
    "sales": {
        "contract_no", "contract_name", "contract_type", "sign_date", "start_date", "end_date",
        "contract_amount", "currency", "tax_rate", "tax_amount", "execution_status",
    },
    "tax_invoice": {
        "invoice_no", "invoice_code", "invoice_type", "invoice_status", "invoice_date",
        "buyer_name", "buyer_tax_no", "seller_name", "seller_tax_no",
        "amount_excluding_tax", "tax_rate", "tax_amount", "total_amount",
    },
    "bank_cash_flow": {
        "transaction_no", "transaction_date", "transaction_time", "transaction_type",
        "account_name", "account_no", "bank_name", "counterparty_name",
        "counterparty_account", "counterparty_bank", "amount", "balance", "summary", "purpose", "remark",
    },
    "inventory_receipt": {
        "document_no", "document_type", "document_date", "warehouse_name", "warehouse_code",
        "counterparty_type", "counterparty_name", "counterparty_code", "total_quantity", "total_amount",
        "inspector", "inspect_date", "inspect_result",
    },
}

DATE_FIELDS = {
    "sign_date", "start_date", "end_date", "invoice_date", "transaction_date",
    "document_date", "inspect_date",
}

DECIMAL_FIELDS = {
    "contract_amount", "tax_rate", "tax_amount", "amount_excluding_tax", "total_amount",
    "amount", "balance", "total_quantity",
}

STATUS_ARCHIVED = "archived"


def _get_register_model(module_key: str):
    model = REGISTER_MODEL_MAP.get(module_key)
    if model is None:
        raise HTTPException(status_code=400, detail="该模块台账暂不支持行级编辑操作")
    return model


def _get_register_row(db: Session, module_key: str, row_id: int):
    model = _get_register_model(module_key)
    row = db.get(model, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="台账行不存在")
    if module_key == "purchase" and getattr(row, "contract_type", None) != "purchase":
        raise HTTPException(status_code=404, detail="采购台账行不存在")
    if module_key == "sales" and getattr(row, "contract_type", None) != "sales":
        raise HTTPException(status_code=404, detail="销售台账行不存在")
    return row


def _coerce_register_value(field_name: str, value: Any) -> Any:
    if value in ("", None):
        return None
    if field_name in DATE_FIELDS:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value)[:10])
    if field_name in DECIMAL_FIELDS:
        return Decimal(str(value))
    return value


def _apply_register_fields(row: Any, module_key: str, fields: dict[str, Any]) -> None:
    editable_fields = REGISTER_EDITABLE_FIELDS.get(module_key, set())
    rejected_fields = sorted(set(fields.keys()) - editable_fields)
    if rejected_fields:
        raise HTTPException(status_code=400, detail=f"字段不允许编辑: {', '.join(rejected_fields)}")
    for field_name, value in fields.items():
        setattr(row, field_name, _coerce_register_value(field_name, value))
    if hasattr(row, "updated_at"):
        row.updated_at = datetime.utcnow()


def _serialize_register_row(db: Session, module_key: str, row: Any) -> dict[str, Any]:
    return list_module_registers(db, module_key, row.ledger_id or 0, limit=500)


@router.get("/definitions")
def list_module_definitions() -> list[dict]:
    return [
        {
            "module_key": key,
            "module_label": meta["label"],
            "module_path": meta["module_path"],
        }
        for key, meta in MODULE_DEFINITIONS.items()
        if key != "general"
    ]


@router.get("/summary")
def module_register_summary(
    ledger_id: int = Query(..., description="账套 ID"),
    db: Session = Depends(get_db),
) -> dict:
    return get_module_register_summary(db, ledger_id)


@router.get("/execution-statuses")
def list_execution_statuses() -> list[dict]:
    return [
        {"value": key, "label": label}
        for key, label in EXECUTION_STATUS_LABELS.items()
    ]


@router.get("/{module_key}")
def get_module_registers(
    module_key: str,
    ledger_id: int = Query(..., description="账套 ID"),
    execution_status: str | None = Query(None, description="合同执行状态（合同类模块）"),
    contract_type: str | None = Query(None, description="合同类型"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> dict:
    if module_key not in VALID_MODULE_KEYS:
        raise HTTPException(status_code=404, detail=f"未知模块台账: {module_key}")

    try:
        items = list_module_registers(
            db,
            module_key,
            ledger_id,
            execution_status=execution_status,
            contract_type=contract_type,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    meta = MODULE_DEFINITIONS.get(module_key, MODULE_DEFINITIONS["general"])
    return {
        "module_key": module_key,
        "module_label": meta["label"],
        "module_path": meta["module_path"],
        "ledger_id": ledger_id,
        "count": len(items),
        "items": items,
    }


@router.patch("/{module_key}/{row_id}")
def update_module_register_row(
    module_key: str,
    row_id: int,
    payload: ModuleRegisterUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    if module_key not in VALID_MODULE_KEYS:
        raise HTTPException(status_code=404, detail=f"未知模块台账: {module_key}")
    row = _get_register_row(db, module_key, row_id)
    _apply_register_fields(row, module_key, payload.fields)
    db.add(row)
    db.commit()
    return {"status": "success", "message": "台账行已更新", "row_id": row_id}


@router.post("/{module_key}/{row_id}/correct")
def correct_module_register_row(
    module_key: str,
    row_id: int,
    payload: ModuleRegisterUpdateRequest,
    db: Session = Depends(get_db),
) -> dict:
    if module_key not in VALID_MODULE_KEYS:
        raise HTTPException(status_code=404, detail=f"未知模块台账: {module_key}")
    if not payload.correction_reason:
        raise HTTPException(status_code=400, detail="更正原因不能为空")
    row = _get_register_row(db, module_key, row_id)
    _apply_register_fields(row, module_key, payload.fields)
    if hasattr(row, "risk_flags"):
        risk_flags = dict(row.risk_flags or {})
        corrections = list(risk_flags.get("corrections") or [])
        corrections.append({
            "reason": payload.correction_reason,
            "corrected_at": datetime.utcnow().isoformat(),
            "fields": sorted(payload.fields.keys()),
        })
        risk_flags["corrections"] = corrections
        row.risk_flags = risk_flags
    db.add(row)
    db.commit()
    return {"status": "success", "message": "台账行已更正", "row_id": row_id}


@router.post("/{module_key}/{row_id}/archive")
def archive_module_register_row(
    module_key: str,
    row_id: int,
    payload: ModuleRegisterArchiveRequest,
    db: Session = Depends(get_db),
) -> dict:
    if module_key not in VALID_MODULE_KEYS:
        raise HTTPException(status_code=404, detail=f"未知模块台账: {module_key}")
    row = _get_register_row(db, module_key, row_id)
    if hasattr(row, "execution_status"):
        row.execution_status = STATUS_ARCHIVED
    elif hasattr(row, "invoice_status"):
        row.invoice_status = STATUS_ARCHIVED
    elif hasattr(row, "inspect_result"):
        row.inspect_result = STATUS_ARCHIVED
    elif hasattr(row, "remark"):
        archive_note = payload.archive_reason or "用户归档"
        row.remark = f"{row.remark or ''} [已归档：{archive_note}]".strip()
    if hasattr(row, "updated_at"):
        row.updated_at = datetime.utcnow()
    db.add(row)
    db.commit()
    return {"status": "success", "message": "台账行已归档", "row_id": row_id}


@router.delete("/{module_key}/{row_id}")
def delete_module_register_row(
    module_key: str,
    row_id: int,
    db: Session = Depends(get_db),
) -> dict:
    if module_key not in VALID_MODULE_KEYS:
        raise HTTPException(status_code=404, detail=f"未知模块台账: {module_key}")
    row = _get_register_row(db, module_key, row_id)
    db.delete(row)
    db.commit()
    return {"status": "success", "message": "台账行已删除", "row_id": row_id}

