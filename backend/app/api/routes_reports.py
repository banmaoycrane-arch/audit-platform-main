# -*- coding: utf-8 -*-
"""
模块功能：三大财务报表 API 路由（科目余额表、资产负债表、利润表）
业务场景：财务核算完成后向用户呈现三大基础报表
政策依据：企业会计准则关于报表列报的基本原则
输入数据：组织 ID、期间 ID
输出结果：三大报表的 JSON 数据
创建日期：2026-06-25
更新记录：
    2026-06-25  增加统一异常捕获，返回业务语义化的错误信息
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod
from app.db.session import get_db
from app.services import financial_statements_service

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _check_period(db: Session, period_id: int) -> None:
    """校验会计期间是否存在，不存在则抛出 404 异常。"""
    if not db.get(AccountingPeriod, period_id):
        raise HTTPException(status_code=404, detail="会计期间不存在")


def _run_report(report_func, db: Session, ledger_id: int, period_id: int) -> dict:
    """
    功能描述：统一调用报表服务并捕获业务异常
    业务逻辑：将 LookupError 映射为 404，ValueError 映射为 400，SQLAlchemyError 映射为 422

    Args:
        report_func: 报表计算函数
        db: 数据库会话
        ledger_id: 账簿 ID
        period_id: 期间 ID

    Returns:
        dict: 报表数据
    """
    try:
        return report_func(db, ledger_id, period_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=422, detail=f"报表数据加载失败，请检查科目表或分录表结构：{exc}")


@router.get("/trial-balance")
def trial_balance(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """科目余额表：返回各科目期初/本期/期末借贷六列及借贷合计。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    return _run_report(
        financial_statements_service.trial_balance_report,
        db,
        effective_ledger_id,
        period_id,
    )


@router.get("/balance-sheet")
def balance_sheet(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """资产负债表：返回资产/负债/权益分组、恒等式校验与重分类调整记录。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    return _run_report(
        financial_statements_service.balance_sheet,
        db,
        effective_ledger_id,
        period_id,
    )


@router.get("/income-statement")
def income_statement(
    period_id: int,
    ledger_id: int | None = None,
    organization_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict:
    """利润表：返回收入、成本、期间费用、营业利润、利润总额、净利润。"""
    _check_period(db, period_id)
    effective_ledger_id = _resolve_ledger_id(db, ledger_id, organization_id, period_id)
    return _run_report(
        financial_statements_service.income_statement,
        db,
        effective_ledger_id,
        period_id,
    )


def _resolve_ledger_id(db: Session, ledger_id: int | None, organization_id: int | None, period_id: int) -> int:
    """解析有效账簿ID：优先使用ledger_id，否则从organization_id或period_id推导。"""
    if ledger_id is not None:
        return ledger_id
    if organization_id is not None:
        period = db.get(AccountingPeriod, period_id)
        if period and period.organization_id == organization_id:
            return period.ledger_id
        raise HTTPException(status_code=400, detail="organization_id与period_id不匹配")
    period = db.get(AccountingPeriod, period_id)
    if period:
        return period.ledger_id
    raise HTTPException(status_code=404, detail="无法确定账簿ID")
