# 自适应文件导入引擎 - 任务清单

## Task 1: 创建格式模板系统
- **Priority**: P0
- **Depends On**: None
- **Status**: ✅ 已完成
- **Files**:
  - `backend/app/services/format_template.py`

## Task 2: 重构字段映射引擎
- **Priority**: P0
- **Depends On**: Task 1
- **Status**: ✅ 已完成
- **Files**:
  - `backend/app/services/file_parser_service.py`

## Task 3: 实现数据验证与质量评分
- **Priority**: P1
- **Depends On**: Task 2
- **Status**: ✅ 已完成
- **Files**:
  - `backend/app/services/data_validator.py`

## Task 4: 分离凭证与原始文件处理流程
- **Priority**: P1
- **Depends On**: Task 1
- **Status**: ✅ 已完成
- **Files**:
  - `backend/app/services/import_service.py`
  - `backend/app/api/routes_imports.py`

## Task 5: AI 辅助字段映射（可选）
- **Priority**: P2
- **Depends On**: Task 2
- **Status**: ✅ 已完成
- **Files**:
  - `backend/app/services/adaptive_mapper.py`

## Task 6: 前端导入报告展示
- **Priority**: P2
- **Depends On**: Task 3
- **Status**: ✅ 已完成
- **Files**:
  - `frontend/src/pages/ImportPage.tsx`
  - `frontend/src/api/client.ts`

## Task 7: 凭证字自动推荐
- **Priority**: P0
- **Depends On**: Task 3
- **Status**: ✅ 已完成
- **Description**:
  - 根据分录科目和摘要自动推荐凭证字
  - 支持：银（银行转账）、现（现金）、转（转账/计提/摊销）、记（通用）
- **Files**:
  - `backend/app/services/tagging_service.py`
