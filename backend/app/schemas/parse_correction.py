from typing import Any

from pydantic import BaseModel


class CreateParseCorrectionRequest(BaseModel):
    task_id: str
    document_type: str
    file_name: str
    original_result: dict[str, Any]
    corrected_result: dict[str, Any]
    correction_reason: str = ""
    corrected_by: str = ""
    original_text: str = ""


class ParseCorrectionResponse(BaseModel):
    id: int
    task_id: str
    document_type: str
    file_name: str
    diff_fields: list[str]
    correction_reason: str | None
    corrected_by: str | None
    status: str
    rule_extracted: bool
    regression_passed: int
    created_at: str | None


class ParseCorrectionListResponse(BaseModel):
    items: list[ParseCorrectionResponse]
    total: int


class ExtractRulesResponse(BaseModel):
    correction_id: int
    extracted_patch_count: int
    patch_names: list[str]
    status: str


class ApplyRulesResponse(BaseModel):
    correction_id: int
    applied_patch_count: int
    status: str
