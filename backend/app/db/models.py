from datetime import date, datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="默认企业")
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    fiscal_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="created")
    source_type: Mapped[str] = mapped_column(String(40), default="voucher_import")
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    entry_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_scope_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    audit_period_id: Mapped[int | None] = mapped_column(ForeignKey("accounting_periods.id"), nullable=True)
    audit_account_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    organization: Mapped[Organization] = relationship()
    source_files: Mapped[list["SourceFile"]] = relationship(back_populates="import_job")


class SourceFile(Base):
    __tablename__ = "source_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"))
    import_job: Mapped[ImportJob] = relationship(back_populates="source_files")
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(300))
    file_type: Mapped[str] = mapped_column(String(80))
    storage_path: Mapped[str] = mapped_column(String(500))
    text_extract_status: Mapped[str] = mapped_column(String(40), default="pending")
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_match_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    customer_confidence_note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ExecutionAuditLog(Base):
    __tablename__ = "execution_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    execution_source: Mapped[str] = mapped_column(String(40), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    confirmed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    accounting_period_id: Mapped[int | None] = mapped_column(ForeignKey("accounting_periods.id"), nullable=True)
    agent_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    agent_task_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    service_name: Mapped[str] = mapped_column(String(160))
    business_object_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    business_object_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(40), default="low")
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    before_snapshot_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    after_snapshot_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(80), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_prompt_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    model_output_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class AgentApproval(Base):
    __tablename__ = "agent_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    agent_role: Mapped[str] = mapped_column(String(80), index=True)
    risk_level: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    requested_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    confirmed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_args_summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confirmation_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AgentDraftReview(Base):
    __tablename__ = "agent_draft_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    approval_id: Mapped[int] = mapped_column(ForeignKey("agent_approvals.id"), index=True)
    tool_name: Mapped[str] = mapped_column(String(120), index=True)
    agent_role: Mapped[str] = mapped_column(String(80), index=True)
    draft_output_type: Mapped[str] = mapped_column(String(40), default="draft")
    review_status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    team_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    returned_for_rework: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_formal_delivery_design: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class SmsVerificationCode(Base):
    __tablename__ = "sms_verification_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phone: Mapped[str] = mapped_column(String(32), index=True)
    code: Mapped[str] = mapped_column(String(16))
    consumed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


# ==================== 会计主体相关表 ====================

class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 主体基本信息
    entity_name: Mapped[str] = mapped_column(String(500))
    entity_code: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 统一社会信用代码等
    entity_type: Mapped[str] = mapped_column(String(50))  # company/group/branch/individual/organization
    entity_category: Mapped[str] = mapped_column(String(50))  # parent/subsidiary/associate/joint_venture
    
    # 多维度主体类型标记
    is_accounting_entity: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否为会计主体
    is_tax_entity: Mapped[bool] = mapped_column(Boolean, default=False)        # 是否为纳税主体
    is_legal_entity: Mapped[bool] = mapped_column(Boolean, default=False)       # 是否为法律主体
    is_management_entity: Mapped[bool] = mapped_column(Boolean, default=False) # 是否为管理主体
    
    # 法律属性
    legal_form: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 法人/非法人/分支机构
    has_legal_personality: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否具有法人资格
    
    # 税务属性
    tax_registration_no: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 税务登记号
    taxpayer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)        # 一般纳税人/小规模
    
    # 层级关系
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=1)  # 层级级别（1=顶层）
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 元数据
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # 关系
    parent: Mapped["Entity"] = relationship("Entity", remote_side=[id])


class EntityTag(Base):
    __tablename__ = "entity_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    
    # 语义标签
    tag: Mapped[str] = mapped_column(String(500))
    tag_type: Mapped[str] = mapped_column(String(50))  # name/alias/acronym/description
    
    # 置信度
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    
    # 来源
    source: Mapped[str] = mapped_column(String(50), default="system")  # system/ai/manual
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EntityScope(Base):
    __tablename__ = "entity_scopes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 范围定义
    scope_name: Mapped[str] = mapped_column(String(200))
    scope_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 时间范围
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    
    # 类型
    scope_type: Mapped[str] = mapped_column(String(50))  # consolidation/tax/management/legal
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EntityScopeMember(Base):
    __tablename__ = "entity_scope_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_id: Mapped[int] = mapped_column(ForeignKey("entity_scopes.id"))
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    
    # 成员类型
    member_type: Mapped[str] = mapped_column(String(50))  # full/proportionate/equity/virtual
    
    # 持股比例（适用于权益法或比例合并）
    ownership_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    
    # 状态
    is_included: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EntityVersion(Base):
    __tablename__ = "entity_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    
    # 版本信息
    version_number: Mapped[int] = mapped_column(Integer)
    version_name: Mapped[str] = mapped_column(String(200))
    
    # 变更时间
    effective_date: Mapped[date] = mapped_column(Date)
    
    # 变更内容（JSON格式）
    changes: Mapped[dict] = mapped_column(JSON)
    
    # 变更原因
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 变更人
    changed_by: Mapped[str] = mapped_column(String(100), default="system")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 虚拟主体集合 ====================

class VirtualEntitySet(Base):
    __tablename__ = "virtual_entity_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 集合信息
    set_name: Mapped[str] = mapped_column(String(200))  # 如 "XX集团"
    set_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    set_type: Mapped[str] = mapped_column(String(50))  # group/division/department/channel
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class VirtualEntitySetMember(Base):
    __tablename__ = "virtual_entity_set_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    set_id: Mapped[int] = mapped_column(ForeignKey("virtual_entity_sets.id"))
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    
    # 成员角色
    member_role: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 如 "总部", "事业部A"
    
    # 优先级（用于排序）
    priority: Mapped[int] = mapped_column(Integer, default=1)
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 主体关系类型 ====================

class EntityRelationType(Base):
    __tablename__ = "entity_relation_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 关系类型定义
    relation_code: Mapped[str] = mapped_column(String(50))  # parent_subsidiary, branch_of, same_control
    relation_name: Mapped[str] = mapped_column(String(100))  # 母子公司关系, 分支机构关系, 同一控制
    relation_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 关系属性
    is_hierarchical: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否层级关系
    is_reciprocal: Mapped[bool] = mapped_column(Boolean, default=True)   # 是否双向关系
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EntityRelation(Base):
    __tablename__ = "entity_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 关系双方
    entity_a_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    entity_b_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    
    # 关系类型
    relation_type_id: Mapped[int] = mapped_column(ForeignKey("entity_relation_types.id"))
    
    # 关系属性
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 股权信息（适用于投资关系）
    ownership_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    investment_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    
    # 置信度
    confidence: Mapped[float] = mapped_column(Float, default=0.9)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountingEntry(Base):
    __tablename__ = "accounting_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"))
    voucher_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voucher_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    account_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    account_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # 主体标识（语义映射用）
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    original_entity_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # 追溯字段：直接关联源文件
    source_file_id: Mapped[int | None] = mapped_column(ForeignKey("source_files.id"), nullable=True)
    
    # 来源标记：区分自动生成与手工录入
    entry_source: Mapped[str] = mapped_column(String(20), default="auto")  # "auto" | "manual"
    
    debit_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    credit_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"), nullable=True)
    original_row: Mapped[dict] = mapped_column(JSON, default=dict)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    entry_line_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    review_status: Mapped[str] = mapped_column(String(20), default="draft")
    post_status: Mapped[str] = mapped_column(String(20), default="draft")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    posted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index(
            "ix_entry_voucher_line",
            "organization_id",
            "voucher_no",
            "entry_line_no",
        ),
    )


# ==================== 会计期间与快照相关表 ====================

class AccountingPeriod(Base):
    __tablename__ = "accounting_periods"
    __table_args__ = (
        UniqueConstraint("organization_id", "period_code", name="uq_accounting_period_org_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    period_code: Mapped[str] = mapped_column(String(40))
    period_type: Mapped[str] = mapped_column(String(40), default="monthly")
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="open")
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PeriodSnapshot(Base):
    __tablename__ = "period_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("accounting_periods.id"))
    snapshot_version: Mapped[int] = mapped_column(Integer, default=1)
    dimension_type: Mapped[str] = mapped_column(String(80))
    dimension_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dimension_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dimension_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    source_scope: Mapped[dict] = mapped_column(JSON, default=dict)
    generation_params: Mapped[dict] = mapped_column(JSON, default=dict)
    snapshot_status: Mapped[str] = mapped_column(String(40), default="valid")
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PeriodCloseLog(Base):
    __tablename__ = "period_close_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    period_id: Mapped[int] = mapped_column(ForeignKey("accounting_periods.id"))
    action_type: Mapped[str] = mapped_column(String(50))
    transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    operator: Mapped[str] = mapped_column(String(100), default="system")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    old_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    snapshot_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 事务性相关表 ====================

# ==================== 内部核算单位相关表 ====================

class AccountingUnitType(Base):
    __tablename__ = "accounting_unit_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 类型定义
    type_code: Mapped[str] = mapped_column(String(50))  # project/department/product/channel/customer/platform
    type_name: Mapped[str] = mapped_column(String(100))  # 项目/部门/产品/渠道/客户/平台
    type_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 层级属性
    allow_hierarchy: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否允许层级
    allow_combination: Mapped[bool] = mapped_column(Boolean, default=True)  # 是否允许组合
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountingUnit(Base):
    __tablename__ = "accounting_units"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 基本信息
    unit_name: Mapped[str] = mapped_column(String(500))
    unit_code: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 编码
    unit_type_id: Mapped[int] = mapped_column(ForeignKey("accounting_unit_types.id"))
    
    # 描述信息
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 层级信息
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("accounting_units.id"), nullable=True)
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=1)
    
    # 关联会计主体（直接追溯）
    entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    
    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # 关系
    parent: Mapped["AccountingUnit"] = relationship("AccountingUnit", remote_side=[id])


class AccountingUnitHierarchy(Base):
    __tablename__ = "accounting_unit_hierarchy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 层级关系
    parent_unit_id: Mapped[int] = mapped_column(ForeignKey("accounting_units.id"))
    child_unit_id: Mapped[int] = mapped_column(ForeignKey("accounting_units.id"))
    
    # 层级深度
    depth: Mapped[int] = mapped_column(Integer, default=1)
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountingUnitCombination(Base):
    __tablename__ = "accounting_unit_combinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 组合信息
    combination_name: Mapped[str] = mapped_column(String(200))
    combination_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    combination_type: Mapped[str] = mapped_column(String(50))  # merge/group/temporary
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountingUnitCombinationMember(Base):
    __tablename__ = "accounting_unit_combination_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 组合关联
    combination_id: Mapped[int] = mapped_column(ForeignKey("accounting_unit_combinations.id"))
    unit_id: Mapped[int] = mapped_column(ForeignKey("accounting_units.id"))
    
    # 权重（用于比例分配）
    weight: Mapped[float] = mapped_column(Numeric(5, 2), default=1.0)
    
    # 优先级
    priority: Mapped[int] = mapped_column(Integer, default=1)
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountingUnitEntityRelation(Base):
    __tablename__ = "accounting_unit_entity_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 关联关系
    unit_id: Mapped[int] = mapped_column(ForeignKey("accounting_units.id"))
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id"))
    
    # 关联类型
    relation_type: Mapped[str] = mapped_column(String(50))  # primary/secondary/shared
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountingUnitVersion(Base):
    __tablename__ = "accounting_unit_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 版本信息
    unit_id: Mapped[int] = mapped_column(ForeignKey("accounting_units.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    version_name: Mapped[str] = mapped_column(String(200))
    
    # 变更时间
    effective_date: Mapped[date] = mapped_column(Date)
    
    # 变更内容
    changes: Mapped[dict] = mapped_column(JSON)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 变更人
    changed_by: Mapped[str] = mapped_column(String(100), default="system")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AccountingUnitTag(Base):
    __tablename__ = "accounting_unit_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 标签信息
    unit_id: Mapped[int] = mapped_column(ForeignKey("accounting_units.id"))
    tag: Mapped[str] = mapped_column(String(500))
    tag_type: Mapped[str] = mapped_column(String(50))  # name/alias/acronym/description
    
    # 置信度
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    source: Mapped[str] = mapped_column(String(50), default="system")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 物料层级与行业颗粒度相关表 ====================

class Industry(Base):
    __tablename__ = "industries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 行业信息
    industry_code: Mapped[str] = mapped_column(String(50))  # manufacturing/trading/retail/service/finance
    industry_name: Mapped[str] = mapped_column(String(100))  # 生产制造/贸易批发/零售电商/服务业/金融
    industry_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 推荐颗粒度
    recommended_granularity: Mapped[str] = mapped_column(String(50))  # sku/product/batch/project/account
    granularity_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 支持的核算单位类型
    supported_unit_types: Mapped[list] = mapped_column(JSON, default=list)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 物料基本信息
    material_code: Mapped[str] = mapped_column(String(100))  # 物料编码
    material_name: Mapped[str] = mapped_column(String(500))  # 物料名称
    material_type: Mapped[str] = mapped_column(String(50))  # raw_material/semi_finished/finished/goods_sku
    
    # 规格信息
    specification: Mapped[str | None] = mapped_column(String(500), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 单位：个/件/千克/米等
    
    # 层级信息
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("materials.id"), nullable=True)
    hierarchy_level: Mapped[int] = mapped_column(Integer, default=1)  # 1=原材料, 2=半成品, 3=成品, 4=SKU
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # 关系
    parent: Mapped["Material"] = relationship("Material", remote_side=[id])


class MaterialHierarchy(Base):
    __tablename__ = "material_hierarchy"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 层级关系
    parent_material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    child_material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    
    # 转换类型
    conversion_type: Mapped[str] = mapped_column(String(50))  # assembly/refining/fermentation/packaging/customization
    
    # 转化率/配比
    conversion_rate: Mapped[float | None] = mapped_column(Numeric(10, 4), nullable=True)
    
    # 层级深度
    depth: Mapped[int] = mapped_column(Integer, default=1)
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MaterialBOM(Base):
    __tablename__ = "material_bom"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # BOM信息
    bom_code: Mapped[str] = mapped_column(String(100))  # BOM编码
    bom_name: Mapped[str] = mapped_column(String(200))  # BOM名称
    
    # 成品物料
    finished_goods_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    
    # 版本信息
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class MaterialBOMItem(Base):
    __tablename__ = "material_bom_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # BOM关联
    bom_id: Mapped[int] = mapped_column(ForeignKey("material_bom.id"))
    
    # 物料信息
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    
    # 用量
    quantity: Mapped[float] = mapped_column(Numeric(18, 4))
    unit: Mapped[str] = mapped_column(String(50))
    
    # 损耗率
    wastage_rate: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    
    # 优先级/顺序
    sequence: Mapped[int] = mapped_column(Integer, default=1)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 事务标识
    transaction_id: Mapped[str] = mapped_column(String(100), unique=True)
    
    # 事务类型
    transaction_type: Mapped[str] = mapped_column(String(50))  # import/analysis/audit/test
    
    # 关联上下文
    context_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 如导入作业ID
    context_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # 状态
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending/committed/rolled_back/failed
    
    # 时间信息
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # 操作计数
    operation_count: Mapped[int] = mapped_column(Integer, default=0)
    succeeded_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # 错误信息
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TransactionOperation(Base):
    __tablename__ = "transaction_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    
    # 操作信息
    operation_order: Mapped[int] = mapped_column(Integer)
    operation_type: Mapped[str] = mapped_column(String(50))  # create/update/delete
    entity_type: Mapped[str] = mapped_column(String(50))  # 如 accounting_entry, contract
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # 操作详情
    operation_details: Mapped[dict] = mapped_column(JSON)
    rollback_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    
    # 状态
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending/succeeded/failed/rolled_back
    
    # 错误信息
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class TransactionCheckpoint(Base):
    __tablename__ = "transaction_checkpoints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    
    # 检查点信息
    checkpoint_name: Mapped[str] = mapped_column(String(100))
    checkpoint_order: Mapped[int] = mapped_column(Integer)
    
    # 状态
    is_reached: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 时间
    reached_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EntryTag(Base):
    __tablename__ = "entry_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entry_id: Mapped[int] = mapped_column(ForeignKey("accounting_entries.id"))
    tag_name: Mapped[str] = mapped_column(String(100))
    tag_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tag_value: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tag_value_normalized: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tag_source: Mapped[str] = mapped_column(String(40), default="rule")
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    reviewed_by_user: Mapped[bool] = mapped_column(Boolean, default=False)
    vector_pending: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChartOfAccounts(Base):
    __tablename__ = "chart_of_accounts"
    __table_args__ = (
        UniqueConstraint("ledger_id", "code", name="uq_chart_of_accounts_ledger_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(200))
    parent_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    category: Mapped[str] = mapped_column(String(40))  # asset/liability/common/equity/cost/profit
    direction: Mapped[str] = mapped_column(String(10))  # debit/credit
    account_category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    account_subcategory: Mapped[str | None] = mapped_column(String(40), nullable=True)
    equity_subcategory: Mapped[str | None] = mapped_column(String(40), nullable=True)
    include_in_dividend_base: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active/disabled/archived
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Counterparty(Base):
    __tablename__ = "counterparties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    role: Mapped[str] = mapped_column(String(40), default="other")
    unified_credit_no: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_related_party: Mapped[bool] = mapped_column(Boolean, default=False)
    default_entity_id: Mapped[int | None] = mapped_column(ForeignKey("entities.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class OpeningBalance(Base):
    __tablename__ = "opening_balances"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "period_id",
            "account_code",
            name="uq_opening_balance_org_period_account",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    period_id: Mapped[int] = mapped_column(ForeignKey("accounting_periods.id"))
    account_code: Mapped[str] = mapped_column(String(20), index=True)
    debit_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    credit_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(60))
    source_id: Mapped[int] = mapped_column(Integer)
    chunk_text: Mapped[str] = mapped_column(Text)
    chunk_hash: Mapped[str] = mapped_column(String(80))
    vector_collection: Mapped[str] = mapped_column(String(100))
    vector_point_id: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditRisk(Base):
    __tablename__ = "audit_risks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"))
    risk_type: Mapped[str] = mapped_column(String(100))
    risk_level: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="pending_review")
    confidence: Mapped[float] = mapped_column(Float, default=0.7)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RiskEvidence(Base):
    __tablename__ = "risk_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("audit_risks.id"))
    evidence_type: Mapped[str] = mapped_column(String(80))
    source_id: Mapped[int] = mapped_column(Integer)
    source_text: Mapped[str] = mapped_column(Text)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str] = mapped_column(Text)


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    risk_id: Mapped[int] = mapped_column(ForeignKey("audit_risks.id"))
    action: Mapped[str] = mapped_column(String(80))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditReport(Base):
    __tablename__ = "audit_reports"
    __table_args__ = (
        UniqueConstraint("import_job_id", name="uq_audit_reports_import_job_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"), nullable=False)
    report_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditFinding(Base):
    __tablename__ = "audit_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    finding_uuid: Mapped[str] = mapped_column(String(64))
    finding_type: Mapped[str] = mapped_column(String(80))
    severity: Mapped[str] = mapped_column(String(20))
    business_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    finding_title: Mapped[str] = mapped_column(String(500))
    finding_description: Mapped[str] = mapped_column(Text, default="")
    audit_procedure: Mapped[str] = mapped_column(Text, default="")
    audit_conclusion: Mapped[str] = mapped_column(Text, default="")
    risk_statement: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    related_entries: Mapped[list] = mapped_column(JSON, default=list)
    related_files: Mapped[list] = mapped_column(JSON, default=list)
    finding_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditFindingReviewAction(Base):
    __tablename__ = "audit_finding_review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finding_id: Mapped[int] = mapped_column(ForeignKey("audit_findings.id"))
    action: Mapped[str] = mapped_column(String(80))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 业务循环相关表 ====================

class BusinessCycle(Base):
    __tablename__ = "business_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    cycle_type: Mapped[str] = mapped_column(String(50))  # purchase/sales/expense
    cycle_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40), default="in_progress")  # in_progress/completed/broken
    
    # 时间范围
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 完整性
    completeness: Mapped[float] = mapped_column(Float, default=0.0)
    
    # 风险标记
    risk_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CycleStep(Base):
    __tablename__ = "cycle_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("business_cycles.id"))
    step_order: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(String(50))  # contract/inventory/invoice/payment
    step_name: Mapped[str] = mapped_column(String(100))
    
    # 关联的证据
    evidence_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    evidence_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # 状态
    status: Mapped[str] = mapped_column(String(40), default="pending")  # pending/completed/missing
    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CycleBreak(Base):
    __tablename__ = "cycle_breaks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey("business_cycles.id"))
    break_point: Mapped[int] = mapped_column(Integer)
    break_type: Mapped[str] = mapped_column(String(50))  # evidence_break/date_error/incomplete
    
    severity: Mapped[str] = mapped_column(String(40))  # high/medium/low
    description: Mapped[str] = mapped_column(Text)
    affected_steps: Mapped[list] = mapped_column(JSON, default=list)
    
    # 审计建议
    suggestion: Mapped[str] = mapped_column(Text)
    audit_procedure: Mapped[str] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 内控相关表 ====================

class InternalControl(Base):
    __tablename__ = "internal_controls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    control_code: Mapped[str] = mapped_column(String(50))  # PC-001, SC-001
    control_name: Mapped[str] = mapped_column(String(200))
    control_type: Mapped[str] = mapped_column(String(50))  # preventive/detective/corrective
    control_category: Mapped[str] = mapped_column(String(50))  # authorization/segregation/approval/reconciliation
    
    description: Mapped[str] = mapped_column(Text)
    objective: Mapped[str] = mapped_column(Text)
    
    # 触发条件
    trigger_conditions: Mapped[list] = mapped_column(JSON, default=list)
    
    # 证据要求
    evidence_required: Mapped[list] = mapped_column(JSON, default=list)
    
    # 频率要求
    frequency: Mapped[str] = mapped_column(String(50))  # per_transaction/daily/monthly
    
    # 行业适用性
    industries: Mapped[list] = mapped_column(JSON, default=list)
    company_size: Mapped[str] = mapped_column(String(50))  # large/medium/small
    
    # 风险关联
    risk_category: Mapped[str] = mapped_column(String(100))
    inherent_risk: Mapped[str] = mapped_column(String(40))  # high/medium/low
    control_risk: Mapped[str] = mapped_column(String(40))  # high/medium/low
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ControlTest(Base):
    __tablename__ = "control_tests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    control_id: Mapped[int] = mapped_column(ForeignKey("internal_controls.id"))
    transaction_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # 测试结果
    is_executed: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_found: Mapped[list] = mapped_column(JSON, default=list)
    evidence_missing: Mapped[list] = mapped_column(JSON, default=list)
    execution_quality: Mapped[str] = mapped_column(String(50))  # full/partial/none
    
    # 风险评估
    inherent_risk: Mapped[float] = mapped_column(Float, default=0.5)
    control_risk: Mapped[float] = mapped_column(Float, default=0.5)
    detection_risk: Mapped[float] = mapped_column(Float, default=0.5)
    overall_risk: Mapped[float] = mapped_column(Float, default=0.5)
    
    # 预警
    alert_level: Mapped[str] = mapped_column(String(40))  # critical/high/medium/low
    alert_message: Mapped[str] = mapped_column(Text)
    suggested_procedure: Mapped[str] = mapped_column(Text)
    
    tested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    tester: Mapped[str] = mapped_column(String(100), default="system")


class ControlAlert(Base):
    __tablename__ = "control_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    control_id: Mapped[int] = mapped_column(ForeignKey("internal_controls.id"))
    test_id: Mapped[int | None] = mapped_column(ForeignKey("control_tests.id"), nullable=True)
    
    alert_level: Mapped[str] = mapped_column(String(40))
    business_type: Mapped[str] = mapped_column(String(50))
    affected_transaction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence_involved: Mapped[list] = mapped_column(JSON, default=list)
    
    problem_type: Mapped[str] = mapped_column(String(50))  # missing_evidence/incomplete_evidence/delayed_evidence
    description: Mapped[str] = mapped_column(Text)
    
    # 风险量化
    inherent_risk: Mapped[float] = mapped_column(Float, default=0.5)
    control_risk: Mapped[float] = mapped_column(Float, default=0.5)
    detection_risk: Mapped[float] = mapped_column(Float, default=0.5)
    overall_risk: Mapped[float] = mapped_column(Float, default=0.5)
    
    suggested_procedure: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 文档解析相关表 ====================

class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    
    # 基本信息
    contract_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    contract_type: Mapped[str] = mapped_column(String(50))  # purchase/sales/service/framework
    contract_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # 时间信息
    sign_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 金额信息
    contract_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    tax_rate: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    
    # 履约义务（收入准则）
    performance_obligations: Mapped[dict] = mapped_column(JSON, default=dict)
    transaction_price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    standalone_price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    
    # 分时段履约
    is_over_time: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # input/output
    completion_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    
    # 审计标记
    revenue_recognition_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # point_in_time/over_time
    risk_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # 账套与往来归属
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"), nullable=True)
    execution_status: Mapped[str] = mapped_column(String(30), default="pending")
    
    # 元数据
    source_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.8)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContractParty(Base):
    __tablename__ = "contract_parties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"))
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True)
    
    party_role: Mapped[str] = mapped_column(String(50))  # party_a/party_b/guarantor/witness
    party_type: Mapped[str] = mapped_column(String(50))  # enterprise/individual/government
    party_name: Mapped[str] = mapped_column(String(500))
    party_code: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 统一社会信用代码/身份证号
    party_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    party_contact: Mapped[str | None] = mapped_column(String(100), nullable=True)
    party_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    legal_representative: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContractPerformanceObligation(Base):
    __tablename__ = "contract_performance_obligations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"))
    
    obligation_no: Mapped[str] = mapped_column(String(50))
    obligation_name: Mapped[str] = mapped_column(String(500))
    obligation_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 价格分摊
    standalone_price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    allocated_price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    allocation_method: Mapped[str | None] = mapped_column(String(50), nullable=True)  # market_adjustment/cost_plus/residual
    
    # 履约进度
    is_over_time: Mapped[bool] = mapped_column(Boolean, default=False)
    progress_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completion_percentage: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0)
    
    # 收入确认
    revenue_recognized: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    revenue_pending: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    
    # 审计标记
    risk_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    audit_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContractPaymentTerm(Base):
    __tablename__ = "contract_payment_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"))
    
    term_no: Mapped[int] = mapped_column(Integer)
    term_name: Mapped[str] = mapped_column(String(200))  # 预付款/进度款/尾款
    term_type: Mapped[str] = mapped_column(String(50))  # fixed_amount/percentage/milestone
    
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    milestone: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 实际执行
    actual_paid: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    paid_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    
    # 发票基本信息
    invoice_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invoice_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    invoice_type: Mapped[str] = mapped_column(String(50))  # 增值税专用发票/普通发票/电子发票
    invoice_status: Mapped[str] = mapped_column(String(50), default="normal")  # normal/canceled/red
    
    # 开票信息
    invoice_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 购买方
    buyer_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    buyer_tax_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    buyer_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    buyer_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    buyer_bank: Mapped[str | None] = mapped_column(String(200), nullable=True)
    buyer_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 销售方
    seller_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seller_tax_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    seller_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seller_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    seller_bank: Mapped[str | None] = mapped_column(String(200), nullable=True)
    seller_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 金额信息
    amount_excluding_tax: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_rate: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    
    # 审计关联
    related_contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"), nullable=True)
    related_order_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 账套与往来归属
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"), nullable=True)
    
    # 元数据
    source_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.8)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    
    item_no: Mapped[int] = mapped_column(Integer)
    goods_name: Mapped[str] = mapped_column(String(500))
    specification: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_rate: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    tax_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InventoryDocument(Base):
    __tablename__ = "inventory_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    
    # 基本信息
    document_no: Mapped[str] = mapped_column(String(100))
    document_type: Mapped[str] = mapped_column(String(50))  # inventory_in/inventory_out/material_issue/return
    document_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 仓库信息
    warehouse_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    warehouse_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # 往来方
    counterparty_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # supplier/customer/department
    counterparty_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    counterparty_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # 金额
    total_quantity: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    
    # 审计关联
    related_contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"), nullable=True)
    related_order_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    
    # 账套与往来归属
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"), nullable=True)
    
    # 验收信息
    inspector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    inspect_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    inspect_result: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # 元数据
    source_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.8)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InventoryItem(Base):
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("inventory_documents.id"))
    
    item_no: Mapped[int] = mapped_column(Integer)
    goods_name: Mapped[str] = mapped_column(String(500))
    specification: Mapped[str | None] = mapped_column(String(200), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    unit_price: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    batch_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BankStatement(Base):
    __tablename__ = "bank_statements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    
    # 交易信息
    transaction_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    transaction_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    transaction_time: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transaction_type: Mapped[str] = mapped_column(String(50))  # income/expense
    
    # 本方账户
    account_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    account_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # 对方账户
    counterparty_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    counterparty_account: Mapped[str | None] = mapped_column(String(100), nullable=True)
    counterparty_bank: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # 金额
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    balance: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    
    # 摘要
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # 审计关联
    related_contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"), nullable=True)
    related_invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), nullable=True)
    
    # 账套与往来归属
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"), nullable=True)
    
    # 元数据
    source_file_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.8)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 企业信息相关表 ====================

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 基本信息
    company_name: Mapped[str] = mapped_column(String(500))
    unified_social_credit_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 有限责任公司/股份有限公司等
    
    # 税务信息
    taxpayer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 一般纳税人/小规模纳税人
    tax_registration_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tax_authority: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # 注册信息
    registered_capital: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    paid_in_capital: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    establishment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    business_term: Mapped[str | None] = mapped_column(String(100), nullable=True)
    registration_status: Mapped[str] = mapped_column(String(50), default="active")  # active/revoked/canceled
    
    # 经营信息
    business_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    registered_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    actual_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # 联系信息
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # 行业信息
    industry_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    industry_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    
    # 元数据
    data_source: Mapped[str] = mapped_column(String(50), default="manual")
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CompanyPersonnel(Base):
    __tablename__ = "company_personnel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    
    # 人员信息
    person_name: Mapped[str] = mapped_column(String(100))
    person_type: Mapped[str] = mapped_column(String(50))  # legal_representative/shareholder/financial_manager/supervisor/director/executive
    id_card_no: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 脱敏
    
    # 职务信息
    position: Mapped[str | None] = mapped_column(String(100), nullable=True)
    appointment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    resignation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 股东信息
    shareholding_ratio: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    subscribed_capital: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    paid_capital: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    
    # 联系信息
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RelatedPartyRelation(Base):
    __tablename__ = "related_party_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # 关联双方
    company_a_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    company_b_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    
    # 关联关系
    relation_type: Mapped[str] = mapped_column(String(100))  # parent_subsidiary/brother/same_control/key_management_family
    relation_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 关联人（如果是人员关联）
    person_a_id: Mapped[int | None] = mapped_column(ForeignKey("company_personnel.id"), nullable=True)
    person_b_id: Mapped[int | None] = mapped_column(ForeignKey("company_personnel.id"), nullable=True)
    person_relation: Mapped[str | None] = mapped_column(String(100), nullable=True)  # spouse/parent/child/sibling
    
    # 有效性
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    
    # 发现来源
    discovery_source: Mapped[str] = mapped_column(String(50), default="system")  # system/manual
    confidence_score: Mapped[float] = mapped_column(Float, default=0.9)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 字段别名映射表 ====================

class FieldAliasMapping(Base):
    __tablename__ = "field_alias_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    document_type: Mapped[str] = mapped_column(String(50))  # contract/invoice/inventory/bank_statement
    field_name: Mapped[str] = mapped_column(String(100))  # 标准字段名
    alias: Mapped[str] = mapped_column(String(200))  # 别名
    alias_type: Mapped[str] = mapped_column(String(50))  # chinese/english/abbreviation/industry_term
    
    # 置信度
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ==================== 文档标签表 ====================

class DocumentTag(Base):
    __tablename__ = "document_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    document_id: Mapped[int] = mapped_column(Integer)  # 关联的源文件ID
    document_type: Mapped[str] = mapped_column(String(50))
    
    tag: Mapped[str] = mapped_column(String(500))
    tag_type: Mapped[str] = mapped_column(String(50))  # business/risk/relation/time/amount/status
    
    # 向量存储信息
    vector_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    vector_stored: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # 元数据
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    source: Mapped[str] = mapped_column(String(50), default="rule")  # rule/ai/manual
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("ledgers.id"), index=True)
    bank_name: Mapped[str] = mapped_column(String(200))
    account_no: Mapped[str] = mapped_column(String(100))
    account_name: Mapped[str] = mapped_column(String(200))
    coa_account_code: Mapped[str] = mapped_column(String(40), default="1002")
    opening_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    current_balance: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BankTransaction(Base):
    __tablename__ = "bank_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"), index=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("ledgers.id"), index=True)
    transaction_date: Mapped[date] = mapped_column(Date)
    direction: Mapped[str] = mapped_column(String(10))  # in / out
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reconciliation_status: Mapped[str] = mapped_column(String(20), default="unmatched")
    matched_entry_id: Mapped[int | None] = mapped_column(ForeignKey("accounting_entries.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bank_account: Mapped["BankAccount"] = relationship()


class BankReconciliation(Base):
    __tablename__ = "bank_reconciliations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("ledgers.id"), index=True)
    bank_account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"), index=True)
    period_end: Mapped[date] = mapped_column(Date)
    statement_balance: Mapped[float] = mapped_column(Numeric(18, 2))
    book_balance: Mapped[float] = mapped_column(Numeric(18, 2))
    adjusted_statement_balance: Mapped[float] = mapped_column(Numeric(18, 2))
    adjusted_book_balance: Mapped[float] = mapped_column(Numeric(18, 2))
    difference: Mapped[float] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    bank_account: Mapped["BankAccount"] = relationship()
    items: Mapped[list["BankReconciliationItem"]] = relationship(
        back_populates="reconciliation",
        cascade="all, delete-orphan",
    )


class BankReconciliationItem(Base):
    __tablename__ = "bank_reconciliation_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reconciliation_id: Mapped[int] = mapped_column(ForeignKey("bank_reconciliations.id"), index=True)
    item_type: Mapped[str] = mapped_column(String(40))
    amount: Mapped[float] = mapped_column(Numeric(18, 2))
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    bank_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("bank_transactions.id"), nullable=True)
    entry_id: Mapped[int | None] = mapped_column(ForeignKey("accounting_entries.id"), nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    reconciliation: Mapped["BankReconciliation"] = relationship(back_populates="items")


class CounterpartyConfirmation(Base):
    __tablename__ = "counterparty_confirmations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("ledgers.id"), index=True)
    counterparty_id: Mapped[int | None] = mapped_column(ForeignKey("counterparties.id"), nullable=True, index=True)
    counterparty_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    balance_type: Mapped[str] = mapped_column(String(40))
    book_balance: Mapped[float] = mapped_column(Numeric(18, 2))
    confirmation_amount: Mapped[float] = mapped_column(Numeric(18, 2))
    reply_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    difference: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_file_id: Mapped[int | None] = mapped_column(ForeignKey("source_files.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    counterparty: Mapped["Counterparty | None"] = relationship()


class WorkpaperIndex(Base):
    __tablename__ = "workpaper_indexes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("ledgers.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("workpaper_indexes.id"), nullable=True, index=True)
    index_no: Mapped[str] = mapped_column(String(50), index=True)
    title: Mapped[str] = mapped_column(String(500))
    audit_area: Mapped[str | None] = mapped_column(String(100), nullable=True)
    archive_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_module_key: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    parent: Mapped["WorkpaperIndex | None"] = relationship(remote_side="WorkpaperIndex.id")
    versions: Mapped[list["WorkpaperVersion"]] = relationship(
        back_populates="workpaper_index",
        cascade="all, delete-orphan",
    )


class WorkpaperVersion(Base):
    __tablename__ = "workpaper_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workpaper_index_id: Mapped[int] = mapped_column(ForeignKey("workpaper_indexes.id"), index=True)
    source_file_id: Mapped[int] = mapped_column(ForeignKey("source_files.id"), index=True)
    version_no: Mapped[str] = mapped_column(String(20), default="1.0")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    prepared_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("workpaper_versions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    workpaper_index: Mapped["WorkpaperIndex"] = relationship(back_populates="versions")
    source_file: Mapped["SourceFile"] = relationship()
    supersedes: Mapped["WorkpaperVersion | None"] = relationship(remote_side="WorkpaperVersion.id")


class ProjectWorkflowConfig(Base):
    __tablename__ = "project_workflow_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), unique=True, index=True)
    granularity: Mapped[str] = mapped_column(String(20), default="standard")
    enabled_procedures: Mapped[dict] = mapped_column(JSON, default=list)
    auto_link_workpaper: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditProcedureRun(Base):
    __tablename__ = "audit_procedure_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    ledger_id: Mapped[int] = mapped_column(ForeignKey("ledgers.id"), index=True)
    procedure_key: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    title: Mapped[str] = mapped_column(String(300))
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    workpaper_index_id: Mapped[int | None] = mapped_column(ForeignKey("workpaper_indexes.id"), nullable=True)
    source_file_id: Mapped[int | None] = mapped_column(ForeignKey("source_files.id"), nullable=True)
    recommended_by: Mapped[str] = mapped_column(String(30), default="manual")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    concluded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
