# Tasks

- [x] Task 1: 确认当前后端入口现状。
  - [x] SubTask 1.1: 读取 `backend/app/main.py`，确认当前路由挂载、CORS、健康检查。
  - [x] SubTask 1.2: 读取 `backend/app/core/config.py` 和 `backend/app/core/security.py`，确认 JWT 与配置现状。
  - [x] SubTask 1.3: 搜索认证依赖、中间件、权限控制、request_id、限流等现有能力。

- [x] Task 2: 梳理后端网关需求目标。
  - [x] SubTask 2.1: 用财务系统语言说明网关的业务意义。
  - [x] SubTask 2.2: 明确网关不做具体记账、审计判断，只做统一入口治理。
  - [x] SubTask 2.3: 明确公开接口和受保护接口边界。
  - [x] SubTask 2.4: 明确团队、账簿、期间上下文治理目标。

- [x] Task 3: 形成分阶段规划。
  - [x] SubTask 3.1: 第一阶段：FastAPI 内部网关层。
  - [x] SubTask 3.2: 第二阶段：统一权限与账簿上下文。
  - [x] SubTask 3.3: 第三阶段：请求追踪、审计日志、统一错误。
  - [x] SubTask 3.4: 第四阶段：部署层反向代理/API Gateway。

- [x] Task 4: 输出确认材料。
  - [x] SubTask 4.1: 写入 `spec.md`。
  - [x] SubTask 4.2: 写入 `tasks.md`。
  - [x] SubTask 4.3: 写入 `checklist.md`。
  - [x] SubTask 4.4: 等待用户确认后再进入实施，不直接改业务代码。

# Task Dependencies
- Task 2 depends on Task 1.
- Task 3 depends on Task 2.
- Task 4 depends on Task 3.
