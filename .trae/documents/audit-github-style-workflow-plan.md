# 审计模块协作机制规划 — 类 GitHub 工作流

> 参考 GitHub 的 Issue / Branch / Pull Request / Review / Merge 工作机制，设计适用于审计/会计专业分工的协作体系。
>
> 本规划严格遵循 `core-business-concepts-boundary.md` 中的核心概念边界，不重新定义 Team / Ledger / Project 等基础概念。

---

## 快速导航

| 章节 | 内容 | 适合人群 |
|---|---|---|
| 〇、需求域与边界 | In Scope / Out of Scope | 项目决策者 |
| 一、现状分析 | 已完成什么、缺什么 | 技术实现者 |
| 二、概念对齐 | GitHub ↔ 审计系统映射关系 | 所有人 |
| 六、实施路线图 | 分阶段执行计划 | 项目决策者 + 技术实现者 |
| 七、财务/审计视角 | 符合审计准则的设计要点 | 专业会计师 |

---

## 关键决策摘要

| 决策项 | 结论 | 理由 |
|---|---|---|
| **Project 对应什么？** | GitHub Repository | Project 是审计工作协作的基本单元，有自己的任务、分支、复核流程 |
| **需求域归属？** | D06 审计证据与审计流程 | 协作机制是审计流程的一部分 |
| **MVP 做几级复核？** | 单级复核 | 先跑通主流程，多级后续扩展 |
| **数据模型状态？** | ✅ 全部已定义（L1） | 6 个新实体已在 models.py 中定义 |
| **当前进度？** | L1 → L2 | 模型已建好，服务层待实现 |
| **推荐实施顺序？** | 阶段一 → 阶段二 → 阶段四 → 阶段三 | 先主流程，再质量控制，再整合，最后项目管理 |

---

## 〇、需求域与边界

### 0.1 需求域归属

| 项 | 值 |
|---|---|
| **Domain** | D06 审计证据与审计流程 |
| **Status** | active-increment（增量规格） |
| **Owner Spec** | audit-day-book-import（D06 主规格） |
| **Depends On** | D02 团队/账套/项目上下文、D09 AI 草稿与标签（可选） |
| **Acceptance Level** | L6（真实业务样例验收通过） |

### 0.2 In Scope（本次做什么）

**核心协作机制：**
- 审计任务（AuditTask）的创建、分配、状态流转
- 工作分支（AuditWorkBranch）的创建、关联底稿版本
- 复核请求（AuditReviewRequest）的提交、单级复核、合并归档
- 审计评论（AuditComment）的简单增删查
- 我的工作台（待办任务、待我复核、我提交的）
- 与现有 AuditFinding、AuditProcedureRun、WorkpaperVersion 的关联

### 0.3 Out of Scope（本次明确不做什么）

- **三级复核**：MVP 只做单级复核，多级留接口后续扩展
- **子任务分解**：任务树、父子任务结构
- **里程碑管理**：AuditMilestone 的完整功能
- **版本对比 UI**：底稿版本 diff 可视化
- **电子签名**：签名认证、CA 证书等
- **高级统计与看板**：甘特图、燃尽图、人员负荷
- **任务标签（Label）管理**：标签的增删改
- **@提及用户通知**：通知推送、消息中心
- **审计报告自动引用**：报告生成集成
- **与银行对账、函证等模块的深度联动**：后续阶段做

---

## 一、现状分析

### 1.1 已完成（L1 - 数据模型已定义）

**数据模型全部已定义**，位于 `backend/app/db/models.py` 第 1786-1964 行：

| 实体 | 表名 | 对应 GitHub | 状态 |
|---|---|---|---|
| `AuditTask` | `audit_tasks` | Issue | ✅ 模型已定义 |
| `AuditWorkBranch` | `audit_work_branches` | Branch | ✅ 模型已定义 |
| `AuditReviewRequest` | `audit_review_requests` | Pull Request | ✅ 模型已定义 |
| `AuditReviewAction` | `audit_review_actions` | Review | ✅ 模型已定义 |
| `AuditComment` | `audit_comments` | Comment | ✅ 模型已定义 |
| `AuditMilestone` | `audit_milestones` | Release/Tag | ✅ 模型已定义 |

### 1.2 现有可复用资产

| 现有实体/服务 | 用途 | 整合方式 |
|---|---|---|
| `AuditFinding` | 审计发现 | 通过 `related_finding_id` 与 AuditTask 关联 |
| `AuditProcedureRun` | 审计程序运行 | 通过 `procedure_run_id` 与 AuditWorkBranch 关联 |
| `WorkpaperIndex` | 工作底稿索引 | 通过 `workpaper_index_id` 与分支关联 |
| `WorkpaperVersion` | 底稿版本 | 通过 `latest_version_id` 关联分支 |
| `ProjectWorkflowConfig` | 项目工作流配置 | 扩展复核级别配置 |
| `audit_workflow_service.py` | 审计程序工作流 | 新增任务/分支/复核服务 |
| `AuditWorkflowPage.tsx` | 审计工作流页面 | 扩展任务和复核入口 |

### 1.3 待实现（从 L2 到 L6）

| 层级 | 内容 | 状态 |
|---|---|---|
| L2 | 服务层实现（audit_task_service、audit_branch_service、audit_review_service） | ❌ 未开始 |
| L3 | API 接口暴露 | ❌ 未开始 |
| L4 | 前端页面接入 | ❌ 未开始 |
| L5 | 自动化测试 | ❌ 未开始 |
| L6 | 真实业务样例验收 | ❌ 未开始 |

---

## 二、概念对齐：GitHub 与现有系统的映射

### 0.1 核心概念边界确认（来自 core-business-concepts-boundary.md）

| 概念 | 中文口径 | 主用途 | 不应承担的职责 |
|------|---------|--------|---------------|
| **Team** | 团队 / 事务所 / 企业组织 | 协作与权限范围，管理成员和账套 | 不作为正式核算数据边界 |
| **Ledger** | 会计账套 | 正式核算数据边界，凭证、期间、报表、审计范围的主过滤口径 | 不代表项目、不代表所有法律主体 |
| **Project** | 项目 | 审计、记账、税务等工作任务边界 | 不直接替代账套、不作为凭证主归属 |
| **Accounting Entity** | 会计主体 / 报表主体 | 报表、合并、内部核算主体判断 | 不等于 Team，不一定等于 Ledger |

### 0.2 GitHub 层级与本系统层级的映射

GitHub 组织架构：
```
Organization（组织）
  └─ Team（团队）
       └─ Repository（仓库）← 代码协作的基本单元
            ├─ Issues（任务）
            ├─ Branches（分支）
            ├─ Pull Requests（合并请求）
            ├─ Reviews（评审）
            └─ Releases / Tags（版本/里程碑）
```

本系统对应架构：
```
Team（团队/事务所）← 协作与权限范围
  └─ Ledger（账套/客户）← 财务数据边界
       └─ Project（审计项目）← 工作任务边界 ≈ GitHub Repository
            ├─ AuditTask（审计任务）← GitHub Issue
            ├─ AuditWorkBranch（工作分支）← GitHub Branch
            ├─ AuditReviewRequest（复核请求）← GitHub Pull Request
            ├─ AuditReviewAction（复核动作）← GitHub Review
            ├─ AuditComment（评论）← GitHub Comment
            └─ AuditMilestone（里程碑）← GitHub Release / Milestone
```

### 0.3 关键结论：Project 对应 GitHub Repository

**答案：是的，Project 对应 GitHub 的 Repository。**

理由：

| GitHub Repository 的特征 | 本系统 Project 的对应特征 |
|-------------------------|-------------------------|
| 是代码协作的基本单元 | 是审计工作协作的基本单元 |
| 有自己的 Issues、Branches、PRs | 有自己的 AuditTask、WorkBranch、ReviewRequest |
| 一个 Organization 下有多个 Repository | 一个 Team 下有多个 Project |
| Repository 可以关联多个代码库（monorepo） | Project 可以关联多个 Ledger（集团审计） |
| 有 Releases / Tags 版本管理 | 有 Milestones 阶段里程碑 |

**但需注意边界（来自核心概念文档）：**

> "Project 是工作任务边界，Ledger 是财务数据边界。一个项目可以关联多个账套。"

因此：
- **Project** 是审计工作流的载体（对应 Repository）
- **Ledger** 是财务数据的载体（对应数据源）
- 两者是多对多关系：一个 Project 可关联多个 Ledger，一个 Ledger 可被多个 Project 引用

### 0.4 与台账审计工作流的关系（三分离原则）

参考 `register-audit-workflow-plan.md`：

| 层级 | 对应本规划 | 说明 |
|------|-----------|------|
| 业务台账层（Register） | 审计证据来源 | 合同、银行流水、发票等原始资料 |
| 会计核算层（Ledger） | 审计对象 | 凭证、科目、报表 |
| 审计工作层（Audit / Project） | 本规划的协作机制 | 任务、分支、复核、归档 |

本规划聚焦于**审计工作层（Project 维度）**的协作机制，向上承接业务台账和会计核算的数据源，向下输出审计结论和报告。

---

## 一、设计理念：为什么用 GitHub 工作流思想

### 1.1 GitHub 工作流的核心机制

| GitHub 概念 | 核心价值 | 审计/会计对应场景 |
|------------|---------|------------------|
| **Issue（任务）** | 问题追踪、任务分解、讨论留痕 | 审计发现、风险点、待办事项 |
| **Branch（分支）** | 并行开发、互不干扰、隔离变更 | 审计程序执行分支、底稿版本分支 |
| **Pull Request（合并请求）** | 代码评审、变更可见、审批前置 | 工作底稿复核、审计结论审批 |
| **Review（评审）** | 同行评审、多级把关、质量控制 | 一级复核、二级复核、项目质量复核 |
| **Merge（合并）** | 变更合入主分支、版本沉淀 | 审计结论归档、底稿定稿 |
| **Tag / Release（标签）** | 版本快照、里程碑、可追溯 | 审计阶段节点、报告出具版本 |

### 1.2 审计/会计场景的特殊性

| 维度 | 软件开发（GitHub） | 审计/会计（本系统） |
|------|-------------------|-------------------|
| **协作对象** | 代码文件 | 审计工作底稿、审计发现、测试结论 |
| **质量要求** | 功能正确、无 bug | 审计准则合规、证据充分、结论恰当 |
| **审批层级** | 1-2 级评审 | 一级复核（项目经理）、二级复核（部门经理）、三级复核（合伙人） |
| **追溯要求** | commit 历史 | 完整审计轨迹、签名盖章、底稿归档 |
| **不可逆性** | 可回退 | 审计结论需谨慎，修改留痕 |

### 1.3 设计原则

1. **任务驱动**：所有工作从「审计任务」（Issue）出发，不做无来源的工作
2. **分支隔离**：每个审计程序/底稿在独立「工作分支」中执行，互不干扰
3. **评审前置**：所有结论/底稿必须经过复核（Review）才能「合并」归档
4. **全程留痕**：每一步操作都有审计轨迹，符合审计准则要求
5. **状态明确**：状态机清晰，当前阶段一目了然

---

## 二、数据模型设计

### 2.1 实体归属原则（遵循核心概念边界）

所有审计工作流实体**以 `project_id` 为主边界**（因为 Project = Repository，是协作单元），`ledger_id` 作为可选的数据范围标记：

| 实体 | `project_id` | `ledger_id` | 说明 |
|------|-------------|------------|------|
| AuditTask | 必填 | 可选 | 一个任务可能跨多个账套（如合并报表审计） |
| AuditWorkBranch | 必填 | 可选 | 分支主要归属任务，账套是数据范围 |
| AuditReviewRequest | 必填 | 可选 | 复核请求归属项目，账套是关联数据 |
| AuditReviewAction | 必填（通过 review_request） | 可选 | 随复核请求继承 |
| AuditComment | - | - | 通过 target_type/target_id 关联 |
| AuditMilestone | 必填 | 可选 | 里程碑归属项目 |

**为什么 ledger_id 是可选的？**
- 核心概念文档：「一个项目可以关联多个账套」
- 例如：集团审计项目下，一个风险评估任务可能涉及多个子公司账套
- 具体审计程序执行时，再明确到单个 ledger_id

---

### 2.2 新增实体

#### 2.2.1 AuditTask（审计任务 — 对应 GitHub Issue）

> 扩展现有 AuditFinding，增加任务管理属性

```python
class AuditTask(Base):
    """审计任务 — 对应 GitHub Issue"""
    __tablename__ = "audit_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)

    # 任务基本信息
    task_no: Mapped[str] = mapped_column(String(50), index=True)       # 任务编号（如 A-001）
    title: Mapped[str] = mapped_column(String(500))                    # 任务标题
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # 任务描述
    task_type: Mapped[str] = mapped_column(String(50))                 # 任务类型：risk_assessment / control_test / substantive / review
    audit_area: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 审计领域

    # 状态 — 对应 Issue 状态
    status: Mapped[str] = mapped_column(String(30), default="open")    # open / in_progress / review / closed / rejected
    priority: Mapped[str] = mapped_column(String(20), default="normal")  # high / normal / low

    # 人员
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))    # 创建人
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # 执行人
    reviewer_ids: Mapped[list | None] = mapped_column(JSON, default=list)  # 复核人列表

    # 关联
    related_finding_id: Mapped[int | None] = mapped_column(ForeignKey("audit_findings.id"), nullable=True)  # 关联审计发现
    related_procedure_key: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 关联审计程序
    parent_task_id: Mapped[int | None] = mapped_column(ForeignKey("audit_tasks.id"), nullable=True)  # 父任务（支持子任务分解）

    # 时间
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # 截止日期
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 标签（对应 GitHub Label）
    labels: Mapped[list | None] = mapped_column(JSON, default=list)  # 标签列表
```

#### 2.2.2 AuditWorkBranch（审计工作分支 — 对应 GitHub Branch）

> 扩展现有 AuditProcedureRun，增加分支管理属性

```python
class AuditWorkBranch(Base):
    """审计工作分支 — 对应 GitHub Branch"""
    __tablename__ = "audit_work_branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("audit_tasks.id"), index=True)  # 关联任务

    # 分支信息
    branch_name: Mapped[str] = mapped_column(String(200))              # 分支名称（如 task-A001-substantive-test）
    base_branch: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 基线分支（如 main）
    status: Mapped[str] = mapped_column(String(30), default="active")   # active / merged / archived / abandoned

    # 人员
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))    # 创建人
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # 当前负责人

    # 关联的工作底稿和程序
    workpaper_index_id: Mapped[int | None] = mapped_column(ForeignKey("workpaper_indexes.id"), nullable=True)
    procedure_run_id: Mapped[int | None] = mapped_column(ForeignKey("audit_procedure_runs.id"), nullable=True)

    # 版本快照
    latest_version_id: Mapped[int | None] = mapped_column(ForeignKey("workpaper_versions.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    merged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

#### 2.2.3 AuditReviewRequest（复核请求 — 对应 GitHub Pull Request）

```python
class AuditReviewRequest(Base):
    """复核请求 — 对应 GitHub Pull Request"""
    __tablename__ = "audit_review_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("audit_tasks.id"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("audit_work_branches.id"), index=True)

    # PR 基本信息
    pr_no: Mapped[str] = mapped_column(String(50), index=True)         # 复核请求编号（如 PR-001）
    title: Mapped[str] = mapped_column(String(500))                    # 请求标题
    description: Mapped[str | None] = mapped_column(Text, nullable=True)  # 请求描述/编制说明

    # 目标分支（要合并到哪里）
    target_branch: Mapped[str] = mapped_column(String(200), default="main")  # 目标分支（归档主分支）

    # 状态
    status: Mapped[str] = mapped_column(String(30), default="draft")   # draft / review / changes_requested / approved / merged / closed
    current_review_level: Mapped[int] = mapped_column(Integer, default=1)  # 当前复核级别：1/2/3

    # 人员
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))    # 提交人
    reviewer_level_1_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # 一级复核人
    reviewer_level_2_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # 二级复核人
    reviewer_level_3_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # 三级复核人
    merged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)  # 合并归档人

    # 时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 提交复核时间
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)   # 最终通过时间
    merged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)     # 合并归档时间
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)     # 关闭时间
```

#### 2.2.4 AuditReviewAction（复核动作 — 对应 GitHub Review）

> 扩展现有 AuditFindingReviewAction，支持多级复核

```python
class AuditReviewAction(Base):
    """复核动作 — 对应 GitHub Review"""
    __tablename__ = "audit_review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_request_id: Mapped[int] = mapped_column(ForeignKey("audit_review_requests.id"), index=True)

    # 复核级别
    review_level: Mapped[int] = mapped_column(Integer)                 # 1/2/3 级复核

    # 复核结果
    action: Mapped[str] = mapped_column(String(40))                    # approve / request_changes / comment / rework
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)   # 复核意见

    # 复核人
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # 签名（电子签名哈希）
    signature_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

#### 2.2.5 AuditComment（审计评论 — 对应 GitHub Comment）

```python
class AuditComment(Base):
    """审计评论 — 对应 GitHub Comment"""
    __tablename__ = "audit_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # 评论对象类型（任务 / 分支 / 复核请求 / 底稿版本）
    target_type: Mapped[str] = mapped_column(String(50), index=True)   # task / branch / review_request / workpaper_version
    target_id: Mapped[int] = mapped_column(Integer, index=True)

    # 评论内容
    content: Mapped[str] = mapped_column(Text)
    mention_user_ids: Mapped[list | None] = mapped_column(JSON, default=list)  # @提及的用户

    # 评论人
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

#### 2.2.6 AuditMilestone（审计里程碑 — 对应 GitHub Milestone/Release）

```python
class AuditMilestone(Base):
    """审计里程碑 — 对应 GitHub Tag/Release"""
    __tablename__ = "audit_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    ledger_id: Mapped[int | None] = mapped_column(ForeignKey("ledgers.id"), nullable=True, index=True)

    # 里程碑信息
    milestone_no: Mapped[str] = mapped_column(String(50), index=True)   # 里程碑编号（如 M1, M2）
    title: Mapped[str] = mapped_column(String(200))                     # 里程碑名称
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    milestone_type: Mapped[str] = mapped_column(String(50))             # risk_assessment / internal_control / substantive / report / final

    # 状态
    status: Mapped[str] = mapped_column(String(30), default="planned")  # planned / in_progress / completed / archived

    # 人员
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    # 快照信息（归档时的版本快照）
    snapshot_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

### 2.3 现有实体增强

| 现有实体 | 增强内容 |
|---------|---------|
| AuditFinding | 增加 `task_id` 外键关联到 AuditTask |
| AuditProcedureRun | 增加 `branch_id` 外键关联到 AuditWorkBranch |
| WorkpaperVersion | 增加 `branch_id`、`review_request_id` 字段 |
| ProjectWorkflowConfig | 增加多级复核配置（几级复核、各级复核人角色） |

---

## 三、工作流全景图与核心状态机

### 3.1 工作流全景图

```
审计任务（Issue）
    │
    ├── 分配任务 → 指定执行人（Assignee）
    │
    ▼
创建工作分支（Branch）
    │
    ├── 执行审计程序
    ├── 编制工作底稿（多次版本/commit）
    ├── 形成初步结论
    │
    ▼
提交复核请求（PR）
    │
    ├── 一级复核（项目经理）
    │   ├── 通过 → 进入二级复核
    │   └── 退回修改 → 回到工作分支
    │
    ├── 二级复核（部门经理）
    │   ├── 通过 → 进入三级复核
    │   └── 退回修改 → 回到工作分支
    │
    ├── 三级复核（合伙人/项目质量复核）
    │   ├── 通过 → 同意合并
    │   └── 退回修改 → 回到工作分支
    │
    ▼
合并归档（Merge）
    │
    ├── 底稿版本标记为「已定稿」
    ├── 审计发现状态更新
    ├── 生成审计轨迹记录
    │
    ▼
阶段节点（Milestone/Tag）
    └── 风险评估阶段、内控测试阶段、实质性程序阶段、报告阶段
```

### 3.2 审计任务（AuditTask）状态机

```
           创建任务              分配/认领              提交复核
open ──────────────► todo ──────────────► in_progress ──────────────► review
  │                                                                    │
  │ 关闭任务                                                           │ 退回修改
  └────────────────────────────────────────────────────────────────────┘
                                                                    │
                              审批通过                               │
                ◄───────────────────────────────────────────────────┘
                │
                ▼
              closed（已归档）
```

| 状态 | 含义 | 触发动作 |
|------|------|---------|
| `open` | 待认领/待分配 | 任务创建后默认状态 |
| `todo` | 待开始 | 已分配执行人 |
| `in_progress` | 进行中 | 执行人开始工作，创建工作分支 |
| `review` | 复核中 | 提交复核请求 |
| `closed` | 已完成 | 复核通过并合并归档 |
| `rejected` | 已拒绝/作废 | 任务被取消或拒绝 |

### 3.3 复核请求（AuditReviewRequest）状态机

```
         提交                   一级通过                  二级通过
draft ─────────► review_l1 ──────────────► review_l2 ──────────────► review_l3
  ▲                  │                       │                       │
  │                  │ 退回修改               │ 退回修改               │ 退回修改
  │                  ▼                       ▼                       ▼
  │             changes_requested        changes_requested        changes_requested
  │                  │                       │                       │
  │                  └──── 修改后重新提交 ────┴───────────────────────┘
  │
  │                                                       三级通过
  │                                              ┌───────────────────────┘
  │                                              ▼
  └─────────── 合并归档 ───────────────────── merged
                     │
                     ▼
                  closed
```

**复核规则：**
- 每级复核只能：通过（进入下一级）或 退回修改（回到 draft）
- 三级全部通过后才能合并归档
- 退回修改后需重新从第一级开始复核（或保留已通过级别，可配置）

### 3.4 工作分支（AuditWorkBranch）状态机

```
        创建分支           提交复核             合并归档
active ──────────► review_pending ──────────► merged
  │                    │                       │
  │                    │ 撤回                  │
  │                    ▼                       ▼
  └───────── 废弃 ─── abandoned             archived
```

---

## 四、前端页面规划

### 4.1 页面清单

| 页面 | 对应 GitHub 页面 | 功能说明 | 优先级 |
|------|----------------|---------|--------|
| **任务列表页** | Issues 列表 | 查看所有审计任务，支持筛选、搜索、指派 | P0 |
| **任务详情页** | Issue 详情 | 任务信息、评论、关联分支、操作按钮 | P0 |
| **工作分支列表** | Branches 页面 | 查看所有工作分支及其状态 | P1 |
| **分支详情页** | 分支详情 + 提交历史 | 分支信息、底稿版本历史、评论 | P1 |
| **复核请求列表** | Pull Requests 列表 | 查看所有复核请求，按级别/状态筛选 | P0 |
| **复核详情页** | Pull Request 详情 | 复核内容、版本对比、复核意见、操作按钮 | P0 |
| **里程碑列表** | Releases 页面 | 审计阶段里程碑管理 | P2 |
| **我的工作台** | Your Work | 待办任务、待我复核、我提交的请求 | P0 |

### 4.2 页面流转图

```
我的工作台
    │
    ├── 待办任务 → 任务详情 → 创建/进入工作分支 → 编制底稿 → 提交复核
    │
    ├── 待我复核 → 复核详情 → 通过/退回
    │
    └── 我提交的 → 复核详情 → 查看状态 / 修改后重新提交
```

---

## 五、服务层设计

### 5.1 核心服务

| 服务 | 职责 | 对应现有服务 |
|------|------|-------------|
| `audit_task_service` | 审计任务 CRUD、分配、状态流转 | 新增 |
| `audit_branch_service` | 工作分支管理、版本关联 | 新增（部分整合 audit_workflow_service） |
| `audit_review_service` | 复核请求、多级复核流转 | 新增（部分整合 audit_test_service） |
| `audit_comment_service` | 评论管理 | 新增 |
| `audit_milestone_service` | 里程碑管理 | 新增 |

### 5.2 API 接口规划

| 接口组 | 主要接口 |
|--------|---------|
| **任务管理** | GET /api/audit/tasks, POST /api/audit/tasks, GET /api/audit/tasks/{id}, PUT /api/audit/tasks/{id}/assign, PUT /api/audit/tasks/{id}/status |
| **分支管理** | GET /api/audit/branches, POST /api/audit/branches, GET /api/audit/branches/{id}, PUT /api/audit/branches/{id}/status |
| **复核请求** | GET /api/audit/review-requests, POST /api/audit/review-requests, GET /api/audit/review-requests/{id}, POST /api/audit/review-requests/{id}/submit, POST /api/audit/review-requests/{id}/review, POST /api/audit/review-requests/{id}/merge |
| **评论** | GET /api/audit/comments?target_type=xxx&target_id=xxx, POST /api/audit/comments |
| **里程碑** | GET /api/audit/milestones, POST /api/audit/milestones, PUT /api/audit/milestones/{id}/complete |
| **工作台** | GET /api/audit/dashboard/todo, GET /api/audit/dashboard/for-my-review, GET /api/audit/dashboard/submitted-by-me |

---

## 六、实施路线图

### 阶段一：MVP — 核心协作主流程（单级复核）

**目标**：跑通「任务 → 分支 → 单级复核 → 归档」最小可用闭环
**预计完成度**：L5（前端接入完成）→ L6（真实数据验证）

#### 1.1 数据库迁移（L1 → L2）

| 序号 | 内容 | 涉及文件 |
|------|------|---------|
| 1.1.1 | 生成 Alembic 迁移脚本，创建 6 张新表 | `backend/alembic/versions/` |
| 1.1.2 | 执行迁移，验证表结构 | 数据库 |
| 1.1.3 | 验证现有模型与数据库一致 | `backend/app/db/models.py` |

#### 1.2 后端服务层（L2）

| 序号 | 内容 | 涉及文件 |
|------|------|---------|
| 1.2.1 | `audit_task_service.py` — 任务 CRUD、分配、状态流转 | 新增 |
| 1.2.2 | `audit_branch_service.py` — 分支创建、状态管理、关联底稿 | 新增 |
| 1.2.3 | `audit_review_service.py` — 复核请求提交、单级复核、合并归档 | 新增 |
| 1.2.4 | `audit_comment_service.py` — 评论 CRUD（简化版） | 新增 |

#### 1.3 后端 API 层（L3）

| 序号 | 内容 | 涉及文件 |
|------|------|---------|
| 1.3.1 | `routes_audit_tasks.py` — 任务管理 API | 新增 |
| 1.3.2 | `routes_audit_branches.py` — 分支管理 API | 新增 |
| 1.3.3 | `routes_audit_review.py` — 复核请求 API | 新增 |
| 1.3.4 | `routes_audit_comments.py` — 评论 API | 新增 |
| 1.3.5 | `routes_audit_dashboard.py` — 工作台统计 API | 新增 |

#### 1.4 前端接入（L4 → L5）

| 序号 | 内容 | 涉及文件 |
|------|------|---------|
| 1.4.1 | 前端 API 客户端类型定义 | `frontend/src/api/client.ts` |
| 1.4.2 | 审计任务列表页 | `frontend/src/pages/Audit/TasksPage.tsx` |
| 1.4.3 | 审计任务详情页 | `frontend/src/pages/Audit/TaskDetailPage.tsx` |
| 1.4.4 | 复核请求列表页 | `frontend/src/pages/Audit/ReviewRequestsPage.tsx` |
| 1.4.5 | 复核详情页 | `frontend/src/pages/Audit/ReviewDetailPage.tsx` |
| 1.4.6 | 我的工作台页 | `frontend/src/pages/Audit/AuditDashboardPage.tsx` |
| 1.4.7 | 导航菜单接入 | `frontend/src/layout/MainShell.tsx` |

#### 1.5 端到端验证（L6）

| 序号 | 内容 |
|------|------|
| 1.5.1 | 创建任务 → 分配执行人 |
| 1.5.2 | 创建工作分支 → 关联底稿版本 |
| 1.5.3 | 提交复核请求 → 复核人审核 |
| 1.5.4 | 复核通过 → 合并归档 |
| 1.5.5 | 退回修改 → 重新提交 → 最终通过 |

---

### 阶段二：质量控制增强（多级复核 + 评论）

**目标**：完善审计质量控制体系，支持三级复核
**依赖**：阶段一已完成并验证

| 序号 | 内容 | 完成度标准 |
|------|------|-----------|
| 2.1 | 三级复核流转逻辑（可配置复核级别数） | L4 |
| 2.2 | 复核意见模板库 | L3 |
| 2.3 | @提及用户 + 消息通知 | L5 |
| 2.4 | 复核详情页版本对比 UI | L5 |
| 2.5 | 复核统计与质量分析 | L3 |
| 2.6 | 多级复核集成测试 | L6 |

---

### 阶段三：项目管理增强（里程碑 + 子任务）

**目标**：完善审计项目阶段管理和任务分解

| 序号 | 内容 | 完成度标准 |
|------|------|-----------|
| 3.1 | AuditMilestone 里程碑管理 | L4 |
| 3.2 | 阶段归档与快照 | L4 |
| 3.3 | 子任务分解（任务树） | L4 |
| 3.4 | 任务标签（Label）管理 | L3 |
| 3.5 | 审计进度看板（Kanban 视图） | L5 |
| 3.6 | 审计人员工作负荷统计 | L3 |

---

### 阶段四：与现有模块深度整合

**目标**：新工作流与现有审计模块全面打通

| 序号 | 内容 | 完成度标准 |
|------|------|-----------|
| 4.1 | 与现有 AuditFinding 双向关联 | L5 |
| 4.2 | 与 WorkpaperVersion 深度整合 | L5 |
| 4.3 | 与 AuditProcedureRun 整合 | L5 |
| 4.4 | 与银行对账、函证、三单匹配等模块联动 | L4 |
| 4.5 | 审计报告自动引用复核结论 | L3 |

---

### 实施优先级建议

**推荐顺序：阶段一 → 阶段二 → 阶段四 → 阶段三**

理由：
1. 阶段一：先跑通主流程，验证核心机制可用
2. 阶段二：审计质量控制是刚需，多级复核是审计准则要求
3. 阶段四：与现有模块打通，让新工作流真正有用
4. 阶段三：项目管理增强属于"锦上添花"，可以后做

---

## 七、财务/审计视角的关键设计

### 7.1 符合审计准则的设计

| 审计准则要求 | 本系统设计 |
|------------|-----------|
| **审计工作底稿编制要求** | 工作底稿版本化，每次修改留痕，可追溯 |
| **多级复核制度** | 三级复核流程，每级签名留痕 |
| **审计证据充分性** | 底稿版本关联原始资料，证据链完整 |
| **审计轨迹** | 完整操作日志，谁在什么时间做了什么一目了然 |
| **审计报告质量控制** | 报告出具前必须经过所有复核流程 |
| **审计档案归档** | 合并归档后不可随意修改，修改需审批 |

### 7.2 会计/审计分工场景

| 场景 | 工作机制 |
|------|---------|
| **大型项目分工** | 项目负责人创建任务 → 分配给审计员 → 审计员编制底稿 → 逐级复核 → 归档 |
| **风险导向审计** | 风险评估阶段识别风险点（任务）→ 设计审计程序 → 执行 → 复核结论 |
| **跨领域协作** | 不同审计领域（收入循环、购货循环等）在各自分支工作，互不干扰 |
| **新员工带教** | 新员工编制底稿 → 高级审计员复核 → 退回修改 → 反复迭代 → 最终通过 |
| **审计调整** | 发现错报 → 创建调整任务 → 编制调整分录 → 复核 → 客户确认 → 归档 |

### 7.3 与「台账审计工作流」的关系

参考 `register-audit-workflow-plan.md` 中的「三分离」原则：

| 层级 | 对应本设计 |
|------|-----------|
| 业务台账层（Register） | 原始资料、银行流水、合同等，作为审计证据来源 |
| 会计核算层（Ledger） | 凭证、科目、报表，作为审计对象 |
| 审计工作层（Audit） | 本规划的任务/分支/复核/归档体系 |

本规划聚焦于「审计工作层」的协作机制，向上承接业务台账和会计核算的数据源，向下输出审计结论和报告。

---

## 八、风险与注意事项

### 8.1 潜在风险

| 风险 | 影响 | 应对措施 |
|------|------|---------|
| **流程过于复杂影响效率** | 审计人员嫌麻烦不愿用 | 提供简化模式（小型项目可配置为单级复核） |
| **数据模型过多增加复杂度** | 开发和维护成本高 | MVP 先做核心模型，后续逐步扩展 |
| **与现有审计模块整合困难** | 两套体系并存，数据不一致 | 设计时考虑兼容性，渐进式迁移 |
| **性能问题** | 大量任务和版本导致慢 | 合理索引、分页、缓存 |
| **权限控制复杂** | 不同级别人员看到不同内容 | 基于角色的权限控制（RBAC） |

### 8.2 MVP 范围控制

**MVP 只做以下内容：**
- 审计任务的基本 CRUD + 状态流转
- 工作分支的创建 + 关联底稿版本
- 单级复核（先不搞三级）
- 评论系统（简单版）
- 我的工作台（待办、待我复核）

**MVP 不做：**
- 三级复核（留接口，后面加）
- 子任务分解
- 里程碑管理
- 版本对比 UI（先列表展示）
- 电子签名
- 高级统计和看板

---

## 九、与现有代码的整合点

### 9.1 可直接复用的现有实体

| 现有实体 | 用途 | 整合方式 |
|---------|------|---------|
| `Project` | 审计项目 | 外键关联 |
| `User` | 审计人员 | 创建人、执行人、复核人 |
| `AuditFinding` | 审计发现 | 与 AuditTask 关联 |
| `WorkpaperIndex` | 工作底稿索引 | 与分支关联 |
| `WorkpaperVersion` | 底稿版本 | 分支中的提交记录 |
| `AuditProcedureRun` | 审计程序运行 | 与分支关联 |
| `AuditFindingReviewAction` | 复核动作 | 重构为通用 AuditReviewAction |

### 9.2 需要调整的现有服务

| 现有服务 | 调整内容 |
|---------|---------|
| `audit_workflow_service.py` | 整合工作分支管理逻辑 |
| `audit_test_service.py` | 把复核相关逻辑迁移到 audit_review_service |
| `workpaper_service.py` | 增加分支维度的版本管理 |

### 9.3 迁移策略

1. **共存期**：新老模块并存，逐步迁移
2. **配置开关**：通过 ProjectWorkflowConfig 配置是否启用新工作流
3. **数据迁移**：提供从现有 AuditFinding 到新 AuditTask 的迁移脚本

---

## 总结

本规划借鉴 GitHub 工作流的成熟机制，结合审计/会计专业的特点，设计了一套完整的审计协作体系：

- **任务驱动**：从审计任务出发，目标明确
- **分支隔离**：并行工作，互不干扰
- **多级复核**：质量控制，符合审计准则
- **全程留痕**：审计轨迹完整
- **渐进式实施**：MVP 先跑通主流程，再逐步完善

建议从阶段一（MVP）开始实施，验证核心流程后再扩展。
