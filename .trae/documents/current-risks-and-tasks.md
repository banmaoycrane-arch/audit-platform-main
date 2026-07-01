# 项目当前风险点与待执行任务清单

> **文档类型**: 项目治理与执行清单
> **更新日期**: 2026-07-02
> **状态**: 已全面核验（基于代码实际状态更新）
> **用途**: 系统性回顾项目当前面临的关键风险点（堵点）与待执行任务，确保团队全面掌握工作重点

---

## 一、项目文档与需求状态总表

### 1.1 规划文档状态（共 47 份）

| 类别 | 文档数 | 已生效 | 历史归档 | 待执行 |
|------|--------|--------|----------|--------|
| 项目治理与路线图 | 8 | 4 | 3 | 1 |
| 架构与未来规划 | 6 | 4 | 2 | 0 |
| 工作流与模块规划 | 10 | 5 | 5 | 0 |
| 导入/解析与凭证规划 | 5 | 5 | 0 | 0 |
| 其他专项规划 | 18 | 14 | 4 | 0 |

### 1.2 需求规格状态（共 57 个 spec，按 D01-D13 域分类）

| 需求域 | 主规格 | 增量规格 | bugfix | planning | mixed | 代码完成度 |
|--------|--------|----------|--------|----------|-------|-----------|
| D01 身份认证 | user-auth-system ✅ | - | 4（已完成） | - | - | **L5** 前端已接入 |
| D02 团队/账簿 | team-multi-ledger ✅ | 4 | - | - | - | **L5** 前端已接入 |
| D03 Shell/导航 | saas-shell-and-navigation ✅ | 5 | - | 1 | 2 | **L5** 前端已接入 |
| D04 凭证生命周期 | unify-voucher-input-modes ✅ | 7 | - | - | 1 | **L5** 前端已接入 |
| D05 原始资料导入 | adaptive-import-engine ✅ | - | - | - | 2 | **L4** API 已暴露 |
| D06 审计证据/流程 | audit-day-book-import ✅ | 7 | - | - | - | **L5** 前端已接入 |
| D07 基础资料 | basic-data-pages ✅ / enhance-coa ✅ | 4 | - | - | - | **L5** 前端已接入 |
| D08 期间/结账/报表 | accounting-period-snapshot ✅ / financial-statements ✅ | 1 | - | - | - | **L5** 前端已接入 |
| D09 EntryTag/AI | entry-tag-vector-sync ✅ / govern-ai-voucher ✅ | 2 | - | - | 1 | **L4** API 已暴露 |
| D10 Agent | agent-lightweight-llm-api ✅ | - | - | 2 | - | **L4** API 已暴露 |
| D11 业务模块 | - | - | - | - | 1 | **L2** 仅占位 |
| D12 缺陷修复 | - | - | 6（已完成） | - | - | **L5** 已修复 |
| D13 项目计划 | - | - | - | 7 | - | **L1** 文档完成 |

### 1.3 关键功能模块代码核验状态（2026-07-02 实际验证）

| 功能模块 | 文件存在 | 代码行数 | 完成层级 | 核验结论 |
|---------|---------|---------|---------|---------|
| 凭证独立 CRUD API | ✅ routes_vouchers.py | 527行 | **L4** | 8个端点，真实业务逻辑（借贷校验/期间校验/状态机） |
| 凭证创建前端页 | ✅ VoucherCreatePage.tsx | 380行 | **L5** | 传统凭证录入表单，借贷平衡实时校验 |
| 凭证编辑前端页 | ✅ VoucherEditPage.tsx | 365行 | **L5** | 回填表单，已入账凭证只读提示 |
| 凭证查询前端页 | ✅ VoucherQueryPage.tsx | 732行 | **L5** | 多维筛选/卡片分页/批量操作 |
| 文件解析引擎 | ✅ parser_engine/ (9个文件) | ~2000行 | **L4** | 格式识别/类型判断/双引擎解析/自动归档 |
| 审计工作流 API | ✅ 9个路由文件 | 多文件 | **L4** | 任务CRUD/分支管理/复核请求/批注/通知 |
| 统一入口界面 | ✅ UnifiedEntryPage.tsx | 265行 | **L5** | 双模式入口/统计概览/快速导航 |
| 序时簿导入服务 | ✅ audit_day_book_service.py | - | **L5** | Voucher创建/分录关联/审计日志（P1已修复） |
| 后端测试文件 | ✅ tests/ (62个文件) | - | **L5** | 覆盖凭证/审计/解析/分录/报表等 |

---

## 二、当前关键风险点（堵点）

### 🟢 风险 1：凭证独立生命周期管理（已解决，原 P0）

**更新状态**: ✅ 已完成
- `routes_vouchers.py` 已暴露完整 CRUD API（8个端点，527行）
- `VoucherCreatePage.tsx`（380行）、`VoucherEditPage.tsx`（365行）、`VoucherQueryPage.tsx`（732行）已实现
- 借贷平衡校验、期间校验、状态机控制均已覆盖
- **残留项**: A10 借贷平衡实时提示组件优化（P1）、A12 端到端验证（P0）

---

### 🟡 风险 2：文件解析直接生成凭证草稿链路（部分解决，原 P0）

**更新状态**: 🔄 部分完成
- `parser_engine/` 框架已具备格式识别、类型判断、双引擎解析（9个模块文件，约2000行）
- 审计序时簿导入链路已修复（Voucher主表记录创建 + 分录关联 + 审计日志）
- **残留项**: B1-B7 独立的"解析结果预览 → 生成凭证草稿"API 和前端预览页尚未开发

**当前阻塞因素**: 解析结果到凭证草稿的直通链路需绕经 ImportJob，前端无预览确认页

---

### 🟡 风险 3：文件解析引擎稳定性不足（P1，维持）

**现状描述**:
- 新 parser_engine 框架已搭建，但规则解析器对复杂版式脆弱
- 旧 `file_parser_service.py` 仍使用 `float` 处理金额，与项目规则冲突
- 存在两套解析体系并存，代码重复

**影响**:
- 真实财务文件解析准确率不稳定
- 金额精度存在误差风险

**当前状态**: ⚠️ P1 阶段处理

**参考文档**: [development-plan-voucher-and-parser.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/development-plan-voucher-and-parser.md)
**关键代码**:
- 旧解析：[backend/app/services/file_parser_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/file_parser_service.py)
- 新解析调度：[backend/app/services/parser_engine/parser_engine_dispatcher.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/parser_engine/parser_engine_dispatcher.py)
- 规则解析器：[backend/app/services/parser_engine/rule_parsers.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/parser_engine/rule_parsers.py)

---

### 🟢 风险 4：数据库迁移版本命名不规范（已核验，非冲突）

**更新状态**: ✅ 已核验，无实际冲突
- `0014_audit_task_ledger_required.py` 的 revision = `0014_audit_task_ledger_required`
- `0014_workpaper_collaboration_package.py` 的 revision = `0014_workpaper_collaboration_package`，down_revision 指向 `0014_audit_task_ledger_required`
- 两个文件 revision ID 不同，形成**线性链式串联**，Alembic 不会报冲突
- **残留项**: 命名前缀均为 "0014" 违反序号唯一约定，建议后续重命名为 0015（低优先级）
**参考文件**: [backend/alembic/versions/](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/alembic/versions/)

---

### 🟡 风险 5：测试覆盖率和稳定性问题

**现状描述**:
- 后端测试存在部分失败（根据 AGENTS.md 说明约 248/255 通过）
- `test_lifecycle.py` 等存在测试代码 bug
- 全量测试运行顺序敏感

**影响**:
- 难以通过 CI/CD 保证质量
- 新功能回归风险高

**当前状态**: ⚠️ 持续存在
**参考文件**: [AGENTS.md](file:///e:/projects/finance-vector-audit/audit-platform-main/AGENTS.md)

---

### 🟡 风险 6：审计工作流（GitHub-style）API 已完成，前端接入未完成

**更新状态**: 🔄 API 已完成，前端待接入
- 后端已有 9 个审计路由文件（routes_audit_workflow/tasks/branches/review/comments/notifications/dashboard/tests/export）
- 配套服务层全部存在（audit_workflow_service/audit_task_service/audit_branch_service/audit_review_service 等）
- **残留项**: F5-F8 前端类型定义、任务看板页面、复核/合并界面、端到端验证

**当前阻塞因素**: 前端缺少审计工作流页面组件，用户无法操作审计协作功能

**参考文档**: [audit-github-style-workflow-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/audit-github-style-workflow-plan.md)

---

### 🟡 风险 7：按业务循环审计（by_cycle）功能已落地但需端到端验证

**现状描述**:
- 前端已添加"按业务循环审计"选项（见 [Step1SelectScope.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/AuditMode/Step1SelectScope.tsx)）
- 后端已更新 schema 和 API 支持 `audit_cycles`（见 [routes_imports.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_imports.py) 和 [import_job.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/schemas/import_job.py)）
- 但完整的资料清单自动匹配、范围校验、提示机制尚未实现

**影响**:
- 用户选择了按业务循环审计，但系统无法自动匹配资料清单
- 范围不一致的提示机制缺失
- 复核人员无法基于范围自动判定导入边界

**当前状态**: 🔄 前端/后端基础已支持，业务逻辑层待完善

---

### 🟢 风险 8：Ledger 多准则并存 / Organization 升级 / Scope Rule（长期规划）

**现状描述**:
- 属于未来架构方向，已在 [future-plan-audit-os-multi-entity-kernel.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/future-plan-audit-os-multi-entity-kernel.md) 和 [semantic-layer-and-rule-engine-roadmap.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/semantic-layer-and-rule-engine-roadmap.md) 中详细规划
- 当前阶段不执行

**当前状态**: ✅ 已规划，不进入当前 Sprint

---

## 三、当前待执行任务清单

### 任务 A：凭证独立生命周期管理（大部分已完成，残留 P1/P0 验收）

| 子任务 | 描述 | 优先级 | 状态 | 负责人 |
|--------|------|--------|------|--------|
| A1-A9 | 后端 CRUD API + 前端三个页面 | P0 | ✅ 已完成 | 后端/前端开发 |
| A10 | 前端组件：借贷平衡实时提示优化 | P1 | 待开发 | 前端开发 |
| A11 | 服务层：凭证号按账簿+期间自动生成 | P1 | 待开发 | 后端开发 |
| A12 | 端到端验证：手工录入 → 编辑 → 过账 → 查询 | P0 | 待验证 | 测试 |

**依赖关系**:
```
A1, A2, A3 → A7, A8, A9 → A12
A4, A5, A6 → A9 → A12
A10, A11 可并行
```

---

### 任务 B：文件解析 → 凭证草稿直接链路（P0，新增）

| 子任务 | 描述 | 优先级 | 状态 | 负责人 |
|--------|------|--------|------|--------|
| B1 | 后端 API：解析文件并返回结构化候选凭证列表 | P0 | 待开发 | 后端开发 |
| B2 | 后端 API：候选凭证确认后生成凭证草稿 | P0 | 待开发 | 后端开发 |
| B3 | 后端 API：解析错误明细与修正建议 | P1 | 待开发 | 后端开发 |
| B4 | 前端页面：解析结果预览页（凭证列表 + 分录） | P0 | 待开发 | 前端开发 |
| B5 | 前端页面：解析错误展示与修正 | P1 | 待开发 | 前端开发 |
| B6 | 前端页面：确认生成凭证草稿 | P0 | 待开发 | 前端开发 |
| B7 | 端到端验证：上传文件 → 解析 → 预览 → 生成草稿 → 编辑 → 过账 | P0 | 待验证 | 测试 |

**依赖关系**:
```
B1 → B2 → B6 → B7
B1 → B3 → B5
B4 → B6
```

---

### 任务 C：文件解析引擎稳定性提升（P1）

| 子任务 | 描述 | 优先级 | 状态 | 负责人 |
|--------|------|--------|------|--------|
| C1 | 统一金额/日期/表头检测工具，消除重复代码 | P1 | 待开发 | 后端开发 |
| C2 | 将 `file_parser_service.py` 金额处理改为 Decimal 或逐步废弃 | P1 | 待开发 | 后端开发 |
| C3 | 强化 `parse_accounting_entry_rules()` 借贷平衡校验 | P1 | 待开发 | 后端开发 |
| C4 | 配置持久化与校验（`GlobalSettings.parser_engine`） | P2 | 待开发 | 后端开发 |
| C5 | 模板持久化（`format_template.py` 自定义模板） | P2 | 待开发 | 后端开发 |
| C6 | 补充 `routes_parser_engine.py` SourceFile 归属校验 | P1 | 待开发 | 后端开发 |

---

### 任务 D：数据库迁移历史冲突修复

| 子任务 | 描述 | 优先级 | 状态 | 负责人 |
|--------|------|--------|------|--------|
| D1 | 重命名冲突的 `0014_workpaper_collaboration_package.py` 为下一个可用版本号 | 高 | 待执行 | 后端开发 |
| D2 | 更新所有相关迁移的 `down_revision` 指向 | 高 | 待执行 | 后端开发 |
| D3 | 在本地/测试环境重新运行迁移验证 | 高 | 待执行 | 后端开发 |
| D4 | 记录迁移历史修复日志 | 中 | 待执行 | 后端开发 |

**参考文件**: [backend/alembic/versions/](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/alembic/versions/)

---

### 任务 E：测试稳定性修复

| 子任务 | 描述 | 优先级 | 状态 | 负责人 |
|--------|------|--------|------|--------|
| E1 | 修复 `test_lifecycle.py` 中未导入 `UserLedgerAuth` 的问题 | 中 | 待执行 | 测试开发 |
| E2 | 隔离共享 SQLite 测试状态，避免测试顺序敏感 | 中 | 待执行 | 测试开发 |
| E3 | 补充凭证独立 CRUD 相关测试 | 高 | 待开发 | 测试开发 |
| E4 | 补充文件解析引擎相关测试 | 高 | 待开发 | 测试开发 |
| E5 | 建立 focused test 运行规范 | 低 | 待执行 | 测试开发 |

**参考文件**: [AGENTS.md](file:///e:/projects/finance-vector-audit/audit-platform-main/AGENTS.md)

---

### 任务 F：审计协作工作流（GitHub-style）API 与前端接入（P1）

| 子任务 | 描述 | 优先级 | 状态 | 负责人 |
|--------|------|--------|------|--------|
| F1 | 后端 API：AuditTask 的完整 CRUD 和状态流转 | 高 | 部分完成 | 后端开发 |
| F2 | 后端 API：AuditWorkBranch 的创建、合并、关闭 | 高 | 部分完成 | 后端开发 |
| F3 | 后端 API：AuditReviewRequest 的多级复核流程 | 高 | 待开发 | 后端开发 |
| F4 | 后端 API：通过 task_id/branch_id 执行审计测试 | 高 | 待开发 | 后端开发 |
| F5 | 前端 API：类型定义和 API 函数 | 中 | 待开发 | 前端开发 |
| F6 | 前端页面：审计工作台/任务看板 | 高 | 待开发 | 前端开发 |
| F7 | 前端页面：复核/合并界面 | 高 | 待开发 | 前端开发 |
| F8 | 端到端验证：工作流完整闭环 | 高 | 待验证 | 测试 |

**参考文档**: [audit-github-style-workflow-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/audit-github-style-workflow-plan.md)

---

### 任务 G：按业务循环审计端到端完善（P1）

| 子任务 | 描述 | 优先级 | 状态 | 负责人 |
|--------|------|--------|------|--------|
| G1 | 后端 API：根据 `audit_cycles` 自动匹配资料清单 | 高 | 待开发 | 后端开发 |
| G2 | 后端 API：导入资料范围与审计范围不一致时提示 | 高 | 待开发 | 后端开发 |
| G3 | 后端 API：按业务循环从账簿截取对应分录 | 高 | 待开发 | 后端开发 |
| G4 | 前端页面：Step4RunTests 添加任务/分支选择 | 高 | 待开发 | 前端开发 |
| G5 | 前端 API：添加新接口的类型定义 | 中 | 待开发 | 前端开发 |
| G6 | 端到端验证：Step1 → Step4 流程贯通 | 高 | 待验证 | 测试 |

---

### 任务 H：未来架构方向（规划阶段，非当前执行）

| 子任务 | 描述 | 优先级 | 状态 | 负责人 |
|--------|------|--------|------|--------|
| H1 | 设计 Ledger 多准则并存模型（Statutory/Tax/Management/Consolidation） | 低 | 规划中 | 架构师 |
| H2 | 设计 Legal Entity + Control Graph 模型 | 低 | 规划中 | 架构师 |
| H3 | 设计 Scope / Engagement Rule 层 | 低 | 规划中 | 架构师 |
| H4 | 设计语义层（Semantic Layer）与审计规则 DSL | 低 | 规划中 | 架构师 |
| H5 | 设计 AccountingEntry 可追溯证明链（audit-proof graph） | 低 | 规划中 | 架构师 |

**参考文档**: [future-plan-audit-os-multi-entity-kernel.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/future-plan-audit-os-multi-entity-kernel.md)

**重要声明**: 任务 H 属于长期规划，当前阶段不执行，仅作为后续版本的设计方向参考。

---

## 四、风险优先级矩阵（2026-07-02 已核验更新）

| 风险/任务 | 紧急程度 | 影响范围 | 当前状态 | 建议处理顺序 |
|-----------|----------|----------|----------|--------------|
| 任务 A：凭证独立生命周期管理 | P1 | 核心业务流程 | ✅ A1-A9已完成，A10-A12残留 | 第 3（验收） |
| 任务 B：文件解析 → 凭证草稿链路 | **P0** | 核心业务流程 | 🔄 部分完成 | **第 1** |
| 任务 C：文件解析引擎稳定性 | P1 | 数据质量 | 待开发 | 第 2 |
| 任务 D：数据库迁移命名规范 | 低 | 部署/规范 | ✅ 已核验无冲突 | 第 5 |
| 任务 E：测试稳定性 | 中 | 质量保障 | 待执行 | 第 3 |
| 任务 F：审计工作流前端接入 | **P1** | 审计功能 | 🔄 API已完成，前端待接入 | **第 2** |
| 任务 G：按业务循环审计 | P1 | 审计功能 | 部分完成 | 第 4 |
| 任务 H：未来架构方向 | 低 | 长期规划 | 已规划 | 第 5 |

---

## 五、下一步重点方向（基于2026-07-02全面核验）

### 5.1 当前项目整体评估

**已完成的里程碑**：
1. ✅ 凭证独立 CRUD API（8端点）+ 前端三个页面（创建/编辑/查询）
2. ✅ 审计工作流后端 API（9个路由文件 + 配套服务层）
3. ✅ 统一入口界面（UnifiedEntryPage）
4. ✅ 序时簿导入 P1 缺陷修复（Voucher创建/分录关联/审计日志）
5. ✅ GitHub 版本控制与分支管理策略
6. ✅ CI 工作流配置（前端构建 + 后端测试 + Lint）
7. ✅ 57个需求规格的 tasks/checklist 已全部勾选

**当前瓶颈**：
1. 🔴 **文件解析 → 凭证草稿直通链路**：解析结果需绕经 ImportJob，无独立预览确认 API
2. 🟡 **审计工作流前端缺失**：9个后端 API 已就绪，但前端无任务看板/复核界面
3. 🟡 **测试稳定性**：约 248/255 通过，存在测试代码 bug 和顺序敏感问题
4. 🟡 **文件解析引擎稳定性**：新旧体系并存，金额精度风险

### 5.2 推荐下一步执行顺序

```
第 1 优先级：任务 B - 文件解析 → 凭证草稿直通链路（P0 核心堵点）
  ├─ B1: 后端 API：解析文件并返回结构化候选凭证列表
  ├─ B2: 后端 API：候选凭证确认后生成凭证草稿
  ├─ B4: 前端页面：解析结果预览页
  └─ B6: 前端页面：确认生成凭证草稿
           ↓
第 2 优先级：任务 F - 审计工作流前端接入（P1，API已就绪）
  ├─ F5: 前端类型定义和 API 函数
  ├─ F6: 前端审计工作台/任务看板
  └─ F7: 前端复核/合并界面
           ↓
第 3 优先级：任务 A 残留 + 任务 E - 端到端验收与测试稳定
  ├─ A12: 凭证 CRUD 端到端验证
  ├─ E1-E2: 修复 test_lifecycle.py 和测试顺序问题
  └─ E3-E4: 补充凭证和解析引擎测试
           ↓
第 4 优先级：任务 C + 任务 G - 解析引擎稳定性 + 业务循环审计
           ↓
第 5 优先级：任务 D 重命名 + 任务 H 长期规划
```

### 5.3 资源协调建议

| 工作内容 | 建议分配 | 理由 |
|---------|---------|------|
| B1-B2 解析→凭证草稿 API | 后端开发 | 核心链路，最高优先 |
| F5-F7 审计工作流前端 | 前端开发 | API已就绪，可立即接入 |
| A12 凭证端到端验证 | 测试开发 | A1-A9已完成，需闭环验收 |
| E1-E2 测试修复 | 测试开发 | 持续进行，不阻塞主线 |
| C1-C3 解析引擎优化 | 后端开发 | B完成后跟进 |

---

## 六、四周冲刺计划（Sprint 2，基于当前实际状态）

**目标**：打通文件解析→凭证草稿直通链路，接入审计工作流前端，完成核心端到端验收

| 周次 | 重点任务 | 输出 |
|------|---------|------|
| 第 1 周 | B1-B2 解析→凭证草稿 API + F5 前端类型定义 | 后端直通API + 前端API层 |
| 第 2 周 | B4/B6 解析预览页 + F6 审计任务看板 | 前端两个核心页面 |
| 第 3 周 | A12 凭证端到端验收 + E1-E2 测试修复 | 验收报告 + 稳定测试 |
| 第 4 周 | F7 复核/合并界面 + B7 端到端测试 | 审计协作闭环 + 解析闭环 |

---

## 七、变更记录

| 日期 | 变更内容 | 更新人 |
|------|----------|--------|
| 2026-07-01 | 初始创建风险点与任务清单 | AI 助手 |
| 2026-07-01 | 根据 planning-review-and-priority-schedule.md 复核结果更新 | AI 助手 |
| 2026-07-02 | **全面核验更新**：基于代码实际状态修正风险1（凭证CRUD已完成）、风险4（迁移无冲突）、风险6（审计API已完成）；新增文档与需求状态总表；更新优先级矩阵和Sprint 2计划 | AI 助手 |

---

## 八、参考文件

- [planning-review-and-priority-schedule.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/planning-review-and-priority-schedule.md) - 规划复核与优先排期报告
- [development-plan-voucher-and-parser.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/development-plan-voucher-and-parser.md) - 当前执行规划
- [future-plan-audit-os-multi-entity-kernel.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/future-plan-audit-os-multi-entity-kernel.md) - 未来架构规划
- [semantic-layer-and-rule-engine-roadmap.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/semantic-layer-and-rule-engine-roadmap.md) - 语义层与规则引擎路线图
- [audit-github-style-workflow-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/audit-github-style-workflow-plan.md) - 审计工作流规划
- [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/core-business-concepts-boundary.md) - 核心业务概念边界
- [task-governance-and-sequencing-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/task-governance-and-sequencing-plan.md) - 任务治理与排序规划
- [backend/app/services/voucher_service.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/voucher_service.py) - 凭证服务
- [backend/app/services/parser_engine/](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/services/parser_engine/) - 解析引擎
- [backend/app/api/routes_entries.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/api/routes_entries.py) - 现有 entries API
- [frontend/src/pages/VoucherQueryPage.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/pages/VoucherQueryPage.tsx) - 前端凭证列表页
- [AGENTS.md](file:///e:/projects/finance-vector-audit/audit-platform-main/AGENTS.md) - 项目运行与测试说明
