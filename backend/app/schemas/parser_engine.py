from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FileParseRequest(BaseModel):
    organization_id: int
    file_path: str | None = None


class ParseResultResponse(BaseModel):
    file_format: str
    document_type: str
    document_sub_type: str | None = None
    confidence: float
    engine_type: str
    data: dict[str, Any]
    raw_text: str | None = None
    error_message: str | None = None
    parse_duration_ms: float | None = None
    stage_timings: dict[str, float] | None = None
    engine_comparison: dict[str, Any] | None = None
    multi_llm_comparison: dict[str, Any] | None = None


class LLMComparisonResponse(BaseModel):
    document_type: str
    final_result: dict[str, Any]
    final_confidence: float
    comparison_strategy: str
    field_consistency_rate: float
    engine_results: list[dict[str, Any]]
    total_duration_ms: float




class QualityTrendItem(BaseModel):
    date: str
    document_type: str
    parse_count: int
    review_required_count: int
    avg_consistency_rate: float
    avg_stability_score: float
    overall_field_accuracy: float
    overall_document_completeness: float
    correction_applied_total: int


class ParserQualityDashboardResponse(BaseModel):
    total_parse_count: int
    total_review_required_count: int
    overall_consistency_rate: float
    overall_stability_score: float
    overall_field_accuracy: float
    overall_document_completeness: float
    review_required_rate: float
    trend: list[QualityTrendItem]


class ParserEngineStatusResponse(BaseModel):
    status: str
    llm_multi_engine_enabled: bool
    llm_enable_parallel_parsing: bool
    llm_max_concurrent_models: int
    llm_preferred_model: str
    llm_comparison_strategy: str
    llm_knowledge_base: str | None = None
    supported_formats: list[str]
    supported_document_types: list[str]
