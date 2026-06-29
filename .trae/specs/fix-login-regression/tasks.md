# Tasks

- [x] Task 1: 定位登录失败原因
  - [x] SubTask 1.1: 使用现有 API 测试或最小请求验证账号密码登录接口
  - [x] SubTask 1.2: 使用现有 API 测试或最小请求验证验证码获取与验证码登录接口
  - [x] SubTask 1.3: 检查前端登录页错误处理，确认失败信息来源

- [x] Task 2: 修复前后端登录链路
  - [x] SubTask 2.1: 修复本地 Vite 代理地址，统一使用 `127.0.0.1:8000`
  - [x] SubTask 2.2: 修复验证码接口与前端显示逻辑不一致问题
  - [x] SubTask 2.3: 修复登录后团队/账簿初始化异常导致的误报登录失败问题

- [x] Task 3: 补充登录回归测试
  - [x] SubTask 3.1: 更新或新增后端认证测试，覆盖密码登录、验证码获取、验证码登录
  - [x] SubTask 3.2: 增加前端类型检查覆盖，确保登录页编译通过

- [x] Task 4: 验证
  - [x] SubTask 4.1: 运行后端认证相关测试
  - [x] SubTask 4.2: 运行后端 `python -m pytest tests -q`
  - [x] SubTask 4.3: 运行前端 `npm run lint`

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
