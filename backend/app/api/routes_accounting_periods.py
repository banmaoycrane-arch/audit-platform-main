from datetime import date
from calendar import monthrange

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, Organization, PeriodSnapshot
from app.db.session import get_db
from app.schemas.accounting_period import (
    AccountingPeriodCreate,
    AccountingPeriodRead,
    AccountingPeriodRecommendation,
    AccountingPeriodSuggestion,
    PeriodActionRequest,
    PeriodSnapshotResponse,
    SnapshotCreateRequest,
    PeriodBatchCreateRequest,
    PeriodBatchCreateResponse,
)
from app.services.accounting_period_service import AccountingPeriodService
from app.services import period_close_service
from app.services.ledger_context_service import (
    resolve_organization_id_for_ledger,
    resolve_or_create_organization_for_ledger,
)

router = APIRouter(prefix="/api/accounting-periods", tags=["accounting-periods"])


def _latest_snapshot_info(db: Session, period_id: int) -> tuple[str | None, int]:
    snapshot = (
        db.query(PeriodSnapshot)
        .filter(PeriodSnapshot.period_id == period_id)
        .order_by(PeriodSnapshot.snapshot_version.desc(), PeriodSnapshot.id.desc())
        .first()
    )
    if not snapshot:
        return None, 0
    return snapshot.snapshot_status, snapshot.snapshot_version


def _period_response(db: Session, period: AccountingPeriod, source: str = "live_calculation") -> AccountingPeriodRead:
    snapshot_status, snapshot_version = _latest_snapshot_info(db, period.id)
    return AccountingPeriodRead(
        id=period.id,
        organization_id=period.organization_id,
        period_code=period.period_code,
        period_type=period.period_type,
        start_date=period.start_date,
        end_date=period.end_date,
        status=period.status,
        snapshot_status=snapshot_status,
        snapshot_version=snapshot_version,
        source=source,
        closed_at=period.closed_at,
        reopened_at=period.reopened_at,
        created_at=period.created_at,
        updated_at=period.updated_at,
    )


def _ensure_period_exists(db: Session, period_id: int) -> AccountingPeriod:
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")
    return period


def _build_period_suggestion(target_date: date, period_type: str) -> AccountingPeriodSuggestion:
    if period_type == "yearly":
        return AccountingPeriodSuggestion(
            period_code=str(target_date.year),
            period_type="yearly",
            start_date=date(target_date.year, 1, 1),
            end_date=date(target_date.year, 12, 31),
        )
    last_day = monthrange(target_date.year, target_date.month)[1]
    return AccountingPeriodSuggestion(
        period_code=f"{target_date.year}-{target_date.month:02d}",
        period_type="monthly",
        start_date=date(target_date.year, target_date.month, 1),
        end_date=date(target_date.year, target_date.month, last_day),
    )


@router.post("", response_model=AccountingPeriodRead)
def create_period(payload: AccountingPeriodCreate, db: Session = Depends(get_db)) -> AccountingPeriodRead:
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="期间开始日期不能晚于结束日期")

    organization_id = payload.organization_id
    if payload.ledger_id is not None:
        resolved_org_id = resolve_organization_id_for_ledger(db, payload.ledger_id)
        if resolved_org_id is not None:
            organization_id = resolved_org_id
        elif organization_id is None:
            organization_id = resolve_or_create_organization_for_ledger(db, payload.ledger_id)

    if organization_id is None:
        raise HTTPException(status_code=400, detail="无法确定组织，请先完成账簿导入或指定组织 ID")

    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="组织不存在")

    overlapped_period = (
        db.query(AccountingPeriod)
        .filter(
            AccountingPeriod.organization_id == organization_id,
            AccountingPeriod.start_date <= payload.end_date,
            AccountingPeriod.end_date >= payload.start_date,
        )
        .first()
    )
    if overlapped_period:
        raise HTTPException(status_code=400, detail="同一组织内会计期间日期不能重叠")

    period = AccountingPeriod(
        organization_id=organization_id,
        ledger_id=payload.ledger_id,
        period_code=payload.period_code,
        period_type=payload.period_type,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status="open",
    )
    db.add(period)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="同一组织内期间编码不能重复")
    db.refresh(period)
    return _period_response(db, period)


@router.get("", response_model=list[AccountingPeriodRead])
def list_periods(
    organization_id: int | None = None,
    ledger_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[AccountingPeriodRead]:
    try:
        if ledger_id is not None and organization_id is None:
            organization_id = resolve_organization_id_for_ledger(db, ledger_id)

        query = db.query(AccountingPeriod).order_by(AccountingPeriod.start_date.desc(), AccountingPeriod.id.desc())
        if organization_id is not None:
            query = query.filter(AccountingPeriod.organization_id == organization_id)
        if ledger_id is not None:
            query = query.filter(
                or_(AccountingPeriod.ledger_id == ledger_id, AccountingPeriod.ledger_id.is_(None))
            )
        return [_period_response(db, period) for period in query.all()]
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=422, detail=f"会计期间加载失败，请检查期间表结构或迁移状态：{exc}")


@router.get("/recommendation", response_model=AccountingPeriodRecommendation)
def recommend_period(
    target_date: date | None = None,
    organization_id: int | None = None,
    period_type: str = "monthly",
    db: Session = Depends(get_db),
) -> AccountingPeriodRecommendation:
    use_date = target_date or date.today()
    query = db.query(AccountingPeriod).filter(
        AccountingPeriod.start_date <= use_date,
        AccountingPeriod.end_date >= use_date,
    )
    if organization_id:
        query = query.filter(AccountingPeriod.organization_id == organization_id)

    matched_period = (
        query.filter(AccountingPeriod.status.in_(["open", "reopened"]))
        .order_by(AccountingPeriod.start_date.desc(), AccountingPeriod.id.desc())
        .first()
    )
    if matched_period:
        return AccountingPeriodRecommendation(
            matched_period=_period_response(db, matched_period),
            suggested_period=None,
            reason="目标日期落入 open/reopened 会计期间，系统建议直接使用该期间",
        )

    return AccountingPeriodRecommendation(
        matched_period=None,
        suggested_period=_build_period_suggestion(use_date, period_type),
        reason="目标日期没有匹配的 open/reopened 会计期间，系统按日期建议新建期间",
    )


@router.post("/{period_id}/snapshots", response_model=PeriodSnapshotResponse)
def create_snapshots(
    period_id: int,
    payload: SnapshotCreateRequest | None = None,
    db: Session = Depends(get_db),
) -> PeriodSnapshotResponse:
    period = _ensure_period_exists(db, period_id)
    service = AccountingPeriodService(db)
    try:
        snapshots = service.generate_period_snapshots(period_id, dimensions=payload.dimensions if payload else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.refresh(period)
    return PeriodSnapshotResponse(period=_period_response(db, period, source="snapshot"), snapshots=snapshots)


@router.get("/{period_id}/summary")
def get_period_summary(
    period_id: int,
    dimension_type: str = "period_total",
    db: Session = Depends(get_db),
) -> dict:
    period = _ensure_period_exists(db, period_id)
    service = AccountingPeriodService(db)
    try:
        summary = service.get_period_summary(period_id, dimension_type=dimension_type)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    snapshot_status, snapshot_version = _latest_snapshot_info(db, period_id)
    summary["period_status"] = period.status
    summary["snapshot_status"] = snapshot_status
    summary["snapshot_version"] = snapshot_version
    return summary


@router.post("/{period_id}/close", response_model=AccountingPeriodRead)
def close_period(
    period_id: int,
    payload: PeriodActionRequest | None = None,
    db: Session = Depends(get_db),
) -> AccountingPeriodRead:
    _ensure_period_exists(db, period_id)
    service = AccountingPeriodService(db)
    try:
        period = service.close_period(
            period_id,
            operator=payload.operator if payload else "system",
            reason=payload.reason if payload else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _period_response(db, period, source="snapshot")


@router.post("/{period_id}/reopen", response_model=AccountingPeriodRead)
def reopen_period(
    period_id: int,
    payload: PeriodActionRequest | None = None,
    db: Session = Depends(get_db),
) -> AccountingPeriodRead:
    _ensure_period_exists(db, period_id)
    service = AccountingPeriodService(db)
    try:
        period = service.reopen_period(
            period_id,
            operator=payload.operator if payload else "system",
            reason=payload.reason if payload else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _period_response(db, period)


@router.post("/{period_id}/pl-transfer")
def pl_transfer(period_id: int, db: Session = Depends(get_db)) -> dict:
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")
    try:
        return period_close_service.auto_pl_transfer(db, period.organization_id, period_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/{period_id}/pl-transfer/reverse")
def pl_transfer_reverse(period_id: int, db: Session = Depends(get_db)) -> dict:
    period = db.get(AccountingPeriod, period_id)
    if not period:
        raise HTTPException(status_code=404, detail="会计期间不存在")
    try:
        return period_close_service.reverse_pl_transfer(db, period.organization_id, period_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/batch-create", response_model=PeriodBatchCreateResponse)
def batch_create_periods(
    payload: PeriodBatchCreateRequest,
    db: Session = Depends(get_db),
) -> PeriodBatchCreateResponse:
    if payload.start_date > payload.end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")

    organization_id = payload.organization_id
    if payload.ledger_id is not None:
        resolved_org_id = resolve_organization_id_for_ledger(db, payload.ledger_id)
        if resolved_org_id is not None:
            organization_id = resolved_org_id
        elif organization_id is None:
            organization_id = resolve_or_create_organization_for_ledger(db, payload.ledger_id)

    if organization_id is None:
        raise HTTPException(status_code=400, detail="无法确定组织，请先完成账簿导入或指定组织 ID")

    organization = db.get(Organization, organization_id)
    if not organization:
        raise HTTPException(status_code=404, detail="组织不存在")

    existing_periods = (
        db.query(AccountingPeriod)
        .filter(AccountingPeriod.organization_id == organization_id)
        .all()
    )

    created_periods: list[AccountingPeriod] = []
    skipped_periods: list[str] = []

    current_year = payload.start_date.year
    current_month = payload.start_date.month
    end_year = payload.end_date.year
    end_month = payload.end_date.month

    while (current_year, current_month) <= (end_year, end_month):
        period_code = f"{current_year}-{current_month:02d}"
        start_date = date(current_year, current_month, 1)
        last_day = monthrange(current_year, current_month)[1]
        end_date = date(current_year, current_month, last_day)

        overlapped = False
        for existing in existing_periods:
            if existing.start_date <= end_date and existing.end_date >= start_date:
                overlapped = True
                break

        if overlapped:
            skipped_periods.append(period_code)
        else:
            period = AccountingPeriod(
                organization_id=organization_id,
                ledger_id=payload.ledger_id,
                period_code=period_code,
                period_type="monthly",
                start_date=start_date,
                end_date=end_date,
                status="open",
            )
            db.add(period)
            created_periods.append(period)

        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="批量创建期间时发生数据冲突，请稍后重试")

    for period in created_periods:
        db.refresh(period)

    return PeriodBatchCreateResponse(
        created_count=len(created_periods),
        skipped_count=len(skipped_periods),
        created_periods=[_period_response(db, p) for p in created_periods],
        skipped_period_codes=skipped_periods,
    )
