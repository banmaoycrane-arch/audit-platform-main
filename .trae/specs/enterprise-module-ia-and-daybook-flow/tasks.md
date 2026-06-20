# Tasks

- [x] Task 1: 重构一级导航信息架构
  - [x] SubTask 1.1: 修改 `MainShell.tsx`，将一级菜单调整为 Agent 助手、财务总账、审计系统、自定义模块、基础资料、银行模块、税务模块等
  - [x] SubTask 1.2: 财务总账下挂凭证管理、账簿管理、总账、明细账、科目余额表、试算平衡表
  - [x] SubTask 1.3: 审计系统下挂审计 Step1-6
  - [x] SubTask 1.4: 自定义模块默认挂凭证管理
  - [x] SubTask 1.5: 银行模块和税务模块提供入口页面或占位页面

- [x] Task 2: 扩展基础资料入口
  - [x] SubTask 2.1: 基础资料菜单增加企业组织架构、员工/协作人员入口
  - [x] SubTask 2.2: 基础资料菜单预留 SKU/物料、仓库、期初数据入口
  - [x] SubTask 2.3: 企业组织架构页面说明实体组织与虚拟核算单位规则
  - [x] SubTask 2.4: 虚拟核算单位必须依托至少一个实体核算对象的说明可见

- [x] Task 3: 工作台模块卡片更新
  - [x] SubTask 3.1: 修改 `WorkspacePage.tsx`，按一级模块展示入口卡片
  - [x] SubTask 3.2: 卡片包含财务总账、审计系统、基础资料、银行模块、税务模块、自定义模块、Agent 助手

- [x] Task 4: 序时簿导入形成分录闭环
  - [x] SubTask 4.1: 明确 Step3 的“序时簿导入”处理结果与凭证导入一致，导入后刷新分录列表
  - [x] SubTask 4.2: 若现有导入服务已支持 CSV 序时簿，补测试验证；若缺失则最小修复
  - [x] SubTask 4.3: 确保序时簿导入生成 EntryTag 映射
  - [x] SubTask 4.4: 确保有分录后可进入 Step4 执行审计测试

- [x] Task 5: 页面/路由补齐
  - [x] SubTask 5.1: 为账簿管理、银行模块、税务模块等尚未实现的入口提供轻量占位页，避免死链
  - [x] SubTask 5.2: 在 `App.tsx` 注册必要路由
  - [x] SubTask 5.3: 不实现复杂业务，只说明后续模块职责和关联关系

- [x] Task 6: 验证
  - [x] SubTask 6.1: 新增或补充序时簿导入测试
  - [x] SubTask 6.2: 运行后端相关 pytest
  - [x] SubTask 6.3: 运行前端 `npm run lint`
  - [x] SubTask 6.4: 验证关键路由：`/ledger/entries`、`/ledger/books`、`/bank/accounts`、`/tax/invoices`、`/basic/org-units`、`/audit/step/3`

# Task Dependencies

- Task 2/3/5 can run after Task 1
- Task 4 can run in parallel with Task 1-3
- Task 6 depends on Task 1-5
