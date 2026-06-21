from datetime import datetime
from pydantic import BaseModel


class ImportJobCreate(BaseModel):
    """
    导入任务创建请求

    功能描述：定义创建导入任务时的请求参数
    业务逻辑：支持指定数据来源类型，区分标准凭证导入与审计序时簿导入

    Args:
        organization_name: 企业名称
        industry: 行业类型
        fiscal_year: 会计年度
        source_type: 数据来源类型，默认 "voucher_import"，可选 "audit_day_book"、"ledger_day_book"
    """
    organization_name: str = "默认企业"
    industry: str | None = None
    fiscal_year: int | None = None
    source_type: str = "voucher_import"
    ledger_id: int | None = None


class ImportJobRead(BaseModel):
    id: int
    organization_id: int
    ledger_id: int | None = None
    status: str
    source_type: str
    file_count: int
    entry_count: int
    error_message: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DayBookReportRead(BaseModel):
    """
    序时簿检测报告响应模型

    功能描述：定义序时簿导入后检测报告的返回结构
    业务逻辑：包含凭证总数、跳号数量、不平衡凭证数量、完整性评分及明细清单

    会计口径：
        - 完整性评分满分 100，跳号与不平衡凭证按比例扣分
        - 金额使用 Decimal 精确计算，保留 2 位小数
    """
    total_vouchers: int
    total_entries: int
    skip_count: int
    unbalanced_count: int
    completeness_score: float
    missing_voucher_nos: list[str]
    unbalanced_vouchers: list[dict]
