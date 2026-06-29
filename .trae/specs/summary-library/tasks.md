# 智能摘要库与逻辑校验系统 - 任务清单

## 审计导向设计理念

**核心目标**：代替审计实质性程序中的重新计算，实现全量审计，规避抽样审计风险。

**两种工作模式**：
1. **记账模式**：导入原始资料 → AI 自动编制定录 → 生成账簿
2. **审计模式（主要）**：导入原始资料 + 被审计单位分录 → 审计测试 → 错误定位 → 审计语言表述

**前端引导界面**：
- 首页模式选择（记账/审计）
- 记账模式：5步引导流程
- 审计模式：6步引导流程

---

## 已完成任务

### ✅ Task 1: 摘要模板库
- **文件**: `summary_template_service.py`
- **内容**: 6种凭证字模板（银/现/转/记）、30+摘要模板、8个预定义风险案例

### ✅ Task 2: 摘要推荐服务
- **文件**: `summary_template_service.py`
- **内容**: `recommend_summary()`、`match_template()`

### ✅ Task 3: 逻辑校验服务
- **文件**: `logic_check_service.py`
- **内容**: 摘要-科目匹配校验、借贷平衡校验、凭证字-科目匹配校验

### ✅ Task 4: 风险案例库
- **文件**: `risk_case_library.py`
- **内容**: 风险案例向量化、相似风险搜索

### ✅ Task 5: Tags 多维度语义标签
- **文件**: `entry_tags_service.py`
- **内容**: 凭证字标签、科目标签（二级科目）、往来单位标签、规模标签

### ✅ Task 6: 集成到导入流程
- **文件**: `import_service.py`
- **内容**: 集成 tags 生成、逻辑校验、风险案例匹配

---

## 执行计划（Step 1-3 优先）

### 🔄 Step 1: 前端模式选择界面（P0 - 立即执行）
- [x] `frontend/src/pages/HomePage.tsx`
- [x] 记账模式/审计模式选择卡片
- [x] 记账模式引导流程（5步）
- [x] 审计模式引导流程（6步）

### 🔄 Step 2: 原始资料导入支持（P0 - 立即执行）
- [x] `backend/app/services/source_document_service.py`
- [x] 发票 OCR 解析
- [x] 银行流水导入
- [x] 合同文本提取

### 🔄 Step 3: 审计测试服务（P0 - 立即执行）
- [x] `backend/app/services/audit_test_service.py`
- [x] 完整性测试
- [x] 准确性测试
- [x] 截止性测试
- [x] 分类测试
- [x] 错误定位 + 审计语言表述

---

### ⏸️ Step 4: 自动编制定录 + 报告（P1 - 暂时搁置）
- [x] `entry_generation_service.py`
- [x] `audit_report_service.py`

### ⏸️ Step 5: Agent入口（P2 - 暂时搁置）
- [x] Agent Chat界面
- [x] 意图识别
- [x] 任务编排

---

## Task Dependencies

```
Step 1 (前端模式选择)
        ↓
    ┌───┴───┐
    ↓       ↓
Step 2    (记账模式)
(原始资料)   │
    │       │
    └───┬───┘
        ↓
    Step 3
   (审计测试)
```
