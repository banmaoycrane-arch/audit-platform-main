# Tasks

- [x] Task 1: 后端用户模型与密码安全
  - [x] SubTask 1.1: 新增 `backend/app/models/user.py` — User 模型（id, username, phone, email, hashed_password, is_active, agreed_terms, agreed_privacy, created_at, updated_at）
  - [x] SubTask 1.2: 新增 `backend/app/core/security.py` — 密码哈希（bcrypt 或 passlib）、JWT 生成与验证
  - [x] SubTask 1.3: 数据库迁移或自动建表（SQLite 兼容）

- [x] Task 2: 后端认证 API
  - [x] SubTask 2.1: 新增 `backend/app/services/auth_service.py` — 注册、密码登录、验证码登录、用户信息
  - [x] SubTask 2.2: 新增 `backend/app/api/routes_auth.py` — POST /register, POST /login/password, POST /login/sms, POST /sms/code, GET /me
  - [x] SubTask 2.3: 验证码模拟：开发环境直接返回验证码文本，生产环境预留短信接口
  - [x] SubTask 2.4: 在 `main.py` 注册 auth 路由

- [x] Task 3: 后端认证中间件
  - [x] SubTask 3.1: 新增 `backend/app/core/dependencies.py` — `get_current_user` 依赖，从 Authorization Header 解析 JWT
  - [x] SubTask 3.2: 为需要保护的 API 路由添加 `current_user` 依赖（先最小实现，不影响现有测试）

- [x] Task 4: 前端登录页面
  - [x] SubTask 4.1: 新增 `frontend/src/pages/Auth/LoginPage.tsx` — 账号密码登录表单 + 验证码登录切换
  - [x] SubTask 4.2: 新增 `frontend/src/pages/Auth/RegisterPage.tsx` — 注册表单 + 用户协议/隐私政策勾选 + 协议内容 Modal
  - [x] SubTask 4.3: 登录/注册页面样式简洁专业，符合财务系统气质

- [x] Task 5: 前端认证状态管理
  - [x] SubTask 5.1: 新增 `frontend/src/stores/authStore.ts` — 管理 token、user、登录状态，使用 localStorage
  - [x] SubTask 5.2: 新增 `frontend/src/api/client.ts` — login/register/smsCode/me API 方法
  - [x] SubTask 5.3: API 请求自动携带 Authorization Header

- [x] Task 6: 前端路由守卫
  - [x] SubTask 6.1: 修改 `frontend/src/App.tsx` — 包装路由守卫组件
  - [x] SubTask 6.2: 公开路由：`/login`、`/register`、`/home`
  - [x] SubTask 6.3: 受保护路由：其余所有路由，未登录重定向 `/login`
  - [x] SubTask 6.4: `/` 根路由：已登录跳转 `/workspace`，未登录跳转 `/login`

- [x] Task 7: 测试与验证
  - [x] SubTask 7.1: 新增 `backend/tests/test_auth_api.py` — 注册、密码登录、验证码登录、Token 验证、未授权访问
  - [x] SubTask 7.2: 运行后端 `pytest -q`
  - [x] SubTask 7.3: 运行前端 `npm run lint`
  - [x] SubTask 7.4: 手动验证：未登录访问 `/workspace` 重定向 `/login`，登录后跳转 `/workspace`

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4/5 can run in parallel with Task 1-3
- Task 6 depends on Task 4/5
- Task 7 depends on Task 1-6
