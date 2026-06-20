# 登录流程优化与实体卡片展示 Spec

## Why

### 问题一：密码登录无法使用

当前验证码登录创建的用户只有 phone 字段，没有设置 hashed_password，导致用户无法使用密码登录。这是一个功能性缺陷，影响用户体验。

### 问题二：团队/账套/项目展示形式不直观

当前这些实体以表格或单选形式展示，用户无法直观浏览多个实体的状态。需要采用卡片形式展示。

## What Changes

1. **登录后引导设置密码**：验证码登录成功后，如果账号未设置密码，弹窗引导用户设置密码
2. **团队卡片列表**：TeamManagementPage 改为卡片网格形式
3. **账套卡片列表**：LedgerManagementPage 改为卡片网格形式
4. **项目卡片列表**：ProjectsPage 改为卡片网格形式

## Impact

- Affected specs:
  - `team-ledger-management-ui`
  - `saas-shell-and-navigation`
- Affected code:
  - `frontend/src/pages/Auth/LoginPage.tsx` — 登录后引导
  - `frontend/src/pages/Auth/SetPasswordModal.tsx` — 设置密码弹窗
  - `frontend/src/pages/TeamManagementPage.tsx`
  - `frontend/src/pages/LedgerManagementPage.tsx`
  - `frontend/src/pages/ProjectsPage.tsx`

## ADDED Requirements

### Requirement: 登录后引导设置密码

系统 SHALL 在验证码登录成功后引导未设置密码的用户设置密码。

#### Scenario: 登录后检测密码状态
- **WHEN** 用户通过验证码登录成功
- **AND** 账号的 hashed_password 为空
- **THEN** 弹窗提示"设置密码后可以使用账号密码登录"
- **AND** 提供设置密码表单（密码 + 确认密码）
- **AND** 用户可选择"稍后设置"跳过

#### Scenario: 设置密码成功
- **WHEN** 用户填写密码并确认
- **THEN** 调用后端 API 设置密码
- **AND** 成功后关闭弹窗
- **AND** 下次登录时可使用密码登录

### Requirement: 团队卡片展示

系统 SHALL 以卡片网格形式展示团队。

#### Scenario: 团队卡片
- **WHEN** 用户进入团队管理页面
- **THEN** 以卡片网格展示所有团队
- **AND** 每个卡片显示：团队名称、类型、成员数量、账套数量、创建时间
- **AND** 支持点击选中高亮
- **AND** 右上角有操作菜单

### Requirement: 账套卡片展示

系统 SHALL 以卡片网格形式展示账套。

#### Scenario: 账套卡片
- **WHEN** 用户进入账套管理页面
- **THEN** 以卡片网格展示所有账套
- **AND** 每个卡片显示：账套名称、所属团队、状态、创建时间
- **AND** 不同状态用不同边框颜色区分
- **AND** 支持快捷操作按钮
- **AND** 支持状态筛选

### Requirement: 项目卡片展示

系统 SHALL 以卡片网格形式展示项目。

#### Scenario: 项目卡片
- **WHEN** 用户进入项目管理页面
- **THEN** 以卡片网格展示所有项目
- **AND** 每个卡片显示：项目名称、类型、状态、团队、负责人、日期
- **AND** 不同状态用不同颜色标识
- **AND** 支持状态筛选

## MODIFIED Requirements

无。

## REMOVED Requirements

无。
