# Checklist

- [x] POST /api/teams 可创建团队
- [x] GET /api/teams 返回用户团队列表
- [x] GET /api/teams/{id}/members 返回团队成员
- [x] POST /api/teams/{id}/members 可添加成员
- [x] GET /api/ledgers/{id}/auths 返回账套授权列表
- [x] DELETE /api/ledgers/{id}/auths/{auth_id} 可撤销授权
- [x] 团队管理页面可用（列表、创建、人员管理）
- [x] 账套管理页面可用（列表、创建、生命周期、授权）
- [x] 登录后引导流程正确（首次登录 → 创建团队 → 创建账套）
- [x] 已有团队/账套用户直接进入工作台
- [x] 工作台用户下拉菜单增加管理入口
- [x] 后端 team 测试通过
- [x] 后端全量 pytest 通过
- [x] 前端 npm run lint 通过
