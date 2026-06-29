# Tasks

## Task 1：完成上下文、角色与需求状态确认
- [x] 1.1 确认用户与 AI 的角色分工
- [x] 1.2 确认当前代码库前后端结构
- [x] 1.3 汇总近期已完成需求
- [x] 1.4 汇总未完成或状态不一致需求
- [x] 1.5 明确下一步执行目标为修复人工录入基础资料加载错误

## Task 2：定位人工录入基础资料加载 Internal Server Error
- [x] 2.1 读取 `Step2ImportSource.tsx` 中基础资料加载逻辑
- [x] 2.2 确认前端同时调用了哪些基础资料 API
- [x] 2.3 分别验证会计期间、会计科目、往来单位等后端接口
- [x] 2.4 定位具体抛出 Internal Server Error 的接口或数据结构
- [x] 2.5 判断是否与当前账簿、用户上下文、权限依赖或 ledger_id 有关

## Task 3：修复基础资料加载错误
- [x] 3.1 修复导致 500 的后端接口或依赖逻辑
- [x] 3.2 如果是前端请求参数问题，修正请求参数或错误处理
- [x] 3.3 后端错误改为业务语义明确的 400/404/422 或可理解提示
- [x] 3.4 前端区分显示会计期间、科目、往来单位的加载失败来源
- [x] 3.5 保持人工凭证录入页面其他已完成功能不回退

## Task 4：测试与验证
- [x] 4.1 后端测试覆盖基础资料接口正常返回
- [x] 4.2 后端测试覆盖缺少账簿/权限时的业务错误
- [x] 4.3 前端 TypeScript 检查通过
- [x] 4.4 人工凭证录入页基础资料加载不再显示 Internal Server Error
- [x] 4.5 运行相关后端测试
- [x] 4.6 运行前端 lint / TypeScript 检查

## Task 5：更新文档状态与后续目标
- [x] 5.1 勾选本 spec 的 tasks.md
- [x] 5.2 勾选本 spec 的 checklist.md
- [x] 5.3 记录下一后续目标：核验 `audit-day-book-import` 状态不一致

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 4
