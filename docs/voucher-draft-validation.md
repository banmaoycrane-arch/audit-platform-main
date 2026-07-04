# 凭证草稿端到端验证功能开发文档

## 1. 功能说明

### 1.1 项目背景

本系统原有的解析-凭证草稿流程存在以下问题：
- `/api/parser-voucher/confirm-drafts` 接口几乎不做校验直接落库
- 借贷不平衡、科目不存在、期间关闭等错误只能在 `create_voucher` 内部触发，返回的错误信息不够结构化
- 同批次多张草稿时，任意一张失败会导致事务回滚，但前端无法精确定位错误
- 生成的草稿凭证缺少 `period_id`

### 1.2 功能目标

实现凭证草稿的端到端统一校验：
1. 在落库前对整张批次的每张草稿执行确定性规则校验
2. 失败时整张批次都不落库
3. 返回按 `draft_index` 组织的结构化错误列表
4. 生成的凭证自动补全 `period_id`

### 1.3 校验规则

| 校验项 | 错误码 | 说明 |
|--------|--------|------|
| 凭证号非空 | `VOUCHER_NO_EMPTY` | 凭证号不能为空字符串 |
| 凭证号同批次重复 | `VOUCHER_NO_DUPLICATE` | 同批次内凭证号唯一 |
| 凭证号数据库重复 | `VOUCHER_NO_DUPLICATE` | 与账簿内已有凭证号不重复 |
| 凭证日期格式 | `VOUCHER_DATE_INVALID` | 必须为 ISO 格式日期 |
| 期间不存在 | `PERIOD_NOT_FOUND` | 凭证日期必须落在某个期间内 |
| 期间已关闭 | `PERIOD_CLOSED` | 期间状态必须为 open 或 reopened |
| 分录行数不足 | `LINES_TOO_FEW` | 至少 2 行分录 |
| 科目编码为空 | `ACCOUNT_CODE_EMPTY` | 分录行必须填写科目编码 |
| 科目不存在 | `ACCOUNT_NOT_FOUND` | 科目必须在当前账簿中存在 |
| 金额负数 | `AMOUNT_NEGATIVE` | 借方/贷方金额不能为负 |
| 金额同时借贷 | `AMOUNT_BOTH_SIDES` | 同一行不能同时有借贷金额 |
| 金额为零 | `AMOUNT_ZERO` | 同一行至少有一方金额非零 |
| 金额格式 | `AMOUNT_PRECISION` | 金额必须为有效数字 |
| 借贷不平衡 | `BALANCE_MISMATCH` | 单张草稿借方合计 = 贷方合计 |

### 1.4 技术架构

```
frontend ParserVoucherPreview.tsx
           │
           ▼
  POST /api/parser-voucher/confirm-drafts
           │
           ▼
  routes_parser_voucher.py
           │
           ▼
  voucher_draft_validation_service.validate_voucher_drafts()
           │
           ├─ 校验不通过：返回结构化 errors，不落库
           │
           └─ 校验通过：调用 voucher_service.create_vouchers_from_drafts()
                        │
                        ▼
                  自动推断 period_id 并写入 Voucher
```

---

## 2. 代码审查记录

### 2.1 新增文件

#### 2.1.1 `backend/app/services/voucher_draft_validation_service.py`

**用途**：凭证草稿统一校验服务

**审查要点**：
- ✓ 错误码定义清晰，便于前端国际化和定位
- ✓ `VoucherDraftValidationReport` 数据结构支持按 `draft_index` 组织错误
- ✓ 校验逻辑分层：凭证号、日期期间、分录行、借贷平衡、数据库唯一性
- ✓ 金额转换使用 `Decimal(str(value))`，避免浮点误差
- ✓ 所有错误消息使用中文业务语义

**潜在改进**：
- 可考虑将校验规则抽象为可配置的策略模式，便于后续扩展

#### 2.1.2 `backend/tests/test_voucher_draft_end_to_end_validation.py`

**用途**：端到端测试

**审查要点**：
- ✓ 覆盖 6 种正常凭证草稿类型（发票、银行收/付款、费用、工资、收据）
- ✓ 覆盖 8 种异常场景（借贷不平衡、负数、空行、科目不存在、DB重复、批次重复、期间关闭、日期越界）
- ✓ 包含 confirm API 集成测试，验证原子性和错误返回

### 2.2 修改文件

#### 2.2.1 `backend/app/services/voucher_service.py`

**修改内容**：`create_vouchers_from_drafts` 增加 `period_id` 推断逻辑

**审查要点**：
- ✓ 当 draft 中未提供 `period_id` 时，根据 `voucher_date` 自动查询匹配的 `AccountingPeriod`
- ✓ 未找到匹配期间时抛出明确的 `VoucherValidationError`
- ✓ 保持 `auto_commit` 事务行为不变

#### 2.2.2 `backend/app/api/routes_parser_voucher.py`

**修改内容**：`confirm-drafts` 接口接入校验服务

**审查要点**：
- ✓ 先校验后落库，失败时不写库
- ✓ 响应新增 `errors` 字段，包含 `draft_index`/`code`/`message`/`field`
- ✓ 校验通过后才调用 `create_vouchers_from_drafts`
- ✓ 透传 `period_id` 给服务层

### 2.3 代码规范检查

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 文件头注释 | ✓ | 新增文件包含完整文件头注释 |
| 函数注释 | ✓ | 主函数和工具函数包含注释 |
| 命名规范 | ✓ | 使用 snake_case 和 PascalCase |
| 金额精度 | ✓ | 使用 Decimal 处理金额 |
| 错误处理 | ✓ | 异常消息包含业务语义 |

---

## 3. 测试报告

### 3.1 测试环境

- Python 版本：3.13.1
- 测试框架：pytest 9.1.0
- 数据库：SQLite（内存模式）

### 3.2 测试用例统计

| 测试类别 | 用例数 | 通过 | 失败 |
|----------|--------|------|------|
| 校验服务 - 正常路径 | 6 | 6 | 0 |
| 校验服务 - 错误路径 | 8 | 8 | 0 |
| Confirm API 集成 | 4 | 4 | 0 |
| **合计** | **18** | **18** | **0** |

### 3.3 覆盖场景

#### 3.3.1 正常路径（6 种凭证草稿类型）

| 测试用例 | 覆盖类型 |
|----------|----------|
| `test_valid_invoice_draft` | 采购发票（含进项税额） |
| `test_valid_bank_income_draft` | 银行收款 |
| `test_valid_bank_payment_draft` | 银行付款 |
| `test_valid_expense_draft` | 费用报销 |
| `test_valid_salary_draft` | 工资发放（含代扣项） |
| `test_valid_receipt_draft` | 收据 |

#### 3.3.2 错误路径（8 种异常场景）

| 测试用例 | 覆盖异常 |
|----------|----------|
| `test_unbalanced_draft` | 借贷不平衡 |
| `test_negative_amount` | 负数金额 |
| `test_empty_lines` | 分录行少于 2 行 |
| `test_account_not_found` | 科目不存在 |
| `test_voucher_no_duplicate_in_db` | 与数据库凭证号重复 |
| `test_voucher_no_duplicate_in_batch` | 同批次凭证号重复 |
| `test_period_closed` | 已结账期间 |
| `test_date_outside_period` | 凭证日期不在任何期间内 |

#### 3.3.3 Confirm API 集成测试

| 测试用例 | 覆盖场景 |
|----------|----------|
| `test_confirm_valid_draft` | 正常草稿落库并验证 `period_id` |
| `test_confirm_rejects_invalid_draft` | 批次中任一失败则全部不落库 |
| `test_confirm_returns_structured_errors` | 返回按 `draft_index` 的结构化错误 |
| `test_confirm_multiple_valid_drafts` | 多张草稿批量落库 |

---

## 4. 实施指南

### 4.1 后端使用

```python
from app.services.voucher_draft_validation_service import validate_voucher_drafts

report = validate_voucher_drafts(
    db,
    ledger_id=ledger.id,
    organization_id=ledger.team_id,
    drafts=drafts,
)

if not report.is_valid:
    for error in report.errors:
        print(f"草稿 {error.draft_index}: [{error.code}] {error.message}")
else:
    # 继续落库
    pass
```

### 4.2 API 请求示例

#### 请求

```http
POST /api/parser-voucher/confirm-drafts
Authorization: Bearer <token>
Content-Type: application/json

{
  "ledger_id": 1,
  "organization_id": 1,
  "drafts": [
    {
      "voucher_no": "记-0001",
      "voucher_date": "2024-01-15",
      "summary": "支付办公费",
      "lines": [
        {"account_code": "6602", "account_name": "管理费用", "summary": "办公费", "debit_amount": "1000.00", "credit_amount": "0.00"},
        {"account_code": "1002", "account_name": "银行存款", "summary": "支付", "debit_amount": "0.00", "credit_amount": "1000.00"}
      ]
    }
  ]
}
```

#### 成功响应

```json
{
  "success": true,
  "created_count": 1,
  "voucher_ids": [123]
}
```

#### 失败响应

```json
{
  "success": false,
  "created_count": 0,
  "voucher_ids": [],
  "error_message": "凭证草稿校验失败，请修正后重新提交",
  "errors": [
    {
      "draft_index": 0,
      "code": "BALANCE_MISMATCH",
      "message": "借贷不平衡：借方合计 1000.00，贷方合计 900.00，差额 100.00",
      "field": "lines"
    }
  ]
}
```

### 4.3 前端集成建议

在 `frontend/src/pages/ParserVoucherPreview.tsx` 的 `handleConfirm` 中：

1. 发送 `confirm-drafts` 请求
2. 若 `success=false`，遍历 `errors` 数组
3. 根据 `draft_index` 定位到对应草稿卡片
4. 根据 `field` 高亮对应输入框
5. 显示 `message` 提示用户

---

## 5. 已知限制与后续改进

### 5.1 当前限制

1. 校验规则目前为硬编码，未完全可配置化
2. 凭证号唯一性校验未考虑凭证字（`voucher_type`）
3. 未对科目方向（借/贷）与金额方向做一致性校验

### 5.2 后续改进建议

1. 将校验规则抽取为可配置的策略，支持自定义校验项
2. 支持更细粒度的字段级校验（如科目禁用状态、往来单位存在性）
3. 增加校验规则缓存，减少数据库查询次数
4. 与前端协同实现字段级实时校验
5. 支持部分落库模式（用户明确选择跳过错误草稿）

---

## 6. 验证方法

### 6.1 运行测试

```bash
cd backend
python -m pytest tests/test_voucher_draft_end_to_end_validation.py -v
```

### 6.2 手动验证

1. 上传发票文件，获取候选草稿
2. 修改某张草稿使借贷不平衡
3. 点击确认，验证返回 `BALANCE_MISMATCH` 错误且未落库
4. 修正后再次确认，验证凭证落库且 `period_id` 正确
