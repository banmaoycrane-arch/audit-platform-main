# Checklist

- [x] 后端 `/` 和 `/health` 可访问
- [x] 后端 `/api/auth/register` 使用唯一账号可返回 Token
- [x] 前端代理 `/api/auth/register` 可正常转发
- [x] 重复用户名提示明确
- [x] 重复手机号提示明确
- [x] 后端不可用提示明确
- [x] 注册成功但团队/账套初始化失败时不误报“注册失败”
- [x] 注册成功后无团队/账套进入 `/onboarding`
- [x] 后端认证测试通过
- [x] 后端全量 `python -m pytest tests -q` 通过
- [x] 前端 `npm run lint` 通过
