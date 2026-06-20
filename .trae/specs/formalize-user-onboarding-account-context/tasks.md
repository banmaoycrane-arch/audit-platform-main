# Tasks

## Task 1：确认当前 mock 与真实边界
- [x] 1.1 检查首次登录引导是否调用真实团队/账套 API
- [x] 1.2 标记短信验证码、用户协议、隐私政策等开发占位内容
- [x] 1.3 梳理注册/登录后当前跳转逻辑
- [x] 1.4 形成当前风险结论：哪些是真实数据，哪些是临时判断

## Task 2：新增用户上下文状态接口
- [x] 2.1 后端新增或扩展 `/api/auth/context` 接口
- [x] 2.2 返回用户、团队、账套、项目、当前账套、缺失绑定项
- [x] 2.3 返回 `requires_onboarding` 和 `next_action`
- [x] 2.4 后端测试覆盖已绑定用户与未绑定用户

## Task 3：调整注册/登录后跳转逻辑
- [x] 3.1 注册成功后调用用户上下文接口
- [x] 3.2 登录成功后调用用户上下文接口
- [x] 3.3 不再仅用 `teams.length === 0 || ledgers.length === 0` 判断是否 onboarding
- [x] 3.4 根据 `next_action` 跳转 onboarding 或 workspace

## Task 4：升级首次登录引导页面
- [x] 4.1 Onboarding 页面根据缺失项动态展示步骤
- [x] 4.2 引导步骤包括团队、账套、项目、会计主体确认
- [x] 4.3 每一步展示财务含义说明
- [x] 4.4 已有团队/账套时允许选择，不强制新建
- [x] 4.5 未完成绑定时显示临时工作状态说明

## Task 5：历史资料与临时状态最小闭环
- [x] 5.1 后端返回可能的历史资料摘要占位结构，不自动认领
- [x] 5.2 前端展示“待确认历史资料”区域
- [x] 5.3 未确认历史资料不得自动并入当前账套
- [x] 5.4 临时状态用户进入系统时显示限制说明

## Task 6：测试与验证
- [x] 6.1 后端测试：新注册用户返回 requires_onboarding
- [x] 6.2 后端测试：已有团队/账套用户返回可进入工作台
- [x] 6.3 前端检查：注册后按 context 跳转
- [x] 6.4 前端检查：登录后按 context 跳转
- [x] 6.5 运行后端相关测试
- [x] 6.6 运行前端 lint / TypeScript 检查

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 2 and Task 3
- Task 5 depends on Task 2 and Task 4
- Task 6 depends on Task 1-5
