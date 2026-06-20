# 进度确认验证清单

## 已完成检查
- [x] 后端目录结构完整 (backend/app/api, services, db, schemas)
- [x] 前端目录结构完整 (frontend/src/pages, components, api)
- [x] 根目录配置文件完整 (README.md, package.json, docker-compose.yml, .env.example)
- [x] 前端类型检查通过 (pnpm --dir frontend lint)
- [x] 前端构建成功 (pnpm --dir frontend build)
- [x] 后端虚拟环境依赖安装完成 (backend/venv)
- [x] 后端测试通过 (pytest backend/tests → 2 passed)
- [x] 后端健康检查正常 (GET /health → 200 {"status":"ok"})
- [x] 导入任务创建成功 (POST /api/import-jobs → job 8, status=created)
- [x] 文件上传成功 (POST /api/import-jobs/{id}/files → file 3)
- [x] 导入处理成功 (POST /api/import-jobs/{id}/process → 16 entries, completed)
- [x] 分录列表查询正常 (GET /api/entries → 16 entries)
- [x] 分录标签更新正常 (PATCH /api/entries/{id}/tags → 人工复核/测试标签)
- [x] 风险列表查询正常 (GET /api/risks → 16 risks)
- [x] 风险详情含证据 (GET /api/risks/{id} → 2 evidence items)
- [x] 风险复核功能正常 (PATCH /api/risks/{id}/review → confirmed / false_positive)
- [x] 相似分录检索优雅降级 (Qdrant 不可用时返回 200 + 提示)

## 已知未验证（受限于环境）
- [ ] Docker 依赖服务启动（PostgreSQL + Redis + Qdrant） — Docker 未安装
- [ ] 真实 Qdrant 向量检索（端口 6333）— Docker 未安装
- [ ] 真实 PostgreSQL 数据写入 — 改用 SQLite 验证
- [ ] 前端开发服务器联调页面（puppeteer 端到端）— 仅做后端 API 联调
