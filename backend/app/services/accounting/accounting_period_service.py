from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod, PeriodCloseLog, PeriodSnapshot


DEFAULT_SNAPSHOT_DIMENSIONS = ["account", "entity", "period_total"]
SUPPORTED_SNAPSHOT_DIMENSIONS = set(DEFAULT_SNAPSHOT_DIMENSIONS)


class AccountingPeriodService:
    def __init__(self, db: Session):
        self.db = db

    def get_period_summary(self, period_id: int, dimension_type: str = "period_total") -> dict[str, Any]:
        if dimension_type not in SUPPORTED_SNAPSHOT_DIMENSIONS:
            raise ValueError(f"Unsupported snapshot dimension: {dimension_type}")

        period = self.db.get(AccountingPeriod, period_id)
        if not period:
            raise ValueError(f"Accounting period {period_id} not found")

        latest_valid_snapshot_version = (
            self.db.query(func.max(PeriodSnapshot.snapshot_version))
            .filter(
                PeriodSnapshot.period_id == period_id,
                PeriodSnapshot.dimension_type == dimension_type,
                PeriodSnapshot.snapshot_status == "valid",
            )
            .scalar()
        )
        if latest_valid_snapshot_version:
            snapshots = (
                self.db.query(PeriodSnapshot)
                .filter(
                    PeriodSnapshot.period_id == period_id,
                    PeriodSnapshot.dimension_type == dimension_type,
                    PeriodSnapshot.snapshot_status == "valid",
                    PeriodSnapshot.snapshot_version == latest_valid_snapshot_version,
                )
                .order_by(PeriodSnapshot.dimension_code, PeriodSnapshot.dimension_id, PeriodSnapshot.id)
                .all()
            )
            return self._format_period_summary(
                period_id=period_id,
                dimension_type=dimension_type,
                source="snapshot",
                items=[self._snapshot_to_summary_item(snapshot) for snapshot in snapshots],
            )

        return self._format_period_summary(
            period_id=period_id,
            dimension_type=dimension_type,
            source="live_calculation",
            items=self._build_live_summary_items(period, dimension_type),
        )

    def get_latest_snapshot_version(self, period_id: int) -> int:
        version = (
            self.db.query(func.max(PeriodSnapshot.snapshot_version))
            .filter(PeriodSnapshot.period_id == period_id)
            .scalar()
        )
        return int(version or 0)

    def invalidate_period_snapshots(self, period_id: int, commit: bool = True) -> None:
        snapshots = (
            self.db.query(PeriodSnapshot)
            .filter(
                PeriodSnapshot.period_id == period_id,
                PeriodSnapshot.snapshot_status == "valid",
            )
            .all()
        )
        now = datetime.now(timezone.utc)
        for snapshot in snapshots:
            snapshot.snapshot_status = "invalidated"
            snapshot.invalidated_at = now
        if commit:
            self.db.commit()
        else:
            self.db.flush()

    def generate_period_snapshots(
        self,
        period_id: int,
        dimensions: list[str] | None = None,
        commit: bool = True,
    ) -> list[PeriodSnapshot]:
        period = self.db.get(AccountingPeriod, period_id)
        if not period:
            raise ValueError(f"Accounting period {period_id} not found")

        selected_dimensions = self._normalize_dimensions(dimensions)
        new_version = self.get_latest_snapshot_version(period_id) + 1
        self.invalidate_period_snapshots(period_id, commit=commit)

        source_scope = self._build_source_scope(period)
        generation_params = {
            "dimensions": selected_dimensions,
            "currency": "CNY",
            "single_currency": True,
            "foreign_currency_conversion": False,
            "amount_basis": "debit_amount_minus_credit_amount",
        }

        snapshots: list[PeriodSnapshot] = []
        for dimension in selected_dimensions:
            if dimension == "account":
                snapshots.extend(self._build_account_snapshots(period, new_version, source_scope, generation_params))
            elif dimension == "entity":
                snapshots.extend(self._build_entity_snapshots(period, new_version, source_scope, generation_params))
            elif dimension == "period_total":
                snapshots.append(self._build_period_total_snapshot(period, new_version, source_scope, generation_params))

        self.db.add_all(snapshots)
        if commit:
            self.db.commit()
            for snapshot in snapshots:
                self.db.refresh(snapshot)
        else:
            self.db.flush()
        return snapshots

    def close_period(
        self,
        period_id: int,
        operator: str = "system",
        reason: str | None = None,
    ) -> AccountingPeriod:
        period = self.db.get(AccountingPeriod, period_id)
        if not period:
            raise ValueError(f"Accounting period {period_id} not found")
        if period.status == "closed":
            raise ValueError(f"Accounting period {period_id} is already closed")

        # 结账前必须先完成损益结转，并再次校验资产负债表平衡
        if period.status != "pl_transferred":
            raise ValueError(
                f"会计期间 {period.period_code} 尚未结转损益，请先执行损益结转再结账"
            )

        from app.services.accounting import financial_statements_service
        effective_ledger_id = period.ledger_id
        balance_sheet = financial_statements_service.balance_sheet(self.db, effective_ledger_id, period_id)
        if not balance_sheet.get("is_balanced"):
            raise ValueError(
                f"结账前资产负债表不平衡：资产总计 {balance_sheet.get('assets_total')} "
                f"不等于负债及权益总计 {balance_sheet.get('liabilities_total')} + {balance_sheet.get('equity_total')}，"
                f"请先排查凭证、期初余额及结转分录后再结账"
            )

        old_status = period.status
        transaction_id = f"period-close-{uuid4()}"
        try:
            snapshots = self.generate_period_snapshots(period_id, commit=False)
            snapshot_version = snapshots[0].snapshot_version if snapshots else self.get_latest_snapshot_version(period_id)
            period.status = "closed"
            period.closed_at = datetime.now(timezone.utc)
            period.updated_at = period.closed_at

            self.db.add(
                PeriodCloseLog(
                    organization_id=period.organization_id,
                    period_id=period.id,
                    action_type="close",
                    transaction_id=transaction_id,
                    operator=operator,
                    reason=reason,
                    old_status=old_status,
                    new_status="closed",
                    snapshot_version=snapshot_version,
                )
            )
            self.db.commit()
            self.db.refresh(period)
            return period
        except Exception:
            self.db.rollback()
            raise

    def reopen_period(
        self,
        period_id: int,
        operator: str = "system",
        reason: str | None = None,
    ) -> AccountingPeriod:
        period = self.db.get(AccountingPeriod, period_id)
        if not period:
            raise ValueError(f"Accounting period {period_id} not found")
        if period.status != "closed":
            raise ValueError(f"Accounting period {period_id} is not closed")

        old_status = period.status
        transaction_id = f"period-reopen-{uuid4()}"
        try:
            snapshot_version = self.get_latest_snapshot_version(period_id)
            self.invalidate_period_snapshots(period_id, commit=False)

            now = datetime.now(timezone.utc)
            period.status = "reopened"
            period.reopened_at = now
            period.updated_at = now

            self.db.add(
                PeriodCloseLog(
                    organization_id=period.organization_id,
                    period_id=period.id,
                    action_type="reopen",
                    transaction_id=transaction_id,
                    operator=operator,
                    reason=reason,
                    old_status=old_status,
                    new_status="reopened",
                    snapshot_version=snapshot_version,
                )
            )
            self.db.commit()
            self.db.refresh(period)
            return period
        except Exception:
            self.db.rollback()
            raise

    def ensure_period_open_for_date(self, organization_id: int, target_date: date) -> None:
        closed_period = (
            self.db.query(AccountingPeriod)
            .filter(
                AccountingPeriod.organization_id == organization_id,
                AccountingPeriod.status == "closed",
                AccountingPeriod.start_date <= target_date,
                AccountingPeriod.end_date >= target_date,
            )
            .first()
        )
        if closed_period:
            raise ValueError(f"Accounting period {closed_period.period_code} is closed")

    def _normalize_dimensions(self, dimensions: Iterable[str] | None) -> list[str]:
        selected_dimensions = list(dimensions or DEFAULT_SNAPSHOT_DIMENSIONS)
        unsupported_dimensions = set(selected_dimensions) - SUPPORTED_SNAPSHOT_DIMENSIONS
        if unsupported_dimensions:
            raise ValueError(f"Unsupported snapshot dimensions: {', '.join(sorted(unsupported_dimensions))}")
        return selected_dimensions

    def _period_entries_query(self, period: AccountingPeriod) -> Any:
        return self.db.query(AccountingEntry).filter(
            AccountingEntry.organization_id == period.organization_id,
            AccountingEntry.voucher_date >= period.start_date,
            AccountingEntry.voucher_date <= period.end_date,
        )

    def _amount_expression(self) -> Any:
        return func.coalesce(func.sum(AccountingEntry.debit_amount - AccountingEntry.credit_amount), 0)

    def _build_source_scope(self, period: AccountingPeriod) -> dict[str, Any]:
        return {
            "period_id": period.id,
            "organization_id": period.organization_id,
            "period_code": period.period_code,
            "start_date": period.start_date.isoformat(),
            "end_date": period.end_date.isoformat(),
            "source_table": "accounting_entries",
            "date_field": "voucher_date",
            "currency": "CNY",
        }

    def _format_period_summary(self, period_id: int, dimension_type: str, source: str, items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "period_id": period_id,
            "dimension_type": dimension_type,
            "source": source,
            "currency": "CNY",
            "items": items,
        }

    def _snapshot_to_summary_item(self, snapshot: PeriodSnapshot) -> dict[str, Any]:
        return {
            "dimension_type": snapshot.dimension_type,
            "dimension_id": snapshot.dimension_id,
            "dimension_code": snapshot.dimension_code,
            "dimension_name": snapshot.dimension_name,
            "amount": snapshot.amount,
        }

    def _build_live_summary_items(self, period: AccountingPeriod, dimension_type: str) -> list[dict[str, Any]]:
        if dimension_type == "account":
            return self._build_live_account_summary_items(period)
        if dimension_type == "entity":
            return self._build_live_entity_summary_items(period)
        return [self._build_live_period_total_summary_item(period)]

    def _build_live_account_summary_items(self, period: AccountingPeriod) -> list[dict[str, Any]]:
        rows = (
            self._period_entries_query(period)
            .with_entities(
                AccountingEntry.account_code,
                AccountingEntry.account_name,
                self._amount_expression().label("amount"),
            )
            .group_by(AccountingEntry.account_code, AccountingEntry.account_name)
            .order_by(AccountingEntry.account_code)
            .all()
        )
        return [
            {
                "dimension_type": "account",
                "dimension_id": None,
                "dimension_code": account_code,
                "dimension_name": account_name,
                "amount": amount,
            }
            for account_code, account_name, amount in rows
        ]

    def _build_live_entity_summary_items(self, period: AccountingPeriod) -> list[dict[str, Any]]:
        rows = (
            self._period_entries_query(period)
            .with_entities(
                AccountingEntry.entity_id,
                AccountingEntry.original_entity_name,
                self._amount_expression().label("amount"),
            )
            .group_by(AccountingEntry.entity_id, AccountingEntry.original_entity_name)
            .order_by(AccountingEntry.entity_id)
            .all()
        )
        return [
            {
                "dimension_type": "entity",
                "dimension_id": entity_id,
                "dimension_code": None,
                "dimension_name": original_entity_name,
                "amount": amount,
            }
            for entity_id, original_entity_name, amount in rows
        ]

    def _build_live_period_total_summary_item(self, period: AccountingPeriod) -> dict[str, Any]:
        amount = self._period_entries_query(period).with_entities(self._amount_expression()).scalar()
        return {
            "dimension_type": "period_total",
            "dimension_id": None,
            "dimension_code": "period_total",
            "dimension_name": "期间总计",
            "amount": amount or 0,
        }

    def _build_snapshot(
        self,
        period: AccountingPeriod,
        snapshot_version: int,
        dimension_type: str,
        amount: Decimal | int | float,
        source_scope: dict[str, Any],
        generation_params: dict[str, Any],
        dimension_id: int | None = None,
        dimension_code: str | None = None,
        dimension_name: str | None = None,
    ) -> PeriodSnapshot:
        return PeriodSnapshot(
            organization_id=period.organization_id,
            ledger_id=period.ledger_id,
            period_id=period.id,
            snapshot_version=snapshot_version,
            dimension_type=dimension_type,
            dimension_id=dimension_id,
            dimension_code=dimension_code,
            dimension_name=dimension_name,
            amount=amount,
            currency="CNY",
            source_scope=source_scope,
            generation_params=generation_params,
            snapshot_status="valid",
        )

    def _build_account_snapshots(
        self,
        period: AccountingPeriod,
        snapshot_version: int,
        source_scope: dict[str, Any],
        generation_params: dict[str, Any],
    ) -> list[PeriodSnapshot]:
        rows = (
            self._period_entries_query(period)
            .with_entities(
                AccountingEntry.account_code,
                AccountingEntry.account_name,
                self._amount_expression().label("amount"),
            )
            .group_by(AccountingEntry.account_code, AccountingEntry.account_name)
            .all()
        )
        return [
            self._build_snapshot(
                period=period,
                snapshot_version=snapshot_version,
                dimension_type="account",
                dimension_code=account_code,
                dimension_name=account_name,
                amount=amount,
                source_scope=source_scope,
                generation_params=generation_params,
            )
            for account_code, account_name, amount in rows
        ]

    def _build_entity_snapshots(
        self,
        period: AccountingPeriod,
        snapshot_version: int,
        source_scope: dict[str, Any],
        generation_params: dict[str, Any],
    ) -> list[PeriodSnapshot]:
        rows = (
            self._period_entries_query(period)
            .with_entities(
                AccountingEntry.entity_id,
                AccountingEntry.original_entity_name,
                self._amount_expression().label("amount"),
            )
            .group_by(AccountingEntry.entity_id, AccountingEntry.original_entity_name)
            .all()
        )
        return [
            self._build_snapshot(
                period=period,
                snapshot_version=snapshot_version,
                dimension_type="entity",
                dimension_id=entity_id,
                dimension_name=original_entity_name,
                amount=amount,
                source_scope=source_scope,
                generation_params=generation_params,
            )
            for entity_id, original_entity_name, amount in rows
        ]

    def _build_period_total_snapshot(
        self,
        period: AccountingPeriod,
        snapshot_version: int,
        source_scope: dict[str, Any],
        generation_params: dict[str, Any],
    ) -> PeriodSnapshot:
        amount = self._period_entries_query(period).with_entities(self._amount_expression()).scalar()
        return self._build_snapshot(
            period=period,
            snapshot_version=snapshot_version,
            dimension_type="period_total",
            dimension_code="period_total",
            dimension_name="期间总计",
            amount=amount or 0,
            source_scope=source_scope,
            generation_params=generation_params,
        )
