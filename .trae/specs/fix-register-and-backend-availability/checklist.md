# Checklist

- [x] `GET /` 返回后端服务状态
- [x] `GET /health` 保持可用
- [x] `POST /api/auth/register` 可正常返回 Token
- [x] 注册后可获取当前用户信息
- [x] 注册后无团队/账套时进入 `/onboarding`
- [x] 注册后已有团队/账套时进入 `/workspace`
- [x] 注册失败提示可理解
- [x] 后端认证测试通过
- [x] 后端全量 `python -m pytest tests -q` 通过
- [x] 前端 `npm run lint` 通过
- [x] 后端服务可通过 `http://127.0.0.1:8000/` 访问
- [x] 前端登录/注册页可通过 `http://127.0.0.1:5173/login` 访问
