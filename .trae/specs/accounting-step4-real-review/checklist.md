# Checklist：会计模式 Step4 真实分录复核

- [x] `Step4ReviewEntries.tsx` 已移除 `mockEntries` 与本地 `Entry` 接口
- [x] 通过 `useSearchParams` 读取 `jobId` 与 `periodId`，并调用 `api.listEntries(jobId)`
- [x] 上一步 / 下一步按钮均携带 `jobId`（上一步同时携带 `periodId`）
- [x] 缺失 `jobId` 时显示 Alert 警告并禁用下一步
- [x] 前端 `npm run lint`（`tsc --noEmit`）通过
