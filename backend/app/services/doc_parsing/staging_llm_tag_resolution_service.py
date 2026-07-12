"""Staging 草稿分录的 LLM 维度识别（确认入账前）。"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config.account_tag_config import load_account_tag_config
from app.db.models import ExecutionAuditLog, StagingAccountingEntry
from app.services.agent.llm_client_service import LlmClientService, LLMResult
from app.services.doc_parsing.llm_tag_resolution_service import LlmTagSuggestion

logger = logging.getLogger(__name__)


@dataclass
class StagingLlmResolutionResult:
    task_id: str
    total_rows: int
    success_count: int
    failed_count: int
    resolved_rows: int
    suggested_tags: list[LlmTagSuggestion] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


class StagingLlmTagResolutionService:
    """对 staging 分录批量调用 LLM，将结果写入 entry_tags_payload。"""

    def __init__(self, db: Session, *, ledger_id: int | None = None):
        self.db = db
        self.ledger_id = ledger_id
        self.client = LlmClientService()
        self.account_tag_config = load_account_tag_config(db, ledger_id=ledger_id)

    def list_pending_rows(
        self,
        job_id: int,
        *,
        staging_ids: list[int] | None = None,
        limit: int = 200,
    ) -> list[StagingAccountingEntry]:
        query = self.db.query(StagingAccountingEntry).filter(
            StagingAccountingEntry.import_job_id == job_id,
        )
        if staging_ids:
            query = query.filter(StagingAccountingEntry.id.in_(staging_ids))
        rows = query.order_by(
            StagingAccountingEntry.voucher_no,
            StagingAccountingEntry.entry_line_no,
        ).all()
        pending = [
            row
            for row in rows
            if (row.original_row or {}).get("_requires_llm_resolution")
        ]
        return pending[:limit]

    def batch_resolve(
        self,
        job_id: int,
        *,
        staging_ids: list[int] | None = None,
        batch_size: int = 20,
        dry_run: bool = False,
    ) -> StagingLlmResolutionResult:
        start_time = time.time()
        rows = self.list_pending_rows(job_id, staging_ids=staging_ids, limit=batch_size * 10)
        if not rows:
            return StagingLlmResolutionResult(
                task_id="",
                total_rows=0,
                success_count=0,
                failed_count=0,
                resolved_rows=0,
            )

        if not self.client.is_configured():
            return StagingLlmResolutionResult(
                task_id=f"staging_llm_{int(time.time())}",
                total_rows=len(rows),
                success_count=0,
                failed_count=len(rows),
                resolved_rows=0,
                error_messages=["LLM 未配置，请先在解析引擎配置中设置 AI 模型"],
            )

        all_suggestions: list[LlmTagSuggestion] = []
        error_messages: list[str] = []
        success_count = 0
        failed_count = 0
        resolved_rows = 0

        for index in range(0, len(rows), batch_size):
            batch = rows[index : index + batch_size]
            prompt = self._build_prompt(batch)
            response = self._call_llm(prompt)
            if not response:
                failed_count += len(batch)
                error_messages.append(f"批次 {index // batch_size + 1} LLM 调用失败")
                continue

            suggestions = self._parse_llm_response(response)
            validated = self._validate_suggestions(suggestions)
            all_suggestions.extend(validated)
            success_count += len([item for item in validated if item.validation_passed])

            if not dry_run:
                resolved_rows += self._apply_suggestions(batch, validated)

        processing_time_ms = (time.time() - start_time) * 1000
        task_id = f"staging_llm_{uuid.uuid4().hex[:12]}"
        result = StagingLlmResolutionResult(
            task_id=task_id,
            total_rows=len(rows),
            success_count=success_count,
            failed_count=failed_count,
            resolved_rows=resolved_rows,
            suggested_tags=all_suggestions,
            error_messages=error_messages,
            processing_time_ms=processing_time_ms,
        )
        self._log_processing(job_id, result)
        if not dry_run and resolved_rows:
            self.db.commit()
        return result

    def _build_prompt(self, rows: list[StagingAccountingEntry]) -> str:
        category_list = ", ".join(self.account_tag_config.account_code_tag_category.values())
        auxiliary_list = ", ".join(self.account_tag_config.auxiliary_keywords.keys())
        entries_data = []
        for row in rows:
            entries_data.append(
                {
                    "staging_id": row.id,
                    "account_code": row.resolved_account_code or row.account_code or "",
                    "account_name": row.resolved_account_name or row.account_name or "",
                    "summary": row.summary or "",
                }
            )

        return f"""你是一个专业的财务数据分析师。请分析以下会计分录草稿的摘要信息，识别其中的辅助核算维度。

## 规则说明
1. 请从摘要中识别以下维度类别：{category_list}、{auxiliary_list}
2. 每个分录可能包含多个维度，也可能不包含任何维度
3. 如果无法从摘要中识别出任何维度，请返回空列表
4. 识别结果必须严格符合财务逻辑和业务常识
5. 置信度范围为0.0-1.0

## 科目与维度映射参考
{json.dumps(self.account_tag_config.account_code_tag_category, ensure_ascii=False, indent=2)}

## 需要分析的分录
{json.dumps(entries_data, ensure_ascii=False, indent=2)}

## 输出格式要求
请严格按照以下JSON格式输出，不要包含任何额外文字：
[
    {{
        "staging_id": 分录草稿ID,
        "category_code": "维度类别代码",
        "tag_value": "识别到的值",
        "display_name": "显示名称",
        "confidence": 置信度
    }}
]"""

    def _call_llm(self, prompt: str, max_retries: int = 3) -> str | None:
        messages = [
            {"role": "system", "content": "你是一个专业的财务数据分析师，精通会计核算和审计流程。"},
            {"role": "user", "content": prompt},
        ]
        delay = 2.0
        for attempt in range(max_retries):
            try:
                result: LLMResult = self.client.chat(messages, temperature=0.1)
                if result.available and result.content:
                    return result.content
                logger.warning("Staging LLM 调用失败 attempt=%s error=%s", attempt + 1, result.error)
            except Exception as exc:
                logger.warning("Staging LLM 调用异常 attempt=%s error=%s", attempt + 1, exc)
            if attempt < max_retries - 1:
                time.sleep(delay)
                delay = min(delay * 2, 30)
        return None

    def _parse_llm_response(self, response: str) -> list[LlmTagSuggestion]:
        suggestions: list[LlmTagSuggestion] = []
        try:
            data = json.loads(response)
            if not isinstance(data, list):
                return suggestions
            for item in data:
                staging_id = item.get("staging_id") or item.get("entry_id")
                if staging_id is None:
                    continue
                suggestions.append(
                    LlmTagSuggestion(
                        entry_id=int(staging_id),
                        category_code=str(item.get("category_code") or ""),
                        tag_value=str(item.get("tag_value") or ""),
                        display_name=str(item.get("display_name") or item.get("tag_value") or ""),
                        confidence=float(item.get("confidence") or 0.0),
                        source="llm",
                    )
                )
        except json.JSONDecodeError as exc:
            logger.error("Staging LLM JSON 解析失败: %s", exc)
        return suggestions

    def _validate_suggestions(self, suggestions: list[LlmTagSuggestion]) -> list[LlmTagSuggestion]:
        valid_categories = set(self.account_tag_config.account_code_tag_category.values())
        valid_categories.update(self.account_tag_config.auxiliary_keywords.keys())
        validated: list[LlmTagSuggestion] = []
        for suggestion in suggestions:
            validation_passed = True
            validation_reason = ""
            if not suggestion.category_code:
                validation_passed = False
                validation_reason = "维度类别代码为空"
            elif suggestion.category_code not in valid_categories:
                validation_passed = False
                validation_reason = f"未知的维度类别: {suggestion.category_code}"
            if not suggestion.tag_value.strip():
                validation_passed = False
                validation_reason = "标签值为空"
            if not (0.0 <= suggestion.confidence <= 1.0):
                validation_passed = False
                validation_reason = f"置信度超出范围: {suggestion.confidence}"
            validated.append(
                LlmTagSuggestion(
                    entry_id=suggestion.entry_id,
                    category_code=suggestion.category_code,
                    tag_value=suggestion.tag_value,
                    display_name=suggestion.display_name or suggestion.tag_value,
                    confidence=suggestion.confidence,
                    source=suggestion.source,
                    validation_passed=validation_passed,
                    validation_reason=validation_reason,
                )
            )
        return validated

    def _apply_suggestions(
        self,
        rows: list[StagingAccountingEntry],
        suggestions: list[LlmTagSuggestion],
    ) -> int:
        row_by_id = {row.id: row for row in rows}
        resolved_ids: set[int] = set()
        suggestions_by_row: dict[int, list[LlmTagSuggestion]] = {}
        for suggestion in suggestions:
            if not suggestion.validation_passed:
                continue
            suggestions_by_row.setdefault(suggestion.entry_id, []).append(suggestion)

        for staging_id, row_suggestions in suggestions_by_row.items():
            row = row_by_id.get(staging_id)
            if row is None:
                continue
            tags = [dict(tag) for tag in (row.entry_tags_payload or []) if isinstance(tag, dict)]
            existing_keys = {
                (str(tag.get("category_code") or ""), str(tag.get("tag_value") or ""))
                for tag in tags
            }
            for suggestion in row_suggestions:
                key = (suggestion.category_code, suggestion.tag_value)
                if key in existing_keys:
                    continue
                tags.append(
                    {
                        "category_code": suggestion.category_code,
                        "tag_value": suggestion.tag_value,
                        "display_name": suggestion.display_name,
                        "tag_source": "llm",
                        "confidence": suggestion.confidence,
                        "name_standardized": suggestion.display_name.strip() != suggestion.tag_value.strip(),
                        "reviewed_by_user": False,
                    }
                )
                existing_keys.add(key)
            row.entry_tags_payload = tags
            original_row = dict(row.original_row or {})
            original_row["_requires_llm_resolution"] = False
            original_row["_llm_resolved_at"] = datetime.now(timezone.utc).isoformat()
            row.original_row = original_row
            resolved_ids.add(staging_id)
        return len(resolved_ids)

    def _log_processing(self, job_id: int, result: StagingLlmResolutionResult) -> None:
        self.db.add(
            ExecutionAuditLog(
                trace_id=result.task_id,
                request_id=result.task_id,
                service_name="staging_llm_tag_resolution",
                tool_name="batch_resolve",
                execution_source="api",
                business_object_type="import_job",
                business_object_id=str(job_id),
                status="success" if result.failed_count == 0 else "partial",
                risk_level="low",
                input_summary={
                    "total_rows": result.total_rows,
                    "success_count": result.success_count,
                    "failed_count": result.failed_count,
                    "resolved_rows": result.resolved_rows,
                    "processing_time_ms": result.processing_time_ms,
                },
                created_at=datetime.now(timezone.utc),
            )
        )
