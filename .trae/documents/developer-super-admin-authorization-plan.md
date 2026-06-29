# 开发者超级管理员与授权审批入口设计规划

## Summary

本规划用于补齐当前系统中“个人设置提交绑定申请后由谁审批”的平台级权限设计缺口。

当前系统已经有团队、账簿、项目、绑定申请、审批页面，但审批权限主要依赖“团队成员或团队下任一账簿 admin”，没有一个平台级、开发者级、可兜底处理所有授权申请的超级管理员定义。

本次规划决定新增“平台级角色”概念，并定义：

```text
开发者超级管理员 = platform_role = "super_admin"
```

其职责：

- 不受团队、账簿、项目绑定限制。
- 可查看全部团队、账簿、项目、绑定申请。
- 可审批所有用户的团队 / 账簿 / 项目绑定申请。
- 可进入专门的超级管理员入口。
- 可作为系统初始化和开发者账号使用。

本次设计优先做 MVP，不引入完整 RBAC 权限表，不新建复杂角色体系，先在 `users` 表增加平台角色字段，并在前后端暴露超级管理员状态和入口。

---

## Current State Analysis

### 1. 用户模型缺少平台级角色

已读文件：

- `backend/app/models/user.py`

当前 `User` 模型字段包括：

- `id`
- `username`
- `phone`
- `email`
- `hashed_password`
- `is_active`
- `agreed_terms`
- `agreed_privacy`
- `team_id`
- `last_ledger_id`

当前没有：

- `platform_role`
- `is_superuser`
- `is_super_admin`
- `developer`
- `system_admin`

因此系统目前无法表达“平台级超级管理员”。

---

### 2. 当前认证上下文只返回业务绑定，不返回平台角色

已读文件：

- `backend/app/services/auth_service.py`
- `frontend/src/api/client.ts`
- `frontend/src/stores/authStore.tsx`

`auth_service.get_auth_context()` 当前返回：

- 用户信息
- 用户团队
- 可访问账簿
- 可访问项目
- 当前账簿
- 缺失绑定项
- 下一步动作
- 是否可不绑定项目使用账簿

但不返回：

- 是否超级管理员
- 平台角色
- 是否可审批全部绑定申请

前端 `AuthContext` 和 `authStore` 也没有保存平台角色。

---

### 3. 当前绑定申请审批权限偏业务侧，缺少平台兜底

已读文件：

- `backend/app/services/binding_request_service.py`
- `backend/app/api/routes_binding_requests.py`
- `frontend/src/pages/TeamManagementPage.tsx`
- `frontend/src/pages/UserSettingsPage.tsx`

绑定申请流程已经存在：

- 用户在 `UserSettingsPage` 或 `OnboardingRequestPage` 提交绑定申请。
- 后端创建 `BindingRequest`。
- 审批人在 `TeamManagementPage` 查看 `scope=reviewable` 的申请。
- 审批通过后写入：
  - `users.team_id`
  - `user_ledger_auths`
  - `project_members`

当前审批判断：

```python
def user_can_review_team(db: Session, reviewer_user_id: int, team_id: int) -> bool:
    reviewer = db.query(User).filter(User.id == reviewer_user_id).first()
    if reviewer and reviewer.team_id == team_id:
        return True

    ledger_ids = [ledger.id for ledger in db.query(Ledger).filter(Ledger.team_id == team_id).all()]
    ...
    return admin_auth is not None
```

问题：

- 同团队成员即可审批，权限偏宽。
- 没有超级管理员兜底。
- 没有开发者账号入口。
- 新系统没有团队/账簿 admin 时，申请可能没人审批。

---

### 4. 前端已有个人设置和团队管理，但无超级管理员入口

已读文件：

- `frontend/src/pages/UserSettingsPage.tsx`
- `frontend/src/pages/WorkspacePage.tsx`
- `frontend/src/layout/MainShell.tsx`
- `frontend/src/App.tsx`

当前已有入口：

- `/user-settings`：个人设置与绑定申请。
- `/team-management`：团队管理和绑定申请审批。
- `/ledger-management`：账簿管理。
- `/projects`：项目管理。
- `/scope-settings`：管理配置。

当前缺口：

- 没有 `/super-admin` 或类似平台管理入口。
- `MainShell` 管理中心没有按超级管理员显示的入口。
- `WorkspacePage` 头像菜单没有超级管理员入口。
- 普通用户与超级管理员在前端上下文中无法区分。

---

### 5. 当前主路由与菜单可承接新页面

已读文件：

- `frontend/src/App.tsx`
- `frontend/src/layout/MainShell.tsx`

现有路由结构已经支持受保护页面：

```tsx
<Route element={<AuthGuard><MainShell /></AuthGuard>}>
  ...
</Route>
```

可以新增：

```tsx
<Route path="/super-admin" element={<SuperAdminPage />} />
```

并在页面内部根据 `authContext.platform_role` 判断是否允许访问。

---

## Proposed Changes

### 1. 后端用户模型增加平台角色字段

#### 文件

- `backend/app/models/user.py`
- `backend/alembic/versions/0016_add_user_platform_role.py`
- `backend/app/main.py`

#### 设计

在 `users` 表增加字段：

```python
platform_role: Mapped[str] = mapped_column(String(40), default="user", nullable=False)
```

角色枚举先限定为：

```text
user        普通业务用户
super_admin 开发者超级管理员
```

不在本轮引入 `developer`、`platform_admin`、`support` 等更多角色，避免过度设计。

#### SQLite 本地兼容

由于项目在 `backend/app/main.py` 中已有 `_ensure_local_sqlite_schema()` 为本地 SQLite 补列，需增加：

```python
"platform_role": "ALTER TABLE users ADD COLUMN platform_role VARCHAR(40) DEFAULT 'user' NOT NULL"
```

#### 迁移

新增 Alembic：

```text
backend/alembic/versions/0016_add_user_platform_role.py
```

`down_revision` 应接当前 head：

```python
down_revision = "0015_add_draft_data_to_import_jobs"
```

升级：

```python
op.add_column("users", sa.Column("platform_role", sa.String(length=40), nullable=False, server_default="user"))
op.alter_column("users", "platform_role", server_default=None)
```

降级：

```python
op.drop_column("users", "platform_role")
```

---

### 2. 新增平台权限服务

#### 文件

- `backend/app/services/platform_permission_service.py`

#### 设计

新增轻量权限服务，先只处理超级管理员判断：

```python
SUPER_ADMIN_ROLE = "super_admin"


def is_super_admin(user: User | None) -> bool:
    return bool(user and user.platform_role == SUPER_ADMIN_ROLE)


def require_super_admin(user: User) -> None:
    if not is_super_admin(user):
        raise PermissionError("需要开发者超级管理员权限")
```

#### 为什么不放到绑定申请服务里

超级管理员后续还会用于：

- 平台管理入口。
- 所有绑定申请审批。
- 用户列表和授权兜底。
- 系统配置或诊断入口。

因此单独放服务文件，避免权限判断继续分散。

---

### 3. 支持开发者账号初始化为超级管理员

#### 文件

- `backend/app/core/config.py`
- `backend/app/services/auth_service.py`

#### 设计

新增配置项：

```python
SUPER_ADMIN_USERNAMES: str = ""
SUPER_ADMIN_PHONES: str = ""
```

约定环境变量：

```text
SUPER_ADMIN_USERNAMES=developer,admin
SUPER_ADMIN_PHONES=13800000000
```

在登录上下文或注册/短信登录后调用一个轻量同步函数：

```python
def sync_configured_super_admin(db: Session, user: User) -> User:
    if user.username in configured_usernames or user.phone in configured_phones:
        user.platform_role = "super_admin"
        db.add(user)
        db.commit()
        db.refresh(user)
    return user
```

#### 决策

- 不硬编码具体用户名或手机号。
- 不把第一个注册用户自动设为超级管理员，避免误授权。
- 由开发者在 `.env` 明确配置开发者账号。
- 该配置只负责“提权为超级管理员”，不负责创建账号；账号仍通过现有注册/登录流程产生。

---

### 4. Auth Context 返回平台角色和超级管理员状态

#### 后端文件

- `backend/app/services/auth_service.py`
- `backend/app/api/routes_auth.py`

#### 前端文件

- `frontend/src/api/client.ts`
- `frontend/src/stores/authStore.tsx`

#### 后端响应新增

在 `get_auth_context()` 的 `user` 对象中增加：

```python
"platform_role": user.platform_role,
"is_super_admin": user.platform_role == "super_admin",
```

同时在顶层增加：

```python
"platform_role": user.platform_role,
"is_super_admin": user.platform_role == "super_admin",
```

#### 为什么 user 内和顶层都返回

- `user` 内字段便于个人设置展示。
- 顶层字段便于页面守卫和菜单判断。

#### 前端类型新增

`frontend/src/api/client.ts`：

```ts
export type AuthContext = {
  user: {
    ...
    platform_role?: 'user' | 'super_admin' | string
    is_super_admin?: boolean
  }
  platform_role?: 'user' | 'super_admin' | string
  is_super_admin?: boolean
  ...
}
```

`frontend/src/stores/authStore.tsx` 的 `AuthContextState` 增加：

```ts
platform_role?: string
is_super_admin?: boolean
```

`User` 增加：

```ts
platform_role?: string
is_super_admin?: boolean
```

---

### 5. 超级管理员绕过业务绑定限制

#### 文件

- `backend/app/services/auth_service.py`
- `backend/app/core/dependencies.py`
- `frontend/src/App.tsx`

#### 后端 Auth Context 行为

超级管理员不应被 `missing_bindings` 阻断。

在 `get_auth_context()` 中：

```python
if is_super_admin(user):
    missing_bindings = []
    next_action = "workspace"
    temporary_status = "ready"
```

但仍返回已有团队、账簿、项目列表，供展示和管理。

#### 账簿访问

`get_current_ledger()` 当前会检查 `user_has_ledger_access()`。

本轮计划只做“超级管理员入口与审批不受限制”，不强行让超级管理员进入所有账簿业务页面直接读写财务数据，避免过度扩大数据访问风险。

如确需超级管理员进入任何账簿业务页，后续单独设计“选择账簿后以平台运维身份访问并留痕”。

#### 前端 LedgerDataGuard

`frontend/src/App.tsx`：

如果 `authContext?.is_super_admin` 为 true，即使 `userLedgers.length === 0`，也允许进入被 `LedgerDataGuard` 包裹的页面；但具体业务页若需要 `currentLedgerId`，仍由页面自身提示选择账簿。

---

### 6. 绑定审批支持超级管理员审批全部申请

#### 文件

- `backend/app/services/binding_request_service.py`

#### 变更

在 `user_can_review_team()` 开头增加：

```python
reviewer = db.query(User).filter(User.id == reviewer_user_id).first()
if platform_permission_service.is_super_admin(reviewer):
    return True
```

`list_binding_requests(scope="reviewable")` 对超级管理员返回全部申请。

`approve_binding_request()` 与 `reject_binding_request()` 复用 `user_can_review_team()`，自然支持超级管理员审批全部申请。

#### 本轮不收紧普通审批权限

当前普通审批“同团队成员可审批”偏宽，但这是已有行为。

本轮用户明确要求补“超级管理员定义和入口”，因此暂不改变普通审批规则，避免影响现有团队管理流程。

后续可单独规划：团队成员角色表 + 审批权限收紧。

---

### 7. 新增超级管理员后端 API

#### 文件

- `backend/app/api/routes_super_admin.py`
- `backend/app/main.py`

#### 路由

新增前缀：

```text
/api/super-admin
```

#### 接口 1：平台概览

```text
GET /api/super-admin/overview
```

返回：

```json
{
  "user_count": 0,
  "team_count": 0,
  "ledger_count": 0,
  "project_count": 0,
  "pending_binding_request_count": 0
}
```

#### 接口 2：全部绑定申请

```text
GET /api/super-admin/binding-requests?status=pending|approved|rejected|all
```

返回复用现有 `BindingRequestResponse` 结构，附带团队、账簿、项目名称。

#### 接口 3：审批/驳回

不新增独立审批接口，前端继续调用：

```text
POST /api/binding-requests/{request_id}/approve
POST /api/binding-requests/{request_id}/reject
```

因为绑定审批服务已经支持超级管理员。

#### 权限

所有 `/api/super-admin/*` 接口调用：

```python
platform_permission_service.require_super_admin(current_user)
```

---

### 8. 前端 API 客户端补超级管理员接口

#### 文件

- `frontend/src/api/client.ts`

新增类型：

```ts
export type SuperAdminOverview = {
  user_count: number
  team_count: number
  ledger_count: number
  project_count: number
  pending_binding_request_count: number
}
```

新增 API：

```ts
getSuperAdminOverview: () => request<SuperAdminOverview>('/api/super-admin/overview')
listSuperAdminBindingRequests: (status?: string) => request<BindingRequest[]>(`/api/super-admin/binding-requests${status ? `?status=${status}` : ''}`)
```

---

### 9. 新增超级管理员前端页面

#### 文件

- `frontend/src/pages/SuperAdminPage.tsx`

#### 页面路径

```text
/super-admin
```

#### 页面内容

页面标题：

```text
开发者超级管理员
```

卡片统计：

- 用户数
- 团队数
- 账簿数
- 项目数
- 待审批绑定申请数

绑定申请表格：

- 申请人
- 手机号
- 团队
- 账簿
- 项目
- 申请角色
- 状态
- 申请原因
- 创建时间
- 操作：通过 / 驳回

审批操作：

- 通过：调用 `api.approveBindingRequest(request.id, reviewComment)`
- 驳回：调用 `api.rejectBindingRequest(request.id, reviewComment)`
- 操作后刷新概览和申请列表。

#### 非超级管理员访问

如果 `authContext?.is_super_admin` 不是 true：

展示 `Result status="403"`：

```text
需要开发者超级管理员权限
```

并提供返回工作台按钮。

---

### 10. 前端入口：工作台头像菜单与主菜单

#### 文件

- `frontend/src/pages/WorkspacePage.tsx`
- `frontend/src/layout/MainShell.tsx`
- `frontend/src/App.tsx`

#### 工作台头像菜单

如果 `authContext?.is_super_admin` 为 true，在头像下拉中增加：

```text
开发者超级管理员
```

点击进入：

```text
/super-admin
```

#### MainShell 管理中心

如果 `authContext?.is_super_admin` 为 true，在“管理中心”增加：

```text
开发者超级管理员
```

点击进入：

```text
/super-admin
```

当前 `navItems` 是模块级常量，不能直接读取 hook。实施时需要改成函数：

```tsx
function buildNavItems(isSuperAdmin: boolean) { ... }
```

在 `MainShell()` 内通过 `useAuthStore()` 获取 `authContext`：

```tsx
const { authContext } = useAuthStore()
const navItems = buildNavItems(Boolean(authContext?.is_super_admin))
```

#### App 路由

新增：

```tsx
<Route path="/super-admin" element={<SuperAdminPage />} />
```

---

### 11. 用户设置页展示平台身份

#### 文件

- `frontend/src/pages/UserSettingsPage.tsx`

#### 变更

在个人状态中增加：

```text
平台角色：普通用户 / 开发者超级管理员
```

如果是超级管理员，展示提示：

```text
当前账号是开发者超级管理员，可审批全部绑定申请并进入平台管理入口。
```

提供按钮：

```text
进入开发者超级管理员
```

---

## Assumptions & Decisions

### 决策 1：超级管理员是平台角色，不是账簿 admin

账簿 admin 只管理某个账簿。

超级管理员管理平台级初始化、授权兜底和审批入口。

二者不混用。

---

### 决策 2：MVP 使用 `users.platform_role`

本轮不新增复杂 RBAC 表。

原因：

- 当前项目权限体系仍在快速演进。
- 用户需求是先补“开发者超级管理员定义和入口”。
- `users.platform_role` 足以表达 MVP 的超级管理员。

---

### 决策 3：开发者账号通过环境变量配置，不硬编码

不写死用户名或手机号。

使用：

```text
SUPER_ADMIN_USERNAMES
SUPER_ADMIN_PHONES
```

开发者在本地或部署环境中明确配置。

---

### 决策 4：超级管理员可审批全部绑定申请

这是本次需求的核心。

审批仍使用原有绑定申请服务，保证审批结果继续写入：

- 用户团队
- 账簿授权
- 项目成员

---

### 决策 5：本轮不重构团队成员角色表

当前团队角色没有正式落库，这是权限体系长期缺口。

但本轮只补超级管理员和审批入口，不引入 `team_members` 表，避免范围过大。

后续可单独规划：团队 owner/admin/member/viewer 角色落库与审批权限收紧。

---

### 决策 6：超级管理员暂不默认拥有所有账簿业务数据读写权

用户说“开发者账号不受任何限制”，本轮落实为：

- 不受绑定限制进入平台管理。
- 可审批全部绑定申请。
- 可查看平台概览。

但不在本轮直接让超级管理员绕过所有账簿业务接口的数据权限读写，避免财务数据安全风险。

如果后续确需“开发者超级管理员可进入任意账簿业务页面”，应增加显式账簿选择、运维身份提示和审计日志。

---

## Verification Steps

### 后端验证

1. 语法检查：

```powershell
python -m py_compile backend/app/models/user.py backend/app/services/auth_service.py backend/app/services/platform_permission_service.py backend/app/services/binding_request_service.py backend/app/api/routes_super_admin.py backend/app/main.py backend/alembic/versions/0016_add_user_platform_role.py
```

2. Alembic 单 head：

```powershell
cd backend
python -m alembic heads
```

期望：

```text
0016_add_user_platform_role (head)
```

3. 迁移升级检查：

```powershell
cd backend
python -m alembic upgrade head
```

4. Auth Context 验证：

- 普通用户：`platform_role = user`，`is_super_admin = false`。
- 配置在 `SUPER_ADMIN_USERNAMES` 或 `SUPER_ADMIN_PHONES` 的开发者账号：`platform_role = super_admin`，`is_super_admin = true`。

5. 绑定审批验证：

- 普通用户仍只能看到原有 `reviewable` 范围。
- 超级管理员能在 `/api/super-admin/binding-requests` 看到全部申请。
- 超级管理员能审批任意团队、账簿、项目绑定申请。

---

### 前端验证

1. 构建：

```powershell
pnpm.cmd build:frontend
```

2. 静态诊断文件：

- `frontend/src/pages/SuperAdminPage.tsx`
- `frontend/src/pages/WorkspacePage.tsx`
- `frontend/src/layout/MainShell.tsx`
- `frontend/src/App.tsx`
- `frontend/src/stores/authStore.tsx`
- `frontend/src/api/client.ts`

3. 普通用户体验：

- 工作台头像菜单不显示“开发者超级管理员”。
- 直接访问 `/super-admin` 显示 403。

4. 超级管理员体验：

- 工作台头像菜单显示“开发者超级管理员”。
- 左侧“管理中心”显示“开发者超级管理员”。
- `/super-admin` 显示平台概览和全部绑定申请。
- 可以审批或驳回绑定申请。

---

## Implementation Order

1. 新增数据库字段和迁移：`users.platform_role`。
2. 新增 `platform_permission_service.py`。
3. 在 `auth_service.py` 中同步配置的超级管理员账号，并返回平台角色。
4. 修改绑定申请服务，使超级管理员可查看/审批全部申请。
5. 新增 `/api/super-admin` 后端接口并挂载到 `main.py`。
6. 更新前端 API 类型与方法。
7. 更新 `authStore` 保存 `is_super_admin` 和 `platform_role`。
8. 新增 `SuperAdminPage.tsx`。
9. 更新 `App.tsx` 路由。
10. 更新 `WorkspacePage.tsx` 头像菜单入口。
11. 更新 `MainShell.tsx` 管理中心入口。
12. 更新 `UserSettingsPage.tsx` 展示平台身份。
13. 执行后端语法、迁移检查和前端构建验证。
