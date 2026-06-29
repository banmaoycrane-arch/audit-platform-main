# 后续任务管理、边界治理与开发顺序建议 Plan

## Summary

本计划用于回顾当前项目上下文、确认双方角色、识别代码库与需求规模，并给出一套后续开发任务管理建议。核心目标是：后续每一个具体任务都先确认需求归属、上下游依赖、验收口径和不做事项，再进入实现，避免在技术栈、需求范围和功能边界之间反复摇摆。

本计划不修改业务代码，只作为后续讨论和任务治理依据。

## Current State Analysis

### 1. 角色确认

依据项目规则与用户规则，当前协作角色如下：

| 角色 | 定位 | 主要职责 |
|---|---|---|
| 用户 | 专业会计师、项目决策者、编程初学者 | 用财务语言提出需求，判断会计逻辑是否正确，决定业务优先级 |
| AI 助手 | 技术实现者、编程知识补充者、财务视角翻译者 | 将财务需求翻译成代码任务，解释技术选择，控制边界并执行实现 |

协作原则：

1. 财务逻辑错误优先级最高。
2. 需求必须先从财务实务含义确认，再转成技术任务。
3. 大需求必须拆成小任务，每个任务可独立验证。
4. 后续任务不得只因为“顺手”而扩大范围。
5. 每个实现任务都要明确：做什么、不做什么、影响哪些文件、如何验收。

### 2. 代码库识别

当前项目是一个前后端分离的财务向量审计系统。

#### 根级启动脚本

实际脚本位于：

- [package.json](file:///e:/projects/finance-vector-audit/wroksapce20260616/package.json)

当前脚本包括：

- `dev:frontend`：启动前端 Vite 服务
- `build:frontend`：构建前端
- `lint:frontend`：前端 TypeScript 检查
- `dev:backend`：启动 FastAPI 后端，端口为 `127.0.0.1:8010`
- `test:backend`：运行后端测试

#### 后端

后端入口：

- [main.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/main.py)

当前后端使用 FastAPI，并已挂载认证、导入、分录、文件、风险、会计期间、基础资料、报表、审计测试、审计导出、业务循环、内控、账簿、团队、项目等 API 路由。

关键观察：

- 后端不是空壳，已经有较完整的 API 与服务层。
- [main.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/main.py#L40-L130) 中存在本地 SQLite 兼容补列逻辑，说明项目处于“边开发边兼容本地数据库”的阶段。
- [main.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/main.py#L141-L168) 已挂载大量业务路由，后续任务应优先复用现有 API 风格，而不是另起一套技术栈。

#### 前端

前端路由入口：

- [App.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/App.tsx)

当前前端使用 React、TypeScript、Vite、React Router、Ant Design。

关键观察：

- [App.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/App.tsx#L83-L154) 已经形成 SaaS Shell 下的完整业务路由。
- 记账流程已有 Step1-Step5：[/accounting/step/1 - /accounting/step/5](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/App.tsx#L98-L107)。
- 审计流程已有 Step1-Step6：[/audit/step/1 - /audit/step/6](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/App.tsx#L108-L113)。
- 基础资料、期间、报表、账簿、团队、Agent、风险、分录等页面入口已存在。

### 3. 总需求统计

通过只读统计当前 `.trae/specs/*/spec.md`，当前共有：

- **57 个需求规格目录**

需求目录根路径：

- [.trae/specs](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs)

需要注意：历史文档中出现过“20 个 spec”“32 个 spec”“56 个规格目录”等表述，但当前实际只读统计结果为 **57 个 spec.md**。后续不能再以历史文档中的旧数量作为当前进度判断依据。

### 4. 需求域分类现状

当前最重要的需求治理文件是：

- [requirements-domain-index.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/requirements-domain-index.md)

该文档已把需求分为 13 个域：

| 编号 | 需求域 | 管理含义 |
|---|---|---|
| D01 | 身份认证与访问控制 | 登录、注册、Token、路由守卫、权限边界 |
| D02 | 团队、账簿、项目、上下文 | Team、Ledger、Project、默认账簿、onboarding |
| D03 | Shell、导航、工作台、模块入口 | MainShell、导航、高亮、模块工作台 |
| D04 | 凭证生命周期 | 输入模式、原始资料、AI 草稿、人工录入、复核、落库、导出 |
| D05 | 原始资料导入与解析 | 上传、导入任务、解析、质量报告 |
| D06 | 审计证据与审计流程 | 审计 Step1-6、序时簿、测试、发现、报告 |
| D07 | 基础资料 | 科目、往来、期初、组织、人员、物料 |
| D08 | 会计期间、结账、快照、报表 | 期间、损益结转、结账、反结账、报表 |
| D09 | EntryTag、语义、向量、AI 草稿 | 标签、向量同步、证据充分性、AI draft |
| D10 | Agent 与执行型助手 | Agent Chat、LLM、任务规划、工具边界 |
| D11 | 业务模块 | 银行、税务、固定资产、进销存等 |
| D12 | 缺陷修复与环境诊断 | 登录修复、注册修复、JWT、后端可用性等 |
| D13 | 项目计划、复盘、路线图 | 计划、回顾、验收路径、项目状态 |

这 13 个域应作为后续任务归类的第一层目录。任何新需求都应先定位到其中一个主域，再判断是否属于主规格、增量规格、bugfix 或历史规格。

### 5. 当前已有治理基础

以下三个文档应作为后续任务管理的基础规则：

1. [requirements-domain-index.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/requirements-domain-index.md)
   - 用于判断需求归属域、主规格、增量规格、历史规格和 bugfix。
2. [requirements-boundary-governance-plan.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/requirements-boundary-governance-plan.md)
   - 用于识别边界重叠、大杂烩规格和重复造车风险。
3. [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/core-business-concepts-boundary.md)
   - 用于冻结 Team、Ledger、Project、Register、Accounting Entity、Counterparty、EntryTag、DocumentTag、organization_id 等核心概念。

### 6. 当前最大管理风险

当前项目的问题不是“没有需求”，而是需求已经很多，且历史演进中出现了以下风险：

1. **需求数量多**：当前 57 个规格目录，容易重复定义同一业务能力。
2. **历史文档与当前代码不同步**：部分文档只适合作为历史参考。
3. **部分规格边界过宽**：例如混合导航、基础资料、序时簿、AI、EntryTag 的规格，不适合继续追加任务。
4. **代码完成层级不一致**：有的功能已有模型和服务，但 API 或前端未闭环；有的 tasks 勾选完成，但真实页面仍有缺陷。
5. **业务概念容易混用**：尤其是 Team、Ledger、Project、organization_id、Accounting Entity。
6. **修 bug 时容易扩大范围**：例如一个 Step2 创建会计期间失败，不应顺手重构整个期间、报表或凭证流程。

## Proposed Changes

### 一、建立后续任务准入卡片

后续每一个具体任务，在进入实现前，都建议先填写一张“任务准入卡片”。这不是复杂流程，而是为了防止边界漂移。

建议格式：

```text
任务名称：
业务问题：
需求域：Dxx
Owner Spec：
任务类型：主线 / 增量 / bugfix / 体验优化 / 治理
Depends On：
In Scope：
Out of Scope：
影响页面：
影响 API：
影响数据表：
验收方式：
完成层级目标：文档 / 模型 / 服务 / API / 前端 / 测试与真实数据验证
```

#### 为什么这样做

从财务角度看，这类似审计底稿的“索引号 + 审计目标 + 程序 + 结论”。

从技术角度看，它相当于给每个开发任务建立边界和验收标准，避免一个任务无限扩展。

### 二、采用六级完成标准

后续不要再只看 `tasks.md` 是否勾选完成，而要按六级完成标准判断真实进度。

```text
L1 文档完成
L2 数据模型完成
L3 服务完成
L4 API 完成
L5 前端接入完成
L6 测试与真实数据验证完成
```

建议所有任务都标注目标完成层级。

例如：

| 任务类型 | 最低完成层级 |
|---|---|
| 纯规划 | L1 文档完成 |
| 后端底座 | L3 服务完成 |
| 可供前端调用 | L4 API 完成 |
| 用户可操作功能 | L5 前端接入完成 |
| 财务主流程功能 | L6 测试与真实数据验证完成 |
| 财务逻辑修复 | L6 测试与真实数据验证完成 |

### 三、用“主线优先 + 依赖优先 + 阻塞优先”的排序规则

基于运筹学的基本思想，后续任务排序不建议只按“想做什么”排序，而应按约束和依赖关系排序。

建议采用以下排序规则：

#### 1. 先做阻塞任务

如果某任务不修，后续多个任务无法验证，则优先级最高。

例子：

- 登录失败导致所有受保护页面无法进入。
- Step2 会计期间创建失败导致 AI 生成凭证无法进入 Step3。
- 报表不平衡导致记账闭环无法验收。

#### 2. 先做依赖节点多的任务

如果某任务是很多后续任务的基础，应优先完成。

例子：

- Ledger 账簿边界。
- AccountingPeriod 会计期间。
- ChartOfAccounts 会计科目。
- ImportJob / SourceFile 原始资料导入。

#### 3. 先闭合主流程，再扩展周边模块

主流程建议优先于银行、税务、库存、固定资产等周边模块。

推荐主流程顺序：

```text
身份认证与上下文
  → 团队 / 账簿 / 项目边界
  → 基础资料
  → 会计期间
  → 原始资料导入 / 人工录入
  → 凭证生成 / 复核 / 落库
  → 期初 + 本期分录
  → 损益结转 / 结账
  → 报表
  → 审计测试 / 审计发现 / 报告
  → AI / Agent 增强
  → 银行 / 税务 / 固定资产 / 进销存扩展
```

#### 4. 不让体验优化打断财务闭环

体验优化有价值，但不能长期打断财务主流程。

例如：

- 页面按钮位置、颜色、说明文字，可以排在主流程稳定之后。
- 但“创建会计期间失败”“凭证不能落库”“报表不平衡”属于主流程阻塞，应优先。

### 四、建立任务分配清单结构

建议后续维护一个“任务分配清单”，按任务状态与依赖关系管理，而不是只按 spec 目录平铺。

建议字段：

| 字段 | 含义 |
|---|---|
| Task ID | 唯一编号，例如 D04-T003 |
| 名称 | 任务名称 |
| 需求域 | D01-D13 |
| Owner Spec | 所属规格目录 |
| 类型 | 主线 / 增量 / bugfix / 体验 / 治理 |
| 前置任务 | 必须先完成的任务 |
| 后续受益任务 | 完成后能解锁哪些任务 |
| 当前完成层级 | L1-L6 |
| 目标完成层级 | L1-L6 |
| In Scope | 本任务做什么 |
| Out of Scope | 本任务明确不做什么 |
| 验收入口 | 页面地址 / API / 测试命令 |
| 状态 | 待排 / 进行中 / 待验收 / 已完成 / 暂缓 |

#### 示例

```text
Task ID：D04-T-Step2-Period-Fix
名称：修复 Step2 AI 路径创建会计期间失败
需求域：D04 凭证生命周期
Owner Spec：improve-step2-source-import-experience
类型：bugfix / 主流程阻塞
前置任务：无
后续受益任务：Step3 AI 生成凭证、Step4 复核、Step5 导出
当前完成层级：L5 页面已有，但失败
目标完成层级：L6 测试与真实数据验证完成
In Scope：定位创建期间失败原因，修复 Step2 创建期间调用链
Out of Scope：不重构结账、不改报表、不改整个期间模型
验收入口：/accounting/step/2?inputMode=ai_generated
```

### 五、后续开发的推荐队列

下面不是按时间长短估计，而是按业务依赖和前后逻辑排序。

#### 第 0 队列：随时插队的阻塞 bug

只要出现阻塞主流程的 bug，应立即优先处理。

范围：

- D01 登录 / 注册 / 鉴权失败。
- D02 无法选择团队或账簿。
- D04 凭证流程中断。
- D08 期间、结账、报表关键错误。
- D06 审计主流程无法继续。

当前可归入此队列的例子：

- Step2 AI 路径创建会计期间失败，应归入 `improve-step2-source-import-experience`，不是新建大需求。

#### 第 1 队列：冻结上下文与主数据边界

目标：让所有正式财务数据有清楚归属，减少后续返工。

建议顺序：

1. D02 Team / Ledger / Project / 当前上下文确认。
2. D07 会计科目、往来单位、期初余额边界确认。
3. D08 会计期间归属边界确认。
4. D04 凭证归属账簿与期间确认。

对应重点文档：

- [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/core-business-concepts-boundary.md)
- [requirements-domain-index.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/requirements-domain-index.md)

#### 第 2 队列：补齐记账闭环

目标：让记账流程可以从基础资料到报表形成可信闭环。

建议顺序：

1. 基础资料稳定：科目、往来、期初。
2. Step1-Step5 凭证流程稳定：输入模式、上传、生成、复核、导出。
3. 会计期间与结账状态稳定。
4. 损益结转补齐。
5. 报表校验稳定。

推荐理由：

- 记账闭环是审计和 AI 的基础。
- 没有稳定凭证和报表，审计测试和 AI 生成的价值会被削弱。

#### 第 3 队列：补齐审计闭环

目标：让审计流程可以从序时簿 / 原始资料到审计发现和报告形成闭环。

建议顺序：

1. 审计 Step3 真实分录 / 序时簿导入稳定。
2. 审计测试 API 稳定。
3. 业务循环审计 API 和页面接入。
4. 内控测试 API 和页面接入。
5. 审计发现持久化与复核留痕。
6. 审计报告真实导出。

推荐理由：

- 审计闭环依赖记账或序时簿数据。
- 审计发现和报告必须建立在真实数据上，不能长期停留在模拟数据。

#### 第 4 队列：AI / EntryTag / 向量增强

目标：增强智能识别、证据充分性、语义标签和检索能力。

建议顺序：

1. EntryTag 与正式分录边界稳定。
2. DocumentTag 与原始资料边界稳定。
3. AI 草稿生成只作为候选，不直接正式入账。
4. 向量同步只作为检索和风险提示，不替代会计规则。
5. Agent 只作为助手，不绕过权限和高风险财务操作。

推荐理由：

- AI 能力必须建立在确定性会计规则之上。
- 先做 AI、后补会计规则，容易造成错误凭证和错误审计结论。

#### 第 5 队列：业务模块扩展

目标：在主流程稳定后，逐步扩展银行、税务、固定资产、库存等模块。

建议顺序：

1. 银行账户 / 银行流水 / 银行对账。
2. 发票 / 税务助手。
3. 固定资产卡片 / 折旧 / 折旧凭证。
4. 进销存 / 库存账 / 成本结转。
5. 合同台账 / 收入确认 / 履约义务。

推荐理由：

- 这些模块最终都会影响凭证、报表和审计。
- 如果凭证和账簿边界没稳定，周边模块会反复返工。

### 六、运筹学视角的任务排序方法

为了让任务排序更稳定，建议采用一个简单的“约束优先评分法”。

每个任务可从 5 个维度打分：

| 维度 | 分数含义 |
|---|---|
| 业务主线价值 | 是否影响记账、报表、审计主流程 |
| 阻塞程度 | 不做是否阻塞多个后续任务 |
| 依赖成熟度 | 前置条件是否已经具备 |
| 边界清晰度 | 是否能明确 In Scope / Out of Scope |
| 验收可见性 | 是否能通过页面、API、测试清楚验收 |

建议优先处理：

```text
高业务价值 + 高阻塞程度 + 依赖已成熟 + 边界清晰 + 可验收
```

不建议优先处理：

```text
价值模糊 + 依赖未成熟 + 边界不清 + 验收困难
```

这相当于运筹学中的“先处理关键路径和瓶颈资源”，而不是平均用力。

### 七、每次开发任务的执行流程建议

后续每个任务建议按以下流程执行：

```text
1. 识别需求域
2. 找 Owner Spec
3. 判断任务类型
4. 写清 In Scope / Out of Scope
5. 确认前置依赖
6. 确认影响文件
7. 执行代码修改
8. 运行测试 / lint / typecheck
9. 给出页面或 API 验收方法
10. 更新对应 tasks/checklist 状态
```

其中第 1-5 步必须在编码前完成。

### 八、边界控制规则

后续每个任务都应遵守以下边界规则：

#### 1. bugfix 不扩功能

例如修复“创建会计期间失败”，只修创建失败原因，不重构结账、报表、导航。

#### 2. 导航任务不改业务逻辑

例如调整 MainShell 菜单，不应顺手改登录、凭证生成或审计测试。

#### 3. 凭证任务不重定义基础资料

凭证流程可以引用科目、往来、期间，但不应在凭证规格中重新定义完整科目体系。

#### 4. AI 任务不绕过人工复核

AI 可以生成草稿、标签和风险提示，但正式凭证、结账、报表仍应由确定性规则和人工确认控制。

#### 5. 报表任务不反向修改凭证录入规则

报表消费凭证、期初和期间数据；如果报表发现数据不平，应通过明确的会计处理任务解决，例如损益结转，而不是在报表里硬调平。

## Assumptions & Decisions

1. 当前以 [requirements-domain-index.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/requirements-domain-index.md) 作为需求归属主索引。
2. 当前以 [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/core-business-concepts-boundary.md) 作为核心业务概念边界文件。
3. 当前实际需求规格数量按只读统计为 57 个 `spec.md`。
4. 历史复盘文档可以参考，但不能单独作为当前完成度依据。
5. 后续不建议继续向 `mixed-needs-split` 类型规格追加新实现任务。
6. 不做技术栈切换；继续基于现有 FastAPI + React + TypeScript + Ant Design + SQLAlchemy 结构推进。
7. 不按时间长短承诺计划，而按依赖顺序、主流程价值和阻塞程度排队。

## Verification Steps

本计划本身不涉及代码修改，验证方式如下：

1. 对照 [requirements-domain-index.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/requirements-domain-index.md)，确认 13 个需求域是否适合作为后续任务归类框架。
2. 对照 [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/core-business-concepts-boundary.md)，确认 Team / Ledger / Project / AccountingPeriod / AccountingEntry 等概念边界是否符合用户的财务实务判断。
3. 后续选择任一新任务时，先填写“任务准入卡片”，验证是否能清楚写出 Owner Spec、In Scope、Out of Scope 和验收方式。
4. 对当前阻塞 bug，例如 Step2 创建会计期间失败，验证其能被准确归入 D04 / `improve-step2-source-import-experience`，而不是新建大需求或误归入报表、结账、导航。

## 建议先讨论的三个决策点

### 决策 1：是否接受 13 个需求域作为后续任务总目录

建议接受。因为当前项目已经有 57 个 spec，如果没有总目录，后续会继续重复造车。

### 决策 2：是否把每个任务都强制写 In Scope / Out of Scope

建议接受。尤其对 bugfix 和体验优化非常重要，可以防止一个小问题演变成大范围重构。

### 决策 3：下一阶段优先队列如何选择

建议采用以下默认顺序：

```text
阻塞 bug
  → 上下文和主数据边界
  → 记账闭环
  → 审计闭环
  → AI / EntryTag / 向量增强
  → 银行 / 税务 / 固定资产 / 进销存扩展
```

如果用户认为当前最重要的是审计产品价值，也可以把“审计闭环”提前到“记账闭环”之后的第一优先级，但不建议在记账凭证、期间、报表还不稳定时启动大量周边业务模块。
