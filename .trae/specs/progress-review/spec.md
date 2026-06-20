# 财务向量审计风险识别系统 - 进度确认与验证 PRD

## Overview
- **Summary**: 本项目是一个基于 Web SaaS 的财务软件，核心能力包括会计凭证导入、自动标签生成、向量库分析和审计风险识别。当前已完成 MVP 基础结构搭建，需要确认进度并完成验证。
- **Purpose**: 确认当前项目进度状态，完成后端测试验证，确保前后端功能闭环可运行。
- **Target Users**: 开发团队、审计人员、财务人员

## Goals
- [x] 确认后端核心模块完整性
- [x] 确认前端页面完整性
- [x] 完成后端测试验证
- [x] 完成前后端联调验证
- [x] 确认向量库集成功能（Qdrant 不可用时优雅降级）

## Non-Goals (Out of Scope)
- 完整财务核算系统
- 多租户权限体系
- 生产环境部署
- AI 模型集成

## Background & Context
项目已完成基础结构：
- 后端：FastAPI + SQLAlchemy + Qdrant
- 前端：React + TypeScript + Vite
- 数据库：SQLite/PostgreSQL
- 向量库：Qdrant

## Functional Requirements
- **FR-1**: 导入会计凭证文件（Excel/CSV/PDF/TXT）
- **FR-2**: 自动解析会计分录并生成标签
- **FR-3**: 向量化入库和相似检索
- **FR-4**: 基于规则识别审计风险
- **FR-5**: 风险证据链展示和复核操作

## Non-Functional Requirements
- **NFR-1**: 前端类型检查通过
- **NFR-2**: 前端构建成功
- **NFR-3**: 后端测试通过
- **NFR-4**: API 健康检查正常

## Constraints
- **Technical**: Python 3.11+, Node.js 18+, Docker
- **Dependencies**: PostgreSQL, Redis, Qdrant

## Assumptions
- 当前代码结构完整
- Docker 依赖服务可正常启动
- 前端已完成构建验证

## Acceptance Criteria

### AC-1: 后端健康检查正常
- **Given**: 后端服务已启动
- **When**: 访问 GET /health
- **Then**: 返回 {"status": "ok"}
- **Verification**: `programmatic`

### AC-2: 后端测试通过
- **Given**: pytest 环境就绪
- **When**: 运行 pytest backend/tests
- **Then**: 所有测试通过
- **Verification**: `programmatic`

### AC-3: 前端类型检查通过
- **Given**: TypeScript 环境就绪
- **When**: 运行 pnpm lint
- **Then**: 无类型错误
- **Verification**: `programmatic`

### AC-4: 前端构建成功
- **Given**: 前端依赖已安装
- **When**: 运行 pnpm build
- **Then**: dist 目录生成成功
- **Verification**: `programmatic`

### AC-5: 导入流程闭环
- **Given**: 后端服务和数据库运行
- **When**: 创建导入任务、上传文件、处理导入
- **Then**: 分录和风险记录成功生成
- **Verification**: `programmatic`

## Open Questions
- [ ] 后端虚拟环境依赖是否正确安装
- [ ] Qdrant 向量库是否可连接
- [ ] 前后端联调是否正常
