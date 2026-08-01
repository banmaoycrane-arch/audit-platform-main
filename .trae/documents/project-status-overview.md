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
| **A. Git `origin/main`** | 已推远程、可协作的代码 | **`4b42cc6`**（2026-08-01 push，4 提交已对齐；含 0028–0034 迁移、OS 总纲、排期、事件规格、E1 事件工单） | 对外进度、回滚基准 |
| **B. 本机工作区** | A + 未提交/未跟踪改动 | 工作区干净（`git status --porcelain` 空）；A/B 已对齐 | 你正在改的内容；**不等于已上线** |
| **C. 生产 `47.122.117.76`** | Docker 里跑的实例 | HTTPS **`:8443`**；库约 **122 表**；记录为 alembic **`0028`**（2026-07-21） | 用户实际访问面；下次部署需升到 **0034** |

```text
聊天里「我们定了 OS / 排期 / 事件规格」
        ↓ 2026-08-01 push 后已全部进入 A 层
生产「能打开登录、结构齐、样例账少」
        ↓ C 层；L6 脚本已过、人工签字未做，Alembic 与 A/B 脱节 6 个迁移
```

---

## 3. 产品完成度（人话）

| 主线 | 大概程度 | 说明 |
|------|----------|------|
| 登录 / 团队 / 账簿 | 可用 | L5 |
| 记账（凭证·期间·报表） | 可用，已脚本验收 | L5；**L6 路径 A 脚本 16/16 通过（2026-08-01），待人工签字** |
| 审计 Step1–6 | 可用，已脚本验收 | L5；**L6 路径 B 脚本 13/13 通过（2026-08-01），待人工签字** |
| 导入 / 解析 | 能用，稳定性未验收 | 双场景策略有文档；96% 指标未达标 |
| 证据云 / Staging / 维度 | 已落地增量 | 未经 L6 签字 |
| Agent | 实验 | 非主路径；将来必须绑工单 |
| 税务出口池 | 有壳 | 未接真实税局 |
| **经济事件工单** | **E1 事件壳完成** | **L5；后端+前端落地（2026-08-01），E2/E3/E4 待开工** |
| 固定资产 / 进销存等 | 占位或决策记录 | 不进当前 Sprint |

**整体直觉**：日常演示约 **七成可用**；相对「完整 OS」大约 **三分之一到一半**（L6 人工签字与生产部署是当前最大缺口）。

---

## 4. 本机相对 `main` 多出来什么（B − A）

### 4.1 工作区状态

**2026-08-01 push `4b42cc6` 后**：`git status --porcelain` 为空，本机工作区与 `origin/main` 完全对齐。此前登记的「已改未提交」「未跟踪」内容（模块登记增强、部署 8443、`Contract.deep_analysis`、OS 总纲、实施排期、事件工单规格、`0028`–`0034` 迁移）**均已入库**。

### 4.2 勿提交清单（待清理或已 gitignore）

| 路径 | 性质 |
|------|------|
| `backend/*test*.txt`、`backend/pytest_*.log`、`backend/mypy_*.txt` | 日志垃圾，勿提交 |
| `backend/tmp_*.py` | 临时脚本，待清理 |
| `backend/finance_audit*.db*` | 本地数据库，已 gitignore |

### 4.3 Alembic 务必读懂的一点

| 位置 | Alembic 文件尖端 | 说明 |
|------|------------------|------|
| Git `HEAD` / `origin/main` | **`0034_add_economic_event_workorder`** | 2026-08-01 push 后已与远程对齐 |
| 本机 | **`0034_add_economic_event_workorder`** | 已通过 `alembic upgrade head` 对齐 |
| 生产记录（7/21） | stamp **`0028`** | 与 Git 文件树脱节 6 个迁移（`0029`–`0034`） |

> 下次收口：在生产执行 `alembic upgrade 0034`（新增经济事件 4 表），staging 复验后部署。**需运维操作**。

---

## 5. 工作区地图（本机目录）

| 目录 | 角色 | 是否主开发 |
|------|------|------------|
| **`audit-platform-main`** | 主线 · `main` @ `4b42cc6`（已与 `origin/main` 对齐） | **是** |
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
| ~~**先收口**~~ | ~~push `4b42cc6`（含 E1 事件工单 + 0028–0034 迁移 + OS/排期文档）到 `origin/main`~~ | ✅ 2026-08-01 已 push |
| ~~**P0**~~ | ~~记账 L6 路径 A 脚本验收~~ | **M0** ✅ 2026-08-01 脚本 16/16；**人工签字待办** |
| ~~**P0**~~ | ~~审计 L6 路径 B 脚本验收~~ | **M0** ✅ 2026-08-01 脚本 13/13；**人工签字待办** |
| ~~**P0**~~ | ~~事件工单 E1：表 → API → 事件卡 UI → steps~~ | **M1** ✅ 2026-08-01 后端+前端落地 |
| **P0** | 生产 Alembic 收口：stamp 0028 → 0034 + staging 复验 — **需运维** | 部署前必须 |
| **P0** | L6 人工签字（路径 A + 路径 B）→ 解冻 API 收敛 Phase 2 — **需会计专业用户** | M0 收尾 |
| ~~**P1**~~ | ~~清理服务层根目录重复文件（`seal_*`、`project_service` 等）~~ | ✅ `4f30bf1` 已清理 6 个重复文件 |
| **P1** | API 边界治理 Phase 1（拆 `import-jobs` 三 Router）— Phase 2/3 受 L6 阻塞 | 结构整理 |
| **P1** | 解析 P2 验收（修正回流 + 96% 稳定性） | 非新功能 |
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
| 端口 / 部署同步 | [../deploy/DEPLOY_SYNC.md](../deploy/DEPLOY_SYNC.md)（生产 HTTPS `:8443`，详见 §8） |

---

## 10. 变更记录

| 日期 | 说明 |
|------|------|
| 2026-07-29 | 首版：三层真值 + 本机漂移 + 主线完成度 + 下一步 |
| 2026-08-01 | 修订：E1 事件工单落地、L6 脚本通过、Alembic 0034、main @ 4f30bf1、阻塞项明确 |
| 2026-08-01 | 二次修订：4 提交已 push 到 `origin/main` @ `4b42cc6`；工作区干净；§2/§4/§5/§7 同步真值；阻塞项细化责任方 |
