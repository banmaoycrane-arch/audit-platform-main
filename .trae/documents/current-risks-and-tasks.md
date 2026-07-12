# 项目风险与待办清单（代码真值派生）

> **更新日期**: 2026-07-05  
> **代码基准**: `main` @ `99a15db`  
> **真值来源**: [code-truth-status.md](./code-truth-status.md) — 冲突以该文档与代码为准  
> **约束**: [AGENTS.md](../../AGENTS.md)

---

## 一、主线目标（不变）

```text
记账：项目 → 账簿 → 分录 → 凭证 → 期间 → 报表
审计：任务 → 业务循环 → 风险 → 证据/底稿 → 发现 → 报告
```

当前阶段重点（`development-plan.md`）：**P2 解析稳定性** + **P3 记账闭环 L6** + **API 收敛**；印章/Money 为 P1 增量，不压主线。

---

## 二、需求域完成度（代码核验 2026-07-05）

| 域 | 主规格 | 代码 L 级 | 说明 |
|----|--------|-----------|------|
| D01 认证 | user-auth-system | **L5** | 登录/SMS/JWT 可用 |
| D02 团队账簿 | team-multi-ledger | **L5** | Team/Project/Ledger 完整 |
| D03 Shell | saas-shell-and-navigation | **L5** | 77+ 页面 |
| D04 凭证 | unify-voucher-input-modes | **L5** | vouchers CRUD + Step 流程；entries 双轨 ⚠️ |
| D05 导入解析 | adaptive-import-engine | **L4** | 5 链路并存；96% 未验收 |
| D06 审计 | audit-day-book-import | **L5** | Step1–6 + 工作流前端 |
| D07 基础资料 | basic-data-pages | **L5** | COA/往来/期初 |
| D08 期间报表 | accounting-period-snapshot | **L5** | 结转/结账/报表 |
| D09 标签向量 | entry-tag-vector-sync | **L4** | entry-tags + document-tags 重叠 |
| D10 Agent | agent-lightweight-llm-api | **L4** | API 有，非主线 |
| D11 业务模块 | — | **L2** | 占位为主 |
| D12 缺陷 | bugfix specs | **L4–L5** | mypy/测试债仍在 |
| D13 计划 | planning docs | **L1** | 本文体系重塑中 |

---

## 三、关键风险（以代码为准）

### 🔴 P0

| # | 风险 | 代码现状 | 动作 |
|---|------|----------|------|
| R1 | **测试未确认全绿** | 666 用例；push 后全量结果待写入 code-truth-status | 跑 pytest，修失败 |
| R2 | **API 多入口重叠** | ~368 端点；import 5 链路、entries/vouchers 双轨 | 执行 api-boundary-governance Phase 2 |
| R3 | **L6 未验收** | 记账/审计缺端到端人工验收记录 | 各走通一条完整路径 |

### 🟠 P1

| # | 风险 | 代码现状 | 动作 |
|---|------|----------|------|
| R4 | 解析稳定性 | correction/quality 已提交；96% 无数据 | P2 指标验收 |
| R5 | 金额 float 残留 | `money/` 已有；file_parser 等可能仍 float | Decimal 迁移 + TD-002 |
| R6 | 服务层重复文件 | 根目录 seal_*、project_service 与子包重复 | 清理 + 单一路径 |
| R7 | 文档与代码脱节 | 多份 checklist 写「88 passed」「B1–B7 未做」 | 以 code-truth-status 为准 |

### 🟡 P2

| # | 风险 | 说明 |
|---|------|------|
| R8 | 标签双体系 | entry-tags(20) + document-tags(17) 同构 |
| R9 | by_cycle 不完整 | 字段有，资料清单匹配无 |
| R10 | mypy 351 错 | TECH_DEBT TD-001 |

### 🟢 已解决（旧文档可归档结论）

| 原风险 | 代码证据 |
|--------|----------|
| 凭证独立 CRUD 缺失 | `routes_vouchers.py` + 三页面 |
| 解析→草稿链路缺失 | `routes_parser_voucher.py` + `ParserVoucherPreview.tsx` |
| 审计工作流前端缺失 | AuditTasks/Review/Workpapers 等页 |
| 服务层扁平未分域 | `99a15db` 领域目录已提交 |
| 登录 SECRET_KEY 500 | `security.py` + `.env` 本地配置 |

---

## 四、待执行任务（Sprint 建议）

### 任务 A：质量门禁（P0）

| ID | 任务 | 验收 |
|----|------|------|
| A1 | 全量 pytest 通过 | `pytest tests -q` 0 failed |
| A2 | 记账 L6 路径 | 录入→过账→结转→结账→报表 人工签字 |
| A3 | 审计 L6 路径 | 任务→序时簿→测试→导出 人工签字 |

### 任务 B：API 收敛（P0–P1）

| ID | 任务 | 验收 |
|----|------|------|
| B1 | vouchers 为凭证唯一主路径 | 前端无新调用 `/entries/vouchers` |
| B2 | 标记 unified-import、/parse deprecated | OpenAPI 或文档注明 |
| B3 | 拆分 import-jobs 三 router | prefix 或文件 1:1 |

### 任务 C：解析 P2（P1）

| ID | 任务 | 验收 |
|----|------|------|
| C1 | 修正回流端到端 | 修正影响下次 parse |
| C2 | 96% 稳定性样张集 | 指标表写入 code-truth-status |

### 任务 D：工程债（P1–P2）

| ID | 任务 | 验收 |
|----|------|------|
| D1 | Money 前端迁移 | 凭证/报表页无 parseFloat |
| D2 | 清理重复 service 文件 | 根目录无与子包重复 |
| D3 | 更新 TECH_DEBT 路径 | 指向 doc_parsing/ 新路径 |

---

## 五、不再作为完成依据的文档

以下仅作历史参考，**不得**用于判断「项目已完成」：

- `next-execution-roadmap/checklist.md` 中「88 passed」
- 本文旧版（2026-07-02）中 B1–B7「待开发」
- `workspace-recap*.md` 中「全部完成」类表述
- 未链接 code-truth-status 的 spec checklist

---

## 六、相关文档

| 文档 | 用途 |
|------|------|
| [code-truth-status.md](./code-truth-status.md) | ★ 状态真值 |
| [api-boundary-governance-plan.md](./api-boundary-governance-plan.md) | API 收敛细则 |
| [development-plan.md](./development-plan.md) | P1–P4 阶段目标 |
| [module-refactoring-plan.md](./module-refactoring-plan.md) | 服务层结构（已执行部分） |
| [requirements-domain-index.md](./requirements-domain-index.md) | 需求域索引 |
