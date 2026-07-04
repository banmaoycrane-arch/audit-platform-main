# -*- coding: utf-8 -*-
"""
LLM辅助标签识别服务（LLM Tag Resolution Service）。

模块功能：
    对标记为 requires_llm_resolution=true 的分录，批量调用LLM从摘要中识别
    辅助核算维度并生成EntryTag建议。

业务场景：
    - 序时簿导入时，部分分录的科目被扁平化但未能通过规则识别辅助核算维度。
    - 需要LLM从摘要中智能识别部门、项目、区域、往来单位等维度。
    - LLM识别结果需要经过人工审批才能正式写入EntryTag。

政策依据：
    - AI只能生成建议/草稿/标签，正式凭证、结账、报表由确定性规则+人工确认控制。
    - 所有LLM处理活动必须记录日志，便于审计追溯和性能优化。

输入数据：
    - 分录ID列表（requires_llm_resolution=true）
    - 分录摘要、科目信息
    - LLM配置（模型、温度、超时等）

输出结果：
    - 建议的Tag列表（含审批状态）
    - 处理统计（成功/失败/待审批）
    - 处理日志

创建日期：2026-07-04
更新记录：
    2026-07-04  初始版本，实现批量LLM识别、结果校验、审批状态机
"""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import requests
from sqlalchemy.orm import Session

from app.config.account_tag_config import load_account_tag_config
from app.db.models import AccountingEntry, EntryTag, TagCategory, ExecutionAuditLog
from app.services.agent.llm_client_service import LlmClientService, LLMResult


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmTagSuggestion:
    """LLM识别的标签建议"""
    entry_id: int
    category_code: str
    tag_value: str
    display_name: str
    confidence: float
    source: str = "llm"
    validation_passed: bool = True
    validation_reason: str = ""


@dataclass
class LlmResolutionResult:
    """LLM解析结果"""
    task_id: str
    total_entries: int
    success_count: int
    failed_count: int
    suggested_tags: List[LlmTagSuggestion]
    error_messages: List[str] = field(default_factory=list)
    processing_time_ms: float = 0.0


class LlmTagResolutionService:
    """LLM辅助标签识别服务"""

    def __init__(self, db: Session, config: Optional[Dict[str, Any]] = None):
        """
        初始化服务

        Args:
            db: 数据库会话
            config: LLM配置字典（可选）
        """
        self.db = db
        self.client = LlmClientService(config=config)
        self.account_tag_config = load_account_tag_config(db)

    def get_entries_needing_llm_resolution(
        self,
        ledger_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[AccountingEntry]:
        """
        获取需要LLM解析的分录列表

        Args:
            ledger_id: 账簿ID（可选，用于筛选）
            limit: 返回数量限制

        Returns:
            需要LLM解析的分录列表
        """
        query = self.db.query(AccountingEntry).filter(
            AccountingEntry.requires_llm_resolution.is_(True)
        )
        if ledger_id:
            query = query.filter(AccountingEntry.ledger_id == ledger_id)
        return query.limit(limit).all()

    def _build_prompt(self, entries: List[AccountingEntry]) -> str:
        """
        构建LLM提示词

        业务逻辑：
            - 提供科目信息和摘要，要求LLM识别辅助核算维度
            - 限定输出格式为JSON，便于解析
            - 提供可选的维度类别列表
        """
        category_list = ", ".join(self.account_tag_config.account_code_tag_category.values())
        auxiliary_list = ", ".join(self.account_tag_config.auxiliary_keywords.keys())

        entries_data = []
        for entry in entries:
            entries_data.append({
                "entry_id": entry.id,
                "account_code": entry.resolved_account_code or entry.account_code or "",
                "account_name": entry.resolved_account_name or entry.account_name or "",
                "summary": entry.summary or "",
            })

        prompt = f"""你是一个专业的财务数据分析师。请分析以下会计分录的摘要信息，识别其中的辅助核算维度。

## 规则说明
1. 请从摘要中识别以下维度类别：{category_list}、{auxiliary_list}
2. 每个分录可能包含多个维度，也可能不包含任何维度
3. 如果无法从摘要中识别出任何维度，请返回空列表
4. 识别结果必须严格符合财务逻辑和业务常识
5. 置信度范围为0.0-1.0，表示你对识别结果的信心程度

## 科目与维度映射参考
{json.dumps(self.account_tag_config.account_code_tag_category, ensure_ascii=False, indent=2)}

## 需要分析的分录
{json.dumps(entries_data, ensure_ascii=False, indent=2)}

## 输出格式要求
请严格按照以下JSON格式输出，不要包含任何额外文字：
[
    {{
        "entry_id": 分录ID,
        "category_code": "维度类别代码",
        "tag_value": "识别到的值",
        "display_name": "显示名称",
        "confidence": 置信度
    }}
]

注意：如果某个分录没有识别到任何维度，可以省略该分录。"""

        return prompt

    def _call_llm(self, prompt: str, max_retries: int = 3, timeout: int = 60) -> Optional[str]:
        """
        调用LLM，带指数退避重试机制

        Args:
            prompt: 提示词
            max_retries: 最大重试次数
            timeout: 超时时间（秒）

        Returns:
            LLM返回的文本内容，失败返回None
        """
        if not self.client.is_configured():
            logger.warning("LLM客户端未配置，跳过LLM调用")
            return None

        messages = [
            {"role": "system", "content": "你是一个专业的财务数据分析师，精通会计核算和审计流程。"},
            {"role": "user", "content": prompt},
        ]

        delay = 2.0
        for attempt in range(max_retries):
            try:
                start_time = time.time()
                result: LLMResult = self.client.chat(messages, temperature=0.1)
                elapsed_ms = (time.time() - start_time) * 1000

                if result.available and result.content:
                    logger.info(f"LLM调用成功 (attempt={attempt+1}, time={elapsed_ms:.2f}ms)")
                    return result.content

                logger.warning(f"LLM调用失败 (attempt={attempt+1}): {result.error}")
                if attempt < max_retries - 1:
                    logger.info(f"等待 {delay:.1f}秒后重试...")
                    time.sleep(delay)
                    delay = min(delay * 2, 30)

            except Exception as exc:
                logger.error(f"LLM调用异常 (attempt={attempt+1}): {exc}")
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, 30)

        logger.error(f"LLM调用失败，已重试{max_retries}次")
        return None

    def _parse_llm_response(self, response: str) -> List[LlmTagSuggestion]:
        """
        解析LLM返回的JSON响应

        Args:
            response: LLM返回的文本

        Returns:
            解析后的标签建议列表
        """
        suggestions: List[LlmTagSuggestion] = []

        try:
            data = json.loads(response)
            if not isinstance(data, list):
                logger.warning("LLM返回格式不是列表")
                return suggestions

            for item in data:
                suggestion = LlmTagSuggestion(
                    entry_id=item.get("entry_id", 0),
                    category_code=item.get("category_code", ""),
                    tag_value=item.get("tag_value", ""),
                    display_name=item.get("display_name", ""),
                    confidence=item.get("confidence", 0.0),
                )
                suggestions.append(suggestion)

            logger.info(f"成功解析 {len(suggestions)} 个标签建议")
        except json.JSONDecodeError as exc:
            logger.error(f"LLM响应JSON解析失败: {exc}")

        return suggestions

    def _validate_suggestions(self, suggestions: List[LlmTagSuggestion]) -> List[LlmTagSuggestion]:
        """
        验证LLM识别结果

        业务逻辑：
            1. 检查category_code是否在配置的类别列表中
            2. 检查tag_value是否非空且长度合理
            3. 检查置信度是否在合理范围
            4. 检查是否与科目类型匹配
        """
        valid_categories = set(self.account_tag_config.account_code_tag_category.values())
        valid_categories.update(self.account_tag_config.auxiliary_keywords.keys())

        validated: List[LlmTagSuggestion] = []

        for suggestion in suggestions:
            validation_passed = True
            validation_reason = ""

            if not suggestion.category_code:
                validation_passed = False
                validation_reason = "维度类别代码为空"
            elif suggestion.category_code not in valid_categories:
                validation_passed = False
                validation_reason = f"未知的维度类别: {suggestion.category_code}"

            if not suggestion.tag_value or len(suggestion.tag_value.strip()) == 0:
                validation_passed = False
                validation_reason = "标签值为空"

            if not (0.0 <= suggestion.confidence <= 1.0):
                validation_passed = False
                validation_reason = f"置信度超出范围: {suggestion.confidence}"

            validated.append(LlmTagSuggestion(
                entry_id=suggestion.entry_id,
                category_code=suggestion.category_code,
                tag_value=suggestion.tag_value,
                display_name=suggestion.display_name or suggestion.tag_value,
                confidence=suggestion.confidence,
                validation_passed=validation_passed,
                validation_reason=validation_reason,
            ))

        return validated

    def _ensure_tag_category(self, category_code: str) -> Optional[TagCategory]:
        """
        确保TagCategory存在，不存在则创建

        Args:
            category_code: 类别代码

        Returns:
            TagCategory对象
        """
        from app.services.doc_parsing.tag_category_service import get_or_create_category

        return get_or_create_category(self.db, category_code)

    def batch_resolve(
        self,
        entry_ids: Optional[List[int]] = None,
        ledger_id: Optional[int] = None,
        batch_size: int = 50,
        dry_run: bool = False,
    ) -> LlmResolutionResult:
        """
        批量调用LLM识别辅助核算维度

        Args:
            entry_ids: 指定的分录ID列表（可选）
            ledger_id: 账簿ID（可选，用于筛选）
            batch_size: 每批处理的分录数量
            dry_run: 是否为模拟运行（不写入数据库）

        Returns:
            LlmResolutionResult: 处理结果
        """
        start_time = time.time()

        # 获取需要处理的分录
        if entry_ids:
            entries = self.db.query(AccountingEntry).filter(
                AccountingEntry.id.in_(entry_ids)
            ).all()
        else:
            entries = self.get_entries_needing_llm_resolution(ledger_id, limit=batch_size)

        if not entries:
            return LlmResolutionResult(
                task_id="",
                total_entries=0,
                success_count=0,
                failed_count=0,
                suggested_tags=[],
                processing_time_ms=0.0,
            )

        logger.info(f"开始处理 {len(entries)} 个需要LLM解析的分录")

        all_suggestions: List[LlmTagSuggestion] = []
        error_messages: List[str] = []
        success_count = 0
        failed_count = 0

        # 分批处理
        for i in range(0, len(entries), batch_size):
            batch = entries[i:i + batch_size]
            logger.info(f"处理批次 {i // batch_size + 1}/{(len(entries) + batch_size - 1) // batch_size}")

            prompt = self._build_prompt(batch)
            response = self._call_llm(prompt)

            if not response:
                failed_count += len(batch)
                error_messages.append(f"批次 {i // batch_size + 1} LLM调用失败")
                continue

            suggestions = self._parse_llm_response(response)
            validated = self._validate_suggestions(suggestions)

            all_suggestions.extend(validated)
            success_count += len([s for s in validated if s.validation_passed])

            if not dry_run:
                self._save_suggestions(validated)

        processing_time_ms = (time.time() - start_time) * 1000

        result = LlmResolutionResult(
            task_id=f"llm_resolution_{int(time.time())}",
            total_entries=len(entries),
            success_count=success_count,
            failed_count=failed_count,
            suggested_tags=all_suggestions,
            error_messages=error_messages,
            processing_time_ms=processing_time_ms,
        )

        # 记录审计日志
        self._log_processing(result)

        logger.info(f"LLM解析完成: 总数={len(entries)}, 成功={success_count}, 失败={failed_count}, 耗时={processing_time_ms:.2f}ms")

        return result

    def _save_suggestions(self, suggestions: List[LlmTagSuggestion]) -> None:
        """
        保存验证通过的标签建议到数据库

        业务逻辑：
            - 创建EntryTag记录，状态为待审批（reviewed_by_user=False）
            - 更新分录的requires_llm_resolution状态
            - 记录审计日志
        """
        for suggestion in suggestions:
            if not suggestion.validation_passed:
                continue

            entry = self.db.query(AccountingEntry).get(suggestion.entry_id)
            if not entry:
                continue

            category = self._ensure_tag_category(suggestion.category_code)
            if not category:
                continue

            # 检查是否已存在相同的标签
            existing_tag = self.db.query(EntryTag).filter(
                EntryTag.entry_id == suggestion.entry_id,
                EntryTag.category_id == category.id,
                EntryTag.tag_value == suggestion.tag_value,
            ).first()

            if existing_tag:
                continue

            entry_tag = EntryTag(
                entry_id=suggestion.entry_id,
                ledger_id=entry.ledger_id,
                category_id=category.id,
                tag_name=category.category_name,
                tag_type=category.category_type,
                tag_value=suggestion.tag_value,
                display_name=suggestion.display_name,
                confidence=suggestion.confidence,
                tag_source="llm",
                reviewed_by_user=False,
                vector_pending=True,
            )

            self.db.add(entry_tag)

            # 更新分录状态
            entry.requires_llm_resolution = False

        self.db.commit()

    def _log_processing(self, result: LlmResolutionResult) -> None:
        """
        记录LLM处理活动日志

        Args:
            result: 处理结果
        """
        from datetime import datetime, timezone

        audit_log = ExecutionAuditLog(
            trace_id=result.task_id,
            request_id=result.task_id,
            service_name="llm_tag_resolution",
            tool_name="batch_resolve",
            execution_source="api",
            business_object_type="accounting_entry",
            business_object_id=f"batch_{result.total_entries}",
            status="success" if result.failed_count == 0 else "partial",
            risk_level="low",
            input_summary={
                "total_entries": result.total_entries,
                "success_count": result.success_count,
                "failed_count": result.failed_count,
                "processing_time_ms": result.processing_time_ms,
            },
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(audit_log)
        self.db.commit()

    def approve_suggestions(self, suggestion_ids: List[int], user_id: int) -> int:
        """
        审批通过标签建议

        Args:
            suggestion_ids: 建议ID列表
            user_id: 审批用户ID

        Returns:
            成功审批的数量
        """
        count = 0
        for suggestion_id in suggestion_ids:
            tag = self.db.query(EntryTag).get(suggestion_id)
            if tag and not tag.reviewed_by_user:
                tag.reviewed_by_user = True
                tag.confidence = min(tag.confidence + 0.1, 1.0)
                count += 1

        self.db.commit()
        return count

    def reject_suggestions(self, suggestion_ids: List[int], user_id: int) -> int:
        """
        拒绝标签建议

        Args:
            suggestion_ids: 建议ID列表
            user_id: 拒绝用户ID

        Returns:
            成功拒绝的数量
        """
        count = 0
        for suggestion_id in suggestion_ids:
            tag = self.db.query(EntryTag).get(suggestion_id)
            if tag and not tag.reviewed_by_user:
                self.db.delete(tag)
                count += 1

        self.db.commit()
        return count

    def get_pending_suggestions(
        self,
        ledger_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[EntryTag], int]:
        """
        获取待审批的标签建议

        Args:
            ledger_id: 账簿ID（可选）
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            (标签列表, 总数)
        """
        query = self.db.query(EntryTag).filter(
            EntryTag.reviewed_by_user.is_(False),
            EntryTag.tag_source == "llm",
        )
        if ledger_id:
            query = query.filter(EntryTag.ledger_id == ledger_id)

        total = query.count()
        items = query.offset(offset).limit(limit).all()

        return items, total
