# -*- coding: utf-8 -*-
"""Parser Evolution Loop API — 自动提案 + 批量审批。"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.parser_evolution import (
    BatchProposalActionResponse,
    BatchProposalIdsRequest,
    EvolutionProposalItem,
    EvolutionProposalListResponse,
    EvolutionRunResponse,
    NightlyRegressionResponse,
)
from app.services.doc_parsing.parser_engine.parser_evolution_service import (
    batch_approve_proposals,
    batch_reject_proposals,
    get_latest_nightly_summary,
    get_latest_run_summary,
    list_proposals,
    proposal_to_dict,
    run_evolution_cycle,
    run_nightly_top3_regression,
)

router = APIRouter(prefix="/api/parser-engine/evolution", tags=["parser-evolution"])


@router.post("/run", response_model=EvolutionRunResponse)
def trigger_evolution_run(db: Session = Depends(get_db)) -> EvolutionRunResponse:
    """
    触发一轮进化环：扫描 TOP3 样本，自动生成 draft 规则提案。

    建议：云端定时任务每日调用；开发者无需手跑脚本。
    """
    summary = run_evolution_cycle(db)
    return EvolutionRunResponse(**summary)


@router.get("/runs/latest")
def get_latest_run() -> dict[str, Any]:
    """获取最近一次进化运行摘要。"""
    summary = get_latest_run_summary()
    return summary or {"message": "尚无进化运行记录"}


@router.get("/proposals", response_model=EvolutionProposalListResponse)
def get_proposals(
    status: str = "draft",
    document_type: str | None = None,
    rule_type: str | None = None,
    source: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> EvolutionProposalListResponse:
    """
    列出待审批 / 已生效 / 已驳回的规则提案。

    source: production（生产改错）| top3（样本扫描）
    """
    items = list_proposals(
        db,
        status=status,
        document_type=document_type,
        rule_type=rule_type,
        source=source,
        limit=limit,
    )
    return EvolutionProposalListResponse(
        items=[EvolutionProposalItem(**proposal_to_dict(p)) for p in items],
        total=len(items),
    )


@router.post("/proposals/batch-approve", response_model=BatchProposalActionResponse)
def approve_proposals(
    request: BatchProposalIdsRequest,
    db: Session = Depends(get_db),
) -> BatchProposalActionResponse:
    """批量采纳提案 → 规则立即对后续解析生效。"""
    result = batch_approve_proposals(db, request.patch_ids, request.approved_by)
    return BatchProposalActionResponse(**result)


@router.post("/proposals/batch-reject", response_model=BatchProposalActionResponse)
def reject_proposals(
    request: BatchProposalIdsRequest,
    db: Session = Depends(get_db),
) -> BatchProposalActionResponse:
    """批量驳回提案。"""
    result = batch_reject_proposals(db, request.patch_ids, request.reason)
    return BatchProposalActionResponse(rejected_count=result["rejected_count"], requested=result["requested"])


@router.post("/nightly-regression", response_model=NightlyRegressionResponse)
def trigger_nightly_regression(db: Session = Depends(get_db)) -> NightlyRegressionResponse:
    """
    Nightly TOP3 回归标尺：重跑固定样本集，记录质量指标，不自动激活规则。
    """
    summary = run_nightly_top3_regression(db)
    return NightlyRegressionResponse(**summary)


@router.get("/nightly-regression/latest")
def get_latest_nightly() -> dict[str, Any]:
    """获取最近一次 nightly 回归摘要。"""
    summary = get_latest_nightly_summary()
    return summary or {"message": "尚无 nightly 回归记录"}
