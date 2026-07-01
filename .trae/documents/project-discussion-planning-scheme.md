# 项目讨论规划方案：审计操作系统 + 多主体会计引擎架构升级

> **文档类型**：项目讨论规划方案
> **更新日期**：2026-07-01
> **适用范围**：核心团队、产品负责人、技术负责人、财务/审计业务专家
> **目标**：为"从结构系统到解释系统"的架构升级制定清晰的讨论路径与实施基础

---

## 一、讨论目标

### 1.1 总体目标

通过一次系统性、结构化的项目讨论，就以下三个核心问题达成团队共识：

1. **架构方向共识**：确认当前系统从"结构系统"向"解释系统"升级的必要性、可行性与节奏。
2. **三大支柱优先级**：明确多准则 Ledger、审计可溯 Entry Graph、审计规则 DSL 三大支柱的优先级与依赖关系。
3. **实施路径共识**：输出未来 6~18 个月的分阶段实施框架，并确定下一阶段立即启动的关键任务。

### 1.2 具体目标

- 理解"语义层"与"规则引擎层"在财务/审计系统中的定位和关系。
- 明确当前数据模型（Team/Project/Ledger/Organization/AccountingEntry）与未来架构的衔接方式。
- 识别 MVP 阶段与未来架构之间的最小必要边界，避免"为远期架构牺牲当前交付"。
- 确定三大支柱的初步数据模型、接口范围和技术选型。
- 分配后续任务Owner、时间节点与验收标准。

---

## 二、讨论议题

### 议题 1：项目当前状态复盘（30 分钟）

- 当前 MVP 完成了哪些核心能力？
- 当前最大的技术债务和业务堵点是什么？
- 用户侧反馈中，哪些指向了"解释系统"的缺失？

### 议题 2：核心架构命题确认（45 分钟）

- **命题**："财务/审计系统的本质不是结构系统，而是解释系统。"
- 是否同意这一判断？
- 如果同意，当前系统距离"解释系统"还差哪些关键能力？
- 如果不同意，当前阶段的真正瓶颈在哪里？

### 议题 3：语义层与规则引擎层的边界与关系（60 分钟）

- **Semantic Layer**：负责"这是什么意思？"（多准则映射、税务解释、审计解释）
- **Rule Engine Layer**：负责"基于这个意思，应该做什么？"（审计程序编排、异常发现）
- 两者如何分层？
- 是否引入独立的 `SourceEvent` 层？
- 是否让 `AccountingEntry` 从属于 `LedgerView`，而 `LedgerView` 从属于 `Ledger`？

### 议题 4：支柱一：多准则 Ledger（60 分钟）

- `Ledger` 是否需要扩展为逻辑视图容器？
- `Ledger` 类型应包括哪些？（statutory / tax / management / consolidation）
- 同一经济事实如何映射到不同准则分录？是否需要 `MappingRule` 层？
- 合并抵消分录如何生成？
- 准则差异调节表如何自动生成？

### 议题 5：支柱二：审计可溯 Entry Graph（60 分钟）

- 是否引入 `SourceEvent` 作为比凭证更原子的业务事件？
- `AccountingEntry` 的证据链应包含哪些字段？
- 证明链的粒度到哪里？（合同 → 发票 → 收付款 → 分录 → 凭证）
- 如何验证证明链的完整性？
- 冲突检测和异常发现如何自动触发？

### 议题 6：支柱三：审计规则 DSL（60 分钟）

- 是否需要一门专门的审计规则语言？
- 语法设计应面向审计师还是技术人员？
- 规则引擎与现有审计程序如何衔接？
- 规则模板如何沉淀为行业最佳实践？
- 规则执行结果如何自动关联到工作底稿？

### 议题 7：实施路径与节奏（45 分钟）

- 当前阶段（MVP）是否需要为未来架构预留扩展点？
- 未来 6 个月的核心目标是什么？
- 是否需要先完成端到端工作流闭环，再启动语义层？
- 技术债务（迁移冲突、测试稳定性）如何排期？

### 议题 8：任务分配与责任矩阵（30 分钟）

- 每个议题的后续任务由谁负责？
- 如何设定验收标准？
- 多久进行一次进度回顾？

---

## 三、参与人员

| 角色 | 人员 | 职责 | 必须参与议题 |
|------|------|------|-------------|
| 项目负责人 / 产品负责人 | 待定 | 把握业务方向、最终决策 | 全部 |
| 财务/审计业务专家 | 待定 | 提供会计准则、审计实务判断 | 议题 4、5、6 |
| 技术负责人 / 架构师 | 待定 | 技术可行性判断、架构设计 | 全部 |
| 后端开发负责人 | 待定 | 数据模型、API 设计、规则引擎实现 | 议题 3、4、5、6、7 |
| 前端开发负责人 | 待定 | 审计工作流、规则配置、可视化界面 | 议题 5、6、7 |
| 测试/QA 负责人 | 待定 | 测试策略、验收标准 | 议题 7、8 |
| 数据/AI 负责人 | 待定 | 语义映射、向量检索、证据链分析 | 议题 5、6 |

**建议参会人数**：5~7 人，避免过多人导致讨论发散。

---

## 四、时间安排

### 4.1 建议总时长

- **半日研讨会**：4.5 小时（含茶歇）
- 或 **两个半天**：每次 2.5 小时，分为"战略对齐"和"方案设计"两阶段

### 4.2 推荐议程（半日版本）

| 时间 | 议题 | 负责人 | 目标产出 |
|------|------|--------|---------|
| 09:00 - 09:30 | 签到、资料发放、开场 | 项目负责人 | 明确讨论目标与规则 |
| 09:30 - 10:00 | 议题 1：当前状态复盘 | 技术负责人 | 形成共识：当前状态与堵点 |
| 10:00 - 10:45 | 议题 2：核心架构命题确认 | 产品负责人 | 确认是否向解释系统升级 |
| 10:45 - 11:00 | 茶歇 | - | - |
| 11:00 - 12:00 | 议题 3：语义层与规则引擎层关系 | 架构师 | 输出分层边界图 |
| 12:00 - 13:30 | 午餐 | - | - |
| 13:30 - 14:30 | 议题 4：多准则 Ledger | 业务专家 + 架构师 | 输出 Ledger 扩展模型草图 |
| 14:30 - 15:30 | 议题 5：审计可溯 Entry Graph | 业务专家 + 后端负责人 | 输出证据链模型草图 |
| 15:30 - 15:45 | 茶歇 | - | - |
| 15:45 - 16:45 | 议题 6：审计规则 DSL | 后端负责人 + 数据负责人 | 输出 DSL 语法范围初稿 |
| 16:45 - 17:30 | 议题 7 + 8：实施路径与任务分配 | 项目负责人 | 输出初步实施框架与责任人 |
| 17:30 - 18:00 | 总结、下一步行动、会议纪要 | 项目负责人 | 会议纪要 + 待办清单 |

### 4.3 议程设计原则

- 上午聚焦"为什么"和"是什么"（战略对齐）
- 下午聚焦"怎么做"（方案设计）
- 每个议题预留 10% 时间用于"异议澄清"和"关键决策"
- 避免连续超过 90 分钟的技术讨论，中间必须有休息

---

## 五、预期成果

### 5.1 直接产出

1. **会议纪要**：记录所有关键决策和未决问题。
2. **架构升级共识文档**：确认是否启动、启动范围、不启动范围。
3. **三大支柱数据模型草图**：
   - Ledger 多准则扩展模型
   - SourceEvent + EntryProofEdge 模型
   - AuditRule DSL 语法范围
4. **实施路径初步框架**：未来 6~18 个月的分阶段计划。
5. **任务分配与责任矩阵**：明确每个后续任务的 Owner、协作人、验收标准。

### 5.2 间接产出

- 团队对"解释系统"形成统一语言。
- 后续需求讨论不再反复摇摆核心概念。
- 建立"远期架构不阻塞当前交付"的工作原则。

---

## 六、讨论流程

### 6.1 会前准备（T-7 天）

1. 主持人向所有参会人员发送本规划方案。
2. 参会人员提前阅读背景文档（见第七节：资料清单）。
3. 每位参会人员会前提交 3 个最关心的关键问题。
4. 主持人汇总问题，形成"关键问题列表"（见第八节）。

### 6.2 会中流程

每个议题按以下四步法推进：

| 步骤 | 名称 | 时长 | 动作 |
|------|------|------|------|
| 1 | 背景陈述 | 10% | 主持人介绍议题背景和相关文档 |
| 2 | 观点发散 | 50% | 参会人员充分表达不同意见 |
| 3 | 收敛聚焦 | 25% | 主持人引导讨论关键决策点 |
| 4 | 决策记录 | 15% | 记录共识、异议、待决策事项 |

### 6.3 会后跟进（T+3 天）

1. 发布会议纪要。
2. 将未决问题升级为"专项任务"，指定 Owner。
3. 更新项目文档：
   - [future-plan-audit-os-multi-entity-kernel.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/future-plan-audit-os-multi-entity-kernel.md)
   - [current-risks-and-tasks.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/current-risks-and-tasks.md)
   - [semantic-layer-and-rule-engine-roadmap.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/semantic-layer-and-rule-engine-roadmap.md)
4. 召开后续专项评审会，逐个解决未决问题。

---

## 七、需要准备的资料清单

### 7.1 会前必读资料（所有参会人员）

| 序号 | 文档 | 路径 | 阅读目的 |
|------|------|------|---------|
| 1 | 未来规划方案：审计操作系统 + 多主体会计引擎 | [future-plan-audit-os-multi-entity-kernel.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/future-plan-audit-os-multi-entity-kernel.md) | 理解架构愿景和三大风险 |
| 2 | 当前风险点与待执行任务清单 | [current-risks-and-tasks.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/current-risks-and-tasks.md) | 了解当前堵点 |
| 3 | 语义层与规则引擎层战略路线图 | [semantic-layer-and-rule-engine-roadmap.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/semantic-layer-and-rule-engine-roadmap.md) | 理解三大支柱和实施路线图 |
| 4 | 核心业务概念边界 | [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/core-business-concepts-boundary.md) | 统一核心概念口径 |
| 5 | 审计 GitHub-style 工作流规划 | [audit-github-style-workflow-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/audit-github-style-workflow-plan.md) | 理解当前工作流模型 |

### 7.2 会前选读资料（技术团队）

| 序号 | 文档 | 路径 | 阅读目的 |
|------|------|------|---------|
| 1 | 数据模型定义 | [backend/app/db/models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py) | 了解当前模型结构 |
| 2 | 数据库迁移文件 | [backend/alembic/versions/](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/alembic/versions/) | 了解迁移历史与冲突 |
| 3 | 项目运行与测试说明 | [AGENTS.md](file:///e:/projects/finance-vector-audit/audit-platform-main/AGENTS.md) | 了解技术环境与测试现状 |

### 7.3 会中展示材料（主持人准备）

| 序号 | 材料 | 用途 |
|------|------|------|
| 1 | 当前架构 ER 图 | 议题 1 复盘 |
| 2 | 目标架构五层图 | 议题 2 命题阐释 |
| 3 | 语义层与规则引擎层关系图 | 议题 3 讨论 |
| 4 | 多准则 Ledger 结构图 | 议题 4 讨论 |
| 5 | 审计可溯 Entry Graph 示例 | 议题 5 讨论 |
| 6 | 审计规则 DSL 示例 | 议题 6 讨论 |
| 7 | 实施路线图甘特图 | 议题 7 讨论 |

### 7.4 会后输出模板

- 会议纪要模板
- 决策记录表
- 任务分配矩阵表
- 数据模型草图模板
- DSL 语法范围模板

---

## 八、关键问题列表

### 8.1 战略层问题

1. 我们是否一致认为当前系统需要从"结构系统"升级为"解释系统"？
2. 这个升级是必须现在启动，还是可以等到 MVP 完成后再启动？
3. 升级过程中，如何确保不牺牲当前交付进度？
4. 如果资源有限，三大支柱中哪一个必须优先启动？

### 8.2 架构层问题

5. 是否必须引入独立的 `SourceEvent` 层？是否可以直接扩展 `AccountingEntry`？
6. `Ledger` 是否应该成为"视图容器"，还是保留为"实体账簿"？
7. `Organization` 是否应该升级为 `Legal Entity + Control Graph`？何时升级？
8. 多准则并存是否意味着同一笔交易需要生成多条分录？如何处理重复？

### 8.3 业务层问题

9. 会计准则、税务规则、管理会计规则之间的差异，哪些最常见？
10. 审计可溯的"证据链"需要细到什么程度？是否必须关联到合同级别？
11. 审计规则 DSL 应该面向审计师（业务人员）还是技术人员？
12. 规则执行结果（Finding）如何与现有审计工作流（Task/Branch/Review）关联？

### 8.4 实施层问题

13. 当前数据库迁移版本冲突是否必须在启动架构升级前修复？
14. 测试稳定性问题如何影响架构升级的节奏？
15. 是否需要先完成端到端审计工作流闭环，再启动语义层？
16. 哪些模块需要作为"扩展点"预留，哪些模块可以暂时保持现状？

### 8.5 资源与组织问题

17. 每个议题需要投入多少人力和时间？
18. 是否需要引入外部咨询（会计准则、审计方法、DSL 设计）？
19. 如何建立定期的架构评审机制？
20. 如何衡量这次架构升级的成功？

---

## 九、后续实施路径初步框架

### 9.1 决策分支

讨论可能产生三种结果：

| 结果 | 含义 | 后续动作 |
|------|------|---------|
| **A. 全面启动** | 立即启动三大支柱设计 | 成立专项小组，分阶段推进 |
| **B. 分阶段启动** | 先完成 MVP，再启动架构升级 | 明确预留扩展点，记录设计约束 |
| **C. 暂不启动** | 当前阶段不升级，继续观察 | 仅更新文档，保持对架构升级的关注 |

### 9.2 推荐路径：分阶段启动（B）

基于当前项目状态，建议采用"分阶段启动"策略：

**第一阶段：MVP 闭环（当前 ~ 3 个月）**
- 完成按业务循环审计端到端
- 完成审计工作流 API 与前端接入
- 修复数据库迁移冲突
- 提升测试稳定性

**第二阶段：语义层试点（3 ~ 6 个月）**
- 引入 `SourceEvent` 和 `EntryProofEdge`
- 在收入确认、采购付款等典型场景建立可溯证明链
- 保留扩展点，为第三阶段做准备

**第三阶段：多准则与规则引擎（6 ~ 12 个月）**
- 扩展 `Ledger` 类型和 `LedgerView`
- 设计并试点 Audit Rule DSL
- 验证规则引擎与审计工作底稿的关联

**第四阶段：Control Graph 与集团审计（12 ~ 18 个月）**
- 升级 `Organization` 为 `Legal Entity + Control Graph`
- 支持合并抵消和复杂集团结构

### 9.3 任务分配矩阵（初步）

| 任务 | Owner | 协作人 | 预计启动时间 | 验收标准 |
|------|-------|--------|-------------|---------|
| 当前 MVP 端到端闭环 | 后端负责人 | 前端负责人 | 立即 | Step1~Step4 流程贯通 |
| 审计工作流接入 | 后端负责人 | 前端负责人 | 立即 | 任务/分支/复核可闭环 |
| 迁移版本冲突修复 | 后端负责人 | 测试负责人 | 1 周内 | 新环境迁移成功 |
| 测试稳定性提升 | 测试负责人 | 后端负责人 | 2 周内 | 核心测试全部通过 |
| 多准则 Ledger 模型设计 | 架构师 | 业务专家 | 3 个月后 | 输出模型草图 |
| SourceEvent 模型设计 | 架构师 | 后端负责人 | 3 个月后 | 输出模型草图 |
| Audit Rule DSL 语法设计 | 后端负责人 | 业务专家 | 6 个月后 | 输出 DSL 范围 |
| Control Graph 模型设计 | 架构师 | 业务专家 | 12 个月后 | 输出模型草图 |

---

## 十、会议纪要模板

### 会议基本信息

- 会议时间：
- 会议地点：
- 主持人：
- 记录人：
- 参会人员：

### 议程与决策

| 议题 | 讨论结论 | 未决问题 | 后续行动 | Owner | 截止日期 |
|------|---------|---------|---------|-------|---------|
| 议题 1 | | | | | |
| 议题 2 | | | | | |
| ... | | | | | |

### 关键决策

1. 
2. 
3. 

### 未决问题

1. 
2. 
3. 

### 后续行动

1. 
2. 
3. 

---

## 十一、附录

### 附录 A：参会人员会前提交问题模板

请每位参会人员在会前 3 天提交以下问题：

1. 你最关心的一个业务问题：
2. 你最关心的一个技术问题：
3. 你最希望本次会议解决的一个问题：

### 附录 B：讨论规则

1. 先理解对方观点，再提出反对意见。
2. 每个议题必须有明确的决策记录，即使是"暂不决策"。
3. 技术可行性判断必须基于现有代码模型或明确假设。
4. 业务判断优先于技术判断，但技术判断必须指出风险。
5. 会议记录人负责实时记录，避免会后信息丢失。

### 附录 C：参考文档索引

- [future-plan-audit-os-multi-entity-kernel.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/future-plan-audit-os-multi-entity-kernel.md)
- [current-risks-and-tasks.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/current-risks-and-tasks.md)
- [semantic-layer-and-rule-engine-roadmap.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/semantic-layer-and-rule-engine-roadmap.md)
- [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/core-business-concepts-boundary.md)
- [audit-github-style-workflow-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/audit-github-style-workflow-plan.md)
- [backend/app/db/models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py)
- [backend/alembic/versions/](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/alembic/versions/)
- [AGENTS.md](file:///e:/projects/finance-vector-audit/audit-platform-main/AGENTS.md)

---

## 十二、变更记录

| 日期 | 变更内容 | 更新人 |
|------|----------|--------|
| 2026-07-01 | 初始创建项目讨论规划方案 | AI 助手 |
