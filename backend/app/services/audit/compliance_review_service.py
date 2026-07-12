"""Staging 草稿分录合规审查：单张凭证 + 向量相似 Tag + LLM 语义识别。"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any, Iterator, Literal

from sqlalchemy.orm import Session

from app.db.models import ImportJob, StagingAccountingEntry
from app.services.audit.staging_review_service import (
    amounts_are_balanced,
    group_staging_rows,
    voucher_group_key,
)

ComplianceMode = Literal["each", "spot", "random", "skip"]
Severity = Literal["info", "warning", "error"]

_SIMILARITY_THRESHOLD = 0.72
_MAX_SIMILAR_REFS = 8
_MAX_VECTOR_QUERY_LINES = 5
_MAX_LLM_VOUCHER_LINES = 24
_COMPLIANCE_LLM_TIMEOUT_SECONDS = 600


def _amount_of(row: StagingAccountingEntry) -> Decimal:
    return max(row.debit_amount or Decimal("0"), row.credit_amount or Decimal("0"))


def _rule_check_voucher(rows: list[StagingAccountingEntry]) -> tuple[str | None, Severity]:
    hints: list[str] = []
    severity: Severity = "info"
    total_debit = sum((row.debit_amount or Decimal("0")) for row in rows)
    total_credit = sum((row.credit_amount or Decimal("0")) for row in rows)
    if not amounts_are_balanced(total_debit, total_credit):
        hints.append("借贷不平衡")
        severity = "error"

    for row in rows:
        amount = _amount_of(row)
        if amount >= Decimal("100000"):
            hints.append(f"存在大额分录（≥10万）：{row.account_name or row.account_code or '未知科目'}")
            severity = "warning" if severity != "error" else severity
        if not (row.summary or "").strip():
            hints.append("存在空摘要分录")
            severity = "warning" if severity != "error" else severity
        if not (row.account_code or row.account_name):
            hints.append("存在未识别科目")
            severity = "warning" if severity != "error" else severity

    if not hints:
        return "未发现明显规则风险", "info"
    return "；".join(dict.fromkeys(hints)), severity


def _staging_line_text(row: StagingAccountingEntry) -> str:
    parts = [
        row.normalized_text or "",
        row.summary or "",
        row.account_code or "",
        row.account_name or "",
        row.resolved_account_name or "",
        row.counterparty or "",
    ]
    for tag in row.entry_tags_payload or []:
        if isinstance(tag, dict):
            parts.append(f"{tag.get('category_code', '')}:{tag.get('tag_value', '')}")
            if tag.get("display_name"):
                parts.append(str(tag["display_name"]))
    if row.debit_amount and row.debit_amount > 0:
        parts.append(f"借方{row.debit_amount}")
    if row.credit_amount and row.credit_amount > 0:
        parts.append(f"贷方{row.credit_amount}")
    return " ".join(part for part in parts if part).strip()


def _voucher_payload(rows: list[StagingAccountingEntry]) -> dict[str, Any]:
    first = rows[0]
    lines: list[dict[str, Any]] = []
    for row in rows:
        tags = []
        for tag in row.entry_tags_payload or []:
            if isinstance(tag, dict):
                tags.append(
                    {
                        "category_code": tag.get("category_code"),
                        "tag_value": tag.get("tag_value"),
                        "display_name": tag.get("display_name"),
                    }
                )
        lines.append(
            {
                "line_no": row.entry_line_no,
                "summary": row.summary,
                "account_code": row.account_code or row.resolved_account_code,
                "account_name": row.account_name or row.resolved_account_name,
                "debit_amount": float(row.debit_amount or 0),
                "credit_amount": float(row.credit_amount or 0),
                "counterparty": row.counterparty,
                "tags": tags,
            }
        )
    total_debit_dec = sum((row.debit_amount or Decimal("0")) for row in rows)
    total_credit_dec = sum((row.credit_amount or Decimal("0")) for row in rows)
    total_debit = float(total_debit_dec)
    total_credit = float(total_credit_dec)
    payload: dict[str, Any] = {
        "voucher_no": first.voucher_no,
        "voucher_date": first.voucher_date.isoformat() if first.voucher_date else None,
        "line_count": len(lines),
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": amounts_are_balanced(total_debit_dec, total_credit_dec),
        "lines": lines,
    }
    return payload


def _voucher_payload_for_llm(rows: list[StagingAccountingEntry]) -> dict[str, Any]:
    payload = _voucher_payload(rows)
    line_count = int(payload.get("line_count") or 0)
    lines = payload.get("lines") or []
    if line_count > _MAX_LLM_VOUCHER_LINES:
        payload = {
            **payload,
            "lines": lines[:_MAX_LLM_VOUCHER_LINES],
            "lines_truncated": True,
            "lines_omitted": line_count - _MAX_LLM_VOUCHER_LINES,
            "note": f"凭证共 {line_count} 行，以下仅展示前 {_MAX_LLM_VOUCHER_LINES} 行供 LLM 审查，借贷合计仍按全凭证计算。",
        }
    return payload


def _find_similar_tag_references(
    db: Session,
    rows: list[StagingAccountingEntry],
    *,
    limit: int = _MAX_SIMILAR_REFS,
) -> list[dict[str, Any]]:
    from app.services.accounting.entry_tag_vector_service import EntryTagVectorService

    if not rows:
        return []

    ledger_id = rows[0].ledger_id
    if ledger_id is None:
        job = db.get(ImportJob, rows[0].import_job_id)
        ledger_id = job.ledger_id if job else None
    if ledger_id is None:
        return []

    service = EntryTagVectorService(db)
    query_rows = sorted(rows, key=_amount_of, reverse=True)[:_MAX_VECTOR_QUERY_LINES]
    combined_query = " ".join(
        part
        for row in query_rows
        for part in [_staging_line_text(row)]
        if part
    ).strip()
    if not combined_query:
        return []

    search_result = service.search(combined_query, limit=_MAX_SIMILAR_REFS, ledger_id=ledger_id)
    if not search_result.get("vector_available"):
        return []

    references: list[dict[str, Any]] = []
    for item in search_result.get("results") or []:
        score = float(item.get("score") or 0)
        if score < _SIMILARITY_THRESHOLD:
            continue
        references.append(
            {
                "score": round(score, 4),
                "category_code": item.get("category_code"),
                "tag_value": item.get("tag_value"),
                "display_name": item.get("display_name"),
                "voucher_no": item.get("voucher_no"),
                "voucher_date": item.get("voucher_date"),
                "account_code": item.get("account_code"),
                "summary": item.get("summary"),
                "source_line_summary": None,
            }
        )
        if len(references) >= limit:
            break
    return references


def _parse_llm_json(content: str) -> dict[str, Any] | None:
    text = (content or "").strip()
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _build_compliance_prompt(
    voucher: dict[str, Any],
    *,
    rule_hint: str | None,
    rule_severity: Severity,
    similar_refs: list[dict[str, Any]],
) -> str:
    return f"""你是资深财务合规审查员。请仅针对下面这一张凭证做语义合规审查，不要推断其他凭证。

## 当前凭证
{json.dumps(voucher, ensure_ascii=False, indent=2)}

## 规则引擎预检结论
severity={rule_severity}
hint={rule_hint or "无"}

## 向量库相似 Tag / 历史分录参考（仅供对照，不代表一定违规）
{json.dumps(similar_refs, ensure_ascii=False, indent=2)}

请结合：
1. 借贷平衡与科目/摘要/金额/往来是否合理；
2. 与相似 Tag 参考案例相比是否存在异常模式；
3. 常见财务合规风险（大额、空摘要、科目与业务不符等）。

严格输出 JSON（不要其他文字）：
{{
  "compliant": true,
  "severity": "info",
  "summary": "一句话结论",
  "findings": ["具体发现1", "具体发现2"],
  "similar_case_notes": "与向量参考案例的比较说明"
}}"""


def _finalize_llm_compliance(
    content: str | None,
    *,
    rule_hint: str | None,
    rule_severity: Severity,
    similar_refs: list[dict[str, Any]],
    llm_thinking: str | None = None,
    llm_error: str | None = None,
) -> tuple[str | None, Severity, str | None, dict[str, Any]]:
    meta: dict[str, Any] = {
        "engine": "rules_fallback",
        "llm_used": False,
        "vector_refs": similar_refs,
        "llm_thinking": (llm_thinking or "").strip() or None,
    }
    if llm_error:
        meta["llm_error"] = llm_error
        if similar_refs:
            meta["engine"] = "rules+vector"
        return rule_hint, rule_severity, llm_thinking, meta

    if not content:
        meta["llm_error"] = "LLM 调用失败"
        if similar_refs:
            meta["engine"] = "rules+vector"
        return rule_hint, rule_severity, llm_thinking, meta

    parsed = _parse_llm_json(content)
    if not parsed:
        meta["llm_error"] = "LLM 返回非 JSON 格式"
        meta["engine"] = "rules+vector" if similar_refs else "rules_fallback"
        return rule_hint, rule_severity, (llm_thinking or content[:500]), meta

    severity_raw = str(parsed.get("severity") or rule_severity).lower()
    severity: Severity = rule_severity
    if severity_raw in {"info", "warning", "error"}:
        severity = severity_raw  # type: ignore[assignment]
    if parsed.get("compliant") is False and severity == "info":
        severity = "warning"

    findings = [str(item) for item in (parsed.get("findings") or []) if str(item).strip()]
    summary = str(parsed.get("summary") or "").strip()
    similar_notes = str(parsed.get("similar_case_notes") or "").strip()
    hint_parts = [part for part in [summary, "；".join(findings), similar_notes] if part]
    hint = "；".join(dict.fromkeys(hint_parts)) or rule_hint or "LLM 未给出明确结论"

    meta.update(
        {
            "engine": "llm+vector" if similar_refs else "llm",
            "llm_used": True,
            "compliant": bool(parsed.get("compliant", True)),
            "findings": findings,
            "similar_case_notes": similar_notes or None,
        }
    )
    return hint, severity, summary or llm_thinking, meta


def _iter_llm_semantic_compliance(
    db: Session,
    voucher: dict[str, Any],
    *,
    rule_hint: str | None,
    rule_severity: Severity,
    similar_refs: list[dict[str, Any]],
) -> Iterator[dict[str, Any]]:
    from app.services.agent.llm_client_service import LlmClientService
    from app.services.doc_parsing.parser_engine.config_service import (
        config_for_reasoning_llm,
        get_runtime_parser_engine_config,
        model_supports_thinking_stream,
        resolve_parse_model,
        resolve_reasoning_model,
    )

    runtime_config = get_runtime_parser_engine_config(db)
    parse_model = resolve_parse_model(runtime_config)
    model_name = resolve_reasoning_model(runtime_config)
    client = LlmClientService(config=config_for_reasoning_llm(runtime_config))

    if not client.is_configured():
        yield {
            "type": "error",
            "message": "LLM 未配置：请在「解析引擎配置」填写 API 地址与对话模型",
        }
        return

    yield {
        "type": "models",
        "parse_model": parse_model,
        "reasoning_model": model_name,
        "active_model": model_name,
        "reasoning_configured": bool(str(runtime_config.get("ai_reasoning_model") or "").strip()),
    }

    if not str(runtime_config.get("ai_reasoning_model") or "").strip():
        yield {
            "type": "status",
            "message": (
                f"未单独配置推理模型，合规审查回退使用解析模型「{parse_model}」。"
                "请在「解析引擎配置」填写「推理模型」并保存。"
            ),
        }

    if "embed" in model_name.lower():
        yield {
            "type": "error",
            "message": f"当前模型「{model_name}」是 Embedding 模型，请改为对话模型",
        }
        return
    if "vl" in model_name.lower():
        yield {
            "type": "status",
            "message": (
                f"当前推理模型「{model_name}」为视觉多模态模型；"
                "请在「解析引擎配置」的「推理模型」中填写 deepseek-r1:8b 等纯文本推理模型。"
            ),
        }
    if not model_supports_thinking_stream(model_name):
        yield {
            "type": "status",
            "message": (
                f"模型「{model_name}」通常不输出思索过程，仅显示正式回复；"
                "若需思索链可换 deepseek-r1、qwen3 等推理模型。"
            ),
        }

    yield {"type": "status", "message": f"正在调用推理模型 {model_name}（流式输出）…"}

    prompt = _build_compliance_prompt(
        voucher,
        rule_hint=rule_hint,
        rule_severity=rule_severity,
        similar_refs=similar_refs,
    )
    messages = [
        {"role": "system", "content": "你是财务合规审查助手，只审查用户给出的单张凭证。"},
        {"role": "user", "content": prompt},
    ]

    full_content = ""
    full_thinking = ""
    for chunk in client.iter_chat_stream(
        messages,
        temperature=0.1,
        timeout_seconds=_COMPLIANCE_LLM_TIMEOUT_SECONDS,
    ):
        channel = chunk.get("channel")
        if channel == "thinking":
            yield {"type": "thinking", "delta": chunk.get("delta", ""), "text": chunk.get("text", "")}
        elif channel == "content":
            yield {"type": "content", "delta": chunk.get("delta", ""), "text": chunk.get("text", "")}
        elif channel == "error":
            error = chunk.get("error") or "LLM 调用失败"
            if "timed out" in str(error).lower():
                error = (
                    f"{error}（已等待 {_COMPLIANCE_LLM_TIMEOUT_SECONDS} 秒；"
                    "可换更小对话模型或稍后重试）"
                )
            hint, severity, reasoning, meta = _finalize_llm_compliance(
                None,
                rule_hint=rule_hint,
                rule_severity=rule_severity,
                similar_refs=similar_refs,
                llm_thinking=full_thinking,
                llm_error=error,
            )
            yield {
                "type": "result",
                "hint": hint,
                "severity": severity,
                "reasoning": reasoning,
                "meta": meta,
            }
            return
        elif channel == "done":
            full_content = str(chunk.get("content") or "")
            full_thinking = str(chunk.get("thinking") or "")

    hint, severity, reasoning, meta = _finalize_llm_compliance(
        full_content,
        rule_hint=rule_hint,
        rule_severity=rule_severity,
        similar_refs=similar_refs,
        llm_thinking=full_thinking,
    )
    yield {
        "type": "result",
        "hint": hint,
        "severity": severity,
        "reasoning": reasoning,
        "meta": meta,
    }


def _llm_semantic_compliance(
    db: Session,
    voucher: dict[str, Any],
    *,
    rule_hint: str | None,
    rule_severity: Severity,
    similar_refs: list[dict[str, Any]],
) -> tuple[str | None, Severity, str | None, dict[str, Any]]:
    from app.services.agent.llm_client_service import LlmClientService
    from app.services.doc_parsing.parser_engine.config_service import (
        config_for_reasoning_llm,
        get_runtime_parser_engine_config,
        resolve_parse_model,
        resolve_reasoning_model,
    )

    runtime_config = get_runtime_parser_engine_config(db)
    client = LlmClientService(config=config_for_reasoning_llm(runtime_config))
    meta: dict[str, Any] = {"engine": "rules_fallback", "llm_used": False, "vector_refs": similar_refs}

    if not client.is_configured():
        meta["llm_error"] = "LLM 未配置：请在「解析引擎配置」填写 API 地址与对话模型，或配置 backend/.env 的 AI_BASE_URL、AI_MODEL"
        if similar_refs:
            meta["engine"] = "rules+vector"
            hint = rule_hint or "规则审查完成；向量库找到相似 Tag 参考，但 LLM 未配置，未完成语义合规识别"
            return hint, rule_severity, None, meta
        return rule_hint, rule_severity, None, meta

    model_name = resolve_reasoning_model(runtime_config)
    if "embed" in model_name.lower():
        meta["llm_error"] = (
            f"当前模型「{model_name}」是向量/Embedding 模型，不能用于对话合规审查；"
            "请改为对话模型（如 qwen2.5:7b、llama3 等）"
        )
        if similar_refs:
            meta["engine"] = "rules+vector"
        return rule_hint, rule_severity, None, meta

    prompt = _build_compliance_prompt(
        voucher,
        rule_hint=rule_hint,
        rule_severity=rule_severity,
        similar_refs=similar_refs,
    )

    result = client.chat(
        [
            {"role": "system", "content": "你是财务合规审查助手，只审查用户给出的单张凭证。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        timeout_seconds=_COMPLIANCE_LLM_TIMEOUT_SECONDS,
    )
    if not result.available or not result.content:
        llm_error = result.error or "LLM 调用失败"
        if "timed out" in str(llm_error).lower():
            llm_error = (
                f"{llm_error}（合规审查已等待 {_COMPLIANCE_LLM_TIMEOUT_SECONDS} 秒；"
                "本地大模型过慢时可换更小对话模型或稍后重试）"
            )
        return _finalize_llm_compliance(
            None,
            rule_hint=rule_hint,
            rule_severity=rule_severity,
            similar_refs=similar_refs,
            llm_error=llm_error,
        )

    return _finalize_llm_compliance(
        result.content,
        rule_hint=rule_hint,
        rule_severity=rule_severity,
        similar_refs=similar_refs,
        llm_thinking=getattr(result, "thinking", None),
    )


def _review_voucher_group(
    db: Session,
    group_rows: list[StagingAccountingEntry],
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    group_rows = sorted(group_rows, key=lambda row: row.entry_line_no or 0)
    rule_hint, rule_severity = _rule_check_voucher(group_rows)
    similar_refs = _find_similar_tag_references(db, group_rows)

    if use_llm:
        hint, severity, reasoning, meta = _llm_semantic_compliance(
            db,
            _voucher_payload_for_llm(group_rows),
            rule_hint=rule_hint,
            rule_severity=rule_severity,
            similar_refs=similar_refs,
        )
    else:
        hint, severity, reasoning, meta = rule_hint, rule_severity, None, {
            "engine": "rules_only",
            "llm_used": False,
            "vector_refs": similar_refs,
        }

    for row in group_rows:
        row.compliance_hint = hint
        row.compliance_severity = severity

    first = group_rows[0]
    key = voucher_group_key(first)
    return {
        "group_key": key,
        "voucher_no": first.voucher_no,
        "compliance_hint": hint,
        "compliance_severity": severity,
        "line_count": len(group_rows),
        "engine": meta.get("engine"),
        "llm_used": meta.get("llm_used", False),
        "llm_error": meta.get("llm_error"),
        "compliant": meta.get("compliant"),
        "similar_tag_refs": similar_refs,
        "llm_reasoning": reasoning,
        "findings": meta.get("findings") or [],
        "similar_case_notes": meta.get("similar_case_notes"),
        "llm_thinking": meta.get("llm_thinking"),
    }


def _build_review_item(
    group_rows: list[StagingAccountingEntry],
    *,
    hint: str | None,
    severity: Severity,
    reasoning: str | None,
    meta: dict[str, Any],
    similar_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    first = group_rows[0]
    return {
        "group_key": voucher_group_key(first),
        "voucher_no": first.voucher_no,
        "compliance_hint": hint,
        "compliance_severity": severity,
        "line_count": len(group_rows),
        "engine": meta.get("engine"),
        "llm_used": meta.get("llm_used", False),
        "llm_error": meta.get("llm_error"),
        "compliant": meta.get("compliant"),
        "similar_tag_refs": similar_refs,
        "llm_reasoning": reasoning,
        "llm_thinking": meta.get("llm_thinking"),
        "findings": meta.get("findings") or [],
        "similar_case_notes": meta.get("similar_case_notes"),
    }


def iter_staging_compliance_review(
    db: Session,
    job_id: int,
    *,
    mode: ComplianceMode = "each",
    voucher_nos: list[str] | None = None,
    group_keys: list[str] | None = None,
    use_llm: bool = True,
) -> Iterator[dict[str, Any]]:
    """流式合规审查：向前端推送状态、思索/回复 token 与最终结果。"""
    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .order_by(StagingAccountingEntry.voucher_no, StagingAccountingEntry.entry_line_no)
        .all()
    )
    if mode == "skip":
        yield {"type": "done", "reviewed_vouchers": 0, "skipped": True, "items": []}
        return

    groups = group_staging_rows(rows)
    target_keys = list(groups.keys())
    if group_keys:
        allowed = set(group_keys)
        target_keys = [key for key in target_keys if key in allowed]
    elif voucher_nos:
        allowed = set(voucher_nos)
        target_keys = [key for key in target_keys if (groups[key][0].voucher_no or "") in allowed]
    elif mode in {"spot", "random"}:
        target_keys = [
            key for key, group_rows in groups.items() if any(row.spot_check_flag for row in group_rows)
        ]

    if not target_keys:
        yield {"type": "error", "message": "未找到待审查凭证"}
        return

    reviewed = 0
    items: list[dict[str, Any]] = []
    for key in target_keys:
        group_rows = sorted(groups[key], key=lambda row: row.entry_line_no or 0)
        voucher_no = group_rows[0].voucher_no or key
        yield {"type": "status", "message": f"规则预检：{voucher_no}"}
        rule_hint, rule_severity = _rule_check_voucher(group_rows)

        yield {"type": "status", "message": "向量库检索相似 Tag…"}
        similar_refs = _find_similar_tag_references(db, group_rows)
        yield {"type": "vector_done", "count": len(similar_refs)}

        if use_llm:
            hint: str | None = rule_hint
            severity: Severity = rule_severity
            reasoning: str | None = None
            meta: dict[str, Any] = {
                "engine": "rules_only",
                "llm_used": False,
                "vector_refs": similar_refs,
            }
            for event in _iter_llm_semantic_compliance(
                db,
                _voucher_payload_for_llm(group_rows),
                rule_hint=rule_hint,
                rule_severity=rule_severity,
                similar_refs=similar_refs,
            ):
                if event["type"] in {"thinking", "content", "status"}:
                    yield event
                elif event["type"] == "error":
                    yield event
                    meta = {
                        "engine": "rules+vector" if similar_refs else "rules_fallback",
                        "llm_used": False,
                        "vector_refs": similar_refs,
                        "llm_error": event.get("message"),
                    }
                    hint, severity, reasoning = rule_hint, rule_severity, None
                    break
                elif event["type"] == "result":
                    hint = event.get("hint")
                    severity = event.get("severity") or rule_severity
                    reasoning = event.get("reasoning")
                    meta = event.get("meta") or meta
        else:
            hint, severity, reasoning, meta = rule_hint, rule_severity, None, {
                "engine": "rules_only",
                "llm_used": False,
                "vector_refs": similar_refs,
            }

        for row in group_rows:
            row.compliance_hint = hint
            row.compliance_severity = severity

        item = _build_review_item(
            group_rows,
            hint=hint,
            severity=severity,
            reasoning=reasoning,
            meta=meta,
            similar_refs=similar_refs,
        )
        reviewed += 1
        items.append(item)
        yield {"type": "voucher_done", "item": item}

    db.commit()
    try:
        from app.services.audit.staging_preview_cache import invalidate_staging_preview_cache

        invalidate_staging_preview_cache(job_id)
    except Exception:
        pass

    single_scope = (group_keys and len(group_keys) == 1) or (voucher_nos and len(voucher_nos) == 1 and reviewed == 1)
    yield {
        "type": "done",
        "reviewed_vouchers": reviewed,
        "skipped": False,
        "scope": "single_voucher" if single_scope else "batch",
        "items": items,
    }


def review_staging_compliance(
    db: Session,
    job_id: int,
    *,
    mode: ComplianceMode = "each",
    voucher_nos: list[str] | None = None,
    group_keys: list[str] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .order_by(StagingAccountingEntry.voucher_no, StagingAccountingEntry.entry_line_no)
        .all()
    )
    if mode == "skip":
        return {"reviewed_vouchers": 0, "skipped": True, "items": []}

    groups = group_staging_rows(rows)

    target_keys = list(groups.keys())
    if group_keys:
        allowed = set(group_keys)
        target_keys = [key for key in target_keys if key in allowed]
    elif voucher_nos:
        allowed = set(voucher_nos)
        target_keys = [key for key in target_keys if (groups[key][0].voucher_no or "") in allowed]
    elif mode == "spot" or mode == "random":
        target_keys = [
            key for key, group_rows in groups.items() if any(row.spot_check_flag for row in group_rows)
        ]

    reviewed = 0
    items: list[dict[str, Any]] = []
    for key in target_keys:
        item = _review_voucher_group(db, groups[key], use_llm=use_llm)
        reviewed += 1
        items.append(item)

    db.commit()
    try:
        from app.services.audit.staging_preview_cache import invalidate_staging_preview_cache

        invalidate_staging_preview_cache(job_id)
    except Exception:
        pass
    single_scope = (group_keys and len(group_keys) == 1) or (voucher_nos and len(voucher_nos) == 1 and reviewed == 1)
    return {
        "reviewed_vouchers": reviewed,
        "skipped": False,
        "scope": "single_voucher" if single_scope else "batch",
        "items": items,
    }


def review_single_staging_voucher(
    db: Session,
    job_id: int,
    group_key: str,
    *,
    use_llm: bool = True,
) -> dict[str, Any]:
    """仅审查一张凭证（Step4 抽屉专用，按 group_key = 凭证号|日期 精确匹配）。"""
    return review_staging_compliance(
        db,
        job_id,
        mode="each",
        group_keys=[group_key],
        use_llm=use_llm,
    )
