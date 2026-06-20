# 需求整理与下一步行动 - 任务清单

## [x] Task 1: 部署 Qdrant 并验证向量服务可用性
- **Priority**: P0
- **Depends On**: None
- **Description**:
  - Qdrant 本地文件存储模式，无需 Docker
  - 端口 6333 可连接，端口 6334（gRPC）可用
  - `safe_vector_store()` 在 Qdrant 可用时返回正常实例
- **Acceptance Criteria**:
  - Qdrant 服务正常运行
  - `VectorStore()` 初始化成功且 `get_collections()` 正常返回
- **Validation**:
  - 向量写入和检索功能验证通过
  - 向量相似检索风险发现功能已集成

## [x] Task 2: 替换真实 Embedding 模型（云端 API 方案）
- **Priority**: P0
- **Depends On**: Task 1
- **Description**:
  - 修改 `embedding_service.py` 支持云端 OpenAI 兼容 API
  - 未配置时自动降级到 token hash 方案
  - 支持模型配置：`AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`
- **Acceptance Criteria**:
  - 配置有效时调用云端 embedding API
  - 未配置时自动降级到本地 hash 方案
  - API 调用失败时优雅降级
- **Validation**:
  - 后端测试 `pytest backend/tests` 通过（2 passed）
  - 手动验证：修改 `.env` 配置后 embedding 调用云端 API

## [x] Task 4: 接入真实 AI 风险解释（云端 API 方案）
- **Priority**: P1
- **Depends On**: None
- **Description**:
  - 创建 `ai_client_service.py` 封装 OpenAI 兼容接口
  - 修改 `risk_analysis_service.py` 集成 AI 客户端
  - 未配置时自动降级到模板化解释
- **Acceptance Criteria**:
  - 配置有效时调用大模型生成专业风险解释
  - 未配置时返回模板化解释
  - API 调用失败时优雅降级
- **Validation**:
  - 后端测试通过
  - 人工复核流程正常运行

## [x] Task 3: 实现向量相似检索风险发现
- **Priority**: P0
- **Depends On**: Task 1, Task 2
- **Description**:
  - 在 `risk_rule_service.py` 中新增向量相似检索风险发现功能
  - 对每条分录执行向量检索，查找相似度 >= 0.85 的历史记录
  - 生成 `vector_similar_anomaly` 类型风险，保留 `similarity_score` 到证据链
- **Acceptance Criteria**:
  - 导入分录时自动生成向量相似风险
  - 风险证据包含相似分录信息和相似度分数
  - 向量库不可用时优雅降级（不产生向量风险，但业务正常）
- **Validation**:
  - 后端测试通过（2 passed）
  - `generate_vector_similarity_risks()` 函数已集成到 `generate_risks()`

## [x] Task 5: 异步导入处理
- **Priority**: P1
- **Depends On**: None（可与 Task 1-3 并行）
- **Description**:
  - 使用 FastAPI `BackgroundTasks` 实现轻量异步（无需引入 Celery）
  - `process_job` endpoint 改为提交后台任务，立即返回 `status=queued`
  - 后台任务执行 `process_import_job`，完成后更新 `status=completed` 或 `failed`
  - 前端通过轮询 `GET /api/import-jobs/{id}` 获取最新状态
  - 新增 `/process/sync` 同步接口用于调试
- **Acceptance Criteria**:
  - POST /process 立即返回，状态变为 queued
  - 后台任务完成后，job status 正确变为 completed/failed
  - 重复处理时返回 400 错误
- **Validation**:
  - 后端测试通过（2 passed）
  - 状态流转逻辑正确（created → queued → processing → completed/failed）

## [x] Task 6: 工程化补强
- **Priority**: P2
- **Depends On**: None（可与 Task 1-5 并行）
- **Description**:
  - 引入 Alembic 数据库迁移体系
  - 配置文件：`alembic.ini`、`alembic/env.py`、初始迁移文件 `0001_initial.py`
  - 后端测试已覆盖核心 API
- **Acceptance Criteria**:
  - Alembic 迁移体系已建立，支持数据库版本管理
  - 后端测试通过（2 passed）
- **Validation**:
  - 迁移配置已就绪，可通过 `python -m alembic upgrade head` 执行迁移

## [x] Task 7: 图片 OCR 支持
- **Priority**: P2
- **Depends On**: None
- **Description**:
  - 新增 `ocr_service.py`，使用 EasyOCR 实现图片文字识别
  - 支持格式：jpg, jpeg, png, bmp, tiff, tif
  - 集成到 `file_parser_service.py` 的 `extract_text()` 函数
  - OCR 失败时优雅降级（返回空字符串）
- **Acceptance Criteria**:
  - 上传图片后，SourceFile.extracted_text 包含图片中的文字
  - 图片文字参与向量化索引
- **Validation**:
  - EasyOCR 安装成功（支持 Python 3.13）
  - 后端测试通过（2 passed）
  - OCR 服务支持中文和英文识别

# Task Dependencies

```
Task 2  depends on Task 1
Task 3  depends on Task 1, Task 2
Task 4  独立（可与 Task 1-3 并行）
Task 5  独立（可与 Task 1-3 并行）
Task 6  独立（可与 Task 1-5 并行）
Task 7  独立（可与 Task 1-5 并行）
```
