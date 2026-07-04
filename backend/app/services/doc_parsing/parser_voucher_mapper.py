# -*- coding: utf-8 -*-
"""
模块功能：将解析引擎的 ParseResult 映射为候选凭证草稿列表
业务场景：用户上传原始资料（发票/银行流水/费用单等），解析引擎提取结构化字段后，
         本模块根据会计规则将其映射为待确认的凭证草稿，供前端预览和确认。
政策依据：企业会计准则——基本准则；增值税相关财税文号
输入数据：ParseResult 对象（来自 parser_engine_dispatcher）
输出结果：CandidateVoucherDraft 列表，每项包含凭证头信息和分录行列表
创建日期：2026-07-02
更新记录：
    2026-07-02  初始创建，支持发票/银行流水/费用单/工资表/收据五种文档类型
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from app.services.doc_parsing.parser_engine.parse_result import (
    ParseResult,
    DocumentType,
)


# =============================================================================
# 数据结构定义
# =============================================================================

@dataclass
class CandidateEntryLine:
    """候选凭证分录行（尚未落库，供前端预览）"""

    account_code: str           # 科目编码
    account_name: str           # 科目名称
    summary: str                # 分录摘要
    debit_amount: Decimal = Decimal("0.00")   # 借方金额
    credit_amount: Decimal = Decimal("0.00")  # 贷方金额
    counterparty: Optional[str] = None        # 对方单位


@dataclass
class CandidateVoucherDraft:
    """候选凭证草稿（尚未落库，供前端预览和确认）"""

    voucher_no: str                         # 凭证号（建议值）
    voucher_date: str                       # 凭证日期（ISO 格式字符串）
    summary: str                            # 凭证摘要
    document_type: str                      # 来源文档类型
    source_confidence: float                # 解析置信度
    lines: list[CandidateEntryLine] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    raw_extracted_data: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# 金额处理工具
# =============================================================================

def _to_decimal(value: Any) -> Decimal:
    """将任意类型安全转换为 Decimal，保留2位小数"""
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    try:
        return Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _generate_voucher_no(document_type: DocumentType, index: int) -> str:
    """根据文档类型生成建议凭证号"""
    prefix_map = {
        DocumentType.INVOICE: "记",
        DocumentType.BANK_STATEMENT: "银",
        DocumentType.EXPENSE_DOCUMENT: "费",
        DocumentType.SALARY_TABLE: "薪",
        DocumentType.RECEIPT: "收",
    }
    prefix = prefix_map.get(document_type, "记")
    return f"{prefix}-{index:04d}"


# =============================================================================
# 各文档类型的映射规则
# =============================================================================

def _map_invoice_to_draft(
    data: dict[str, Any],
    confidence: float,
    voucher_no: str,
) -> CandidateVoucherDraft:
    """
    功能描述：将发票解析结果映射为凭证草稿
    业务逻辑：采购发票 → 借记存货/费用科目，借记进项税额，贷记应付账款
    会计口径：价税分离，不含税金额计入资产/费用，税额计入应交税费-进项税额
    """
    amount_excl_tax = _to_decimal(data.get("amount_excl_tax"))
    tax_amount = _to_decimal(data.get("tax_amount"))
    total_amount = _to_decimal(data.get("total_amount"))
    seller_name = data.get("seller_name", "")
    invoice_date = data.get("invoice_date", datetime.now().strftime("%Y-%m-%d"))

    # 【财税〔2016〕36 号】价税分离原则
    lines: list[CandidateEntryLine] = []

    # 借方：存货/原材料（不含税金额）
    lines.append(CandidateEntryLine(
        account_code="1401",
        account_name="原材料",
        summary=f"采购入库-{seller_name}",
        debit_amount=amount_excl_tax,
        counterparty=seller_name,
    ))

    # 借方：应交税费-应交增值税-进项税额
    if tax_amount > 0:
        lines.append(CandidateEntryLine(
            account_code="2221.01.02",
            account_name="应交税费-应交增值税-进项税额",
            summary=f"进项税额-{seller_name}",
            debit_amount=tax_amount,
            counterparty=seller_name,
        ))

    # 贷方：应付账款（价税合计）
    lines.append(CandidateEntryLine(
        account_code="2202",
        account_name="应付账款",
        summary=f"应付采购款-{seller_name}",
        credit_amount=total_amount,
        counterparty=seller_name,
    ))

    draft = CandidateVoucherDraft(
        voucher_no=voucher_no,
        voucher_date=str(invoice_date),
        summary=f"采购发票-{seller_name}",
        document_type="invoice",
        source_confidence=confidence,
        lines=lines,
        raw_extracted_data=data,
    )

    # 勾稽校验：借方合计应等于贷方合计
    debit_total = sum(line.debit_amount for line in lines)
    credit_total = sum(line.credit_amount for line in lines)
    if debit_total != credit_total:
        draft.validation_errors.append(
            f"借贷不平衡：借方 {debit_total}，贷方 {credit_total}，差额 {debit_total - credit_total}"
        )

    return draft


def _map_bank_statement_to_draft(
    data: dict[str, Any],
    confidence: float,
    voucher_no: str,
) -> CandidateVoucherDraft:
    """
    功能描述：将银行流水解析结果映射为凭证草稿
    业务逻辑：收款 → 借记银行存款，贷记应收账款/主营业务收入；
             付款 → 借记应付账款/费用科目，贷记银行存款
    会计口径：按交易方向区分借贷
    """
    amount = _to_decimal(data.get("transaction_amount"))
    counterparty = data.get("counterparty_name", "")
    transaction_date = data.get("transaction_date", datetime.now().strftime("%Y-%m-%d"))
    summary_text = data.get("summary", "")
    bank_name = data.get("bank_name", "")

    lines: list[CandidateEntryLine] = []

    # 判断收支方向：金额为正表示收款，为负表示付款
    if amount >= 0:
        # 收款：借银行存款，贷应收账款
        lines.append(CandidateEntryLine(
            account_code="1002",
            account_name="银行存款",
            summary=f"收款-{counterparty}-{summary_text}",
            debit_amount=amount,
        ))
        lines.append(CandidateEntryLine(
            account_code="1122",
            account_name="应收账款",
            summary=f"收回欠款-{counterparty}",
            credit_amount=amount,
            counterparty=counterparty,
        ))
    else:
        # 付款：借应付账款，贷银行存款（金额取绝对值）
        abs_amount = abs(amount)
        lines.append(CandidateEntryLine(
            account_code="2202",
            account_name="应付账款",
            summary=f"支付欠款-{counterparty}",
            debit_amount=abs_amount,
            counterparty=counterparty,
        ))
        lines.append(CandidateEntryLine(
            account_code="1002",
            account_name="银行存款",
            summary=f"付款-{counterparty}-{summary_text}",
            credit_amount=abs_amount,
        ))

    draft = CandidateVoucherDraft(
        voucher_no=voucher_no,
        voucher_date=str(transaction_date),
        summary=f"银行流水-{bank_name}-{counterparty}",
        document_type="bank_statement",
        source_confidence=confidence,
        lines=lines,
        raw_extracted_data=data,
    )
    return draft


def _map_expense_to_draft(
    data: dict[str, Any],
    confidence: float,
    voucher_no: str,
) -> CandidateVoucherDraft:
    """
    功能描述：将费用报销单解析结果映射为凭证草稿
    业务逻辑：借记管理费用，贷记库存现金/银行存款
    会计口径：按费用类型归集到对应费用科目
    """
    total_amount = _to_decimal(data.get("total_amount"))
    reimburser = data.get("reimburser_name", "")
    expense_type = data.get("expense_type", "管理费用")
    reimbursement_date = data.get("reimbursement_date", datetime.now().strftime("%Y-%m-%d"))

    # 费用类型到科目编码的映射
    expense_account_map = {
        "差旅费": ("6602.01", "管理费用-差旅费"),
        "办公费": ("6602.02", "管理费用-办公费"),
        "业务招待费": ("6602.03", "管理费用-业务招待费"),
        "交通费": ("6602.04", "管理费用-交通费"),
    }
    account_code, account_name = expense_account_map.get(
        expense_type, ("6602", "管理费用")
    )

    lines: list[CandidateEntryLine] = []

    # 借方：管理费用
    lines.append(CandidateEntryLine(
        account_code=account_code,
        account_name=account_name,
        summary=f"报销-{reimburser}-{expense_type}",
        debit_amount=total_amount,
    ))

    # 贷方：库存现金（默认现金报销，实际可根据情况调整）
    lines.append(CandidateEntryLine(
        account_code="1001",
        account_name="库存现金",
        summary=f"支付报销-{reimburser}",
        credit_amount=total_amount,
    ))

    draft = CandidateVoucherDraft(
        voucher_no=voucher_no,
        voucher_date=str(reimbursement_date),
        summary=f"费用报销-{reimburser}-{expense_type}",
        document_type="expense_document",
        source_confidence=confidence,
        lines=lines,
        raw_extracted_data=data,
    )
    return draft


def _map_salary_to_draft(
    data: dict[str, Any],
    confidence: float,
    voucher_no: str,
) -> CandidateVoucherDraft:
    """
    功能描述：将工资表解析结果映射为凭证草稿
    业务逻辑：借记应付职工薪酬（应发总额），贷记银行存款（实发），
             贷记其他应付款（社保+公积金+个税）
    会计口径：应发与实发的差额计入代扣款项
    """
    total_salary = _to_decimal(data.get("total_salary"))
    total_tax = _to_decimal(data.get("total_personal_income_tax"))
    total_social = _to_decimal(data.get("total_social_insurance"))
    total_fund = _to_decimal(data.get("total_housing_fund"))
    total_net = _to_decimal(data.get("total_net_pay"))
    salary_period = data.get("salary_period", datetime.now().strftime("%Y-%m"))

    lines: list[CandidateEntryLine] = []

    # 借方：应付职工薪酬-工资（应发总额）
    lines.append(CandidateEntryLine(
        account_code="2211",
        account_name="应付职工薪酬-工资",
        summary=f"发放{salary_period}工资",
        debit_amount=total_salary,
    ))

    # 贷方：银行存款（实发金额）
    lines.append(CandidateEntryLine(
        account_code="1002",
        account_name="银行存款",
        summary=f"支付{salary_period}工资",
        credit_amount=total_net,
    ))

    # 贷方：其他应付款-代扣个人所得税
    if total_tax > 0:
        lines.append(CandidateEntryLine(
            account_code="2241.01",
            account_name="其他应付款-代扣个人所得税",
            summary=f"代扣{salary_period}个税",
            credit_amount=total_tax,
        ))

    # 贷方：其他应付款-代扣社保
    if total_social > 0:
        lines.append(CandidateEntryLine(
            account_code="2241.02",
            account_name="其他应付款-代扣社保",
            summary=f"代扣{salary_period}社保",
            credit_amount=total_social,
        ))

    # 贷方：其他应付款-代扣公积金
    if total_fund > 0:
        lines.append(CandidateEntryLine(
            account_code="2241.03",
            account_name="其他应付款-代扣公积金",
            summary=f"代扣{salary_period}公积金",
            credit_amount=total_fund,
        ))

    draft = CandidateVoucherDraft(
        voucher_no=voucher_no,
        voucher_date=f"{salary_period}-15" if len(salary_period) == 7 else str(salary_period),
        summary=f"工资发放-{salary_period}",
        document_type="salary_table",
        source_confidence=confidence,
        lines=lines,
        raw_extracted_data=data,
    )

    # 勾稽校验：借方合计应等于贷方合计
    debit_total = sum(line.debit_amount for line in lines)
    credit_total = sum(line.credit_amount for line in lines)
    if debit_total != credit_total:
        draft.validation_errors.append(
            f"工资表借贷不平衡：借方 {debit_total}，贷方 {credit_total}，"
            f"差额 {debit_total - credit_total}（可能解析字段缺失）"
        )

    return draft


def _map_receipt_to_draft(
    data: dict[str, Any],
    confidence: float,
    voucher_no: str,
) -> CandidateVoucherDraft:
    """
    功能描述：将收据解析结果映射为凭证草稿
    业务逻辑：借记库存现金/银行存款，贷记其他应付款/主营业务收入
    会计口径：收据通常不涉及增值税，直接按金额入账
    """
    amount = _to_decimal(data.get("amount"))
    payee_name = data.get("payee_name", "")
    payer_name = data.get("payer_name", "")
    receipt_date = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    reason = data.get("reason", "")

    lines: list[CandidateEntryLine] = []

    # 借方：库存现金
    lines.append(CandidateEntryLine(
        account_code="1001",
        account_name="库存现金",
        summary=f"收-{payer_name}-{reason}",
        debit_amount=amount,
    ))

    # 贷方：其他应付款（默认，实际需根据业务判断）
    lines.append(CandidateEntryLine(
        account_code="2241",
        account_name="其他应付款",
        summary=f"收-{payer_name}-{reason}",
        credit_amount=amount,
        counterparty=payer_name,
    ))

    draft = CandidateVoucherDraft(
        voucher_no=voucher_no,
        voucher_date=str(receipt_date),
        summary=f"收据-{payer_name}-{reason}",
        document_type="receipt",
        source_confidence=confidence,
        lines=lines,
        raw_extracted_data=data,
    )
    return draft


# =============================================================================
# 主映射函数
# =============================================================================

# 文档类型到映射函数的调度表
_MAPPER_DISPATCH = {
    DocumentType.INVOICE: _map_invoice_to_draft,
    DocumentType.BANK_STATEMENT: _map_bank_statement_to_draft,
    DocumentType.EXPENSE_DOCUMENT: _map_expense_to_draft,
    DocumentType.SALARY_TABLE: _map_salary_to_draft,
    DocumentType.RECEIPT: _map_receipt_to_draft,
}


def parse_result_to_voucher_drafts(
    parse_result: ParseResult,
) -> list[CandidateVoucherDraft]:
    """
    功能描述：将解析引擎的 ParseResult 转换为候选凭证草稿列表
    业务逻辑：根据文档类型调度对应的映射函数，生成会计分录候选
    会计口径：所有金额使用 Decimal 精确计算，借贷平衡校验

    Args:
        parse_result: 解析引擎返回的 ParseResult 对象

    Returns:
        候选凭证草稿列表，每个草稿包含凭证头和分录行

    注意事项：
        1. 当前支持发票、银行流水、费用单、工资表、收据五种文档类型
        2. 不支持的类型返回空列表，调用方应提示用户手工录入
        3. 生成的凭证号为建议值，前端可修改
        4. 所有草稿状态为 draft，需人工复核后才可入账
    """
    document_type = parse_result.document_type
    mapper = _MAPPER_DISPATCH.get(document_type)

    if mapper is None:
        return []

    data = parse_result.data
    if not data:
        return []

    # 对于银行流水，data 可能包含多条交易记录
    if document_type == DocumentType.BANK_STATEMENT and isinstance(data.get("transactions"), list):
        drafts: list[CandidateVoucherDraft] = []
        for index, txn in enumerate(data["transactions"], start=1):
            voucher_no = _generate_voucher_no(document_type, index)
            draft = mapper(txn, parse_result.confidence, voucher_no)
            drafts.append(draft)
        return drafts

    # 单条记录的文档类型
    voucher_no = _generate_voucher_no(document_type, 1)
    draft = mapper(data, parse_result.confidence, voucher_no)
    return [draft]


def drafts_to_voucher_service_format(
    drafts: list[CandidateVoucherDraft],
    ledger_id: int,
    organization_id: int,
) -> list[dict[str, Any]]:
    """
    功能描述：将候选凭证草稿转换为 voucher_service.create_vouchers_from_drafts 的输入格式
    业务逻辑：展开每个草稿的分录行为扁平字典列表

    Args:
        drafts: 用户确认后的候选凭证草稿列表
        ledger_id: 账簿 ID
        organization_id: 组织 ID

    Returns:
        voucher_service.create_vouchers_from_drafts 所需的 draft 字典列表
    """
    result: list[dict[str, Any]] = []
    for draft in drafts:
        for line in draft.lines:
            result.append({
                "voucher_no": draft.voucher_no,
                "voucher_date": draft.voucher_date,
                "summary": draft.summary,
                "account_code": line.account_code,
                "account_name": line.account_name,
                "debit_amount": str(line.debit_amount),
                "credit_amount": str(line.credit_amount),
                "counterparty": line.counterparty,
            })
    return result
