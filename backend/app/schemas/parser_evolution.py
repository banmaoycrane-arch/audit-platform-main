from typing import Any

from pydantic import BaseModel, Field


class EvolutionRunResponse(BaseModel):
    run_id: str
    started_at: str
    top3_root: str
    new_proposals: int
    proposal_ids: list[int]
    categories: dict[str, Any] | None = None


class EvolutionProposalItem(BaseModel):
    id: int
    rule_name: str
    document_type: str
    rule_type: str
    target_field: str
    status: str
    priority: int
    source: str | None = None
    source_correction_id: int | None = None
    source_header: str | None = None
    evidence_file: str | None = None
    file_name: str | None = None
    category: str | None = None
    shadow_note: str | None = None
    run_id: str | None = None
    original_value: Any | None = None
    corrected_value: Any | None = None
    created_at: str | None = None


class NightlyRegressionResponse(BaseModel):
    run_id: str
    started_at: str
    type: str
    top3_root: str
    categories: dict[str, Any]
    note: str
    delta_vs_previous: dict[str, Any] | None = None


class EvolutionProposalListResponse(BaseModel):
    items: list[EvolutionProposalItem]
    total: int


class BatchProposalIdsRequest(BaseModel):
    patch_ids: list[int] = Field(..., min_length=1)
    approved_by: str = ""
    reason: str = ""


class BatchProposalActionResponse(BaseModel):
    approved_count: int | None = None
    rejected_count: int | None = None
    requested: int
