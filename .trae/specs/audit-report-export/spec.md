# Spec：审计报告导出（audit-report-export）

## Why（背景与动机）

当前 `frontend/src/pages/AuditMode/Step6ExportReport.tsx` 使用
`setTimeout` 假装 2 秒后导出成功，并未生成任何真实文件，存在两个问题：

1. **没有可交付物**：审计执行完毕后，注册会计师 / 内部审计员无法把
   「审计发现 + 测试结论」以电子文件形式提交给项目组、被审计单位或归档。
2. **闭环断裂**：审计模式 Step1（选范围）→ Step5（复核发现）的链路
   在最后一步「导出报告」失效，等同于演示性 UI。

## What（目标与范围）

### 目标

让 Step6 真实下载一份「审计测试报告」文件，内容来自 `audit_test_service`
已经生成的报告字典（含 `summary` / `findings` / `forward_test` / `reverse_test`
/ `accuracy_result` / `cutoff_result` / `period` / `scope` 等）。

### 范围

#### 后端

- 新增 `backend/app/api/routes_audit_export.py`：
  - `GET /api/audit-tests/{job_id}/export?format=xlsx|json`
  - 复用现有审计发现表 `audit_findings`（无需重新跑测试），并从
    `_audit_reports` 内存缓存中取最近一次完整报告（若有）。
  - 不支持的格式 → 返回 400；ImportJob 不存在 → 404。
  - `xlsx` 用 `openpyxl` 生成两 Sheet：「概览」与「审计发现」。
  - `json` 直接序列化 dict 返回（UTF-8）。
- 在 `backend/app/main.py` 注册新路由。

#### 前端

- `frontend/src/api/client.ts`：新增 `exportAuditReport(jobId, format)`，
  返回 `Blob`（参考已有 `exportImportJob`）。
- `frontend/src/pages/AuditMode/Step6ExportReport.tsx`：
  - 用 `useSearchParams` 读取 `jobId`，缺失则 Alert 警告并禁用按钮；
  - 移除 PDF / HTML / Word 选项，导出格式只保留 `xlsx` 与 `json`
    （首期不引入 docx 依赖）；
  - `handleExport` 调用 `api.exportAuditReport`，触发 Blob 下载（参考
    `Step5Export.tsx` 已有 `URL.createObjectURL` + 隐藏 `<a>` 模式）；
  - 保留「报告类型」radio（standard/executive/detailed）作为前端展示，
    不影响 API 调用。

### 不在范围

- 不实现 docx / pdf / html 格式（首期最小可用）。
- 不新增审计发现持久化字段；不调整复核流程。
- 不实现「报告类型」对内容的差异化（保留 UI 即可）。

## 受影响代码

- 新增：`backend/app/api/routes_audit_export.py`
- 修改：`backend/app/main.py`（注册路由）
- 修改：`frontend/src/api/client.ts`（新增 `exportAuditReport`）
- 修改：`frontend/src/pages/AuditMode/Step6ExportReport.tsx`（接入真实下载）
- 新增：`backend/tests/test_audit_export.py`

## ADDED Requirements

1. **REQ-AE-1（xlsx 导出）**：`GET /api/audit-tests/{job_id}/export?format=xlsx`
   返回 200，`Content-Type` 为
   `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`，
   附件名形如 `audit_report_{job_id}.xlsx`，至少包含两个 Sheet：
   「概览」与「审计发现」。
2. **REQ-AE-2（json 导出）**：同接口 `format=json` 返回 200，
   `Content-Type: application/json; charset=utf-8`，正文是包含
   `summary` 与 `findings` 字段的合法 JSON。
3. **REQ-AE-3（任务不存在）**：`job_id` 在 `import_jobs` 表中不存在 → 返回
   404，`detail = "导入任务不存在"`。
4. **REQ-AE-4（不支持格式）**：`format` 不在 {`xlsx`, `json`} 内 → 返回 400，
   `detail` 含「不支持的导出格式」。
5. **REQ-AE-5（Step6 真实下载）**：审计模式 Step6 必须调用
   `api.exportAuditReport(jobId, format)` 真实下载 Blob，
   不再使用 `setTimeout` 模拟；缺失 `jobId` 时显示 Alert 警告并禁用导出按钮。

## 财务视角解读（写给会计同学）

> 审计工作底稿的最终形态有两类：
>
> - **结构化数据（json/xlsx）**：可被 IT 审计、复算工具二次加工，便于
>   归档进 OA / EAM；
> - **文字报告（doc/pdf）**：用于正式出具给被审计单位与监管。
>
> 本期我们先做「结构化数据」一档，避免引入 docx 模板依赖；
> 等模板与签字流程成熟后再扩展正式报告导出。从内部控制角度，
> 这一步对应「审计意见的载体输出」，是审计闭环的最后一公里。
