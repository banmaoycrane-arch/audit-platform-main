# Tasks

- [x] Task 1: 确认注册失败和后端不可访问原因
  - [x] SubTask 1.1: 验证后端 `/health` 和 `/` 的访问状态
  - [x] SubTask 1.2: 验证注册接口 `POST /api/auth/register` 是否可正常返回 Token
  - [x] SubTask 1.3: 检查前端注册页成功后的跳转逻辑

- [x] Task 2: 修复后端可用性识别
  - [x] SubTask 2.1: 在 `backend/app/main.py` 增加 `GET /` 根路径响应
  - [x] SubTask 2.2: 确认 `/health` 保持可用

- [x] Task 3: 修复注册后初始化流程
  - [x] SubTask 3.1: 修改 `frontend/src/pages/Auth/RegisterPage.tsx`，注册成功后获取用户信息
  - [x] SubTask 3.2: 注册后加载团队和账簿列表
  - [x] SubTask 3.3: 无团队或账簿时跳转 `/onboarding`，否则进入 `/workspace`
  - [x] SubTask 3.4: 注册失败时展示可理解错误信息

- [x] Task 4: 补充回归测试
  - [x] SubTask 4.1: 更新 `backend/tests/test_auth_api.py`，覆盖注册成功、获取当前用户
  - [x] SubTask 4.2: 如有必要，补充根路径健康响应测试

- [x] Task 5: 验证与启动服务
  - [x] SubTask 5.1: 运行后端认证相关测试
  - [x] SubTask 5.2: 运行后端 `python -m pytest tests -q`
  - [x] SubTask 5.3: 运行前端 `npm run lint`
  - [x] SubTask 5.4: 启动后端与前端服务，并验证 `http://127.0.0.1:8000/` 和 `http://127.0.0.1:5173/login`

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 2-3
- Task 5 depends on Task 4
