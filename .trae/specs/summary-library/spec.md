# 智能摘要库与逻辑校验系统

## 0. 设计理念（审计导向）

### 0.1 核心目标
**代替审计实质性程序中的重新计算，实现全量审计，规避抽样审计风险。**

### 0.2 两种工作模式与前端引导

#### 模式一：记账模式（代理记账）
适用于**未按要求建账的企业**，基于原始资料自动编制定录。
```
入口选择「记账模式」→ 导入原始资料 → AI 自动编制定录 → 生成账簿
```
**核心功能**：
- 原始资料解析（发票/银行流水/合同）
- AI 自动编制定录
- 凭证复核与调整
- 生成标准账簿

#### 模式二：审计模式
适用于**已有账簿的企业**，对分录进行全量审计测试。
```
入口选择「审计模式」→ 导入原始资料 → 导入被审计单位分录 → 审计测试 → 生成审计报告
```
**核心功能**：
- 原始资料归档管理
- 已有分录导入
- 审计测试（完整性/准确性/截止性/分类）
- 错误定位与标注
- 审计语言表述
- 生成审计报告

### 0.3 审计测试类型

| 测试类型 | 内容 | 审计目标 |
|---------|------|---------|
| **完整性测试** | 原始资料是否都有对应分录 | 完整性 |
| **准确性测试** | 分录金额是否与原始资料一致 | 准确性 |
| **截止性测试** | 分录是否在正确会计期间 | 截止性 |
| **分类测试** | 凭证字与科目是否匹配 | 分类 |
| **存在性测试** | 原始资料是否真实存在 | 存在性 |
| **配比测试** | 收入与成本是否配比 | 准确性 |

### 0.5 审计语言表述

**错误定位**：精确定位到分录ID、凭证号、行号
**审计语言**：使用审计准则术语表述问题

#### 审计语言示例

| 问题类型 | 审计语言表述 |
|---------|------------|
| 原始资料无对应分录 | "XXX银行回单（金额XXX元，日期XXX）未见对应会计凭证，**销售收入的完整性**存在重大错报风险" |
| 金额不一致 | "发票XXX金额为XXX元，但对应分录金额为XXX元，存在**计价不准确**错报" |
| 跨期分录 | "该银行回单日期为XXX年XX月XX日，但对应凭证日期为XXX年XX月XX日，存在**截止测试**重大错报" |
| 科目错误 | "摘要显示为采购业务，但借方科目为管理费用，**分类错误**可能导致费用错报" |
| 缺少原始资料 | "XXX元转账未附银行回单，**审计证据不足**无法确认业务真实性" |

### 0.6 前端引导界面设计

#### 首页模式选择

```
┌─────────────────────────────────────────────────────┐
│           财务审计智能辅助系统                         │
│                                                     │
│   ┌─────────────────┐    ┌─────────────────┐       │
│   │                 │    │                 │       │
│   │   📝 记账模式    │    │   🔍 审计模式    │       │
│   │                 │    │                 │       │
│   │  代理记账/自动   │    │  审计测试/风险   │       │
│   │  编制定录       │    │  识别           │       │
│   │                 │    │                 │       │
│   └─────────────────┘    └─────────────────┘       │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### 记账模式引导流程

```
Step 1: 选择原始资料类型
  ○ 发票  ○ 银行流水  ○ 合同  ○ 收据  ○ 全选

Step 2: 导入原始资料
  [拖拽上传区域] 支持批量上传

Step 3: AI 自动编制定录
  [查看待审核分录列表]

Step 4: 凭证复核与调整
  [逐笔审核/批量确认]

Step 5: 生成账簿
  [导出Excel] [导出会计凭证]
```

#### 审计模式引导流程

```
Step 1: 选择审计范围
  ○ 全量审计  ○ 按科目审计  ○ 按期间审计

Step 2: 导入原始资料
  [拖拽上传区域] 发票/银行流水/合同

Step 3: 导入被审计单位分录
  [导入分录Excel/CSV]

Step 4: 执行审计测试
  [完整性测试] [准确性测试] [截止性测试] [分类测试]

Step 5: 审计发现复核
  [查看异常清单] [复核确认]

Step 6: 生成审计报告
  [导出PDF] [导出异常清单]
```

## 当前执行计划

### 立即执行（Step 1-3）

| Step | 任务 | 优先级 | 状态 |
|-----|------|--------|------|
| Step 1 | 前端模式选择界面 | P0 | 🔄 待实现 |
| Step 2 | 原始资料导入支持 | P0 | 🔄 待实现 |
| Step 3 | 审计测试服务 | P0 | 🔄 待实现 |

### 暂时搁置

| Step | 任务 | 优先级 | 状态 |
|-----|------|--------|------|
| Step 4 | 自动编制定录 + 报告 | P1 | ⏸️ 搁置 |
| Step 5 | Agent入口 | P2 | ⏸️ 搁置 |

---

## 1. 当前完成功能

### 1.1 已实现
- ✅ 摘要模板库（6种凭证字、30+模板）
- ✅ 逻辑校验服务（摘要-科目匹配校验）
- ✅ Tags 多维度语义标签
- ✅ 风险案例库
- ✅ 凭证字自动推荐

### 1.2 待实现（审计导向）
- [ ] 原始资料导入支持（发票 OCR、合同解析）
- [ ] 自动编制定录（从原始资料到分录）
- [ ] 完整性测试（原始资料与分录交叉核对）
- [ ] 截止性测试（期初/期末检查）
- [ ] 配比测试（收入与成本配比）
- [ ] 审计报告生成

## 2. 摘要模板库（审计视角）

### 2.1 摘要作为审计证据
摘要不仅用于做账，更用于审计线索：
- **销售类**：摘要→发票→分录→收入完整性验证
- **采购类**：摘要→合同→发票→分录→成本准确性验证
- **费用类**：摘要→发票→费用合理性验证

### 2.2 摘要-原始资料映射
| 摘要关键词 | 对应原始资料 | 审计目标 |
|---------|------------|---------|
| 收到货款 | 银行回单+发票 | 完整性/存在性 |
| 支付采购款 | 发票+合同 | 准确性/完整性 |
| 计提折旧 | 固定资产清单 | 准确性 |
| 工资 | 工资表+银行回单 | 完整性/准确性 |

## 3. 设计方案

### 3.1 摘要模板库（与凭证字联动）

**核心原则**：摘要库不仅是推荐工具，更是审计案例库，用于识别分录逻辑错误。

```python
SUMMARY_TEMPLATES = {
    "银": {
        # 收款类
        "收款_销售收入": {
            "template": "收到{客户}货款",
            "debit": "银行存款",
            "credit_pattern": ["主营业务收入", "应交税费"],
            "expected_flow": "银行↑ → 收入↑",
            "risk_patterns": {
                "mismatch_credit": "贷方不是收入类科目",
            },
        },
        "收款_预收款": {
            "template": "收到{客户}预付款",
            "debit": "银行存款",
            "credit_pattern": ["预收账款"],
            "expected_flow": "银行↑ → 负债↑",
        },
        "付款_采购款": {
            "template": "支付{供应商}{商品}款",
            "debit_pattern": ["在途物资", "原材料", "应付账款"],
            "credit": "银行存款",
            "expected_flow": "资产↑ → 银行↓",
            "risk_patterns": {
                "mismatch_debit": "借方不是资产/应付类科目",
            },
        },
        "付款_费用": {
            "template": "支付{费用项}",
            "debit_pattern": ["管理费用", "销售费用"],
            "credit": "银行存款",
            "expected_flow": "费用↑ → 银行↓",
        },
    },
    "现": {
        "提现": {
            "template": "提现",
            "debit": "库存现金",
            "credit": "银行存款",
            "expected_flow": "现金↑ → 银行↓",
        },
        "报销": {
            "template": "报销{部门}{人员}差旅费",
            "debit_pattern": ["管理费用", "销售费用"],
            "credit": "库存现金",
            "expected_flow": "费用↑ → 现金↓",
        },
        "工资": {
            "template": "发放{人员}工资",
            "debit_pattern": ["应付职工薪酬"],
            "credit": "库存现金",
            "expected_flow": "负债↓ → 现金↓",
        },
    },
    "转": {
        "计提_工资": {
            "template": "计提{期间}工资",
            "debit_pattern": ["管理费用", "销售费用"],
            "credit": ["应付职工薪酬"],
            "expected_flow": "费用↑ → 负债↑",
        },
        "计提_折旧": {
            "template": "计提{期间}折旧",
            "debit_pattern": ["管理费用", "制造费用"],
            "credit": ["累计折旧"],
            "expected_flow": "费用↑ → 资产备抵↑",
        },
        "摊销_费用": {
            "template": "摊销{期间}{费用项}",
            "debit_pattern": ["管理费用"],
            "credit": ["长期待摊费用"],
            "expected_flow": "费用↑ → 资产↓",
        },
        "结转_成本": {
            "template": "结转{期间}成本",
            "debit_pattern": ["主营业务成本"],
            "credit": ["库存商品"],
            "expected_flow": "成本↑ → 资产↓",
        },
        "结转_收入": {
            "template": "结转{期间}收入",
            "debit_pattern": ["主营业务收入"],
            "credit": ["本年利润"],
            "expected_flow": "收入↓ → 权益↑",
        },
    },
    "记": {
        "调整": {
            "template": "调整{科目}{说明}",
            "debit_pattern": ["任意"],
            "credit_pattern": ["任意"],
            "expected_flow": "调整分录",
            "risk_patterns": {
                "suspicious_amount": "调整金额过大",
            },
        },
    },
}
```

### 3.2 摘要库作为审计案例库

**核心设计**：摘要模板中的 `risk_patterns` 不仅是校验规则，更是向量库中的风险案例模板。

```python
class RiskCaseTemplate:
    """风险案例模板"""
    summary_pattern: str      # 摘要模式
    debit_account_pattern: str
    credit_account_pattern: str
    risk_type: str           # 错账/异常/可疑
    risk_description: str    # 风险描述
    severity: str            # 高/中/低
    audit_suggestion: str    # 审计建议

# 预定义风险案例
RISK_CASES = [
    RiskCaseTemplate(
        summary_pattern="收到货款",
        debit_account_pattern="银行存款",
        credit_account_pattern="应付账款",  # ❌ 错误：货款不应进应付
        risk_type="错账",
        risk_description="摘要为收到货款，但贷方为应付账款而非收入类科目",
        severity="高",
        audit_suggestion="核实是否为销售退回或款项性质确认错误",
    ),
    RiskCaseTemplate(
        summary_pattern="支付货款",
        debit_account_pattern="管理费用",
        credit_account_pattern="银行存款",
        risk_type="可疑",
        risk_description="摘要为支付货款，但借方为费用类科目",
        severity="中",
        audit_suggestion="核实款项性质，是否存在费用化错误",
    ),
    # ... 更多案例
]
```
```

### 2.2 摘要推荐流程

```
导入分录 → 识别凭证字 → 提取科目 → 匹配摘要模板 → 推荐摘要候选
```

### 2.3 逻辑自洽校验

#### 校验规则

| 规则 | 条件 | 判断 |
|-----|------|-----|
| 摘要-科目匹配 | 摘要关键词 vs 对方科目 | 摘要"销售收入"→对方科目应是"主营业务收入/应交税费"，而非"应付账款" |
| 借贷平衡 | 借方合计 vs 贷方合计 | 必须相等 |
| 凭证字-科目匹配 | 凭证字 vs 科目关键词 | "银字"凭证的对方科目应包含"银行存款" |
| 金额-摘要匹配 | 大额 vs 摘要 | 大额但摘要模糊 → 标记复核 |

#### 校验示例

| 摘要 | 借方科目 | 贷方科目 | 判断 |
|-----|---------|---------|-----|
| 收到货款 | 银行存款 | 主营业务收入 | ✅ 正常 |
| 收到货款 | 银行存款 | 应付账款 | ❌ 错误（摘要与科目不匹配）|
| 支付货款 | 在途物资 | 银行存款 | ✅ 正常 |
| 支付货款 | 管理费用 | 银行存款 | ⚠️ 可疑（支付货款却入费用）|

### 2.4 摘要库数据结构

```python
class SummaryTemplate:
    template: str           # 摘要模板，如"收到{客户}货款"
    voucher_type: str       # 对应凭证字：银/现/转/记
    debit_patterns: list    # 借方科目模式
    credit_patterns: list   # 贷方科目模式
    keywords: list          # 关键词列表（用于匹配）
    examples: list          # 示例
    business_meaning: str    # 业务含义

class LogicCheckResult:
    is_consistent: bool
    issue_type: str          # mismatch/suspicious/unbalanced
    message: str
    severity: str           # error/warning/info
    suggestion: str          # 修正建议
```

## 3. 实现计划

### Phase 1: 摘要模板库
- 创建 `summary_template_service.py`
- 定义与凭证字联动的摘要模板
- 实现模板匹配引擎

### Phase 2: 摘要推荐
- 基于凭证字和科目推荐摘要
- 前端展示摘要候选

### Phase 3: 逻辑校验
- 实现摘要-科目匹配校验
- 实现借贷平衡校验
- 实现凭证字-科目匹配校验

### Phase 4: 校验报告
- 在导入报告中展示逻辑校验结果
- 标记可疑分录

## 4. 技术实现

### 4.1 摘要推荐算法

```python
def recommend_summary(voucher_type: str, debit_account: str, credit_account: str, amount: float) -> list[dict]:
    """推荐摘要"""
    candidates = []

    for category, templates in SUMMARY_TEMPLATES.get(voucher_type, {}).items():
        # 检查借方科目匹配
        debit_match = any(p in debit_account or p in credit_account
                          for p in templates.get("debit_patterns", []))
        # 检查贷方科目匹配
        credit_match = any(p in debit_account or p in credit_account
                           for p in templates.get("credit_patterns", []))

        if debit_match or credit_match:
            candidates.append({
                "template": templates["template"],
                "category": category,
                "confidence": 0.8 if debit_match and credit_match else 0.5,
            })

    return sorted(candidates, key=lambda x: x["confidence"], reverse=True)
```

### 4.2 逻辑校验算法

```python
def check_logic_consistency(entry: dict, summary_library: dict) -> LogicCheckResult:
    """校验分录逻辑自洽性"""

    # 1. 检查摘要-科目匹配
    summary_keywords = extract_keywords(entry["summary"])
    for keyword in summary_keywords:
        expected_accounts = summary_library.get(keyword, {}).get("expected_accounts", [])
        actual_account = entry.get("account_name", "")
        if expected_accounts and not any(e in actual_account for e in expected_accounts):
            return LogicCheckResult(
                is_consistent=False,
                issue_type="mismatch",
                message=f"摘要包含「{keyword}」，但科目是「{actual_account}」",
                severity="error",
                suggestion=f"「{keyword}」通常对应{expected_accounts}",
            )

    # 2. 检查借贷平衡
    if entry["debit_amount"] != entry["credit_amount"]:
        return LogicCheckResult(
            is_consistent=False,
            issue_type="unbalanced",
            message="借贷不平衡",
            severity="error",
        )

    return LogicCheckResult(is_consistent=True, issue_type=None)
```
