# 需求域分类表

## 目的

本文件用于登记当前 `.trae/specs` 下所有规格的主归属域、治理状态和后续使用规则，避免同一需求被多个规格重复实现，或一个规格混入多个互不相同的需求。

本文件不删除历史规格，不移动目录，只提供后续开发时的判断口径。

## 状态说明

| 状态 | 含义 |
|---|---|
| active-main | 当前需求域主规格，后续同域需求优先引用它 |
| active-increment | 当前有效增量规格，只处理一个清晰增量 |
| merged | 内容已并入主规格或后续规格，保留历史记录 |
| superseded | 已被后续规格替代，不建议继续追加实现 |
| historical | 历史记录，仅供理解项目演进 |
| bugfix | 缺陷修复或环境修复规格 |
| planning | 计划、复盘、路线图，不作为业务实现规格 |
| mixed-needs-split | 范围过大或混合多个需求域，后续不得继续追加实现任务 |

## 准入规则

后续新建或继续执行任意 spec 前，必须先确认：

```text
Domain:
Status:
Owner Spec:
Depends On:
In Scope:
Out of Scope:
Acceptance Level:
```

其中 `Out of Scope` 必须明确不做什么。

## 需求域总览

| 编号 | 需求域 | 说明 |
|---|---|---|
| D01 | 身份认证与访问控制 | 登录、注册、Token、网关、路由守卫、权限边界 |
| D02 | 团队、账套、项目、上下文 | Team、Ledger、Project、当前账套、默认账套、onboarding |
| D03 | Shell、导航、工作台、模块入口 | MainShell、导航顺序、高亮、模块工作台、首页入口 |
| D04 | 凭证生命周期 | 输入模式、原始资料、AI 草稿、人工录入、复核、落库、导出 |
| D05 | 原始资料导入与解析 | 文件上传、导入任务、CSV/Excel/PDF/图片解析、质量报告 |
| D06 | 审计证据与审计流程 | 审计 Step1-6、序时簿、测试、发现、报告 |
| D07 | 基础资料 | 会计科目、往来单位、期初余额、组织架构、人员、物料、仓库 |
| D08 | 会计期间、结账、快照、报表 | 会计期间、损益结转、结账、反结账、报表 |
| D09 | EntryTag、语义、向量、AI 草稿 | 分录标签、文档标签、向量同步、证据充分性、AI draft |
| D10 | Agent 与执行型助手 | Agent Chat、LLM、任务规划、工具边界 |
| D11 | 业务模块 | 银行、税务、固定资产、进销存等模块 |
| D12 | 缺陷修复与环境诊断 | 登录修复、注册修复、IDE 保存、JWT、后端可用性等 |
| D13 | 项目计划、复盘、路线图 | 计划、回顾、验收路径、路线图、项目状态 |

## D01 身份认证与访问控制

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| user-auth-system | active-main | 主规格 | 登录、注册、用户认证主线 |
| plan-backend-gateway-design | active-increment | 网关规划 | 后端网关、鉴权、统一错误结构等边界 |
| fix-login-regression | bugfix | 修复规格 | 登录回归问题修复，不作为新认证主规格 |
| fix-register-and-backend-availability | bugfix | 修复规格 | 注册和后端可用性修复 |
| diagnose-register-failure | bugfix | 诊断规格 | 注册失败诊断 |
| fix-audit-report-storage-and-jwt-secret | bugfix | 修复规格 | JWT secret 和审计报告存储修复 |

边界规则：认证规格不应修改主导航顺序、凭证流程、审计导入、基础资料模型。

## D02 团队、账套、项目、上下文

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| team-multi-ledger-management | active-main | 主规格 | 团队、多账套、用户授权、默认账套 |
| formalize-user-onboarding-account-context | active-increment | 上下文规格 | 登录后团队/账套/项目/会计主体上下文 |
| ledger-register-project-concept-unification | active-increment | 概念规格 | Ledger、Register、Project 等概念统一 |
| team-ledger-management-ui | active-increment | UI 增量 | 团队和账套管理页面 |
| lifecycle-management | active-increment | 生命周期 | 账套或项目生命周期治理 |

边界规则：团队/账套/项目规格可以影响权限和上下文，但不应直接实现凭证生成、报表计算、AI 语义规则。

## D03 Shell、导航、工作台、模块入口

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| saas-shell-and-navigation | active-main | 主规格 | Shell、导航、整体布局主线 |
| reorder-main-navigation-modules | active-increment | 清晰增量 | 仅处理左侧主导航顺序、管理中心一级、自定义模块底部 |
| workspace-navigation-continuity | active-increment | 导航连续性 | 路由连续、高亮、返回关系 |
| team-dashboard-and-module-workspaces | active-increment | 模块工作台 | 团队/模块工作台入口 |
| review-ui-consistency-and-ux | active-increment | UI 评审 | UI 一致性优化，不能扩大到业务逻辑 |
| dashboard-home-and-day-book-import | mixed-needs-split | 混合规格 | 混合 dashboard 和序时簿入口，后续不再追加实现 |
| enterprise-module-ia-and-daybook-flow | mixed-needs-split | 混合规格 | 混合导航、基础资料、银行税务、序时簿、EntryTag |
| plan-acceptance-test-paths | planning | 验收计划 | 页面验收路径，不作为业务实现规格 |

边界规则：导航规格只允许处理 `MainShell`、路由入口、模块工作台、高亮、父级默认跳转；不得混入登录认证、dashboard API、凭证生成、审计导入。

## D04 凭证生命周期

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| unify-voucher-input-modes | active-main | 主规格 | 统一手工、文件导入、AI 生成等凭证输入模式 |
| restore-voucher-management-step-flow | active-increment | 流程恢复 | 恢复 Step1-Step5 流程 |
| improve-step2-source-import-experience | active-increment | Step2 增量 | 原始资料上传、解析反馈、期间推荐 |
| improve-manual-voucher-entry-ui | active-increment | 人工录入增量 | 人工凭证录入体验和部分提交问题 |
| accounting-step4-real-review | active-increment | Step4 增量 | Step4 真实草稿复核 |
| export-accounting-package | active-increment | Step5 增量 | 账套/凭证导出 |
| entry-line-number | active-increment | 凭证行号 | 凭证分录连续行号规则 |
| auto-generate-entries-from-source | mixed-needs-split | 核心但过宽 | AI 生成分录主线，但混入科目、往来、EntryTag、基础资料 |

边界规则：凭证生命周期只负责输入、草稿、复核、落库、导出。会计科目、往来单位、EntryTag、期间、报表只能作为依赖，不应在凭证规格中重复定义完整主规则。

## D05 原始资料导入与解析

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| adaptive-import-engine | active-main | 主规格 | 通用导入引擎、字段映射、质量报告 |
| document-parsing-engine | mixed-needs-split | 架构型规格 | 文档解析范围过大，需拆成文件解析、收入准则、关联方、标签等子域 |
| add-ledger-files-customer-context-coa-presets | mixed-needs-split | 混合规格 | 账套文件、客户上下文、行业科目模板混合 |

边界规则：导入解析域负责把资料变成结构化信息和质量报告，不直接决定正式入账、不直接修改导航、不重复定义审计测试规则。

## D06 审计证据与审计流程

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| audit-day-book-import | active-main | 序时簿主规格 | `source_type=audit_day_book`、凭证号分组、跳号、平衡检测 |
| audit-step3-real-entries | active-increment | Step3 增量 | 审计 Step3 接入真实分录 |
| business-cycle-audit | active-increment | 业务循环 | 审计业务循环测试 |
| internal-control-audit | active-increment | 内控审计 | 内部控制测试 |
| persist-audit-findings | active-increment | 审计发现 | 审计发现持久化 |
| audit-report-export | active-increment | 报告导出 | 审计报告导出 |
| summary-library | active-increment | 摘要/风险辅助 | 摘要模板和审计风险线索，需与 AI/EntryTag 区分 |

边界规则：审计流程域负责证据、分录、测试、发现、报告；不负责总账凭证正式入账，不直接修改会计科目主规则。

## D07 基础资料

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| basic-data-pages | active-main | 主规格 | 基础资料页面集合 |
| enhance-chart-of-accounts-design | active-main | 科目主规格 | 会计科目自主设计、空白建账口径 |
| opening-balances | active-increment | 期初余额 | 期初数据录入和联动 |
| internal-accounting-unit | active-increment | 内部核算单位 | 内部核算、虚拟核算单位 |
| entity-semantic-mapping | active-increment | 主体语义 | 法律主体、会计主体、纳税主体、管理主体等语义映射 |

边界规则：基础资料域负责主数据维护，不直接实现凭证生成算法、审计测试算法、导航重排。

会计科目统一口径：空白建账优先；行业模板是可选导入；模板必须预览确认；不得静默覆盖已有科目；AI 推荐科目只能作为候选。

## D08 会计期间、结账、快照、报表

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| accounting-period-snapshot | active-main | 期间主规格 | 会计期间、结账、反结账、快照 |
| financial-statements | active-main | 报表主规格 | 资产负债表、利润表等报表逻辑 |
| transactional-design | active-increment | 事务一致性 | 数据事务、回滚、审计追溯 |
| opening-balances | active-increment | 期初依赖 | 报表和期间计算依赖期初余额 |
| lifecycle-management | active-increment | 生命周期依赖 | 与结账、归档、恢复等状态相关 |

边界规则：报表消费凭证、期初、期间数据，不负责录入页面；结账状态不应被 UI 任务随意修改。

## D09 EntryTag、语义、向量、AI 草稿

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| entry-tag-vector-sync | active-main | 标签/向量主规格 | EntryTag 与向量同步 |
| govern-ai-voucher-evidence-tags | active-main | AI 凭证证据主规格 | 证据充分性、AI draft、EntryTag、人工留痕 |
| verify-ai-evidence-draft-flow | active-increment | 验证增量 | AI evidence/draft 流程验证 |
| summary-library | active-increment | 摘要辅助 | 摘要模板、风险线索 |
| entity-semantic-mapping | active-increment | 语义依赖 | 主体语义映射依赖 |
| document-parsing-engine | mixed-needs-split | 文档标签相关 | DocumentTag 与解析混合，需拆分 |

边界规则：AI/向量只能生成建议、草稿、标签、风险提示；正式凭证、结账、报表必须由确定性规则和人工确认控制。

## D10 Agent 与执行型助手

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| agent-lightweight-llm-api | active-main | Agent 主规格 | Agent Chat、LLM 接口、规则兜底 |
| multi-agent-cli-execution-roadmap.md | planning | 长期路线图 | Agent 执行型能力规划，位于 documents |
| agent-architecture-plan.md | planning | 架构计划 | Agent 架构计划，位于 documents |

边界规则：Agent 不绕过后端权限，不直接生成正式凭证，不直接执行结账、反结账等高风险财务操作。

## D11 银行、税务、库存、固定资产等业务模块

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| enterprise-module-ia-and-daybook-flow | mixed-needs-split | 历史混合规格 | 曾包含银行、税务、固定资产、进销存入口，但不再作为业务模块主规格 |
| saas-shell-and-navigation | active-main | 入口依赖 | 只负责业务模块入口，不负责具体业务规则 |
| reorder-main-navigation-modules | active-increment | 入口增量 | 固定资产、进销存作为一级可展开模块 |

边界规则：银行、税务、固定资产、进销存后续应分别独立立项，不能继续塞进导航或企业级混合规格。

## D12 缺陷修复与环境诊断

| Spec | 状态 | 角色 | 说明 |
|---|---|---|---|
| fix-login-regression | bugfix | 登录修复 | 登录回归问题 |
| fix-register-and-backend-availability | bugfix | 注册/后端 | 注册与后端可用性 |
| diagnose-register-failure | bugfix | 注册诊断 | 注册失败诊断 |
| diagnose-ide-save-failures | bugfix | IDE 环境 | IDE 保存失败诊断 |
| fix-audit-report-storage-and-jwt-secret | bugfix | JWT/审计报告 | JWT secret 与审计报告存储 |
| review-context-and-fix-next-blocker | bugfix | 阻塞修复 | 上下文回顾和下一阻塞修复 |

边界规则：bugfix 规格只修复缺陷，不应顺手新增业务功能或调整产品信息架构。

## D13 项目计划、复盘、路线图

| Spec / Document | 状态 | 角色 | 说明 |
|---|---|---|---|
| confirm-context-and-next-target | planning | 上下文确认 | 不作为业务实现规格 |
| next-execution-roadmap | planning | 路线图 | 不作为业务实现规格 |
| next-execution-roadmap-ii | planning | 路线图 | 不作为业务实现规格 |
| progress-review | planning | 进度回顾 | 不作为业务实现规格 |
| summarize-requirements | planning | 需求总结 | 不作为业务实现规格 |
| plan-acceptance-test-paths | planning | 验收路径 | 不作为业务实现规格 |
| requirements-boundary-governance-plan.md | planning | 治理计划 | 当前治理计划 |
| finance-vector-audit-plan.md | historical | 初始计划 | 部分内容已过期 |
| frontend-ui-coverage-review.md | historical | UI 评审 | 部分状态已过期 |
| workspace-requirements-progress-review-plan.md | historical | 进度文档 | 规格数量描述已过期 |
| project_status_review_and_next_steps.md | historical | 状态回顾 | “全部完成”等判断需重新核验 |
| workspace-recap-and-next-step.md | historical | 复盘 | 历史参考 |
| workspace-recap-v2-after-financial-statements.md | historical | 复盘 | 历史参考 |
| project-progress-status-plan.md | planning | 项目状态 | 计划类文档 |
| project-review-plan.md | planning | 项目评审 | 计划类文档 |
| frontend-api-fix-plan.md | planning | 前端 API 修复计划 | 计划类文档 |
| environment-recognition-plan.md | planning | 环境识别计划 | 计划类文档 |

边界规则：计划/复盘/路线图不得直接当作业务完成依据。业务完成度必须回到对应 active-main 或 active-increment 规格核验。

## 最高风险重复造车清单

### 1. 导航 / 工作台

- 主规格：`saas-shell-and-navigation`
- 增量：`reorder-main-navigation-modules`
- 不再追加：`enterprise-module-ia-and-daybook-flow` 中的导航部分

风险：导航任务混入登录、dashboard、审计导入。

治理规则：导航任务只处理 UI 入口和高亮。

### 2. 序时簿

- 主规格：`audit-day-book-import`
- 依赖：`adaptive-import-engine`、`audit-step3-real-entries`
- 不再追加：`dashboard-home-and-day-book-import` 和 `enterprise-module-ia-and-daybook-flow` 中的序时簿部分

风险：多个规格重复定义 source_type、跳号、借贷平衡。

治理规则：序时簿语义只由 `audit-day-book-import` 管理。

### 3. 凭证生命周期

- 主规格：`unify-voucher-input-modes`
- 增量：Step2、人工录入、Step4、Step5、AI 证据规则
- 需拆分：`auto-generate-entries-from-source`

风险：AI 生成、基础资料、EntryTag、科目治理、期间选择混在同一规格。

治理规则：凭证规格只处理凭证生命周期；基础资料和标签作为依赖。

### 4. 会计科目

- 主规格：`enhance-chart-of-accounts-design`
- 依赖：`basic-data-pages`
- 增量：行业模板导入

风险：一处要求默认一级科目，一处要求默认跨级科目，一处要求空白建账。

治理规则：空白建账优先，行业模板可选导入，不静默覆盖。

## 新规格模板

后续新规格建议在 `spec.md` 顶部加入：

```text
Domain: Dxx - [需求域]
Status: active-main | active-increment | bugfix | planning
Owner Spec: [主规格目录名]
Depends On: [依赖规格]
In Scope:
- [本规格负责什么]
Out of Scope:
- [本规格明确不负责什么]
Acceptance Level: L0-L6
```

## 完成度等级

| 等级 | 含义 |
|---|---|
| L0 | 文档已写 |
| L1 | 数据模型已定义 |
| L2 | 服务层已实现 |
| L3 | API 已暴露 |
| L4 | 前端已接入 |
| L5 | 自动化测试通过 |
| L6 | 真实业务样例验收通过 |

## 使用规则

1. 新需求先选需求域，再写 spec。
2. 一个 spec 只能主归属一个需求域。
3. 影响多个域时，其他域只能写入 `Depends On` 或 `Impact`。
4. 混合规格不得继续追加实现任务，应拆分后再执行。
5. bugfix 不得顺手新增业务功能。
6. planning 文档不得作为业务完成依据。
7. checklist 勾选不等于业务闭环，必须注明完成度等级。
