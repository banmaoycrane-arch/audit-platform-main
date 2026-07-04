from typing import Any
from collections import defaultdict
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AuditRisk, RiskEvidence
from app.services.audit.risk_analysis_service import explain_risk
from app.services.doc_parsing.vector_store_service import safe_vector_store


def _amount(entry: AccountingEntry) -> Decimal:
    debit = Decimal(str(entry.debit_amount)) if entry.debit_amount else Decimal("0.00")
    credit = Decimal(str(entry.credit_amount)) if entry.credit_amount else Decimal("0.00")
    return debit if debit != Decimal("0.00") else credit


def _find_similar_entries(db: Session, entry: AccountingEntry, threshold: float = 0.85) -> list[tuple[str, float, dict[str, Any]]]:
    """查找与当前分录相似的历史分录（基于向量检索）"""
    store = safe_vector_store()
    if not store:
        return []
    
    text = entry.normalized_text or entry.summary or ""
    if not text:
        return []
    
    try:
        results = store.search(text, limit=10)
        similar = []
        for result in results:
            score = result.get("score", 0)
            if score >= threshold:
                payload = result.get("payload", {})
                source_id = payload.get("source_id")
                if source_id and int(source_id) != entry.id:
                    similar.append((str(source_id), score, payload))
        return similar
    except Exception:
        return []


def generate_vector_similarity_risks(db: Session, import_job_id: int, seen: set[tuple[str, str]]) -> list[AuditRisk]:
    """基于向量相似检索生成风险"""
    created: list[AuditRisk] = []
    entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == import_job_id).all()
    
    for entry in entries:
        similar_list = _find_similar_entries(db, entry)
        if similar_list:
            title = f"向量相似风险：{entry.summary[:30] if entry.summary else '未知摘要'}"
            key = ("vector_similar_anomaly", title)
            if key in seen:
                continue
            
            risk = AuditRisk(
                organization_id=entry.organization_id,
                import_job_id=entry.import_job_id,
                risk_type="vector_similar_anomaly",
                risk_level="medium",
                title=title,
                description=explain_risk("发现与历史分录语义相似的记录，需核查是否存在重复入账、关联交易未披露或异常模式", entry.normalized_text or ""),
                confidence=min(0.95, max(s[1] for s in similar_list)),
                review_status="pending_review",
            )
            db.add(risk)
            db.flush()
            
            db.add(RiskEvidence(
                risk_id=risk.id,
                evidence_type="accounting_entry",
                source_id=entry.id,
                source_text=entry.normalized_text or entry.summary or "",
                reason="当前分录作为风险主体"
            ))
            
            for source_id, score, payload in similar_list[:5]:
                reason = f"相似分录（相似度：{score:.2f}）"
                if "voucher_no" in payload:
                    reason += f"，凭证号：{payload['voucher_no']}"
                db.add(RiskEvidence(
                    risk_id=risk.id,
                    evidence_type="similar_entry",
                    source_id=int(source_id),
                    source_text=payload.get("chunk_text", "")[:200],
                    reason=reason,
                    similarity_score=score,
                ))
            
            created.append(risk)
            seen.add(key)
    
    return created


def generate_risks(db: Session, import_job_id: int) -> list[AuditRisk]:
    entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == import_job_id).all()
    created: list[AuditRisk] = []
    seen = {(risk.risk_type, risk.title) for risk in db.query(AuditRisk).filter(AuditRisk.import_job_id == import_job_id).all()}

    duplicate_groups: dict[tuple[str, Decimal], list[AccountingEntry]] = defaultdict(list)
    for entry in entries:
        duplicate_groups[((entry.summary or "").strip(), _amount(entry))].append(entry)

    for entry in entries:
        checks: list[tuple[str, str, str, str, float]] = []
        amount = _amount(entry)
        if amount >= 100000 and amount % 10000 == 0:
            checks.append(("large_round_amount", "high", "大额整数金额", "分录金额较大且为整数金额，需核查交易真实性和审批依据。", 0.85))
        if len((entry.summary or "").strip()) < 4:
            checks.append(("weak_summary", "medium", "摘要过短或为空", "凭证摘要信息不足，难以支撑业务实质判断。", 0.8))
        if entry.voucher_date and entry.voucher_date.month == 12 and amount >= 50000:
            checks.append(("period_end_expense", "medium", "期末大额交易", "期末发生大额交易，需关注跨期确认和利润调节风险。", 0.78))
        if any(word in (entry.account_name or "") for word in ["其他应收", "其他应付"]):
            checks.append(("long_outstanding_current", "medium", "往来科目挂账风险", "往来科目分录需要结合账龄和对方单位核查长期挂账风险。", 0.72))

        for risk_type, level, title, description, confidence in checks:
            key = (risk_type, f"{title}：{entry.voucher_no or entry.id}")
            if key in seen:
                continue
            evidence_text = entry.normalized_text or entry.summary or ""
            risk = AuditRisk(
                organization_id=entry.organization_id,
                import_job_id=entry.import_job_id,
                risk_type=risk_type,
                risk_level=level,
                title=key[1],
                description=explain_risk(description, evidence_text),
                confidence=confidence,
                review_status="pending_review",
            )
            db.add(risk)
            db.flush()
            db.add(RiskEvidence(risk_id=risk.id, evidence_type="accounting_entry", source_id=entry.id, source_text=evidence_text, reason=description))
            created.append(risk)
            seen.add(key)

    for (summary, amount), group in duplicate_groups.items():
        if summary and amount and len(group) > 1:
            first = group[0]
            key = ("duplicate_entry", f"重复交易疑似：{summary[:30]}")
            if key in seen:
                continue
            risk = AuditRisk(
                organization_id=first.organization_id,
                import_job_id=first.import_job_id,
                risk_type="duplicate_entry",
                risk_level="medium",
                title=key[1],
                description=explain_risk("存在同摘要、同金额的多笔分录，需核查是否重复入账或重复报销", summary),
                confidence=0.82,
                review_status="pending_review",
            )
            db.add(risk)
            db.flush()
            for entry in group:
                db.add(RiskEvidence(risk_id=risk.id, evidence_type="accounting_entry", source_id=entry.id, source_text=entry.normalized_text, reason="同摘要、同金额重复出现"))
            created.append(risk)
            seen.add(key)

    vector_risks = generate_vector_similarity_risks(db, import_job_id, seen)
    created.extend(vector_risks)

    db.commit()
    return created
