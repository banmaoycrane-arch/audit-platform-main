# 项目总览（重新梳理 · 2026-08-01）

> **用途**: 给决策者与协作 AI 的「一张图」——产品是什么、做到哪、下一步做什么。  
> **真值优先级**: 代码与生产实测 > [code-truth-status.md](./code-truth-status.md) > 本文 > 聊天记忆。  
> **不替代**: 完成度细节仍以 code-truth 为准；排期以 [implementation-plan-and-schedule.md](./implementation-plan-and-schedule.md) 为准。

---

## 1. 一句话定位

**财务向量审计 MVP**，正在演进为 **AI 原生财税 OS**：

- 今天能用的：账簿 / 导入 / 凭证 / 报表 / 审计 Step / 证据云 / 实验 Agent  
- 明天要补的：**事件工单**（调度真相源）+ L6 人工验收  
- 以后再谈的：灰度 SFT、Graph RAG、税局直连、固资全生命周期（知识储备 / 单独立项）

口令：**查是问；事件是办。**

---

## 2. 三层真值（必须分清）

| 层 | 指什么 | 当前尖端 | 怎么用 |
|----|--------|----------|--------|
| **A. Git `origin/main`** | 已推远程、可协作的代码 | **`9579069`**（领先 1 commit） | 对外进度、回滚基准 |
| **B. 本机工作区** | A + 未提交/未跟踪改动 | 见 §4；含 `0028`–`0033` 迁移、OS 总纲、排期、事件规格 | 你正在改的内容；**不等于已上线** |
| **C. 生产 `47.122.117.76`** | Docker 里跑的实例 | HTTPS **`:8443`**；库约 **122 表**；记录为 alembic **`0028`**（2026-07-21） | 用户实际访问面；下次部署需升到 **0033** |

```text
聊天里「我们定了 OS / 排期 / 事件规格」
        ↓ 多数在 B 层文档里，尚未进 A
生产「能打开登录、结构齐、样例账少」
        ↓ C 层；L6 样例未跑，Alembic 与 A/B 脱节
```

---

## 3. 产品完成度（人话）

| 主线 | 大概程度 | 说明 |
|------|----------|------|
| 登录 / 团队 / 账簿 | 可用 | L5 |
| 记账（凭证·期间·报表） | 可用，缺签字 | L5；**L6 人工路径未签字** |
| 审计 Step1–6 | 可用，缺签字 | L5；L6 路径 B 未签字 |
| 导入 / 解析 | 能用，稳定性未验收 | 双场景策略有文档；96% 指标未达标 |
| 证据云 / Staging / 维度 | 已落地增量 | 未经 L6 签字 |
| Agent | 实验 | 非主路径；将来必须绑工单 |
| 税务出口池 | 有壳 | 未接真实税局 |
| **经济事件工单** | **仅规格** | **L1；代码未开工**（M1） |
| 固定资产 / 进销存等 | 占位或决策记录 | 不进当前 Sprint |

**整体直觉**：日常演示约 **七成可用**；相对「完整 OS」大约 **三分之一到一半**（工单与 L6 是最大缺口）。

---

## 4. 本机相对 `main` 多出来什么（B − A）

### 4.1 已改未提交（modified）

| 区域 | 内容直觉 |
|------|----------|
| 模块登记 | 前后端增强（`ModuleRegisterPage`、ingestion/register 服务、API client） |
| 部署 | Caddy / compose **8443**、DEPLOY_SYNC、fix_legacy、同步脚本 |
| 文档 | code-truth、requirements 域索引、README、DEPLOYMENT |
| 模型 | `Contract.deep_analysis` 字段（工作区） |

### 4.2 未跟踪（untracked）——方向已定、仓库未收口

| 路径 | 性质 |
|------|------|
| `ai-native-finance-os-definition.md` | OS 总纲 |
| `implementation-plan-and-schedule.md` | M0–M6 排期 |
| `economic-event-workorder/` | D14 事件工单规格 |
| `deploy/SERVER_PORTS.md` · `DOMAIN_PLAN.md` | 端口与域名 `puqing.cn` |
| `0028_tax_city_egress_pool.py` | 税务池正式迁移文件 |
| `0029_add_contract_deep_analysis.py` | 合同深度分析字段迁移 |
| `backend/*test*.txt` 等 | **日志垃圾，勿提交** |

### 4.3 Alembic 务必读懂的一点

| 位置 | Alembic 文件尖端 | 说明 |
|------|------------------|------|
| Git `HEAD` | **`0027_cash_flow_item`** | 远程仓库里**没有** 0028–0033 文件 |
| 本机 | 未跟踪 **0028–0033** | 已通过 `alembic upgrade head` 对齐到 `0033_ops_missing_indexes` |
| 生产记录（7/21） | stamp **`0028`** | 与 Git 文件树脱节 |

→ 下次收口：把 **0028–0033 全部纳入 Git**，并在生产执行 `alembic upgrade 0033` 后部署新代码。

---

## 5. 工作区地图（本机目录）

| 目录 | 角色 | 是否主开发 |
|------|------|------------|
| **`audit-platform-main`** | 主线 · `main` @ 4d8dd89 | **是** |
| `audit-platform-agent` | Agent 实验 worktree | 否（tip 偏旧） |
| `audit-platform-sandbox` | 沙箱 | 否 |
| `audit-platform-d08-report-fix` | 报表实验 | 否 |
| `audit-platform-ledger-books-step4` | Step4 实验 | 否 |

根目录 `finance-vector-audit` **不是** Git 仓库；说明书在 `audit-platform-main/README.md`。

---

## 6. 架构口径（已拍板、防跑偏）

| 原则 | 含义 |
|------|------|
| OS 核心自研 | 事件工单、过账 API、权限、Tag/金额底线、`event_steps` |
| 开源只做「读懂/想起/推理」 | Ollama/vLLM、Qdrant、LlamaIndex（限 RAG）、Instructor |
| 工单 = 调度真相 | LangGraph 可选薄封装；**禁止**第二套 Agent 中枢 |
| 知识 ≠ 排期 | 量化/SFT/Graph RAG 先攒认知与样本；默认 ≥12 周后专项（B1） |

详：OS 总纲 §5；事件规格；实施排期 §0。

---

## 7. 近期该干什么（与排期对齐）

| 优先级 | 事项 | 里程碑 |
|--------|------|--------|
| **先收口** | 提交 OS/排期/事件规格/端口文档 + Alembic 0028–0033 迁移到 `origin/main` | 文档/迁移真值 |
| **P0** | 记账 L6 路径 A 签字或缺陷台账 | **M0** |
| **P0** | 事件工单 E1：表 → API → 事件卡 UI → steps | **M1** |
| **P0** | 审计 L6 路径 B 签字或缺陷台账 | **M0**（与记账并行） |
| 并行 | Instructor 合同字段 + LlamaIndex→Qdrant | **M2** |
| 随后 | 合同双 Skill（合规 / 入账准备，人不点不过账） | **M3** |
| 明确不做（本季） | 税局直连、固资生产化、先开 SFT/图谱抢主线 | — |

---

## 8. 生产访问（C 层）

| 项 | 值 |
|----|-----|
| 审计平台 | https://47.122.117.76:8443 |
| 官网 | 主机 nginx **:80**（与审计分离） |
| 域名规划 | `puqing.cn` → www / audit（待备案后） |
| 数据画像 | 有用户/账簿；**分录与审计任务几乎为空** → 适合结构验证，不适合当 L6 样例结论 |

---

## 9. 文档怎么找

| 想查 | 打开 |
|------|------|
| 完成度 / 待办 / 生产库数字 | [code-truth-status.md](./code-truth-status.md) |
| 90 天排期 | [implementation-plan-and-schedule.md](./implementation-plan-and-schedule.md) |
| OS 是什么 | [ai-native-finance-os-definition.md](./ai-native-finance-os-definition.md) |
| 事件工单 | [../specs/economic-event-workorder/spec.md](../specs/economic-event-workorder/spec.md) |
| 需求域 D01–D14 | [requirements-domain-index.md](./requirements-domain-index.md) |
| L6 怎么验 | [l6-acceptance-checklist.md](./l6-acceptance-checklist.md) |
| 端口 | [../deploy/SERVER_PORTS.md](../deploy/SERVER_PORTS.md) |

---

## 10. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-07-29 | 首版：三层真值 + 本机漂移 + 主线完成度 + 下一步 |
