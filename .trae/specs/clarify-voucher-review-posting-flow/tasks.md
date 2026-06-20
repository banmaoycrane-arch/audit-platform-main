# Tasks

## Task 1：上下文与边界确认
- [x] 1.1 回顾当前角色分工：用户是财务/审计业务决策者，AI 是技术实现与需求边界守门员
- [x] 1.2 查重既有 specs，确认不重复实现 `unify-voucher-input-modes` 和 `accounting-step4-real-review`
- [x] 1.3 明确本任务只处理凭证主流程语义和低风险 UI 文案，不做后端过账引擎

## Task 2：会计模式 Step 页面梳理
- [x] 2.1 读取 `Step3GenerateEntries.tsx`，识别“确认、落库、入账”等复核前最终状态文案
- [x] 2.2 读取 `Step4ReviewEntries.tsx`，识别复核页面标题、说明、按钮与空状态
- [x] 2.3 读取 `Step5Export.tsx`，识别导出页面是否缺少“确认入账”语义

## Task 3：低风险 UI 语义调整
- [x] 3.1 将 Step3 调整为“生成 / 保存待复核凭证草稿”口径
- [x] 3.2 将 Step4 调整为“复核调整待复核凭证草稿”口径
- [x] 3.3 将 Step5 调整为“确认入账与导出”口径
- [x] 3.4 保留现有数据结构、接口和导出能力，不新增复杂审批流

## Task 4：验证
- [x] 4.1 运行前端 TypeScript / lint 检查
- [x] 4.2 使用 IDE 诊断检查改动文件
- [x] 4.3 核对 checklist 全部通过并勾选

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
