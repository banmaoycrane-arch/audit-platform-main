"""审计协作工作流相关 Pydantic schema。

模块功能：定义审计任务、工作分支、复核请求、评论等数据结构
业务场景：审计项目协作中的任务分配、底稿编制、多级复核流程
政策依据：中国注册会计师审计准则第1121号（项目质量控制）
输入数据：前端提交的任务/分支/复核请求数据
输出结果：标准化的请求/响应数据结构
创建日期：2026-06-26
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


AuditTaskStatus = Literal[
    "open", "todo", "in_progress", "review", "closed", "rejected"
]
AuditTaskPriority = Literal["high", "normal", "low"]
AuditTaskType = Literal[
    "risk_assessment", "control_test", "substantive", "review", "other"
]
AuditBranchStatus = Literal["active", "review_pending", "merged", "archived", "abandoned"]
AuditReviewStatus = Literal[
    "draft", "review", "changes_requested", "approved", "merged", "closed"
]
AuditReviewActionType = Literal["approve", "request_changes", "comment", "rework"]
AuditCommentTargetType = Literal["task", "branch", "review_request", "workpaper_version"]


class AuditTaskCreate(BaseModel):
    """
    审计任务创建请求

    功能描述：创建新的审计任务
    业务逻辑：从审计风险点或审计程序出发，创建可分配的任务
    会计口径：任务类型对应审计程序分类，必须绑定账簿以确保数据边界

    Args:
        project_id: 所属项目ID
        ledger_id: 关联账簿ID（必填，确保审计测试有明确的数据边界）
        title: 任务标题
        description: 任务描述
        task_type: 任务类型
        audit_area: 审计领域
        priority: 优先级
        assignee_id: 指派的执行人ID
        due_date: 截止日期
        related_finding_id: 关联的审计发现ID
        related_procedure_key: 关联的审计程序键
    """
    project_id: int
    ledger_id: int
    title: str
    description: str | None = None
    task_type: AuditTaskType = "substantive"
    audit_area: str | None = None
    priority: AuditTaskPriority = "normal"
    assignee_id: int | None = None
    due_date: date | None = None
    related_finding_id: int | None = None
    related_procedure_key: str | None = None


class AuditTaskUpdate(BaseModel):
    """审计任务更新请求"""
    title: str | None = None
    description: str | None = None
    task_type: AuditTaskType | None = None
    audit_area: str | None = None
    priority: AuditTaskPriority | None = None
    status: AuditTaskStatus | None = None
    assignee_id: int | None = None
    due_date: date | None = None


class AuditTaskAssign(BaseModel):
    """任务分配请求"""
    assignee_id: int


class AuditTaskStatusUpdate(BaseModel):
    """任务状态更新请求"""
    status: AuditTaskStatus
    comment: str | None = None


class AuditTaskRead(BaseModel):
    """审计任务读取模型"""
    id: int
    project_id: int
    ledger_id: int | None = None
    task_no: str
    title: str
    description: str | None = None
    task_type: str
    audit_area: str | None = None
    status: str
    priority: str
    created_by: int
    assignee_id: int | None = None
    reviewer_ids: list[int] | None = Field(default=None)
    related_finding_id: int | None = None
    related_procedure_key: str | None = None
    parent_task_id: int | None = None
    labels: list[str] | None = Field(default=None)
    due_date: date | None = None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuditTaskListResponse(BaseModel):
    """任务列表响应"""
    items: list[AuditTaskRead]
    total: int
    page: int
    page_size: int


class AuditWorkBranchCreate(BaseModel):
    """
    工作分支创建请求

    功能描述：为审计任务创建工作分支
    业务逻辑：类似 Git branch，隔离不同审计人员的工作
    会计口径：每个分支对应一套独立的底稿版本
    """
    task_id: int
    project_id: int
    ledger_id: int | None = None
    branch_name: str
    base_branch: str = "main"
    assignee_id: int | None = None
    workpaper_index_id: int | None = None
    procedure_run_id: int | None = None


class AuditWorkBranchUpdate(BaseModel):
    """工作分支更新请求"""
    status: AuditBranchStatus | None = None
    latest_version_id: int | None = None


class AuditWorkBranchRead(BaseModel):
    """工作分支读取模型"""
    id: int
    project_id: int
    ledger_id: int | None = None
    task_id: int
    branch_name: str
    base_branch: str | None = None
    status: str
    created_by: int
    assignee_id: int | None = None
    workpaper_index_id: int | None = None
    procedure_run_id: int | None = None
    latest_version_id: int | None = None
    created_at: datetime
    updated_at: datetime
    merged_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuditReviewRequestCreate(BaseModel):
    """
    复核请求创建请求

    功能描述：提交工作底稿进入复核流程
    业务逻辑：对应审计准则中的多级复核制度
    会计口径：一级复核（项目经理）、二级复核（部门经理）、三级复核（合伙人）
    """
    task_id: int
    branch_id: int
    project_id: int
    ledger_id: int | None = None
    title: str
    description: str | None = None
    target_branch: str = "main"
    reviewer_level_1_id: int | None = None
    reviewer_level_2_id: int | None = None
    reviewer_level_3_id: int | None = None
    submitted_version_id: int | None = None


class AuditReviewSubmit(BaseModel):
    """提交复核请求（从 draft 到 review）"""
    reviewer_level_1_id: int | None = None


class AuditReviewActionCreate(BaseModel):
    """
    复核动作请求

    功能描述：复核人执行复核操作
    业务逻辑：通过（进入下一级）或 退回修改（回到draft）
    会计口径：每级复核都需签署意见，留下审计轨迹
    """
    action: AuditReviewActionType
    comment: str | None = None
    review_level: int = 1


class AuditReviewRequestRead(BaseModel):
    """复核请求读取模型"""
    id: int
    project_id: int
    ledger_id: int | None = None
    task_id: int
    branch_id: int
    pr_no: str
    title: str
    description: str | None = None
    target_branch: str
    status: str
    current_review_level: int
    created_by: int
    reviewer_level_1_id: int | None = None
    reviewer_level_2_id: int | None = None
    reviewer_level_3_id: int | None = None
    submitted_version_id: int | None = None
    approved_version_id: int | None = None
    merged_version_id: int | None = None
    merged_by: int | None = None
    created_at: datetime
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    merged_at: datetime | None = None
    closed_at: datetime | None = None

    model_config = {"from_attributes": True}


class AuditReviewActionRead(BaseModel):
    """复核动作读取模型"""
    id: int
    review_request_id: int
    review_level: int
    action: str
    comment: str | None = None
    reviewer_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditCommentCreate(BaseModel):
    """
    评论创建请求

    功能描述：在任务、分支、复核请求上添加评论
    业务逻辑：审计工作中的沟通留痕
    """
    target_type: AuditCommentTargetType
    target_id: int
    content: str
    mention_user_ids: list[int] | None = None
    marker_type: str | None = None
    sheet_name: str | None = None
    cell_ref: str | None = None
    range_ref: str | None = None
    severity: str | None = None


class AuditCommentRead(BaseModel):
    """评论读取模型"""
    id: int
    target_type: str
    target_id: int
    content: str
    mention_user_ids: list[int] | None = Field(default=None)
    marker_type: str | None = None
    sheet_name: str | None = None
    cell_ref: str | None = None
    range_ref: str | None = None
    severity: str | None = None
    resolved_at: datetime | None = None
    resolved_by: int | None = None
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AuditDashboardStats(BaseModel):
    """工作台统计数据"""
    todo_tasks_count: int = 0
    in_progress_tasks_count: int = 0
    review_tasks_count: int = 0
    pending_my_review_count: int = 0
    submitted_by_me_count: int = 0
    closed_today_count: int = 0
