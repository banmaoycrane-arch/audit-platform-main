# 统一金额处理系统开发者指南

> **版本**: 1.0
> **更新日期**: 2026-07-02
> **适用范围**: 财务向量审计系统全项目

---

## 一、设计目标

本系统旨在为全项目提供**单一数据源**的金额处理规则，解决以下问题：

1. 后端 `float` 与 `Decimal` 混用导致的精度误差
2. 前端 JavaScript `Number` 浮点误差风险
3. 各服务重复实现 `_to_decimal`、`_round_amount` 等工具函数
4. 舍入方式不统一（`ROUND_HALF_UP` 与 `ROUND_HALF_EVEN` 并存）
5. 金额格式化风格不一致
6. 重大金额交易缺少审计留痕

---

## 二、核心原则

| 原则 | 说明 |
|------|------|
| **后端权威** | 所有金额计算以 Python `Decimal` 为准 |
| **前端轻量显示** | 前端使用 `decimal.js` 进行必要校验，复杂计算交给后端 |
| **单一舍入方式** | 统一使用 `ROUND_HALF_UP`（四舍五入） |
| **默认精度 2 位** | 人民币金额保留 2 位小数 |
| **API 传输用字符串** | 避免 JSON 中 float 精度丢失 |
| **审计留痕** | 单笔超 100 万或关键操作记录审计日志 |

---

## 三、目录结构

```
backend/app/money/
├── __init__.py          # 统一入口，导出所有公共 API
├── amount.py            # Money 领域对象
├── currency.py          # Currency 币种定义
├── constants.py         # 常量：CNY、精度、舍入方式
├── errors.py            # 金额相关异常体系
├── parsing.py           # 解析：任意类型 -> Decimal/Money
├── formatting.py        # 格式化：金额 -> 显示字符串/API 字符串
├── rounding.py          # 舍入：ROUND_HALF_UP 量化
├── validation.py        # 校验：范围、精度、符号
├── exchange.py          # 币种转换（可扩展）
└── audit_logger.py      # 重大金额操作审计日志

backend/app/schemas/money.py  # Pydantic MoneyField

frontend/src/money/
├── index.ts             # 统一入口
├── constants.ts         # CNY、精度、舍入方式
├── Money.ts             # Money 类（基于 decimal.js）
├── format.ts            # 格式化工具
├── parse.ts             # 解析工具
├── validate.ts          # 校验工具
└── round.ts             # 舍入与汇总工具
```

---

## 四、后端使用指南

### 4.1 快速开始

```python
from app.money import Money, parse_decimal, format_money, round_decimal

# 构造金额
m = Money.cny("1234.56")

# 解析任意输入
d = parse_decimal("¥1,234.56")  # Decimal('1234.56')

# 格式化输出
s = format_money(m)  # "¥1,234.56"

# 舍入
r = round_decimal(Decimal("2.345"))  # Decimal('2.35')
```

### 4.2 Money 类运算

```python
a = Money.cny("100.00")
b = Money.cny("30.50")

a.add(b)       # Money.cny("130.50")
a.subtract(b)  # Money.cny("69.50")
a.mul("1.13")  # Money.cny("113.00")
a.div(3)       # Money.cny("33.33")
```

### 4.3 校验输入

```python
from app.money import validate_decimal_input

try:
    amount = validate_decimal_input(
        user_input,
        min_value="0.00",
        max_value="999999999999.99",
        allow_negative=False,
        max_decimal_places=2,
    )
except MoneyParseError as e:
    raise HTTPException(status_code=400, detail=str(e))
except (MoneyPrecisionError, MoneyRangeError) as e:
    raise HTTPException(status_code=422, detail=str(e))
```

### 4.4 Pydantic Schema 中使用 MoneyField

```python
from pydantic import BaseModel
from app.schemas.money import MoneyField

class VoucherLineCreate(BaseModel):
    account_code: str
    debit_amount: MoneyField   # 输入任意格式，输出字符串 "1234.56"
    credit_amount: MoneyField
```

### 4.5 审计日志

```python
from app.money.audit_logger import log_money_operation

log_money_operation(
    db,
    user_id=current_user.id,
    ledger_id=ledger_id,
    service_name="voucher_service",
    tool_name="create_voucher",
    business_object_type="voucher",
    business_object_id=str(voucher.id),
    action="create",
    money_value=Money.cny(total_debit),
    input_summary={"voucher_no": voucher_no},
)
```

---

## 五、前端使用指南

### 5.1 安装

已安装 `decimal.js`，无需重复安装：

```bash
pnpm add decimal.js
```

### 5.2 格式化金额

```typescript
import { formatMoney, formatAmount } from '@/money';

formatMoney('1234.5');           // "1,234.50"
formatAmount('1234.5');          // "¥1,234.50"
formatMoney('-1234.5', { symbol: true, negativeInParens: true });  // "(¥1,234.50)"
```

### 5.3 安全计算

```typescript
import { Money, sumDecimals } from '@/money';

const a = Money.cny('100.00');
const b = Money.cny('30.50');
const total = a.add(b).toString();  // "130.50"

// 汇总表格列
const debitTotal = sumDecimals(rows.map(r => r.debit_amount)).toFixed(2);
```

### 5.4 输入校验

```typescript
import { validateMoneyInput } from '@/money';

const result = validateMoneyInput(inputValue, {
  allowNegative: false,
  allowZero: false,
  maxDecimalPlaces: 2,
});

if (!result.valid) {
  message.error(result.error);
}
```

### 5.5 金额输入组件建议

Ant Design 的 `InputNumber` 底层是 JavaScript Number，**不推荐直接用于大金额**。建议方案：

```tsx
// 方案 1：使用普通 Input，失焦后格式化
<Input
  value={displayValue}
  onChange={(e) => setRawValue(e.target.value)}
  onBlur={() => setDisplayValue(formatDecimalInput(rawValue))}
/>

// 方案 2：提交时统一转字符串
const payload = {
  ...formValues,
  debit_amount: Money.cny(formValues.debit_amount).toString(),
};
```

---

## 六、数据库类型规范

当前数据库列类型已是 `Numeric(p, 2)`，但 ORM 类型标注多为 `Mapped[float]`。建议按以下规则调整：

| 字段类型 | 数据库列 | ORM 标注 |
|---------|---------|---------|
| 金额 | `Numeric(14, 2)` / `Numeric(18, 2)` | `Mapped[Decimal]` |
| 数量/单价 | `Numeric(18, 4)` | `Mapped[Decimal]` |
| 置信度/风险分 | - | 保留 `Mapped[float]` |

**迁移示例**：

```python
from decimal import Decimal

# 修改前
total_debit: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

# 修改后
total_debit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"))
```

> **注意**：此变更影响面较广，需配合全量回归测试逐步推进。

---

## 七、错误处理协议

| 异常 | 触发场景 | HTTP 状态码建议 |
|------|---------|----------------|
| `MoneyParseError` | 输入无法解析为金额 | 400 |
| `MoneyPrecisionError` | 小数位超出限制 | 422 |
| `MoneyRangeError` | 金额超出范围或为不允许符号 | 422 |
| `CurrencyNotSupportedError` | 币种未注册或不一致 | 400 |
| `ExchangeRateMissingError` | 缺少汇率 | 422 |
| `MoneyBalanceError` | 借贷不平衡 | 422 |

---

## 八、审计日志规范

### 8.1 触发场景

- 单笔金额 ≥ 100 万 CNY 的凭证创建/修改
- 币种转换
- 损益结转、期间关闭
- 金额解析失败（如导入非法金额）

### 8.2 记录字段

- trace_id / request_id
- user_id / team_id / ledger_id / project_id
- service_name / tool_name
- business_object_type / business_object_id
- action / money_value
- before_snapshot / after_snapshot
- risk_level / status / error_message

---

## 九、测试规范

金额相关测试必须覆盖以下边界：

1. `0.1 + 0.2 == 0.3`
2. 四舍五入边界：`2.345 -> 2.35`，`2.344 -> 2.34`
3. 大金额：`999999999999.99`
4. 负数格式：`(-123.45)` 与 `-123.45`
5. 货币符号/千分位清理：`¥1,234.56` -> `1234.56`
6. 除法精度：`100 / 3 == 33.33`

---

## 十、迁移路线图

### 阶段 1：基础设施 ✅ 已完成
- 创建 `backend/app/money/` 模块
- 创建 `frontend/src/money/` 模块
- 安装 `decimal.js`

### 阶段 2：关键服务修复 🔄 进行中
- 修复 `voucher_service.py` 中的 `float()` 转换 ✅
- 修复 `voucher_management_service.py` 中的 `float()` 转换 ✅
- 将 `file_parser_service.py` 金额解析改为 `Decimal` ✅
- 后续：逐步替换其他服务中的 `float()` 金额处理

### 阶段 3：模型类型标注调整 ⏳ 待规划
- 将金额字段 `Mapped[float]` 改为 `Mapped[Decimal]`
- 配合 Alembic 迁移（通常无需改 schema，仅类型标注）

### 阶段 4：前端接入 ⏳ 待规划
- 新页面使用 `@/money` 工具
- 逐步替换现有页面中的 `toLocaleString` / `Math.round` / `toFixed`

---

## 十一、参考资料

- Python `decimal` 模块文档
- `decimal.js` GitHub 仓库
- 项目规则：`.trae/rules/yyyy.md`（金额精度强制规则）
