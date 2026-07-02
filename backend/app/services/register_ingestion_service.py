"""AI 导入路径：原始资料 → 功能模块台账登记。

底稿（SourceFile）保留文件载体；本服务将 AI/规则识别结果写入各模块台账表，
并同步内存台账服务，不生成会计分录（AccountingEntry）。

模块映射规则：
- 发票 → 税务模块台账；若形成未结清往来余额，可登记往来款项台账
- 银行流水 → 银行资金台账（仅资金事实，不登记往来款项）
- 合同 → 合同台账（承诺状态）；若为采购/销售合同，同时登记采购/销售模块
- 往来款项台账仅登记已发生的应收/应付/预收/预付余额，不登记合同承诺或银行流水
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import SourceFile
from app.services.document_parsing_service import DocumentParsingService
from app.services.draft_semantic_decomposition_service import (
    ModuleTarget,
    SemanticDecomposition,
    decompose_draft,
)
from app.services.ledger_service import BusinessType, ContractLedger, LedgerEntry, ledger_service
from app.services.source_document_service import SourceDocumentResult, classify_document

# 功能模块台账定义（非会计分录）
MODULE_DEFINITIONS: dict[str, dict[str, str]] = {
    "tax_invoice": {
        "label": "税务模块-发票台账",
        "module_path": "/tax/invoices",
    },
    "bank_cash_flow": {
        "label": "银行模块-资金收支台账",
        "module_path": "/bank/cash-flow-ledger",
    },
    "contract_register": {
        "label": "合同台账",
        "module_path": "/audit/contracts",
    },
    "counterparty_ledger": {
        "label": "往来款项台账",
        "module_path": "/basic/receivable-payable",
    },
    "purchase": {
        "label": "采购模块-采购业务台账",
        "module_path": "/inventory/purchase-in",
    },
    "sales": {
        "label": "销售模块-销售业务台账",
        "module_path": "/inventory/sale-out",
    },
    "inventory_receipt": {
        "label": "库存模块-收发台账",
        "module_path": "/inventory/stock-receipt-ledger",
    },
    "payroll": {
        "label": "薪酬模块-工资台账",
        "module_path": "/payroll/ledger",
    },
    "general": {
        "label": "通用底稿资料",
        "module_path": "/ledger/files",
    },
}

HINT_TO_DOCUMENT_TYPE: dict[str, str] = {
    "invoice": "invoice",
    "bank_statement": "bank_statement",
    "bank": "bank_statement",
    "contract": "contract",
    "inventory": "inventory_receipt",
    "receipt": "bank_statement",
    "payroll": "payroll",
    "expense": "general",
    "other": "general",
}

PURCHASE_KEYWORDS = ("采购", "购买", "进货", "供应", "purchase", "procurement", "买方", "购入")
SALES_KEYWORDS = ("销售", "出售", "经销", "客户", "sales", "sell", "卖方", "销货")

EXECUTION_STATUS_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cancelled": ("取消", "终止", "作废", "解除"),
    "not_executed": ("未执行", "未履行", "未开工"),
    "completed": ("已完成", "履行完毕", "执行完毕"),
    "executing": ("执行中", "履行中", "进行中"),
}


def _scope_payload(source_file: SourceFile, **extra: Any) -> dict[str, Any]:
    payload = {
        "ledger_id": source_file.ledger_id,
        "counterparty_id": source_file.counterparty_id,
        "source_file_id": source_file.id,
    }
    payload.update(extra)
    return payload


def _infer_execution_status(data: dict[str, Any], raw_text: str | None, filename: str) -> str:
    if data.get("execution_status"):
        return str(data["execution_status"])
    text = " ".join([raw_text or "", filename or "", str(data.get("content") or "")])
    for status, keywords in EXECUTION_STATUS_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return status
    return "pending"


@dataclass
class ModuleRegistration:
    module_key: str
    module_label: str
    module_path: str
    register_ids: list[int] = field(default_factory=list)
    register_count: int = 0
    accounting_dimension: str | None = None
    semantic_only: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_key": self.module_key,
            "module_label": self.module_label,
            "module_path": self.module_path,
            "register_ids": self.register_ids,
            "register_count": self.register_count,
            "accounting_dimension": self.accounting_dimension,
            "semantic_only": self.semantic_only,
            "reason": self.reason,
        }


@dataclass
class RegisterIngestionResult:
    success: bool
    document_type: str
    module_label: str
    module_path: str
    register_ids: list[int] = field(default_factory=list)
    register_count: int = 0
    confidence: float = 0.0
    summary: str = ""
    error_message: str | None = None
    draft_only: bool = False
    module_registrations: list[ModuleRegistration] = field(default_factory=list)
    semantic_decomposition: dict[str, Any] = field(default_factory=dict)
    semantic_tags: list[str] = field(default_factory=list)
    risk_hints: list[dict[str, Any]] = field(default_factory=list)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _normalize_document_type(document_type: str) -> str:
    if document_type in {"bank", "bank_statement"}:
        return "bank_statement"
    if document_type in {"inventory", "inventory_receipt"}:
        return "inventory_receipt"
    return document_type


def _apply_type_hints(result: SourceDocumentResult, hints: list[str] | None) -> SourceDocumentResult:
    if not hints or result.confidence >= 0.55:
        return result

    for hint in hints:
        mapped = HINT_TO_DOCUMENT_TYPE.get(hint)
        if not mapped:
            continue
        return SourceDocumentResult(
            document_type=mapped,
            confidence=max(result.confidence, 0.55),
            data=result.data,
            raw_text=result.raw_text,
            file_name=result.file_name,
        )
    return result


def _detect_contract_modules(data: dict[str, Any], raw_text: str | None, filename: str) -> list[str]:
    """兼容旧调用：委托语义分解引擎。"""
    from app.services.source_document_service import SourceDocumentResult

    classification = SourceDocumentResult(
        document_type="contract",
        confidence=0.9,
        data=data,
        raw_text=raw_text,
        file_name=filename,
    )
    return decompose_draft(classification).module_keys()


def _map_bank_transaction_type(value: str | None) -> str:
    if not value:
        return "income"
    text = str(value)
    if any(token in text for token in ("支", "付", "借", "debit", "expense", "out")):
        return "expense"
    return "income"


def _register_to_module(module_key: str, entry: LedgerEntry) -> None:
    bucket = ledger_service.module_ledgers.setdefault(module_key, {})
    bucket[entry.id] = entry


def _build_module_registration(
    module_key: str,
    register_ids: list[int] | None = None,
    *,
    accounting_dimension: str | None = None,
    semantic_only: bool = False,
    reason: str = "",
) -> ModuleRegistration:
    meta = MODULE_DEFINITIONS.get(module_key, MODULE_DEFINITIONS["general"])
    ids = register_ids or []
    return ModuleRegistration(
        module_key=module_key,
        module_label=meta["label"],
        module_path=meta["module_path"],
        register_ids=ids,
        register_count=len(ids),
        accounting_dimension=accounting_dimension,
        semantic_only=semantic_only,
        reason=reason,
    )


def _register_semantic_projection(
    source_file: SourceFile,
    module_key: str,
    data: dict[str, Any],
    confidence: float,
    target: ModuleTarget,
    linked_db_id: int | None = None,
) -> None:
    """为分解出的次要模块建立语义台账投影（不一定有独立 DB 行）。"""
    entry = ContractLedger(
        source_file=source_file.filename,
        source_type="contract",
        contract_number=data.get("contract_number") or data.get("contract_no"),
        party_a=data.get("party_a") or data.get("buyer_name"),
        party_b=data.get("party_b") or data.get("seller_name"),
        sign_date=data.get("sign_date"),
        contract_amount=data.get("amount") or data.get("contract_amount") or data.get("total_amount"),
        counterparty=data.get("party_b") or data.get("seller_name") or data.get("buyer_name"),
        amount=data.get("amount") or data.get("contract_amount") or data.get("total_amount"),
        date=data.get("sign_date") or data.get("invoice_date"),
        confidence=target.confidence,
        business_type=BusinessType.PURCHASE if module_key == "purchase" else BusinessType.SALES if module_key == "sales" else BusinessType.OTHER,
        metadata={
            **data,
            "module_key": module_key,
            "module_path": MODULE_DEFINITIONS.get(module_key, MODULE_DEFINITIONS["general"])["module_path"],
            "semantic_projection": True,
            "accounting_dimension": target.accounting_dimension,
            "decomposition_reason": target.reason,
            "linked_db_id": linked_db_id,
        },
    )
    _register_to_module(module_key, entry)


def _persist_invoice(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
    raw_text: str | None,
    decomposition: SemanticDecomposition,
) -> tuple[list[int], list[ModuleRegistration]]:
    service = DocumentParsingService(db)
    payload = _scope_payload(
        source_file,
        invoice_no=data.get("invoice_number") or data.get("invoice_no"),
        invoice_date=_parse_date(data.get("invoice_date")),
        buyer_name=data.get("buyer_name"),
        seller_name=data.get("seller_name"),
        tax_amount=data.get("tax_amount"),
        tax_rate=data.get("tax_rate"),
        total_amount=data.get("total_amount"),
        items=data.get("items") or [],
        extracted_text=raw_text,
        confidence_score=confidence,
    )
    invoice = service.parse_invoice(organization_id, payload)
    db.commit()

    invoice_entry = ledger_service.add_invoice(data, source_file.filename)
    invoice_entry.metadata["module_key"] = "tax_invoice"
    invoice_entry.metadata["module_path"] = MODULE_DEFINITIONS["tax_invoice"]["module_path"]
    invoice_entry.metadata["semantic_tags"] = decomposition.semantic_tags
    _register_to_module("tax_invoice", invoice_entry)

    module_regs = [_build_module_registration("tax_invoice", [invoice.id], reason="主资料：发票")]
    persisted_modules = {"tax_invoice"}

    for target in decomposition.module_targets:
        if target.module_key in persisted_modules:
            continue
        _register_semantic_projection(source_file, target.module_key, data, target.confidence, target, invoice.id)
        module_regs.append(_build_module_registration(
            target.module_key,
            [invoice.id],
            accounting_dimension=target.accounting_dimension,
            semantic_only=True,
            reason=target.reason,
        ))
        persisted_modules.add(target.module_key)

    return [invoice.id], module_regs


def _persist_contract(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
    raw_text: str | None,
    filename: str,
    decomposition: SemanticDecomposition,
    *,
    contract_parse_result: Any | None = None,
) -> tuple[list[int], list[ModuleRegistration]]:
    """
    将合同解析结果持久化到合同台账

    功能描述：支持两种数据来源：
        1. 传统 source_document_service 解析结果
        2. ContractParser 基于 CAS 14 五步法的解析结果
    业务逻辑：
        1. 优先使用 ContractParser 结果（更详细的会计准则信息）
        2. 回退到传统解析结果
        3. 写入 contracts 表和关联表
        4. 同步内存台账服务
    """
    service = DocumentParsingService(db)

    # 优先使用 ContractParser 结果（基于 CAS 14 五步法）
    if contract_parse_result:
        return _persist_contract_from_parser(
            db, organization_id, source_file, contract_parse_result,
            confidence, raw_text, filename, decomposition, service,
        )

    # 传统解析路径（保持向后兼容）
    parties = []
    if data.get("party_a"):
        parties.append({"party_role": "party_a", "party_name": data.get("party_a")})
    if data.get("party_b"):
        parties.append({"party_role": "party_b", "party_name": data.get("party_b")})

    module_keys = decomposition.module_keys() or ["contract_register"]
    contract_type = "purchase" if "purchase" in module_keys else "sales" if "sales" in module_keys else "service"

    payload = _scope_payload(
        source_file,
        contract_no=data.get("contract_number") or data.get("contract_no"),
        contract_type=contract_type,
        contract_name=data.get("contract_name") or data.get("content", "")[:80] or source_file.filename,
        sign_date=_parse_date(data.get("sign_date")),
        contract_amount=data.get("amount") or data.get("contract_amount"),
        parties=parties,
        extracted_text=raw_text,
        confidence_score=confidence,
        execution_status=_infer_execution_status(data, raw_text, filename),
    )
    contract = service.parse_contract(organization_id, payload)
    db.commit()

    base_entry = ledger_service.add_contract(data, source_file.filename)
    base_entry.metadata["semantic_tags"] = decomposition.semantic_tags
    module_regs: list[ModuleRegistration] = []
    target_by_key = {item.module_key: item for item in decomposition.module_targets}

    for module_key in module_keys:
        if module_key == "counterparty_ledger":
            continue
        target = target_by_key.get(module_key) or ModuleTarget(module_key=module_key, confidence=confidence, reason="合同语义分解")
        semantic_only = module_key in {"tax_invoice", "bank_cash_flow"} or module_key not in {"contract_register", "purchase", "sales"}

        if semantic_only:
            _register_semantic_projection(source_file, module_key, data, target.confidence, target, contract.id)
        else:
            module_entry = ContractLedger(
                source_file=source_file.filename,
                source_type="contract",
                contract_number=base_entry.contract_number,
                party_a=base_entry.party_a,
                party_b=base_entry.party_b,
                sign_date=base_entry.sign_date,
                contract_amount=base_entry.contract_amount,
                counterparty=base_entry.counterparty,
                amount=base_entry.amount,
                date=base_entry.date,
                confidence=target.confidence,
                business_type=BusinessType.PURCHASE if module_key == "purchase" else BusinessType.SALES if module_key == "sales" else BusinessType.OTHER,
                metadata={
                    **data,
                    "module_key": module_key,
                    "module_path": MODULE_DEFINITIONS[module_key]["module_path"],
                    "contract_db_id": contract.id,
                    "accounting_dimension": target.accounting_dimension,
                    "decomposition_reason": target.reason,
                    "semantic_tags": decomposition.semantic_tags,
                },
            )
            _register_to_module(module_key, module_entry)

        module_regs.append(_build_module_registration(
            module_key,
            [contract.id],
            accounting_dimension=target.accounting_dimension,
            semantic_only=semantic_only,
            reason=target.reason,
        ))

    return [contract.id], module_regs


def _persist_contract_from_parser(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    contract_parse_result: Any,
    confidence: float,
    raw_text: str | None,
    filename: str,
    decomposition: SemanticDecomposition,
    service: DocumentParsingService,
) -> tuple[list[int], list[ModuleRegistration]]:
    """
    使用 ContractParser 结果持久化合同台账

    功能描述：将基于 CAS 14 五步法的解析结果写入合同台账
    业务逻辑：
        1. 提取合同基本信息（编号、类型、名称）
        2. 提取时间信息（签署日期、执行周期）
        3. 提取金额信息（价税分离）
        4. 提取履约义务（时段法/时点法）
        5. 提取违约责任（预计负债）
        6. 写入 contracts 表和关联表
    """
    from app.services.contract_parser_service import ContractParseResult

    result = contract_parse_result
    if not isinstance(result, ContractParseResult):
        raise ValueError("contract_parse_result 必须是 ContractParseResult 类型")

    # 确定合同类型
    contract_type = "service"
    if result.contract_type:
        type_lower = result.contract_type.lower()
        if any(kw in type_lower for kw in PURCHASE_KEYWORDS):
            contract_type = "purchase"
        elif any(kw in type_lower for kw in SALES_KEYWORDS):
            contract_type = "sales"
        elif "框架" in type_lower or "framework" in type_lower:
            contract_type = "framework"

    # 构建合同 payload
    parties_data = []
    for party in result.parties:
        parties_data.append({
            "party_role": party.role.lower().replace("甲方", "party_a").replace("乙方", "party_b").replace("丙方", "party_c"),
            "party_name": party.name,
            "party_code": party.tax_id,
            "party_address": party.address,
            "party_contact": party.contact,
        })

    # 履约义务（JSON 格式）
    performance_obligations = []
    for obligation in result.performance_obligations:
        performance_obligations.append({
            "obligation_no": str(obligation.item_no),
            "obligation_name": obligation.description[:50] if obligation.description else "",
            "obligation_description": obligation.description,
            "quantity": float(obligation.quantity) if obligation.quantity else 0,
            "unit": obligation.unit,
            "unit_price": float(obligation.unit_price) if obligation.unit_price else 0,
            "total_price": float(obligation.total_price) if obligation.total_price else 0,
            "distinct": obligation.distinct,
            "separately_identifiable": obligation.separately_identifiable,
            "highly_interdependent": obligation.highly_interdependent,
            "integration_service": obligation.integration_service,
            "revenue_recognition_method": obligation.revenue_recognition_method,
            "time_method_criteria": obligation.time_method_criteria,
            "qualified_payment_right": obligation.qualified_payment_right,
            "irreplaceable_use": obligation.irreplaceable_use,
            "standalone_selling_price": float(obligation.standalone_selling_price) if obligation.standalone_selling_price else 0,
            "allocation_ratio": float(obligation.allocation_ratio) if obligation.allocation_ratio else 0,
        })

    # 风险标记（违约责任）
    risk_flags = {
        "penalties": [
            {
                "penalty_clause": p.penalty_clause,
                "penalty_amount": float(p.penalty_amount) if p.penalty_amount else 0,
                "penalty_type": p.penalty_type,
                "is_probable": p.is_probable,
                "provision_required": p.provision_required,
                "provision_amount": float(p.provision_amount) if p.provision_amount else 0,
                "impact_on_revenue": p.impact_on_revenue,
            }
            for p in result.penalties
        ],
        "contract_costs": [
            {
                "cost_type": c.cost_type,
                "amount": float(c.amount) if c.amount else 0,
                "amortization_method": c.amortization_method,
            }
            for c in result.contract_costs
        ],
        "financial_assets": [
            {
                "asset_type": a.asset_type,
                "amount": float(a.amount) if a.amount else 0,
                "expected_credit_loss": float(a.expected_credit_loss) if a.expected_credit_loss else 0,
                "risk_rating": a.risk_rating,
            }
            for a in result.financial_assets
        ],
        "tax_treatment": {
            "tax_type": result.tax_treatment.tax_type,
            "tax_rate": float(result.tax_treatment.tax_rate) if result.tax_treatment.tax_rate else 0,
            "tax_amount": float(result.tax_treatment.tax_amount) if result.tax_treatment.tax_amount else 0,
            "special_treatment": result.tax_treatment.special_treatment,
        },
        "accounting_notes": result.accounting_notes,
        "five_step_analysis": result.five_step_analysis,
        "validation_errors": result.validation_errors if hasattr(result, 'validation_errors') else [],
    }

    payload = _scope_payload(
        source_file,
        contract_no=None,  # 合同编号从文本中提取，如未提取则为空
        contract_type=contract_type,
        contract_name=result.summary[:80] if result.summary else filename,
        sign_date=_parse_date(result.signing_date),
        start_date=_parse_date(result.period.start_date) if result.period else None,
        end_date=_parse_date(result.period.end_date) if result.period else None,
        contract_amount=float(result.price.total_amount) if result.price.total_amount else 0,
        currency=result.price.currency,
        tax_rate=float(result.price.tax_rate) if result.price.tax_rate else 0,
        tax_amount=float(result.price.tax_amount) if result.price.tax_amount else 0,
        performance_obligations=performance_obligations,
        transaction_price=float(result.price.amount_excl_tax) if result.price.amount_excl_tax else 0,
        is_over_time=any(
            o.revenue_recognition_method == "时段法"
            for o in result.performance_obligations
        ),
        progress_method="output" if any(
            o.revenue_recognition_method == "时段法" and "产出法" in str(o.time_method_criteria)
            for o in result.performance_obligations
        ) else "input",
        revenue_recognition_type="over_time" if any(
            o.revenue_recognition_method == "时段法"
            for o in result.performance_obligations
        ) else "point_in_time",
        risk_flags=risk_flags,
        parties=parties_data,
        extracted_text=raw_text,
        confidence_score=float(result.confidence_score) if result.confidence_score else 0.8,
        execution_status="pending",
    )

    contract = service.parse_contract(organization_id, payload)
    db.commit()

    # 同步内存台账
    module_keys = decomposition.module_keys() or ["contract_register"]
    if contract_type == "purchase" and "purchase" not in module_keys:
        module_keys.append("purchase")
    if contract_type == "sales" and "sales" not in module_keys:
        module_keys.append("sales")

    base_data = {
        "contract_number": contract.contract_no,
        "party_a": next((p.party_name for p in contract.parties if p.party_role == "party_a"), ""),
        "party_b": next((p.party_name for p in contract.parties if p.party_role == "party_b"), ""),
        "sign_date": result.signing_date,
        "contract_amount": float(result.price.total_amount) if result.price.total_amount else 0,
        "amount": float(result.price.amount_excl_tax) if result.price.amount_excl_tax else 0,
        "date": result.signing_date,
    }
    base_entry = ledger_service.add_contract(base_data, source_file.filename)
    base_entry.metadata["semantic_tags"] = decomposition.semantic_tags
    base_entry.metadata["cas14_five_step"] = True
    base_entry.metadata["contract_parse_result"] = {
        "contract_type": result.contract_type,
        "contract_valid": result.contract_valid,
        "commercial_substance": result.commercial_substance,
        "collection_probable": result.collection_probable,
        "parties": [{"name": p.name, "role": p.role} for p in result.parties],
        "price": {
            "total_amount": float(result.price.total_amount) if result.price.total_amount else 0,
            "amount_excl_tax": float(result.price.amount_excl_tax) if result.price.amount_excl_tax else 0,
            "tax_rate": float(result.price.tax_rate) if result.price.tax_rate else 0,
            "tax_amount": float(result.price.tax_amount) if result.price.tax_amount else 0,
        },
        "performance_obligations_count": len(result.performance_obligations),
        "penalties_count": len(result.penalties),
    }

    module_regs: list[ModuleRegistration] = []
    target_by_key = {item.module_key: item for item in decomposition.module_targets}

    for module_key in module_keys:
        if module_key == "counterparty_ledger":
            continue
        target = target_by_key.get(module_key) or ModuleTarget(module_key=module_key, confidence=confidence, reason="CAS 14 五步法合同解析")
        semantic_only = module_key in {"tax_invoice", "bank_cash_flow"} or module_key not in {"contract_register", "purchase", "sales"}

        if semantic_only:
            _register_semantic_projection(source_file, module_key, base_data, target.confidence, target, contract.id)
        else:
            module_entry = ContractLedger(
                source_file=source_file.filename,
                source_type="contract",
                contract_number=base_entry.contract_number,
                party_a=base_entry.party_a,
                party_b=base_entry.party_b,
                sign_date=base_entry.sign_date,
                contract_amount=base_entry.contract_amount,
                counterparty=base_entry.counterparty,
                amount=base_entry.amount,
                date=base_entry.date,
                confidence=target.confidence,
                business_type=BusinessType.PURCHASE if module_key == "purchase" else BusinessType.SALES if module_key == "sales" else BusinessType.OTHER,
                metadata={
                    **base_data,
                    "module_key": module_key,
                    "module_path": MODULE_DEFINITIONS[module_key]["module_path"],
                    "contract_db_id": contract.id,
                    "accounting_dimension": target.accounting_dimension,
                    "decomposition_reason": target.reason,
                    "semantic_tags": decomposition.semantic_tags,
                    "cas14_five_step": True,
                },
            )
            _register_to_module(module_key, module_entry)

        module_regs.append(_build_module_registration(
            module_key,
            [contract.id],
            accounting_dimension=target.accounting_dimension,
            semantic_only=semantic_only,
            reason=target.reason,
        ))

    return [contract.id], module_regs


def _persist_bank_statements(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
    raw_text: str | None,
    decomposition: SemanticDecomposition | None = None,
) -> tuple[list[int], list[ModuleRegistration]]:
    service = DocumentParsingService(db)
    register_ids: list[int] = []
    transactions = data.get("transactions") or []
    if not transactions and data.get("transaction_date"):
        transactions = [data]

    for index, transaction in enumerate(transactions, start=1):
        payload = _scope_payload(
            source_file,
            transaction_no=transaction.get("transaction_no") or f"{source_file.id}-{index}",
            transaction_date=_parse_date(transaction.get("transaction_date") or transaction.get("date")),
            transaction_type=_map_bank_transaction_type(transaction.get("transaction_type")),
            counterparty_name=transaction.get("counterparty"),
            amount=abs(float(transaction.get("amount") or 0)),
            summary=transaction.get("summary"),
            extracted_text=raw_text,
            confidence_score=confidence,
        )
        statement = service.parse_bank_statement(organization_id, payload)
        db.commit()
        register_ids.append(statement.id)

        bank_entry = ledger_service.add_bank_statement(transaction, source_file.filename)
        bank_entry.metadata["module_key"] = "bank_cash_flow"
        bank_entry.metadata["module_path"] = MODULE_DEFINITIONS["bank_cash_flow"]["module_path"]
        _register_to_module("bank_cash_flow", bank_entry)

    module_regs = [_build_module_registration("bank_cash_flow", register_ids, reason="主资料：银行流水")]
    if decomposition:
        for target in decomposition.module_targets:
            if target.module_key in {"bank_cash_flow", "counterparty_ledger"}:
                continue
            _register_semantic_projection(source_file, target.module_key, data, target.confidence, target, register_ids[0] if register_ids else None)
            module_regs.append(_build_module_registration(
                target.module_key,
                register_ids[:1],
                accounting_dimension=target.accounting_dimension,
                semantic_only=True,
                reason=target.reason,
            ))
    return register_ids, module_regs


def _persist_inventory(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
    raw_text: str | None,
) -> tuple[list[int], list[ModuleRegistration]]:
    service = DocumentParsingService(db)
    payload = _scope_payload(
        source_file,
        document_no=data.get("receipt_number") or data.get("document_no") or f"INV-{source_file.id}",
        document_type=data.get("document_type") or "inventory_in",
        document_date=_parse_date(data.get("receipt_date") or data.get("document_date")),
        counterparty_name=data.get("supplier") or data.get("counterparty_name"),
        counterparty_type="supplier",
        total_amount=data.get("total_amount"),
        items=data.get("items") or [],
        extracted_text=raw_text,
        confidence_score=confidence,
    )
    document = service.parse_inventory_document(organization_id, payload)
    db.commit()

    inventory_entry = ledger_service.add_inventory(data, source_file.filename)
    inventory_entry.metadata["module_key"] = "inventory_receipt"
    inventory_entry.metadata["module_path"] = MODULE_DEFINITIONS["inventory_receipt"]["module_path"]
    _register_to_module("inventory_receipt", inventory_entry)

    module_regs = [_build_module_registration("inventory_receipt", [document.id])]
    return [document.id], module_regs


def _persist_payroll(
    source_file: SourceFile,
    data: dict[str, Any],
    confidence: float,
) -> tuple[list[int], list[ModuleRegistration]]:
    from app.services.ledger_service import PayrollLedger

    entry = PayrollLedger(
        source_file=source_file.filename,
        source_type="payroll",
        period=data.get("period"),
        total_amount=data.get("total_amount"),
        employee_count=data.get("employee_count"),
        amount=data.get("total_amount"),
        date=data.get("period"),
        confidence=confidence,
        metadata={
            **data,
            "module_key": "payroll",
            "module_path": MODULE_DEFINITIONS["payroll"]["module_path"],
        },
    )
    ledger_service.payroll_ledger[entry.id] = entry
    _register_to_module("payroll", entry)
    return [], [_build_module_registration("payroll", [])]


def _summarize_modules(module_regs: list[ModuleRegistration]) -> str:
    if not module_regs:
        return "已保存为底稿资料"
    parts = [f"{item.module_label} {item.register_count or 1} 条" for item in module_regs]
    return "已登记：" + "；".join(parts)


def ingest_register_from_document(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    classification: SourceDocumentResult,
    document_type_hints: list[str] | None = None,
    decomposition: SemanticDecomposition | None = None,
) -> RegisterIngestionResult:
    """将已分类原始资料登记到功能模块台账（非会计分录）。"""
    result = _apply_type_hints(classification, document_type_hints)
    document_type = _normalize_document_type(result.document_type)
    semantic = decomposition or decompose_draft(result, document_type_hints)

    if document_type == "general" or result.confidence < 0.35:
        general = _build_module_registration("general", [], reason="待确认资料类型")
        return RegisterIngestionResult(
            success=True,
            document_type="general",
            module_label=general.module_label,
            module_path=general.module_path,
            confidence=result.confidence,
            summary="已保存为底稿资料，待 AI 语义分解确认后登记台账",
            draft_only=True,
            module_registrations=[general],
            semantic_decomposition=semantic.to_dict(),
            semantic_tags=semantic.semantic_tags,
            risk_hints=[asdict(item) for item in semantic.risk_hints],
        )

    try:
        data = result.data or {}
        raw_text = result.raw_text
        module_regs: list[ModuleRegistration] = []
        register_ids: list[int] = []

        if document_type == "invoice":
            register_ids, module_regs = _persist_invoice(db, organization_id, source_file, data, result.confidence, raw_text, semantic)
        elif document_type == "contract":
            register_ids, module_regs = _persist_contract(
                db, organization_id, source_file, data, result.confidence, raw_text, source_file.filename, semantic
            )
        elif document_type == "bank_statement":
            register_ids, module_regs = _persist_bank_statements(db, organization_id, source_file, data, result.confidence, raw_text, semantic)
        elif document_type == "inventory_receipt":
            register_ids, module_regs = _persist_inventory(db, organization_id, source_file, data, result.confidence, raw_text)
        elif document_type == "payroll":
            register_ids, module_regs = _persist_payroll(source_file, data, result.confidence)
        else:
            general = _build_module_registration("general", [], reason="未识别模块")
            return RegisterIngestionResult(
                success=True,
                document_type=document_type,
                module_label=general.module_label,
                module_path=general.module_path,
                confidence=result.confidence,
                summary="已保存底稿，暂未匹配到可落库的模块台账结构",
                draft_only=True,
                module_registrations=[general],
                semantic_decomposition=semantic.to_dict(),
                semantic_tags=semantic.semantic_tags,
                risk_hints=[asdict(item) for item in semantic.risk_hints],
            )

        primary = module_regs[0]
        risk_summary = f"；识别 {len(semantic.risk_hints)} 条风险线索" if semantic.risk_hints else ""
        return RegisterIngestionResult(
            success=True,
            document_type=document_type,
            module_label=primary.module_label,
            module_path=primary.module_path,
            register_ids=register_ids,
            register_count=len(register_ids),
            confidence=result.confidence,
            summary=_summarize_modules(module_regs) + risk_summary,
            module_registrations=module_regs,
            semantic_decomposition=semantic.to_dict(),
            semantic_tags=semantic.semantic_tags,
            risk_hints=[asdict(item) for item in semantic.risk_hints],
        )
    except Exception as exc:
        general = MODULE_DEFINITIONS.get(document_type, MODULE_DEFINITIONS["general"])
        return RegisterIngestionResult(
            success=False,
            document_type=document_type,
            module_label=general["label"],
            module_path=general["module_path"],
            confidence=result.confidence,
            summary="底稿已保存，但台账登记失败",
            error_message=str(exc),
            draft_only=True,
            module_registrations=[],
            semantic_decomposition=semantic.to_dict(),
            semantic_tags=semantic.semantic_tags,
            risk_hints=[asdict(item) for item in semantic.risk_hints],
        )


def classify_and_ingest_register(
    db: Session,
    organization_id: int,
    source_file: SourceFile,
    document_type_hints: list[str] | None = None,
) -> tuple[SourceDocumentResult, RegisterIngestionResult]:
    classification = classify_document(source_file.storage_path, source_file.filename)
    decomposition = decompose_draft(classification, document_type_hints)
    ingestion = ingest_register_from_document(
        db,
        organization_id,
        source_file,
        classification,
        document_type_hints=document_type_hints,
        decomposition=decomposition,
    )
    ledger_id = source_file.ledger_id
    if ledger_id is None and source_file.import_job_id:
        from app.db.models import ImportJob

        job = db.get(ImportJob, source_file.import_job_id)
        ledger_id = job.ledger_id if job else None
    if ledger_id is not None:
        try:
            from app.services import audit_workflow_service

            recommendations = audit_workflow_service.recommend_procedures_from_decomposition(
                decomposition.to_dict()
            )
            if recommendations:
                audit_workflow_service.create_runs_from_recommendations(
                    db,
                    ledger_id,
                    recommendations,
                    source_file_id=source_file.id,
                )
        except Exception:
            pass
    return classification, ingestion
