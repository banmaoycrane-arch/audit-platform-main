# Tasks

- [x] Task 1: 多维度复现与定位注册失败
  - [x] SubTask 1.1: 验证 `GET /`、`GET /health`、`POST /api/auth/register` 的实际响应
  - [x] SubTask 1.2: 验证前端代理 `/api/auth/register` 是否能转发到后端
  - [x] SubTask 1.3: 使用唯一用户名/手机号验证注册成功路径
  - [x] SubTask 1.4: 使用重复用户名/手机号验证业务错误路径
  - [x] SubTask 1.5: 检查注册成功后 `me/teams/ledgers` 初始化是否导致误报

- [x] Task 2: 修复注册页错误分层
  - [x] SubTask 2.1: 修改 `RegisterPage.tsx`，拆分注册请求和后续初始化错误
  - [x] SubTask 2.2: 注册接口成功后即保存 Token 和用户信息，初始化失败不再显示“注册失败”
  - [x] SubTask 2.3: 对后端不可用、用户名重复、手机号重复、协议未同意分别显示明确提示

- [x] Task 3: 改进 API 错误解析
  - [x] SubTask 3.1: 修改 `client.ts`，解析 FastAPI `detail` 字段，避免直接显示原始 JSON 字符串
  - [x] SubTask 3.2: 网络连接失败时返回明确的“后端服务不可用”错误

- [x] Task 4: 补充回归测试
  - [x] SubTask 4.1: 更新后端认证测试，覆盖唯一注册、重复用户名、重复手机号
  - [x] SubTask 4.2: 运行前端类型检查，确保注册页编译通过

- [x] Task 5: 验证
  - [x] SubTask 5.1: 运行 `python -m pytest tests/test_auth_api.py -q`
  - [x] SubTask 5.2: 运行 `python -m pytest tests -q`
  - [x] SubTask 5.3: 运行 `npm run lint`
  - [x] SubTask 5.4: 验证 `http://127.0.0.1:5173/register` 可完成注册并进入 onboarding 或工作台

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 2-3
- Task 5 depends on Task 4
