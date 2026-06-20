# 项目整体方案复盘计划

## 1. Summary

本次复盘旨在：
1. 梳理项目的整体技术方案和架构
2. 确认当前 MVP 任务的完成状态
3. 识别 tasks.md 中存在的问题（重复 Task 4）
4. 确定下一步行动

## 2. 项目整体方案

### 2.1 技术栈

| 层级 | 技术选型 | 当前状态 |
|-----|---------|---------|
| 前端 | React + TypeScript + Vite | 已搭建 |
| 后端 | Python FastAPI | 已搭建 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产） | SQLite 就绪 |
| 向量库 | Qdrant 本地模式 | 已部署 |
| Embedding | 云端 API（OpenAI 兼容） | 已实现 |
| AI 解释 | 云端 API + 模板降级 | 已实现 |
| OCR | EasyOCR（本地） | 已实现 |
| 异步处理 | FastAPI BackgroundTasks | 已实现 |
| 数据库迁移 | Alembic | 已配置 |

### 2.2 MVP 核心闭环

```
上传文件 → 解析分录 → 向量化入库 → 风险识别 → AI 解释 → 人工复核
    ↓           ↓           ↓           ↓          ↓
 Excel/CSV   标准化      Qdrant     规则+向量    云端API   状态跟踪
 PDF/TXT     normalized   检索       similarity   模板降级
 图片(OCR)   text                               
```

### 2.3 三层识别策略

| 层级 | 策略 | 实现 |
|-----|------|-----|
| 第一层 | 规则引擎 | 大额整数、弱摘要、期末大额、往来挂账、重复交易 |
| 第二层 | 向量相似检索 | Qdrant 本地模式，相似度 >= 0.85 |
| 第三层 | AI 风险解释 | 云端 API（gpt-4o-mini）+ 模板降级 |

## 3. 当前任务状态

### 3.1 tasks.md 问题

tasks.md 中存在**重复的 Task 4**：
- 第 32-45 行：已完成的 AI 风险解释（云端 API 方案）✅
- 第 62-76 行：未完成的旧版 Task 4 描述

### 3.2 清理计划

| 操作 | 文件 | 说明 |
|-----|------|-----|
| 删除 | tasks.md 第 62-76 行 | 移除重复的 Task 4 描述 |
| 确认 | tasks.md | 确保所有任务都有 ✅ 标记 |

### 3.3 MVP 任务完成状态

| 任务 | 状态 | 说明 |
|-----|------|-----|
| Task 1: Qdrant 部署 | ✅ | 本地文件存储模式 |
| Task 2: Embedding 云端 API | ✅ | OpenAI 兼容 |
| Task 3: 向量相似检索风险 | ✅ | 已集成到风险引擎 |
| Task 4: AI 风险解释 | ✅ | 云端 API + 模板降级 |
| Task 5: 异步导入处理 | ✅ | BackgroundTasks |
| Task 6: 工程化补强 | ✅ | Alembic 已配置 |
| Task 7: 图片 OCR | ✅ | EasyOCR |

## 4. Proposed Changes

### 4.1 清理重复 Task 4

**文件**: `.trae/specs/summarize-requirements/tasks.md`

**操作**: 删除第 62-76 行的重复 Task 4 描述（与第 32-45 行重复）

**原因**: 
- 第 32-45 行是已完成的新版 Task 4（云端 API 方案）
- 第 62-76 行是未完成的旧版 Task 4 描述
- 旧版描述与新版冲突，需要清理

### 4.2 更新验证清单

**文件**: `.trae/specs/summarize-requirements/checklist.md`

**操作**: 确认所有检查项都已勾选

## 5. Assumptions & Decisions

| 决策项 | 选择 | 理由 |
|-------|------|-----|
| 本地模型 vs 云端 API | 云端 API 为主 | Python 3.13 兼容性 |
| 向量库部署 | Qdrant 本地模式 | 无 Docker 环境 |
| 异步方案 | BackgroundTasks | 避免引入 Celery 复杂性 |
| OCR 方案 | EasyOCR | 纯 Python，支持 Python 3.13 |

## 6. Verification Steps

1. **后端测试**: `cd backend && python -m pytest tests -v`（2 passed）
2. **API 健康检查**: `GET /health` 返回 `{"status": "ok"}`
3. **Qdrant 服务**: 端口 6333 可连接
4. **前端构建**: `cd frontend && pnpm build`（可选）

## 8. 下一步行动

### 8.1 当前问题

用户反馈端口 6901/6897 无法访问，经检查：
- README.md 配置的后端端口是 **8000**，前端端口是 **5173**
- 6901/6897 的连接状态已断开（ESTABLISHED 但无服务监听）

### 8.2 服务启动步骤

1. **启动后端**（端口 8000）：
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

2. **启动前端**（端口 5173）：
```powershell
cd frontend
pnpm dev
```

### 8.3 行动计划

1. 🔲 清理 tasks.md 中的重复 Task 4
2. 🔲 更新 README.md 中的端口说明
3. 🔲 确认 Qdrant 服务运行中（端口 6333）
4. 🔲 验证后端 API 可访问（http://localhost:8000/health）
5. 🔲 验证前端页面可访问（http://localhost:5173）

## 8. 结论

**项目 MVP 已完成，可以进入测试阶段。**
