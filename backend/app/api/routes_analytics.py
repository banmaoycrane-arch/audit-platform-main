# -*- coding: utf-8 -*-
"""
多维度管理分析 API 路由。

提供客户往来分析、项目成本分析等管理视图的 RESTful 接口，
支持数据筛选、钻取、导出。
"""
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.shared.analytics_service import (
    analyze_counterparty,
    analyze_project_cost,
    drill_down_counterparty,
    drill_down_project_cost,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _date_param(value: str | None) -> date | None:
    """
    将 YYYY-MM-DD 字符串转换为 date 对象。
    """
    if not value:
        return None
    return date.fromisoformat(value)


@router.get("/counterparty", response_model=dict[str, Any])
def get_counterparty_analysis(
    ledger_id: int,
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    account_code_prefix: str | None = Query(None, description="科目前缀过滤"),
    counterparty_value: str | None = Query(None, description="指定往来单位"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    客户往来分析视图。
    """
    data = analyze_counterparty(
        db,
        ledger_id=ledger_id,
        start_date=_date_param(start_date),
        end_date=_date_param(end_date),
        account_code_prefix=account_code_prefix,
        counterparty_value=counterparty_value,
    )
    return {"ledger_id": ledger_id, "data": data}


@router.get("/counterparty/{counterparty_value}/details", response_model=dict[str, Any])
def get_counterparty_details(
    counterparty_value: str,
    ledger_id: int,
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    account_code_prefix: str | None = Query(None, description="科目前缀过滤"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    客户往来明细钻取。
    """
    data = drill_down_counterparty(
        db,
        ledger_id=ledger_id,
        counterparty_value=counterparty_value,
        start_date=_date_param(start_date),
        end_date=_date_param(end_date),
        account_code_prefix=account_code_prefix,
    )
    return {"ledger_id": ledger_id, "counterparty": counterparty_value, "data": data}


@router.get("/project-cost", response_model=dict[str, Any])
def get_project_cost_analysis(
    ledger_id: int,
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    project_value: str | None = Query(None, description="指定项目"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    项目成本分析视图。
    """
    data = analyze_project_cost(
        db,
        ledger_id=ledger_id,
        start_date=_date_param(start_date),
        end_date=_date_param(end_date),
        project_value=project_value,
    )
    return {"ledger_id": ledger_id, "data": data}


@router.get("/project-cost/{project_value}/details", response_model=dict[str, Any])
def get_project_cost_details(
    project_value: str,
    ledger_id: int,
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    business_type: str | None = Query(None, description="业务类型过滤"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    项目成本明细钻取。
    """
    data = drill_down_project_cost(
        db,
        ledger_id=ledger_id,
        project_value=project_value,
        start_date=_date_param(start_date),
        end_date=_date_param(end_date),
        business_type=business_type,
    )
    return {"ledger_id": ledger_id, "project": project_value, "data": data}
