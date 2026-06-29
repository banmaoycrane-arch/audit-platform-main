# 功能验收路径与目标次序 Spec

## Why

当前系统已经完成多轮功能修复和合并，但用户需要以会计/审计业务视角进行页面验收。为了避免随机测试导致遗漏，需要把下一步功能测试路径、目标次序和可打开页面整理成明确清单。

## What Changes

- 输出当前角色定位和项目总需求的验收视角。
- 按“先基础环境，再账户账簿，再原始资料导入，再凭证生成，再报表审计”的稳妥顺序安排测试。
- 列出每个测试目标对应的前端页面路径。
- 明确每个页面验收时应观察的关键结果。
- 不新增业务功能，不修改正式代码。

## Impact

- Affected specs: 用户验收、功能测试、工作台导航、账簿文件管理、凭证管理、基础资料、审计流程、报表流程
- Affected code: 无直接代码影响；参考前端路由 `frontend/src/App.tsx` 和 `frontend/src/layout/MainShell.tsx`

## ADDED Requirements

### Requirement: 输出人工验收路径

The system SHALL provide a user-facing acceptance testing path that lists pages, test goals, and expected observations in a stable business order.

#### Scenario: 用户准备测试系统

- **WHEN** 用户要求回顾上下文并输出下一步功能测试路径
- **THEN** 系统应给出可直接打开的页面地址、验收目标和建议测试次序

### Requirement: 按财务业务闭环排序

The system SHALL order tests by accounting business dependency, not by random page order.

#### Scenario: 业务闭环测试

- **WHEN** 用户开始人工验收
- **THEN** 应先验证登录/工作台/团队账簿，再验证基础资料、会计期间、原始资料导入、凭证生成、账簿文件、报表、审计和 AI 助手

### Requirement: 明确角色和总需求

The system SHALL restate the user/developer roles and overall project requirements before listing pages.

#### Scenario: 用户需要上下文确认

- **WHEN** 用户要求明确角色和总需求
- **THEN** 系统应说明用户是财务决策者/专业会计师，开发者是技术实现者/财务逻辑翻译者，并概括项目主线

## MODIFIED Requirements

### Requirement: 页面验收输出

页面验收输出不应只给单个链接，而应包含：页面名称、URL、测试目标、验收观察点和测试顺序。

## REMOVED Requirements

无。
