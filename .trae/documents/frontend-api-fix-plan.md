# 前端 API 连接问题修复计划

## 1. 问题分析

### 1.1 当前问题
- 前端 API Client (`client.ts`) 使用 `VITE_API_BASE_URL`
- 但项目根目录没有 `.env` 文件
- 导致 `API_BASE` 为空，请求相对路径失败

### 1.2 错误日志
```
[error] Error at request (http://localhost:5173/src/api/client.ts:5:11)
at async createJob (http://localhost:5173/src/pages/ImportPage.tsx:27:17)
```

### 1.3 根本原因
```typescript
// client.ts 第 1 行
const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
// 当 .env 不存在时，API_BASE 为空字符串
// 请求 '/api/import-jobs' 变成相对路径
// 但相对路径可能被前端代理拦截或解析错误
```

## 2. 解决方案

### 2.1 创建 .env 文件
**文件**: `e:\projects\finance-vector-audit\wroksapce20260616\.env`

**内容**:
```
VITE_API_BASE_URL=http://127.0.0.1:8001
```

### 2.2 前端重启
创建 .env 后需要重启 Vite 开发服务器才能生效

## 3. 验证步骤

1. 创建 `.env` 文件
2. 重启前端服务（`pnpm dev`）
3. 刷新浏览器页面
4. 点击"新建导入批次"按钮
5. 确认 API 请求成功

## 4. 前端功能现状

| 页面 | 功能 | 状态 |
|-----|------|------|
| DashboardPage | 仪表盘展示 | ✅ 已实现 |
| ImportPage | 导入批次管理 | ✅ 已实现（需修复 API 连接）|
| EntriesPage | 分录列表 | ✅ 已实现 |
| RisksPage | 风险列表 | ✅ 已实现 |
| RiskDetailPage | 风险详情 | ✅ 已实现 |

## 5. 后续规划建议

用户提到前端功能规划不足，建议后续：
1. 完善 Error 边界和错误提示
2. 添加 Loading 状态
3. 优化用户体验（表单验证、反馈提示）
4. 添加前端路由（react-router）
