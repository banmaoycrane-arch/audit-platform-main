from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.module_register_service import (
    EXECUTION_STATUS_LABELS,
    VALID_MODULE_KEYS,
    get_module_register_summary,
    list_module_registers,
)
from app.services.register_ingestion_service import MODULE_DEFINITIONS

router = APIRouter(prefix="/api/module-registers", tags=["module-registers"])


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
