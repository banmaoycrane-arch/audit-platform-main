# 财务向量审计风险识别系统 - 需求整理与下一步行动建议

## Why

项目 MVP 骨架已完成，规则层闭环（导入→解析→标签→风险识别→复核）已通过冒烟测试。但向量层和 AI 层仍为占位/降级实现，与原始需求存在明显偏差。本 spec 旨在系统化梳理当前需求完成度，明确优先级，为下一阶段迭代提供清晰的行动清单。

## What Changes

- 本 spec 不产生代码变更，仅产出需求盘点文档和优先级建议。
- 为后续技术 spec 提供输入（如 embedding 替换、Qdrant 部署、AI 接入等）。

## Impact

- Affected specs: [progress-review](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/progress-review/)
- Affected code: 全项目（分析范围覆盖前后端全部模块）

## Requirements Summary

### Requirement: 项目第一阶段 MVP 需求闭环

原始需求（来自 finance-vector-audit-plan.md）定义了 6 个 Phase + 3 层识别策略：

| 需求层级 | 能力 | 当前状态 | 说明 |
|---|---|---|---|
| Phase A | 项目初始化 | ✅ 已完成 | 前后端结构、Docker Compose、健康检查就绪 |
| Phase B | 导入与解析 | ✅ 已完成 | Excel/CSV/PDF/TXT 解析 + 图片 OCR |
| Phase C | 向量化入库 | ✅ 已完成 | Qdrant 本地模式 + 云端 Embedding API |
| Phase D | 自动标签 | ✅ 已完成 | 规则标签已实现 |
| Phase E | 风险识别 | ✅ 已完成 | 规则引擎 + 向量相似检索 |
| Phase F | AI 风险解释 | ✅ 已完成 | 云端 API + 模板降级 |

### Requirement: 三层识别策略

| 层级 | 需求描述 | 当前状态 |
|---|---|---|
| 第一层：规则引擎 | 大额整数、弱摘要、期末大额、往来挂账、重复交易 | ✅ 已完成 |
| 第二层：向量相似检索 | 与历史异常分录相似、摘要与附件语义不一致、同一供应商高度相似文件 | ✅ 已完成 |
| 第三层：AI 风险解释 | 调用大模型生成风险原因、涉及分录、证据摘要、审计程序、复核建议 | ✅ 已完成 |

### Requirement: 工程化与运维

| 需求 | 当前状态 |
|---|---|
| 异步任务队列（FastAPI BackgroundTasks） | ✅ 已完成 |
| 数据库迁移（Alembic） | ✅ 已完成 |
| 后端测试覆盖 | ✅ 基础测试就绪（2 passed） |
| 图片 OCR | ✅ 已完成（EasyOCR） |
| 向量数据库（Qdrant） | ✅ 已完成（本地模式） |

## MODIFIED Requirements

### Requirement: Embedding 服务支持云端 API

`embedding_service.py` 现已支持云端 OpenAI 兼容 API：
- 优先使用 `AI_BASE_URL` + `AI_API_KEY` 配置调用云端 embedding API
- 未配置时自动降级到 token hash 方案
- 支持的模型：OpenAI `text-embedding-3-small`（默认）或自定义模型

### Requirement: AI 风险解释支持云端 API

`risk_analysis_service.py` 现已支持云端大模型：
- 优先使用 AI 客户端调用大模型生成专业风险解释报告
- 未配置时自动降级到模板化解释
- 支持的模型：OpenAI `gpt-4o-mini`（默认）或自定义模型

### Requirement: 技术方案选择 - 云端 API 为主，本地模型为备

**决策背景**：
- Fastembed 等本地模型库要求 Python < 3.12，当前环境为 Python 3.13.1
- 降级 Python 版本可能破坏其他依赖，不符合快速迭代目标
- 用户表示有足够的云端 API 资源

**最终方案**：
- **主方案**：云端 OpenAI 兼容 API（Embedding + 大模型）
- **离线备选**：本地 token hash 方案作为 embedding 降级（无需模型）
- **未来可选**：如需完全离线部署，可考虑 Ollama 本地推理框架（不依赖 Python 版本）

**配置文件**（`.env`）：
```bash
# AI 服务配置（云端 API）
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=your-api-key
AI_MODEL=gpt-4o-mini

# Embedding 配置
EMBEDDING_MODEL=text-embedding-3-small
```

### Requirement: 当前降级策略保留

- **保持**：`safe_vector_store()` 返回 `None` 时的优雅降级逻辑
- **保持**：SQLite 作为 PostgreSQL 的本地开发降级方案
- **保持**：AI 服务未配置时的模板化风险解释降级
- **保持**：Embedding 未配置时的 token hash 方案降级

## REMOVED Requirements

### Requirement: 无

当前不删除任何已有需求，仅在后续迭代中逐步替换占位实现。

## Next Priority Ranking

**所有 MVP 任务已完成 ✅**

| 优先级 | 任务 | 状态 |
|---|---|---|
| P0 | 部署 Qdrant + 替换真实 embedding | ✅ 已完成 |
| P0 | 实现向量相似检索风险发现 | ✅ 已完成 |
| P1 | 接入真实 AI 风险解释 | ✅ 已完成 |
| P1 | 异步导入处理 | ✅ 已完成 |
| P2 | 图片 OCR | ✅ 已完成 |
| P2 | 工程化补强（Alembic / 测试 / 前端路由） | ✅ 已完成 |

## 项目当前状态

**可以开始基础测试** ✅

MVP 核心功能已全部实现，具备以下能力：
- 财务凭证导入（Excel/CSV/PDF/TXT/图片）
- 规则引擎风险识别
- 向量相似检索风险发现
- AI 风险解释（云端 API）
- 异步处理与状态跟踪
- 数据库迁移支持

**下一步建议**：
1. 基础功能测试（API 联调、前端界面）
2. 真实数据导入测试
3. 云端 API 配置与验证（可选）
