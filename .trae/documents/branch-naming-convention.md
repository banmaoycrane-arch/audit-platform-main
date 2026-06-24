# 分支命名规范

## 目的

本文件用于规范项目分支命名，确保：
- 分支名一眼就能识别所属阶段、功能域、具体功能
- Agent 创建分支时自动遵循统一规范
- 多环境并行开发时分支管理清晰有序
- PR 合理时能快速判断优先级和归属域

## 关联文档

- [需求域分类表](./requirements-domain-index.md) — D01-D13 领域划分
- [任务治理与排序计划](./task-governance-and-sequencing-plan.md) — 执行顺序规则
- [核心业务概念边界](./core-business-concepts-boundary.md) — 概念口径定义

---

## 分支命名格式

### 基本格式

```text
<阶段>/<功能域>-<具体功能>-<序号>
```

### 示例

```text
phase-a/voucher-entry-01
phase-b/bank-reconciliation-01
fix/d04-voucher-validation-01
docs/api-reference-01
```

---

## 阶段划分

根据项目需求优先级规则（核心核算流程 → 基础资料 → 报表 → 审计 → 高级分析），划分为四个阶段：

| 阶段 | 代码 | 说明 | 需求域覆盖 |
|---|---|---|---|
| **记账主线** | `phase-a` | 核心核算流程、基础资料、期间管理、报表 | D04, D07, D08 |
| **审计主线** | `phase-b` | 审计流程、证据、风险识别、底稿管理 | D06 |
| **AI 增强** | `phase-c` | EntryTag、语义分解、向量检索、AI 草稿 | D09 |
| **扩展模块** | `phase-d` | 银行、税务、固定资产、进销存等业务模块 | D11 |

---

## 功能域对照表

基于 [需求域分类表](./requirements-domain-index.md) 的 D01-D13 划分：

| 领域代码 | 功能域 | 分支命名关键词 | 阶段归属 |
|---|---|---|---|
| D01 | 身份认证与访问控制 | `auth`, `login`, `gateway` | 基础设施 |
| D02 | 团队、账套、项目、上下文 | `team`, `ledger`, `project`, `context` | 基础设施 |
| D03 | Shell、导航、工作台、模块入口 | `shell`, `nav`, `workspace` | 基础设施 |
| D04 | 凭证生命周期 | `voucher`, `entry`, `journal` | phase-a |
| D05 | 原始资料导入与解析 | `import`, `parse`, `upload` | phase-a |
| D06 | 审计证据与审计流程 | `audit`, `evidence`, `test`, `report` | phase-b |
| D07 | 基础资料 | `account`, `counterparty`, `period-init` | phase-a |
| D08 | 会计期间、结账、快照、报表 | `period`, `close`, `snapshot`, `report` | phase-a |
| D09 | EntryTag、语义、向量、AI 草稿 | `entrytag`, `semantic`, `vector`, `ai-draft` | phase-c |
| D10 | Agent 与执行型助手 | `agent`, `chat`, `llm` | phase-c |
| D11 | 业务模块 | `bank`, `tax`, `fixed-assets`, `inventory` | phase-d |
| D12 | 缺陷修复与环境诊断 | `fix`, `diagnose` | fix |
| D13 | 项目计划、复盘、路线图 | `plan`, `review`, `roadmap` | docs |

---

## 分支类型

| 分支类型 | 前缀 | 用途 | 示例 |
|---|---|---|---|
| **功能开发** | `phase-*` | 新功能开发，按阶段划分 | `phase-a/voucher-entry-01` |
| **Bug 修复** | `fix` | 缺陷修复、环境诊断 | `fix/d04-voucher-validation-01` |
| **重构** | `refactor` | 代码重构、架构调整 | `refactor/d03-shell-layout-01` |
| **文档** | `docs` | 文档更新、规格编写 | `docs/api-reference-01` |
| **测试** | `test` | 测试用例、验收清单 | `test/acceptance-path-01` |
| **基础设施** | `infra` | 认证、上下文、导航等基础设施 | `infra/d01-auth-gateway-01` |

---

## Agent 任务分工

### 分工原则

每个 Agent 只负责自己领域的分支，不串领域。

### Agent 角色与分支归属

| Agent 角色 | 负责分支类型 | 需求域覆盖 |
|---|---|---|
| **基础设施 Agent** | `infra/*` | D01, D02, D03 |
| **核心核算 Agent** | `phase-a/*` | D04, D05, D07, D08 |
| **审计流程 Agent** | `phase-b/*` | D06 |
| **AI 增强 Agent** | `phase-c/*` | D09, D10 |
| **扩展模块 Agent** | `phase-d/*` | D11 |
| **Bugfix Agent** | `fix/*` | D12 |
| **文档 Agent** | `docs/*` | D13 |

### 任务治理规则

根据 [任务治理与排序计划](./task-governance-and-sequencing-plan.md)：

1. **阻塞 bug → 上下文和主数据边界 → 记账闭环 → 审计闭环 → AI/EntryTag/向量增强 → 银行/税务/固定资产/进销存扩展**
2. **bugfix 不扩功能**：修复具体错误时，只解决该错误的直接原因
3. **导航任务不改业务逻辑**：Shell、菜单、高亮、入口调整不得混入登录、凭证生成、审计测试、报表计算等业务实现
4. **凭证任务不重定义基础资料**：凭证流程可以引用科目、往来、期间，但完整科目、往来、期初等主规则应回到基础资料域

---

## 分支生命周期

### 标准流程

```text
创建分支 → 开发 → 本地测试 → 推送 → 创建 PR → CI checks → 合并 → 删除分支
```

### 关键节点与责任人

| 节点 | 操作 | 负责人 | 说明 |
|---|---|---|---|
| 创建分支 | 按命名规范创建 | Agent | 必须遵循本规范 |
| 开发 | 编写代码、修改文件 | Agent | 只修改 In Scope 内的内容 |
| 本地测试 | Trae 本地验证 | 用户 + Agent | 确保功能可运行 |
| 推送远端 | push 到 GitHub | Agent | 使用 SSH 或 Token 认证 |
| 创建 PR | 填写标题、描述 | Agent | 标题格式：`<阶段>：<功能描述>` |
| CI checks | 自动运行 | GitHub Actions | 等待 checks 通过 |
| 合并 PR | 点击合并 | **用户** | 最终决策权在用户 |
| 删除分支 | 合并后清理 | Agent 或用户 | 保持分支列表整洁 |

---

## PR 标题格式

### 格式

```text
<阶段>：<功能描述>
```

### 示例

```text
Phase A：凭证录入核心功能
Phase B：银行调节表草稿
Phase C：语义分解服务
Fix：凭证借贷平衡校验错误
Docs：API 接口文档更新
```

---

## 实际应用示例

### 当前 PR #11 的分支名分析

原分支名：

```text
cursor/phase-b-audit-workflow-mvp-5d1b
```

问题：
- `cursor/` 前缀是自动生成的，不够语义化
- `mvp` 是阶段描述，但不够具体
- `5d1b` 是随机后缀，无实际意义

建议改成：

```text
phase-b/audit-workflow-01
```

或更细化：

```text
phase-b/bank-reconciliation-01
phase-b/confirmations-01
phase-b/purchase-match-01
```

---

## 常见错误示例

### 错误命名

| 错误示例 | 问题 |
|---|---|---|
| `cursor/xxx-5d1b` | 自动生成前缀，无语义 |
| `feature/new-stuff` | 缺少阶段、功能域 |
| `fix-bug` | 缺少功能域、具体描述 |
| `my-branch` | 完全无语义 |
| `phase-a/all-functions` | 范围过大，应拆分 |

### 正确命名

| 正确示例 | 说明 |
|---|---|---|
| `phase-a/voucher-entry-01` | 阶段 + 功能域 + 功能 + 序号 |
| `fix/d04-voucher-validation-01` | 类型 + 功能域 + 具体问题 + 序号 |
| `docs/api-reference-01` | 类型 + 文档类型 + 序号 |
| `infra/d01-auth-gateway-01` | 类型 + 功能域 + 功能 + 序号 |

---

## 序号规则

### 规则

- 同一 `<阶段>/<功能域>-<具体功能>` 下，序号从 `01` 开始递增
- 序号用于区分同一功能的多次迭代或不同实现方案

### 示例

```text
phase-a/voucher-entry-01  # 第一次实现
phase-a/voucher-entry-02  # 第二次迭代（如重构、扩展）
phase-a/voucher-entry-03  # 第三次迭代
```

---

## 多环境并行开发

### Trae 本地 + Cursor Cloud

| 环境 | 用途 | 分支操作 |
|---|---|---|
| **Trae 本地** | 快速调试、代码修改、依赖安装 | 创建分支、开发、本地测试、推送 |
| **Cursor Cloud** | 验证远端分支、CI checks | 拉取、验证、创建 PR |

### 注意事项

1. **分支同步**：两边修改同一分支时，注意先 pull 再 push
2. **数据库状态**：Trae 本地和 Cursor Cloud 的数据库是独立的，测试数据不一致可能导致测试结果不同
3. **依赖版本**：虽然理论上一致，但可能存在缓存差异

---

## 检查清单

### Agent 创建分支前必须确认

```text
阶段：phase-a / phase-b / phase-c / phase-d / fix / docs / test / infra
功能域：D01-D13 对应关键词
具体功能：清晰描述本次开发目标
序号：01 / 02 / 03 ...
In Scope：本次做什么
Out of Scope：本次明确不做什么
```

### 用户合并 PR 前必须确认

```text
分支名是否符合规范？
PR 标题是否清晰？
CI checks 是否通过？
功能是否在 In Scope 内？
是否影响 Out of Scope 内容？
```

---

## 版本历史

| 日期 | 版本 | 说明 |
|---|---|---|
| 2026-06-24 | v1.0 | 初版，基于需求域分类表和任务治理规则制定 |

---

## 维护说明

本文件由用户和 Agent 共同维护：
- **用户**：决定阶段划分、功能域归属、Agent 分工
- **Agent**：创建分支时自动遵循本规范，不随意创建新命名规则

如有调整需求，请先与用户确认后再修改本文件。