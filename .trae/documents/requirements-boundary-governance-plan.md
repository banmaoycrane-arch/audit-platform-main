# 需求边界治理计划

## Summary

本计划用于治理当前工作区内 specs / documents 中出现的需求边界不清、重复造车、一个规格混入多个需求域、计划文档与实际代码状态不一致等问题。

本计划不直接修改业务代码，也不直接删除任何历史规格。实施目标是先建立一套“需求域、主规格、增量规格、历史规格、缺陷修复规格”的归类口径，让后续开发先确认需求归属，再进入实现，避免继续把导航、登录、工作台、凭证、审计、基础资料、AI 等不同任务混在一起。

## Current State Analysis

### 1. 角色与项目规则

依据 `.trae/rules/project_rules.md`：

- 用户是专业会计师、项目决策者、编程初学者。
- AI 是技术实现者、编程知识补充者、财务视角翻译者。
- 项目规则要求：
  - 财务主线优先；
  - 大需求拆成小步骤；
  - 每步可独立验证；
  - 财务逻辑错误优先于技术优化；
  - 审计和记账两条主线结构应保持对称。

当前问题是：部分规格没有严格遵守“一个需求一个边界”，导致后续任务执行时容易把不同层级的问题混在一起。例如前期“工作台导航顺序”任务被扩展到登录异常、工作台数据加载、后端 dashboard/auth 调试，这与原任务边界不一致。

### 2. 已识别的规格规模

只读探索发现 `.trae/specs` 下约有 56 个规格目录，主题覆盖：

- 全局导航、Shell、工作台、UI；
- 用户认证、onboarding、团队、账簿、项目、上下文；
- 凭证管理、AI 生成、人工录入、复核、导出；
- 原始资料导入、文档解析、序时簿导入；
- 基础资料、会计科目、往来单位、期初余额；
- 会计期间、结账、快照、报表；
- 审计测试、审计发现、报告；
- EntryTag、向量、AI、Agent；
- 修复、诊断、复盘、路线图。

其中既有业务规格，也有项目计划、历史复盘、缺陷修复、环境诊断文档。它们目前都以 spec 目录形式并列存在，容易造成“看起来都是同级需求”的误判。

### 3. 明显边界重叠区域

#### A. 导航 / Shell / 工作台

相关规格包括：

- `.trae/specs/saas-shell-and-navigation`
- `.trae/specs/workspace-navigation-continuity`
- `.trae/specs/team-dashboard-and-module-workspaces`
- `.trae/specs/dashboard-home-and-day-book-import`
- `.trae/specs/enterprise-module-ia-and-daybook-flow`
- `.trae/specs/reorder-main-navigation-modules`
- `.trae/specs/review-ui-consistency-and-ux`
- `.trae/specs/plan-acceptance-test-paths`

问题：多个规格都在定义 `MainShell`、`App`、`WorkspacePage`、模块工作台、导航顺序、高亮规则。

当前较清晰的增量规格是 `.trae/specs/reorder-main-navigation-modules/spec.md`，它已明确只负责左侧主导航顺序、管理中心一级层级、自定义模块底部预留，不负责登录异常、后端接口、工作台数据加载。

#### B. 序时簿导入

相关规格包括：

- `.trae/specs/dashboard-home-and-day-book-import`
- `.trae/specs/enterprise-module-ia-and-daybook-flow`
- `.trae/specs/audit-day-book-import`
- `.trae/specs/audit-step3-real-entries`
- `.trae/specs/adaptive-import-engine`

问题：序时簿导入至少被 4 个规格触碰。`audit-day-book-import` 的边界最清楚：专门定义 `source_type=audit_day_book`、凭证号分组、借贷平衡、跳号检测、检测报告。其他规格中涉及序时簿的内容应作为历史入口或依赖，不应继续重复实现序时簿语义。

#### C. 凭证生命周期

相关规格包括：

- `.trae/specs/restore-voucher-management-step-flow`
- `.trae/specs/unify-voucher-input-modes`
- `.trae/specs/auto-generate-entries-from-source`
- `.trae/specs/improve-step2-source-import-experience`
- `.trae/specs/improve-manual-voucher-entry-ui`
- `.trae/specs/accounting-step4-real-review`
- `.trae/specs/export-accounting-package`
- `.trae/specs/entry-line-number`
- `.trae/specs/govern-ai-voucher-evidence-tags`
- `.trae/specs/verify-ai-evidence-draft-flow`

问题：这些规格共同覆盖 Step1-Step5，但存在演进链条未显式标记的问题。比如 Step1 从“选择原始资料类型”演进为“选择凭证输入模式”；Step2 同时承担上传、解析反馈、资料类型、期间推荐；AI 证据规则和 EntryTag 又进一步影响 Step3/Step4。

需要建立“凭证生命周期主域”，否则每次优化 Step2/Step3/Step4 都可能重复设计上下文。

#### D. 基础资料和会计科目口径

相关规格包括：

- `.trae/specs/basic-data-pages`
- `.trae/specs/auto-generate-entries-from-source`
- `.trae/specs/enhance-chart-of-accounts-design`
- `.trae/specs/add-ledger-files-customer-context-coa-presets`
- `.trae/specs/opening-balances`
- `.trae/specs/internal-accounting-unit`
- `.trae/specs/entity-semantic-mapping`

问题：会计科目口径存在冲突。

- `.trae/specs/auto-generate-entries-from-source/spec.md` 一处写“默认科目库只预置一级”，但 ADDED Requirements 又写“预置《企业会计准则》默认跨级科目（一级 + 常用二级）”。
- `.trae/specs/enhance-chart-of-accounts-design/spec.md` 明确要求首次建账不应自动塞入完整模板，由用户自主设计。
- `.trae/specs/add-ledger-files-customer-context-coa-presets` 又引入行业预设科目模板。

建议统一为：空白建账优先，行业模板仅可选导入，导入前预览，不能静默覆盖已有科目。

#### E. Team / Ledger / Project / Accounting Entity / Organization 口径

相关规格包括：

- `.trae/specs/team-multi-ledger-management`
- `.trae/specs/ledger-register-project-concept-unification`
- `.trae/specs/formalize-user-onboarding-account-context`
- `.trae/specs/entity-semantic-mapping`
- `.trae/specs/opening-balances`
- `.trae/specs/financial-statements`
- `.trae/specs/accounting-period-snapshot`

问题：早期规格仍使用 `organization_id`，后续规格要求正式核算数据以 `ledger_id` 为边界。会计主体、项目、团队、账簿之间的口径需要冻结，否则报表、期初、凭证、审计测试都会重复改上下文。

#### F. AI / EntryTag / 向量 / Agent

相关规格包括：

- `.trae/specs/entry-tag-vector-sync`
- `.trae/specs/govern-ai-voucher-evidence-tags`
- `.trae/specs/summary-library`
- `.trae/specs/entity-semantic-mapping`
- `.trae/specs/document-parsing-engine`
- `.trae/specs/agent-lightweight-llm-api`
- `.trae/specs/verify-ai-evidence-draft-flow`

问题：AI 能力逐渐扩张为统一语义层，但需要明确边界：AI 只能生成建议、草稿、标签、风险提示；正式凭证、结账、报表必须由确定性规则和人工确认控制。

### 4. 明显“大杂烩规格”

#### `.trae/specs/enterprise-module-ia-and-daybook-flow/spec.md`

该规格同时覆盖：

- 企业级一级导航；
- 财务总账；
- 自定义模块；
- 基础资料；
- 银行模块；
- 税务模块；
- 涉税助手；
- 审计 Step3 序时簿；
- EntryTag 映射。

结论：这是典型混合规格，应标记为“历史整合规格”，不建议继续在该规格上追加实现任务。

#### `.trae/specs/dashboard-home-and-day-book-import`

该规格混合了 dashboard 首页 KPI 和审计 Step3 序时簿入口。Dashboard 与序时簿是不同需求域，应拆开。

#### `.trae/specs/auto-generate-entries-from-source/spec.md`

该规格名义上是“原始资料自动生成分录”，但实际包含会计科目治理、对方单位、EntryTag、向量同步、基础资料页面、Step2 期间、Step3 API 等。应作为“AI 生成凭证引擎主规格”保留，但其中基础资料、科目、对方单位、EntryTag 应拆为依赖域。

#### `.trae/specs/document-parsing-engine`

该规格接近架构设计文档，包含合同、发票、银行、收入准则、企业登记、关联方、向量标签、审计风险等多个域。应拆小。

#### `.trae/specs/add-ledger-files-customer-context-coa-presets`

该规格同时包含账簿文件管理、客户上下文识别、行业科目模板，建议拆成三个独立域。

### 5. documents 状态不一致

`.trae/documents` 中存在多个计划/复盘文档，部分已明显过期。例如早期计划还描述“未发现已有代码文件”，而当前项目已有完整前后端和大量规格。后续不应以单个历史计划文档判断当前完成度。

## Proposed Changes

### Phase 1：建立需求域分类表

新增一个治理文档，建议路径：

- `.trae/documents/requirements-domain-index.md`

内容包括：

1. 需求域清单；
2. 每个需求域的主规格；
3. 增量规格；
4. 历史规格；
5. 缺陷修复规格；
6. 计划/复盘类文档；
7. 不再追加实现的规格。

建议需求域：

1. 身份认证与访问控制；
2. 团队、账簿、项目、上下文；
3. Shell、导航、工作台、模块入口；
4. 凭证生命周期；
5. 原始资料导入与解析；
6. 审计证据与审计流程；
7. 基础资料；
8. 会计期间、结账、快照、报表；
9. EntryTag、语义、向量、AI 草稿；
10. Agent 与执行型助手；
11. 银行、税务、库存、固定资产等业务模块；
12. 缺陷修复与环境诊断；
13. 项目计划、复盘、路线图。

### Phase 2：为每个 spec 标记治理状态

不删除历史 spec，只在治理文档中登记状态。

建议状态：

- `active-main`：当前主规格；
- `active-increment`：当前增量规格；
- `merged`：已合并到主规格；
- `superseded`：已被后续规格替代；
- `historical`：历史记录，仅供参考；
- `bugfix`：缺陷修复；
- `planning`：计划/复盘/路线图；
- `mixed-needs-split`：范围过大，后续不得继续追加实现任务。

### Phase 3：冻结核心业务概念口径

新增或补充一个概念口径文档，建议路径：

- `.trae/documents/core-business-concepts-boundary.md`

必须明确：

| 概念 | 建议口径 |
|---|---|
| Team | 团队/事务所/企业组织，权限协作范围 |
| Ledger | 会计账簿，正式核算数据边界 |
| Project | 审计/记账/税务等工作项目 |
| Register | 业务台账，归属于业务模块，不等于会计账簿 |
| Accounting Entity | 会计主体/报表主体 |
| Counterparty | 往来单位/交易对象 |
| EntryTag | 分录语义标签/辅助核算维度 |
| DocumentTag | 原始资料语义标签 |
| organization_id | 历史兼容字段或待明确字段，不作为新业务主边界 |

### Phase 4：处理最高风险的重复造车区

优先治理以下四组：

#### 1. 导航域

建议主规格：

- `.trae/specs/saas-shell-and-navigation`

增量规格：

- `.trae/specs/reorder-main-navigation-modules`
- `.trae/specs/workspace-navigation-continuity`
- `.trae/specs/team-dashboard-and-module-workspaces`

混合/历史规格：

- `.trae/specs/enterprise-module-ia-and-daybook-flow`
- `.trae/specs/dashboard-home-and-day-book-import`

规则：导航规格只允许改 `MainShell`、路由入口、高亮、模块工作台入口，不允许混入登录、dashboard 数据、审计导入、凭证生成。

#### 2. 序时簿域

建议主规格：

- `.trae/specs/audit-day-book-import`

依赖规格：

- `.trae/specs/adaptive-import-engine`
- `.trae/specs/audit-step3-real-entries`

规则：序时簿语义统一由 `audit-day-book-import` 管理，其他规格只引用，不重复定义跳号、平衡、凭证号分组规则。

#### 3. 凭证生命周期域

建议主规格：

- `.trae/specs/unify-voucher-input-modes`

增量规格：

- `.trae/specs/improve-step2-source-import-experience`
- `.trae/specs/improve-manual-voucher-entry-ui`
- `.trae/specs/accounting-step4-real-review`
- `.trae/specs/export-accounting-package`
- `.trae/specs/govern-ai-voucher-evidence-tags`

规则：凭证生命周期规格只处理输入模式、资料上传、草稿生成、人工录入、复核、落库、导出。基础资料、报表、审计导入、导航只能作为依赖，不能混入实现范围。

#### 4. 会计科目域

需要统一口径：

- 空白建账是默认体验；
- 行业模板是可选导入；
- 模板导入必须预览、确认、冲突提示；
- 不得静默覆盖已有科目；
- AI 推荐科目只能作为候选，不自动变成正式科目。

主规格建议：

- `.trae/specs/enhance-chart-of-accounts-design`

增量规格：

- `.trae/specs/add-ledger-files-customer-context-coa-presets` 中的科目模板部分。

### Phase 5：建立新需求准入规则

后续每个新 spec 必须包含：

```text
Domain:
Status:
Owner Spec:
Depends On:
In Scope:
Out of Scope:
Acceptance Level:
```

其中 `Out of Scope` 必须明确写出不做什么。例如：

- 导航规格：不改认证、不改 dashboard API、不改凭证业务；
- 登录规格：不改导航、不改账簿文件、不改 AI；
- 凭证规格：不改报表、不改审计测试、不改主导航；
- 报表规格：只消费凭证、期初、期间数据，不负责录入页面；
- Agent 规格：不绕过后端权限，不直接生成正式凭证。

### Phase 6：建立完成度标准

建议统一完成度等级：

```text
L0 文档已写
L1 数据模型已定义
L2 服务层已实现
L3 API 已暴露
L4 前端已接入
L5 自动化测试通过
L6 真实业务样例验收通过
```

以后 checklist 不应只用 `[x]` 表示“完成”，还应注明完成到 L 几。这样可以避免“文档完成 / UI 完成 / mock 完成”被误认为“业务闭环完成”。

## Assumptions & Decisions

1. 不删除历史 spec，因为历史规格能解释项目演进过程。
2. 不移动目录，先用治理文档登记状态，避免破坏现有引用。
3. 先治理边界，不新增业务功能。
4. 导航、登录、dashboard、凭证、审计、基础资料、AI 必须拆成不同需求域。
5. 后续任何实现任务开始前，应先确认它属于哪个需求域。
6. 如果一个需求影响多个域，只能选择一个主域，其他作为依赖或影响范围列出。

## Verification Steps

实施该计划后，应按以下方式验收：

1. 检查 `.trae/documents/requirements-domain-index.md` 是否存在，并覆盖当前 `.trae/specs` 下所有规格目录。
2. 每个规格是否至少被标记为一个状态：`active-main`、`active-increment`、`merged`、`superseded`、`historical`、`bugfix`、`planning`、`mixed-needs-split`。
3. 检查导航相关规格是否只归入 Shell / 导航 / 工作台域，不再混入登录或后端 dashboard。
4. 检查序时簿相关规格是否以 `audit-day-book-import` 为主规格。
5. 检查凭证流程相关规格是否归入凭证生命周期域。
6. 检查会计科目相关规格是否统一为“空白建账 + 可选行业模板导入”口径。
7. 检查 Team / Ledger / Project / Accounting Entity / organization_id 是否有统一概念定义。
8. 新建一个样例 spec，确认模板中包含 Domain / Status / Owner Spec / In Scope / Out of Scope / Acceptance Level。

## Recommended Next Action

建议下一步不要继续新增功能，而是执行“需求边界归档”任务：

1. 创建 `.trae/documents/requirements-domain-index.md`；
2. 将 56 个规格目录按需求域归类；
3. 标记主规格、增量规格、历史规格、混合规格；
4. 创建 `.trae/documents/core-business-concepts-boundary.md`；
5. 后续所有新需求必须先选域，再写 spec。

这样可以避免继续出现：

- 一个导航任务混入登录调试；
- 一个 Dashboard 任务混入序时簿；
- 一个 AI 凭证任务混入基础资料和科目治理；
- 一个基础资料任务混入文件中心和行业模板；
- 一个计划文档被误当成业务完成依据。
