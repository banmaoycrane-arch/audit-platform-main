# Tasks

## Task 1：调整 MainShell 主导航顺序
- [x] 1.1 将左侧导航一级模块顺序调整为：工作台、Agent 助手、财务总账、审计系统、银行模块、税务模块、固定资产模块、进销存模块、基础资料、管理中心、自定义模块
- [x] 1.2 将管理中心移动到基础资料之后、自定义模块之前
- [x] 1.3 将自定义模块固定放在最底部
- [x] 1.4 保留工作台和 Agent 助手在最前面

## Task 2：固定资产与进销存模块层级化
- [x] 2.1 将固定资产模块改为一级可展开模块
- [x] 2.2 固定资产模块至少包含工作台入口和预留业务入口
- [x] 2.3 将进销存模块改为一级可展开模块
- [x] 2.4 进销存模块至少包含工作台入口和预留业务入口
- [x] 2.5 保持现有 `/fixed-assets` 和 `/inventory` 路由可访问

## Task 3：完善自定义模块预留区
- [x] 3.1 自定义模块保留在导航最底部
- [x] 3.2 自定义模块下保留更具体层级的入口，例如凭证列表、风险列表、工作台
- [x] 3.3 自定义模块文案体现“可扩展/客户自定义/专项入口”含义
- [x] 3.4 不把主业务模块重复作为自定义模块的一级入口

## Task 4：修正导航高亮和父级默认跳转
- [x] 4.1 更新 `workspaceMap`，支持固定资产和进销存父级点击进入工作台
- [x] 4.2 更新 `defaultOpenKeys`，按新模块顺序合理展开
- [x] 4.3 检查 `/fixed-assets`、`/fixed-assets/workspace`、`/inventory`、`/inventory/workspace` 的高亮关系
- [x] 4.4 保持 `/entries`、`/ledger/entries` 等别名高亮不回退

## Task 5：验证导航 UI 顺序
- [x] 5.1 运行前端 TypeScript / lint 检查
- [x] 5.2 验证主导航顺序符合 spec
- [x] 5.3 验证自定义模块位于最底部
- [x] 5.4 验证固定资产和进销存入口可访问
- [x] 5.5 勾选本 spec 的 tasks.md 和 checklist.md

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 1-3
- Task 5 depends on Task 1-4
