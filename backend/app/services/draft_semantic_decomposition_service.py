"""底稿语义分解引擎。

利用规则 + 可选 LLM 对原始底稿进行稳定、可复现的多维语义分解：
- 识别涉及的会计维度（收入、成本、发票、往来、资金等）
- 映射到多个功能模块台账（非人工逐条指定）
- 提取语义标签与风险线索（供大数据与后续审计使用）
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.services.llm_client_service import LightweightLLMClient, LLMResult
from app.services.source_document_service import SourceDocumentResult

DECOMPOSITION_VERSION = "1.0.0"

# 会计语义维度 → 功能模块台账（可多模块）
DIMENSION_MODULE_MAP: dict[str, list[str]] = {
    "revenue": ["sales", "counterparty_ledger"],
    "cost": ["purchase", "counterparty_ledger"],
    "invoice": ["tax_invoice"],
    "tax": ["tax_invoice"],
    "counterparty": ["counterparty_ledger"],
    "inventory": ["inventory_receipt", "purchase"],
    "bank_cash": ["bank_cash_flow", "counterparty_ledger"],
    "payroll": ["payroll"],
    "fixed_asset": ["purchase"],
}

DIMENSION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "revenue": ("收入", "销售", "营收", "回款", "收款", "revenue", "sales", "主营业务收入"),
    "cost": ("成本", "费用", "采购", "支出", "付款", "cost", "expense", "主营业务成本", "管理费用"),
    "invoice": ("发票", "增值税", "开票", "销项", "进项", "invoice", "税号"),
    "tax": ("税率", "税额", "应税", "免税", "所得税", "印花税", "契税"),
    "counterparty": ("甲方", "乙方", "客户", "供应商", "往来", "应收", "应付", "预付", "预收", "对方单位"),
    "inventory": ("入库", "出库", "库存", "存货", "领料", "验收", "发货"),
    "bank_cash": ("银行", "流水", "汇款", "转账", "回单", "对账", "资金"),
    "payroll": ("工资", "薪酬", "社保", "公积金", "个税", "salary"),
    "fixed_asset": ("固定资产", "折旧", "设备", "在建工程"),
}

PRIMARY_DOCUMENT_MODULES: dict[str, list[str]] = {
    "invoice": ["tax_invoice"],
    "bank_statement": ["bank_cash_flow"],
    "contract": [],
    "inventory_receipt": ["inventory_receipt"],
    "payroll": ["payroll"],
    "general": [],
}

HINT_TO_DIMENSIONS: dict[str, list[str]] = {
    "invoice": ["invoice", "tax"],
    "bank_statement": ["bank_cash", "counterparty"],
    "contract": ["counterparty", "revenue", "cost"],
    "inventory": ["inventory", "cost"],
    "receipt": ["bank_cash"],
    "payroll": ["payroll"],
    "expense": ["cost"],
}


@dataclass
class ModuleTarget:
    module_key: str
    confidence: float
    accounting_dimension: str | None = None
    reason: str = ""
    semantic_only: bool = False


@dataclass
class RiskHint:
    risk_type: str
    severity: str
    description: str
    confidence: float = 0.7


@dataclass
class SemanticDecomposition:
    decomposition_version: str
    decomposition_source: str
    primary_document_type: str
    accounting_dimensions: dict[str, bool]
    module_targets: list[ModuleTarget]
    semantic_tags: list[str] = field(default_factory=list)
    risk_hints: list[RiskHint] = field(default_factory=list)

    def module_keys(self) -> list[str]:
        return [item.module_key for item in self.module_targets]

    def to_dict(self) -> dict[str, Any]:
        return {
            "decomposition_version": self.decomposition_version,
            "decomposition_source": self.decomposition_source,
            "primary_document_type": self.primary_document_type,
            "accounting_dimensions": self.accounting_dimensions,
            "module_targets": [asdict(item) for item in self.module_targets],
            "semantic_tags": self.semantic_tags,
            "risk_hints": [asdict(item) for item in self.risk_hints],
        }


def _normalize_document_type(document_type: str) -> str:
    if document_type in {"bank", "bank_statement"}:
        return "bank_statement"
    if document_type in {"inventory", "inventory_receipt"}:
        return "inventory_receipt"
    return document_type


def _build_text_blob(
    classification: SourceDocumentResult,
    document_type_hints: list[str] | None = None,
) -> str:
    data = classification.data or {}
    parts = [
        classification.file_name or "",
        classification.raw_text or "",
        str(data.get("content") or ""),
        json.dumps(data, ensure_ascii=False),
    ]
    if document_type_hints:
        parts.append(" ".join(document_type_hints))
    return " ".join(parts)


def _detect_dimensions(text: str, data: dict[str, Any], hints: list[str] | None) -> dict[str, bool]:
    dimensions = {key: False for key in DIMENSION_KEYWORDS}
    lowered = text.lower()

    for dimension, keywords in DIMENSION_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            dimensions[dimension] = True

    if data.get("party_a") or data.get("party_b") or data.get("buyer_name") or data.get("seller_name"):
        dimensions["counterparty"] = True
    if data.get("invoice_number") or data.get("invoice_no") or data.get("tax_amount"):
        dimensions["invoice"] = True
        dimensions["tax"] = True
    if data.get("transactions"):
        dimensions["bank_cash"] = True
        dimensions["counterparty"] = True
    if data.get("items"):
        dimensions["inventory"] = True

    for hint in hints or []:
        for dimension in HINT_TO_DIMENSIONS.get(hint, []):
            dimensions[dimension] = True

    return dimensions


def _dimensions_to_modules(dimensions: dict[str, bool]) -> list[ModuleTarget]:
    module_map: dict[str, ModuleTarget] = {}
    for dimension, active in dimensions.items():
        if not active:
            continue
        for module_key in DIMENSION_MODULE_MAP.get(dimension, []):
            existing = module_map.get(module_key)
            confidence = 0.82 if dimension in {"invoice", "bank_cash"} else 0.75
            reason = f"语义维度「{dimension}」映射"
            if existing is None or existing.confidence < confidence:
                module_map[module_key] = ModuleTarget(
                    module_key=module_key,
                    confidence=confidence,
                    accounting_dimension=dimension,
                    reason=reason,
                )
    return sorted(module_map.values(), key=lambda item: item.module_key)


def _primary_modules(document_type: str) -> list[ModuleTarget]:
    return [
        ModuleTarget(module_key=module_key, confidence=0.9, reason="主资料类型映射")
        for module_key in PRIMARY_DOCUMENT_MODULES.get(document_type, [])
    ]


def _merge_module_targets(*groups: list[ModuleTarget]) -> list[ModuleTarget]:
    merged: dict[str, ModuleTarget] = {}
    for group in groups:
        for target in group:
            current = merged.get(target.module_key)
            if current is None or target.confidence > current.confidence:
                merged[target.module_key] = target
            elif current and target.reason and target.reason not in current.reason:
                current.reason = f"{current.reason}；{target.reason}"
    return sorted(merged.values(), key=lambda item: item.module_key)


def _extract_semantic_tags(text: str, dimensions: dict[str, bool], data: dict[str, Any]) -> list[str]:
    tags: list[str] = []
    for dimension, active in dimensions.items():
        if active:
            tags.append(f"dimension:{dimension}")

    amount = data.get("total_amount") or data.get("amount") or data.get("contract_amount")
    try:
        if amount and float(amount) >= 1_000_000:
            tags.append("amount:large")
    except (TypeError, ValueError):
        pass

    if "关联方" in text or "关联企业" in text:
        tags.append("related_party:suspected")
    if "预付款" in text or "预付" in text:
        tags.append("payment:prepay")
    if "质保金" in text or "保证金" in text:
        tags.append("payment:retention")

    for keyword in ("服务费", "咨询费", "佣金", "补贴", "罚款", "违约金"):
        if keyword in text:
            tags.append(f"keyword:{keyword}")

    return sorted(set(tags))


def _extract_risk_hints(text: str, data: dict[str, Any], dimensions: dict[str, bool]) -> list[RiskHint]:
    hints: list[RiskHint] = []
    amount = data.get("total_amount") or data.get("amount") or data.get("contract_amount")
    try:
        numeric_amount = float(amount) if amount is not None else None
    except (TypeError, ValueError):
        numeric_amount = None

    if numeric_amount and numeric_amount >= 1_000_000:
        hints.append(RiskHint(
            risk_type="large_amount",
            severity="medium",
            description="识别到大额交易金额，建议重点复核合同/发票真实性与审批流程",
            confidence=0.85,
        ))

    if dimensions.get("revenue") and dimensions.get("cost"):
        hints.append(RiskHint(
            risk_type="mixed_revenue_cost",
            severity="low",
            description="同一底稿同时涉及收入与成本语义，可能存在多方交易或复杂结算条款",
            confidence=0.72,
        ))

    if dimensions.get("invoice") and not dimensions.get("bank_cash"):
        hints.append(RiskHint(
            risk_type="invoice_without_cash_evidence",
            severity="medium",
            description="资料体现发票/税务语义但未识别到资金收付信息，存在票款不一致风险",
            confidence=0.78,
        ))

    if "关联方" in text or "关联企业" in text:
        hints.append(RiskHint(
            risk_type="related_party",
            severity="high",
            description="文本出现关联方语义，需关注交易定价公允性与披露完整性",
            confidence=0.8,
        ))

    if not data.get("contract_number") and not data.get("invoice_number") and "合同" in text:
        hints.append(RiskHint(
            risk_type="missing_document_no",
            severity="low",
            description="合同类资料未识别到编号，可能影响后续勾稽与完整性测试",
            confidence=0.65,
        ))

    return hints


def _parse_llm_decomposition(content: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(content)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None


def _llm_enhance_decomposition(
    base: SemanticDecomposition,
    text: str,
    llm_client: LightweightLLMClient | None = None,
) -> SemanticDecomposition:
    client = llm_client or LightweightLLMClient()
    if not client.is_configured():
        return base

    prompt = {
        "task": "decompose_financial_draft",
        "instructions": (
            "你是财务底稿语义分解引擎。根据文本判断涉及的会计维度，并映射到模块台账。"
            "模块键仅限：tax_invoice, bank_cash_flow, counterparty_ledger, purchase, sales, inventory_receipt, payroll。"
            "返回 JSON："
            "{primary_document_type, accounting_dimensions:{revenue:bool,...}, "
            "module_targets:[{module_key,confidence,accounting_dimension,reason}], "
            "semantic_tags:[], risk_hints:[{risk_type,severity,description,confidence}]}"
        ),
        "primary_document_type": base.primary_document_type,
        "text_preview": text[:3000],
        "rule_baseline": base.to_dict(),
    }
    result: LLMResult = client.chat(
        [
            {"role": "system", "content": "只返回 JSON，不要解释。"},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.1,
    )
    if not result.available or not result.content:
        return base

    payload = _parse_llm_decomposition(result.content)
    if not payload:
        return base

    llm_dimensions = payload.get("accounting_dimensions") or {}
    merged_dimensions = dict(base.accounting_dimensions)
    if isinstance(llm_dimensions, dict):
        for key, value in llm_dimensions.items():
            if key in merged_dimensions and bool(value):
                merged_dimensions[key] = True

    llm_targets: list[ModuleTarget] = []
    for item in payload.get("module_targets") or []:
        if not isinstance(item, dict) or not item.get("module_key"):
            continue
        llm_targets.append(ModuleTarget(
            module_key=str(item["module_key"]),
            confidence=float(item.get("confidence") or 0.7),
            accounting_dimension=item.get("accounting_dimension"),
            reason=str(item.get("reason") or "LLM 语义补充"),
        ))

    merged_targets = _merge_module_targets(
        base.module_targets,
        _dimensions_to_modules(merged_dimensions),
        llm_targets,
    )

    semantic_tags = sorted(set(base.semantic_tags) | set(payload.get("semantic_tags") or []))
    risk_hints = list(base.risk_hints)
    seen_risk = {item.risk_type for item in risk_hints}
    for item in payload.get("risk_hints") or []:
        if not isinstance(item, dict) or not item.get("risk_type"):
            continue
        risk_type = str(item["risk_type"])
        if risk_type in seen_risk:
            continue
        seen_risk.add(risk_type)
        risk_hints.append(RiskHint(
            risk_type=risk_type,
            severity=str(item.get("severity") or "low"),
            description=str(item.get("description") or ""),
            confidence=float(item.get("confidence") or 0.7),
        ))

    return SemanticDecomposition(
        decomposition_version=DECOMPOSITION_VERSION,
        decomposition_source="rules+llm",
        primary_document_type=str(payload.get("primary_document_type") or base.primary_document_type),
        accounting_dimensions=merged_dimensions,
        module_targets=merged_targets,
        semantic_tags=semantic_tags,
        risk_hints=risk_hints,
    )


def decompose_draft(
    classification: SourceDocumentResult,
    document_type_hints: list[str] | None = None,
    llm_client: LightweightLLMClient | None = None,
) -> SemanticDecomposition:
    """对底稿进行稳定语义分解（规则基线 + 可选 LLM 增强）。"""
    document_type = _normalize_document_type(classification.document_type)
    text = _build_text_blob(classification, document_type_hints)
    data = classification.data or {}

    dimensions = _detect_dimensions(text, data, document_type_hints)
    rule_targets = _merge_module_targets(_primary_modules(document_type), _dimensions_to_modules(dimensions))

    if not rule_targets and document_type != "general":
        rule_targets = _dimensions_to_modules({"counterparty": True})

    base = SemanticDecomposition(
        decomposition_version=DECOMPOSITION_VERSION,
        decomposition_source="rules",
        primary_document_type=document_type,
        accounting_dimensions=dimensions,
        module_targets=rule_targets,
        semantic_tags=_extract_semantic_tags(text, dimensions, data),
        risk_hints=_extract_risk_hints(text, data, dimensions),
    )

    return _llm_enhance_decomposition(base, text, llm_client=llm_client)
