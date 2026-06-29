# Spec：会计模式 Step4 真实分录复核

## Why（背景与动机）

当前 `frontend/src/pages/AccountingMode/Step4ReviewEntries.tsx` 的分录数据来自硬编码的
`mockEntries`，与 Step3「生成 / commit 凭证」环节生成的真实分录完全脱节，导致：

- 用户在 Step3 commit 入账后，进入 Step4 看到的仍是三条样例数据，无法对真实凭证执行复核；
- commit → review → export 的会计闭环（凭证生成 → 复核 → 出具账簿）在前端被截断；
- 从财务视角看，复核环节是内部控制中「不相容职务分离」的关键一环，必须以真实台账为对象，
  否则无法形成有效的二次审核记录。

## What（目标与范围）

### 目标

让 Step4ReviewEntries 真正读取当前导入任务（import_job_id）下、已落库的会计分录，并保留
现有的行内编辑、勾选、批量复核 UI。

### 范围

仅前端页面级改造，**不**新增后端接口（`GET /api/entries?import_job_id=` 已存在）：

- 替换 mock 数据：使用 `api.listEntries(jobId)` 拉取真实分录；
- URL 通过 `?jobId=&periodId=` 携带上下文（与 Step3 一致）；
- 保留现有 UI 元素：行内编辑（科目、摘要）、批量勾选确认、状态 Tag；
- "上一步" 跳回 Step3 时携带 `jobId&periodId`；"下一步" 跳到 Step5 时携带 `jobId`；
- 缺失 jobId 时显示 Alert 警告，禁用下一步按钮；
- `verified` 复核状态使用本地内存 Map（id → boolean）维护，不持久化到后端
  （后续如需持久化再单独立 spec）。

### 不在范围

- 不新增 / 修改任何后端接口；
- 不实现 verified 状态的服务端持久化；
- 不调整 Step3 / Step5 的逻辑；
- 不修改分录字段的真实写库流程。

## 受影响代码

- `frontend/src/pages/AccountingMode/Step4ReviewEntries.tsx`（唯一改动文件）

依赖（已存在，无需改动）：

- `frontend/src/api/client.ts` 中的 `api.listEntries` 与 `AccountingEntry` 类型；
- 后端路由 `GET /api/entries?import_job_id=`。

## ADDED Requirements

1. **REQ-S4-1 真实分录加载**：Step4 进入后必须根据 URL `jobId` 调用 `api.listEntries(jobId)`
   加载真实分录，不再使用任何 mock 数据。
2. **REQ-S4-2 URL 上下文携带**：上一步/下一步跳转必须携带 `jobId`（上一步同时携带
   `periodId`），保持会计闭环上下文不丢失。
3. **REQ-S4-3 跳转 Step5 携带 jobId**：「下一步导出账簿」按钮必须 `navigate` 到
   `/accounting/step/5?jobId=${jobId}`。
4. **REQ-S4-4 缺失 jobId 警告**：当 URL 中缺失 `jobId` 时，必须以 Alert 提示用户从上一步
   重新进入，并禁用「下一步」按钮。
5. **REQ-S4-5 verified 本地状态**：复核勾选状态以本地 `Map<id, boolean>` 形式维护，
   单次会话内有效，不持久化。

## 财务视角解读（写给会计同学）

> 分录复核（vouching review）相当于「会计岗位审核」+「内部稽核」的过程：
>
> - 第一步（Step3）相当于「会计编制」并入账成台账（已写入 `accounting_entries` 表）；
> - 第二步（Step4，本 spec）相当于「主管会计 / 财务复核」对台账逐笔检查；
> - 复核完成后才能进入「报表 / 账簿出具」（Step5）。
>
> 真实接入分录后，复核记录才有审计意义，否则只是演示数据，等同于「形式上的复核」。
