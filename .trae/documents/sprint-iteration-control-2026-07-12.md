# Sprint 迭代节奏与主线边界（2026-07-12）

> **用途**：决策者看「现在在哪、下一步做什么、什么不做」  
> **真值链**：本文 → [code-truth-status.md](./code-truth-status.md) → [development-convergence-charter.md](./development-convergence-charter.md) → 代码  
> **Git 基准**：`main` 在 `99a15db` 之后的大批本地增量（待 push）

---

## 一、进展历史（简史）

| 阶段 | 时间 | 里程碑 | 状态 |
|------|------|--------|------|
| MVP 骨架 | 2025 Q4–2026 Q1 | 导入、向量、风险、凭证 CRUD、审计工作流前端 | ✅ 已合并 `main` |
| 服务层领域化 | 2026-06 | `services/{accounting,audit,doc_parsing,...}` + API 治理文档 | ✅ `99a15db` |
| 结构化 Staging | 2026-07-07~08 | Step4 维度中心、签章链、向量 ledger 隔离、维度门禁 | ✅ 本地，待 L6 签字 |
| 经典报表 + 现金流量表 | 2026-07 | 三大表经典表样、PDF/Excel、行次固定 | ✅ 本地 |
| 证据云空间 × 工作台 | 2026-07-12 | 收件箱/归档、ingest API、工作台聚合、分录反查证据 | ✅ 本地 |
| 对话式 Agent | 2026-07-12 | `/api/agent/assist`、工具白名单、Ollama/云端配置 | ✅ 本地 |
| 生产部署 | 持续 | `47.122.117.76` Docker + legacy schema 补丁 | ⚠️ 须随代码同步 schema |

---

## 二、当前主线（只做这些）

### 主线 A — 记账 v1.0 可验收（P0）

1. 全量 pytest 跑绿（发布闸门）
2. **L6 路径 A** 人工验收：导入 → Step4 维度/签章 → Step5 入账 → 三大表导出  
   依据：[bookkeeping-v1-decision-record.md](../../backend/docs/bookkeeping-v1-decision-record.md)、[l6-acceptance-checklist.md](./l6-acceptance-checklist.md)
3. 生产库 schema 与模型一致（`apply_prod_schema.sh`）

### 主线 B — 证据与待办（P0 已落地，P2 扩展）

| 已交付 | 下一步（P2，按需） |
|--------|-------------------|
| 证据云空间收件箱/归档 | 邮箱 ingest、OSS 同步 |
| 工作台三源聚合 | 待办 → AuditTask、缺附件规则 |
| Ingest API + CLI 示例 | 企业专用 ingest token |
| 分录 → 云空间反查 | 明细账页同样加链接 |

规格：[evidence-cloud-and-icf-workbench/spec.md](../specs/evidence-cloud-and-icf-workbench/spec.md)

### 主线 C — 解析质量（P1，不抢 A 的带宽）

- 修正回流 + 96% 稳定性验收（`document-parsing-engine` spec）
- **不**新增第 6 条导入 API 链路

---

## 三、明确边界（本 Sprint 不做）

| 类别 | 不做项 | 原因 |
|------|--------|------|
| 架构 | API Phase 2 物理收敛、DDD 四层拆包 | 章程冻结至 L6 签字后 |
| 产品 | D11 采购/进销存生产化、固定资产 v1 | 决策记录标为后续 |
| 产品 | 多准则内核、SOX 完整内控底稿 | 非 MVP |
| 工程 | 新增 `unified-import` / `/api/parse` 调用方 | deprecated 只读 |
| Agent | 写操作工具自动执行、流式 SSE | P1 以后 |

---

## 四、迭代节奏建议（2 周一轮）

```text
Week 1
  Mon–Tue  跑绿 pytest + 修发布阻塞（依赖/reportlab 等）
  Wed–Thu  L6 路径 A 人工走一遍，记缺陷
  Fri      合入 GitHub main + 可选生产 sync（schema 必跑）

Week 2
  Mon–Tue  只修 L6 阻塞项（不扩需求）
  Wed      证据云/工作台 P2 中选 1 项（你拍板）
  Thu–Fri  解析 P2 指标或文档回写 code-truth
```

**需求进门规则**：

1. 必须标 P0/P1/P2 并对齐 §二主线之一  
2. 新 API 先查 [api-boundary-governance-plan.md](./api-boundary-governance-plan.md)  
3. 产品文案改导航前，先更新 spec 再改代码  

---

## 五、GitHub 与生产同步清单

### 推送前

- [ ] 不提交 `backend/.env`、`.db`、`qdrant_local_storage/`、一次性 `fix_*.py`、测试输出 txt  
- [ ] `pip install -e .` 后后端可 import  
- [ ] pytest 全绿  

### 推送后

```powershell
git push -u origin main
```

### 生产（代码已在服务器目录时）

```powershell
cd e:\projects\finance-vector-audit\audit-platform-main
.\deploy\sync_and_deploy.ps1
```

或仅 schema：`ssh ... "sh /root/audit-platform-main/deploy/apply_prod_schema.sh"`

---

## 六、文档索引（决策时只打开这些）

| 文档 | 何时看 |
|------|--------|
| [code-truth-status.md](./code-truth-status.md) | 完成度、测试数、P0 待办 |
| [development-convergence-charter.md](./development-convergence-charter.md) | 能不能加 API / 能不能拆 DDD |
| [parser-dual-scenario-strategy.md](./parser-dual-scenario-strategy.md) | 解析相关需求 |
| [bookkeeping-v1-decision-record.md](../../backend/docs/bookkeeping-v1-decision-record.md) | 记账发布范围 |
| [evidence-cloud-and-icf-workbench/spec.md](../specs/evidence-cloud-and-icf-workbench/spec.md) | 云空间/工作台 |
| [DEPLOY_SYNC.md](../../deploy/DEPLOY_SYNC.md) | 上线步骤 |
