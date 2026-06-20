# 原始文件解析引擎与数据库设计规范

## 1. 设计理念

### 1.1 核心原则

**稳定框架 + 灵活映射**：
- **稳定框架**：核心字段存入关系数据库（SQLite/PostgreSQL）
- **灵活映射**：字段别名、不同称谓通过大模型判断
- **准则视角**：从收入准则等审计准则出发设计解析引擎

### 1.2 原始文件范围扩展

| 文件类型 | 子类型 | 审计准则关联 | 解析复杂度 |
|---------|-------|-------------|-----------|
| **合同** | 采购合同、销售合同、服务合同、框架协议、补充协议 | 收入准则、采购循环 | ⭐⭐⭐⭐⭐ |
| **订单** | 采购订单、销售订单、框架订单 | 收入确认时点 | ⭐⭐⭐ |
| **入库单** | 验收单、收货单、领料单、退库单 | 存货确认 | ⭐⭐⭐ |
| **出库单** | 发货单、提货单、退货单 | 收入确认 | ⭐⭐⭐ |
| **发票** | 增值税专用发票、普通发票、电子发票 | 税务、债权确认 | ⭐⭐⭐⭐ |
| **银行回单** | 转账回单、收款回单、电子回单 | 资金流水 | ⭐⭐⭐ |
| **物流单据** | 运单、快递单、签收单 | 收入确认时点 | ⭐⭐ |
| **结算单** | 对账单、结算确认单 | 应收应付确认 | ⭐⭐⭐ |
| **验收单** | 验收报告、检测报告、确认函 | 履约义务完成 | ⭐⭐⭐⭐ |
| **审批单** | 请购单、付款申请单、费用报销单 | 内控证据 | ⭐⭐⭐ |

## 2. 数据库设计

### 2.1 合同表（核心）

```sql
-- 合同主表
CREATE TABLE contracts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 基本信息
    contract_no VARCHAR(100),              -- 合同编号
    contract_type VARCHAR(50),            -- 合同类型：采购/销售/服务/框架
    contract_name VARCHAR(500),           -- 合同名称
    
    -- 时间信息
    sign_date DATE,                       -- 签订日期
    start_date DATE,                      -- 开始日期
    end_date DATE,                        -- 结束日期
    effective_date DATE,                  -- 生效日期
    
    -- 金额信息
    contract_amount DECIMAL(18, 2),       -- 合同总金额
    currency VARCHAR(10) DEFAULT 'CNY',   -- 币种
    tax_rate DECIMAL(5, 4),               -- 税率
    tax_amount DECIMAL(18, 2),            -- 税额
    
    -- 履约义务（收入准则）
    performance_obligations TEXT,         -- 履约义务描述（JSON）
    transaction_price DECIMAL(18, 2),     -- 交易价格
    standalone_price DECIMAL(18, 2),      -- 单独售价
    
    -- 分时段履约
    is_over_time BOOLEAN DEFAULT FALSE,   -- 是否分时段履约
    progress_method VARCHAR(50),          -- 进度确认方法：投入法/产出法
    completion_percentage DECIMAL(5, 2),  -- 完工百分比
    
    -- 审计标记
    revenue_recognition_type VARCHAR(50), -- 收入确认类型：时点/时段
    risk_flags TEXT,                      -- 风险标记（JSON）
    
    -- 元数据
    source_file_id INTEGER,               -- 来源文件ID
    extracted_text TEXT,                  -- 提取的原始文本
    confidence_score DECIMAL(3, 2),       -- 解析置信度
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (source_file_id) REFERENCES source_files(id)
);

-- 合同当事人表（支持多方）
CREATE TABLE contract_parties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    
    party_role VARCHAR(50),               -- 角色：甲方/乙方/丙方/担保方/见证方
    party_type VARCHAR(50),               -- 类型：企业/个人/政府
    party_name VARCHAR(500),              -- 名称
    party_code VARCHAR(100),              -- 统一社会信用代码/身份证号
    party_address VARCHAR(500),           -- 地址
    party_contact VARCHAR(100),           -- 联系人
    party_phone VARCHAR(50),              -- 电话
    legal_representative VARCHAR(100),    -- 法定代表人
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (contract_id) REFERENCES contracts(id)
);

-- 合同履约义务明细表（收入准则核心）
CREATE TABLE contract_performance_obligations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    
    obligation_no VARCHAR(50),            -- 履约义务编号
    obligation_name VARCHAR(500),         -- 履约义务名称
    obligation_description TEXT,          -- 履约义务描述
    
    -- 价格分摊
    standalone_price DECIMAL(18, 2),      -- 单独售价
    allocated_price DECIMAL(18, 2),       -- 分摊价格
    allocation_method VARCHAR(50),        -- 分摊方法：市场调整法/成本加成法/余值法
    
    -- 履约进度
    is_over_time BOOLEAN DEFAULT FALSE,   -- 是否时段履约
    progress_method VARCHAR(50),          -- 进度方法
    completion_percentage DECIMAL(5, 2),  -- 完工百分比
    
    -- 收入确认
    revenue_recognized DECIMAL(18, 2),    -- 已确认收入
    revenue_pending DECIMAL(18, 2),       -- 待确认收入
    
    -- 审计标记
    risk_flags TEXT,                      -- 风险标记
    audit_notes TEXT,                     -- 审计备注
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (contract_id) REFERENCES contracts(id)
);

-- 合同付款条款表
CREATE TABLE contract_payment_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    
    term_no INTEGER,                      -- 条款序号
    term_name VARCHAR(200),               -- 条款名称：预付款/进度款/尾款
    term_type VARCHAR(50),                -- 类型：固定金额/比例/里程碑
    
    amount DECIMAL(18, 2),                -- 金额
    percentage DECIMAL(5, 2),             -- 比例
    milestone VARCHAR(200),               -- 里程碑描述
    
    due_date DATE,                        -- 应付日期
    due_condition TEXT,                   -- 触发条件
    
    -- 实际执行
    actual_paid DECIMAL(18, 2),           -- 实际支付
    paid_date DATE,                       -- 实际支付日期
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (contract_id) REFERENCES contracts(id)
);

-- 合同时间线表（分时段合同）
CREATE TABLE contract_timeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    
    phase_no INTEGER,                     -- 阶段序号
    phase_name VARCHAR(200),              -- 阶段名称
    phase_description TEXT,               -- 阶段描述
    
    start_date DATE,                      -- 开始日期
    end_date DATE,                        -- 结束日期
    
    -- 预算/实际
    planned_amount DECIMAL(18, 2),        -- 计划金额
    actual_amount DECIMAL(18, 2),         -- 实际金额
    completion_percentage DECIMAL(5, 2),  -- 完成百分比
    
    -- 审计标记
    status VARCHAR(50),                   -- 状态：进行中/已完成/延期
    risk_flags TEXT,                      -- 风险标记
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (contract_id) REFERENCES contracts(id)
);
```

### 2.2 发票表

```sql
-- 发票主表
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 发票基本信息
    invoice_no VARCHAR(50),               -- 发票号码
    invoice_code VARCHAR(50),             -- 发票代码
    invoice_type VARCHAR(50),             -- 类型：增值税专用发票/普通发票/电子发票
    invoice_status VARCHAR(50),           -- 状态：正常/作废/红冲
    
    -- 开票信息
    invoice_date DATE,                    -- 开票日期
    
    -- 购买方
    buyer_name VARCHAR(500),              -- 购买方名称
    buyer_tax_no VARCHAR(100),            -- 购买方税号
    buyer_address VARCHAR(500),           -- 购买方地址
    buyer_phone VARCHAR(50),              -- 购买方电话
    buyer_bank VARCHAR(200),              -- 购买方开户行
    buyer_account VARCHAR(100),           -- 购买方账号
    
    -- 销售方
    seller_name VARCHAR(500),             -- 销售方名称
    seller_tax_no VARCHAR(100),           -- 销售方税号
    seller_address VARCHAR(500),          -- 销售方地址
    seller_phone VARCHAR(50),             -- 销售方电话
    seller_bank VARCHAR(200),             -- 销售方开户行
    seller_account VARCHAR(100),          -- 销售方账号
    
    -- 金额信息
    amount_excluding_tax DECIMAL(18, 2),  -- 不含税金额
    tax_rate DECIMAL(5, 4),               -- 税率
    tax_amount DECIMAL(18, 2),            -- 税额
    total_amount DECIMAL(18, 2),          -- 价税合计
    
    -- 审计关联
    related_contract_id INTEGER,          -- 关联合同ID
    related_order_no VARCHAR(100),        -- 关联订单号
    
    -- 元数据
    source_file_id INTEGER,
    extracted_text TEXT,
    confidence_score DECIMAL(3, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (source_file_id) REFERENCES source_files(id),
    FOREIGN KEY (related_contract_id) REFERENCES contracts(id)
);

-- 发票明细表
CREATE TABLE invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    
    item_no INTEGER,                      -- 序号
    goods_name VARCHAR(500),              -- 货物/服务名称
    specification VARCHAR(200),           -- 规格型号
    unit VARCHAR(50),                     -- 单位
    quantity DECIMAL(18, 4),              -- 数量
    unit_price DECIMAL(18, 4),            -- 单价
    amount DECIMAL(18, 2),                -- 金额
    tax_rate DECIMAL(5, 4),               -- 税率
    tax_amount DECIMAL(18, 2),            -- 税额
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (invoice_id) REFERENCES invoices(id)
);
```

### 2.3 入库单/出库单表

```sql
-- 入库单/出库单主表
CREATE TABLE inventory_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 基本信息
    document_no VARCHAR(100),             -- 单据编号
    document_type VARCHAR(50),            -- 类型：入库单/出库单/领料单/退库单
    document_date DATE,                   -- 单据日期
    
    -- 仓库信息
    warehouse_name VARCHAR(200),          -- 仓库名称
    warehouse_code VARCHAR(50),           -- 仓库编码
    
    -- 往来方
    counterparty_type VARCHAR(50),        -- 类型：供应商/客户/部门
    counterparty_name VARCHAR(500),       -- 名称
    counterparty_code VARCHAR(100),       -- 编码
    
    -- 金额
    total_quantity DECIMAL(18, 4),        -- 总数量
    total_amount DECIMAL(18, 2),          -- 总金额
    
    -- 审计关联
    related_contract_id INTEGER,          -- 关联合同
    related_order_no VARCHAR(100),        -- 关联订单
    related_invoice_id INTEGER,           -- 关联发票
    
    -- 验收信息
    inspector VARCHAR(100),               -- 验收人
    inspect_date DATE,                    -- 验收日期
    inspect_result VARCHAR(50),           -- 验收结果
    
    -- 元数据
    source_file_id INTEGER,
    extracted_text TEXT,
    confidence_score DECIMAL(3, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (source_file_id) REFERENCES source_files(id),
    FOREIGN KEY (related_contract_id) REFERENCES contracts(id),
    FOREIGN KEY (related_invoice_id) REFERENCES invoices(id)
);

-- 入库单/出库单明细表
CREATE TABLE inventory_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    
    item_no INTEGER,                      -- 序号
    goods_name VARCHAR(500),              -- 货物名称
    specification VARCHAR(200),           -- 规格型号
    unit VARCHAR(50),                     -- 单位
    quantity DECIMAL(18, 4),              -- 数量
    unit_price DECIMAL(18, 4),            -- 单价
    amount DECIMAL(18, 2),                -- 金额
    batch_no VARCHAR(100),                -- 批号
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (document_id) REFERENCES inventory_documents(id)
);
```

### 2.4 银行回单表

```sql
-- 银行回单表
CREATE TABLE bank_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 交易信息
    transaction_no VARCHAR(100),          -- 交易流水号
    transaction_date DATE,                -- 交易日期
    transaction_time TIME,                -- 交易时间
    transaction_type VARCHAR(50),         -- 类型：收入/支出
    
    -- 本方账户
    account_name VARCHAR(500),            -- 账户名称
    account_no VARCHAR(100),              -- 账号
    bank_name VARCHAR(200),               -- 开户行
    
    -- 对方账户
    counterparty_name VARCHAR(500),       -- 对方户名
    counterparty_account VARCHAR(100),    -- 对方账号
    counterparty_bank VARCHAR(200),       -- 对方银行
    
    -- 金额
    amount DECIMAL(18, 2),                -- 金额
    balance DECIMAL(18, 2),               -- 余额
    
    -- 摘要
    summary VARCHAR(500),                 -- 摘要
    purpose VARCHAR(500),                 -- 用途
    remark VARCHAR(500),                  -- 备注
    
    -- 审计关联
    related_contract_id INTEGER,          -- 关联合同
    related_invoice_id INTEGER,           -- 关联发票
    
    -- 元数据
    source_file_id INTEGER,
    extracted_text TEXT,
    confidence_score DECIMAL(3, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (source_file_id) REFERENCES source_files(id),
    FOREIGN KEY (related_contract_id) REFERENCES contracts(id),
    FOREIGN KEY (related_invoice_id) REFERENCES invoices(id)
);
```

### 2.5 字段别名映射表

```sql
-- 字段别名映射表（灵活映射）
CREATE TABLE field_alias_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    document_type VARCHAR(50),            -- 文档类型：contract/invoice/inventory/bank_statement
    field_name VARCHAR(100),              -- 标准字段名
    alias VARCHAR(200),                   -- 别名
    alias_type VARCHAR(50),               -- 别名类型：中文/英文/缩写/行业术语
    
    -- 置信度
    confidence DECIMAL(3, 2) DEFAULT 1.0, -- 置信度
    verified BOOLEAN DEFAULT FALSE,       -- 是否人工验证
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 预置常用别名
INSERT INTO field_alias_mappings (document_type, field_name, alias, alias_type) VALUES
-- 合同字段别名
('contract', 'contract_no', '合同编号', '中文'),
('contract', 'contract_no', '合同号', '中文'),
('contract', 'contract_no', '合约编号', '中文'),
('contract', 'contract_no', 'contract_no', '英文'),
('contract', 'contract_no', 'contract number', '英文'),
('contract', 'contract_amount', '合同金额', '中文'),
('contract', 'contract_amount', '总金额', '中文'),
('contract', 'contract_amount', '合同总价', '中文'),
('contract', 'contract_amount', 'amount', '英文'),
('contract', 'sign_date', '签订日期', '中文'),
('contract', 'sign_date', '签署日期', '中文'),
('contract', 'sign_date', '签约日期', '中文'),
('contract', 'sign_date', 'sign_date', '英文'),

-- 发票字段别名
('invoice', 'invoice_no', '发票号码', '中文'),
('invoice', 'invoice_no', '发票号', '中文'),
('invoice', 'invoice_no', '票号', '中文'),
('invoice', 'invoice_no', 'invoice_no', '英文'),
('invoice', 'buyer_name', '购买方', '中文'),
('invoice', 'buyer_name', '购货方', '中文'),
('invoice', 'buyer_name', '购方名称', '中文'),
('invoice', 'seller_name', '销售方', '中文'),
('invoice', 'seller_name', '销货方', '中文'),
('invoice', 'seller_name', '销方名称', '中文'),

-- 银行回单字段别名
('bank_statement', 'transaction_no', '交易流水号', '中文'),
('bank_statement', 'transaction_no', '流水号', '中文'),
('bank_statement', 'transaction_no', '交易号', '中文'),
('bank_statement', 'counterparty_name', '对方户名', '中文'),
('bank_statement', 'counterparty_name', '对方名称', '中文'),
('bank_statement', 'counterparty_name', '收款人', '中文'),
('bank_statement', 'counterparty_name', '付款人', '中文');
```

## 3. 合同解析引擎（收入准则视角）

### 3.1 收入准则五步法

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    收入准则五步法识别                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   第一步：识别合同                                                           │
│   ├─ 合同是否存在？                                                          │
│   ├─ 合同各方是否已批准？                                                    │
│   ├─ 各方权利义务是否明确？                                                  │
│   └─ 支付条款是否明确？                                                      │
│                                                                             │
│   第二步：识别履约义务                                                       │
│   ├─ 合同中承诺的商品/服务                                                   │
│   ├─ 是否可明确区分？                                                        │
│   ├─ 是否需要合并？                                                          │
│   └─ 履约义务数量                                                            │
│                                                                             │
│   第三步：确定交易价格                                                       │
│   ├─ 合同金额                                                                │
│   ├─ 可变对价？                                                              │
│   ├─ 重大融资成分？                                                          │
│   ├─ 非现金对价？                                                            │
│   └─ 应付客户对价？                                                          │
│                                                                             │
│   第四步：分摊交易价格                                                       │
│   ├─ 各履约义务单独售价                                                      │
│   ├─ 分摊方法：市场调整法/成本加成法/余值法                                  │
│   └─ 分摊结果                                                                │
│                                                                             │
│   第五步：确认收入                                                           │
│   ├─ 时段履约 vs 时点履约                                                    │
│   ├─ 时段履约：进度确认方法                                                  │
│   └─ 时点履约：控制权转移时点                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 履约义务识别引擎

```python
class PerformanceObligationIdentifier:
    """履约义务识别引擎"""
    
    def identify(self, contract: Contract) -> List[PerformanceObligation]:
        """
        识别合同中的履约义务
        """
        obligations = []
        
        # 1. 提取合同中的承诺事项
        promises = self._extract_promises(contract)
        
        # 2. 判断是否可明确区分
        for promise in promises:
            is_distinct = self._check_distinctness(promise, contract)
            
            if is_distinct:
                # 单独的履约义务
                obligations.append(PerformanceObligation(
                    name=promise.name,
                    description=promise.description,
                    is_distinct=True,
                ))
            else:
                # 需要合并
                self._merge_obligations(obligations, promise)
        
        # 3. 判断履约类型（时段 vs 时点）
        for obligation in obligations:
            obligation.is_over_time = self._check_over_time(obligation, contract)
            
            if obligation.is_over_time:
                obligation.progress_method = self._determine_progress_method(obligation, contract)
        
        return obligations
    
    def _check_distinctness(self, promise: Promise, contract: Contract) -> bool:
        """
        判断承诺是否可明确区分
        
        收入准则标准：
        1. 客户能够从该商品/服务本身获取利益
        2. 企业向客户转让该商品/服务的承诺与合同中其他承诺可明确区分
        """
        # 检查是否可单独使用
        can_benefit_alone = self._check_individual_benefit(promise)
        
        # 检查是否与合同中其他承诺相关联
        is_separable = self._check_separability(promise, contract)
        
        return can_benefit_alone and is_separable
    
    def _check_over_time(self, obligation: PerformanceObligation, contract: Contract) -> bool:
        """
        判断是否时段履约
        
        收入准则标准（满足任一即为时段履约）：
        1. 客户在企业履约的同时即取得并消耗企业履约所带来的经济利益
        2. 客户能够控制企业履约过程中在建的商品
        3. 企业履约过程中所产出的商品具有不可替代用途，且企业在整个合同期间内有权就累计至今已完成的履约部分收取款项
        """
        # 检查条件1：客户同时消耗利益
        condition_1 = self._check_simultaneous_consumption(obligation, contract)
        
        # 检查条件2：客户控制在建商品
        condition_2 = self._check_customer_control(obligation, contract)
        
        # 检查条件3：不可替代用途 + 收取款项权利
        condition_3 = self._check_no_alternative_use_and_enforceable_right(obligation, contract)
        
        return condition_1 or condition_2 or condition_3
```

### 3.3 合同解析流程

```python
class ContractParser:
    """合同解析引擎"""
    
    def parse(self, file_path: str) -> Contract:
        """
        解析合同文件
        """
        # 1. 提取文本
        raw_text = self._extract_text(file_path)
        
        # 2. 结构化解析
        structured_data = self._structure_parse(raw_text)
        
        # 3. 字段映射（灵活映射）
        mapped_data = self._field_mapping(structured_data)
        
        # 4. 大模型辅助判断
        ai_enhanced_data = self._ai_enhance(mapped_data, raw_text)
        
        # 5. 收入准则识别
        revenue_data = self._revenue_recognition_analysis(ai_enhanced_data)
        
        # 6. 风险识别
        risk_flags = self._risk_identification(revenue_data)
        
        # 7. 构建合同对象
        contract = Contract(
            contract_no=revenue_data.get('contract_no'),
            contract_type=revenue_data.get('contract_type'),
            # ... 其他字段
            performance_obligations=revenue_data.get('performance_obligations', []),
            risk_flags=risk_flags,
            confidence_score=revenue_data.get('confidence', 0.8),
        )
        
        return contract
    
    def _field_mapping(self, structured_data: dict) -> dict:
        """
        字段映射（支持别名）
        """
        mapped = {}
        
        for standard_field, value in structured_data.items():
            # 查询别名映射表
            aliases = self._get_aliases('contract', standard_field)
            
            # 尝试匹配
            for alias in aliases:
                if alias in structured_data:
                    mapped[standard_field] = structured_data[alias]
                    break
        
        return mapped
    
    def _ai_enhance(self, mapped_data: dict, raw_text: str) -> dict:
        """
        大模型辅助判断
        """
        # 对于无法确定映射的字段，调用大模型
        uncertain_fields = self._find_uncertain_fields(mapped_data)
        
        if uncertain_fields:
            prompt = f"""
            以下是一份合同的原始文本：
            {raw_text}
            
            请识别以下字段的值：
            {uncertain_fields}
            
            返回 JSON 格式。
            """
            
            ai_result = self._call_llm(prompt)
            mapped_data.update(ai_result)
        
        return mapped_data
    
    def _revenue_recognition_analysis(self, data: dict) -> dict:
        """
        收入准则分析
        """
        # 五步法识别
        identifier = PerformanceObligationIdentifier()
        
        contract = Contract(**data)
        obligations = identifier.identify(contract)
        
        data['performance_obligations'] = obligations
        data['revenue_recognition_type'] = self._determine_recognition_type(obligations)
        
        return data
```

## 4. 字段别名映射引擎

### 4.1 映射策略

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    字段别名映射策略                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   输入：原始字段名                                                           │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  1. 精确匹配                                                      │     │
│   │     - 查询 field_alias_mappings 表                               │     │
│   │     - 置信度 = 1.0                                               │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                              ↓ 不匹配                                        │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  2. 模糊匹配                                                      │     │
│   │     - 相似度计算（Levenshtein 距离）                             │     │
│   │     - 相似度 > 0.8 则采用                                        │     │
│   │     - 置信度 = 相似度                                            │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                              ↓ 不匹配                                        │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  3. 语义匹配                                                      │     │
│   │     - 使用 Embedding 向量相似度                                  │     │
│   │     - 相似度 > 0.85 则采用                                       │     │
│   │     - 置信度 = 相似度                                            │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                              ↓ 不匹配                                        │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  4. 大模型判断                                                    │     │
│   │     - 调用 LLM 进行语义理解                                      │     │
│   │     - 返回最可能的映射                                           │     │
│   │     - 置信度 = LLM 返回的置信度                                  │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                              ↓                                               │
│   输出：标准字段名 + 置信度                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 映射实现

```python
class FieldAliasMapper:
    """字段别名映射器"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def map_field(
        self, 
        document_type: str, 
        raw_field_name: str
    ) -> Tuple[str, float]:
        """
        映射字段名到标准字段名
        
        Returns:
            (标准字段名, 置信度)
        """
        # 1. 精确匹配
        result = self._exact_match(document_type, raw_field_name)
        if result:
            return result
        
        # 2. 模糊匹配
        result = self._fuzzy_match(document_type, raw_field_name)
        if result:
            return result
        
        # 3. 语义匹配
        result = self._semantic_match(document_type, raw_field_name)
        if result:
            return result
        
        # 4. 大模型判断
        result = self._llm_match(document_type, raw_field_name)
        if result:
            # 保存新的映射到数据库
            self._save_new_mapping(document_type, result[0], raw_field_name)
            return result
        
        return (raw_field_name, 0.0)  # 无法映射，保持原名
    
    def _exact_match(self, document_type: str, field_name: str) -> Optional[Tuple[str, float]]:
        """精确匹配"""
        mapping = self.db.query(FieldAliasMapping).filter(
            FieldAliasMapping.document_type == document_type,
            FieldAliasMapping.alias == field_name,
        ).first()
        
        if mapping:
            return (mapping.field_name, mapping.confidence)
        return None
    
    def _fuzzy_match(self, document_type: str, field_name: str) -> Optional[Tuple[str, float]]:
        """模糊匹配"""
        all_mappings = self.db.query(FieldAliasMapping).filter(
            FieldAliasMapping.document_type == document_type,
        ).all()
        
        best_match = None
        best_similarity = 0.0
        
        for mapping in all_mappings:
            similarity = self._calculate_similarity(field_name, mapping.alias)
            if similarity > 0.8 and similarity > best_similarity:
                best_similarity = similarity
                best_match = mapping
        
        if best_match:
            return (best_match.field_name, best_similarity)
        return None
    
    def _semantic_match(self, document_type: str, field_name: str) -> Optional[Tuple[str, float]]:
        """语义匹配（使用 Embedding）"""
        # 获取字段名的 Embedding
        field_embedding = self._get_embedding(field_name)
        
        # 获取所有标准字段的 Embedding
        standard_fields = self._get_standard_fields(document_type)
        
        best_match = None
        best_similarity = 0.0
        
        for standard_field, standard_embedding in standard_fields.items():
            similarity = self._cosine_similarity(field_embedding, standard_embedding)
            if similarity > 0.85 and similarity > best_similarity:
                best_similarity = similarity
                best_match = standard_field
        
        if best_match:
            return (best_match, best_similarity)
        return None
    
    def _llm_match(self, document_type: str, field_name: str) -> Optional[Tuple[str, float]]:
        """大模型判断"""
        standard_fields = self._get_standard_field_names(document_type)
        
        prompt = f"""
        以下是一个{document_type}文档中的字段名：
        "{field_name}"
        
        请判断它最可能对应以下哪个标准字段：
        {standard_fields}
        
        返回 JSON 格式：
        {{"standard_field": "字段名", "confidence": 0.0-1.0}}
        """
        
        result = self._call_llm(prompt)
        if result and result.get('standard_field'):
            return (result['standard_field'], result.get('confidence', 0.7))
        return None
```

## 5. 审计风险识别

### 5.1 合同相关风险

```python
CONTRACT_RISK_RULES = {
    # 收入确认风险
    "revenue_recognition": {
        "rules": [
            {
                "id": "RR-001",
                "name": "履约义务识别不完整",
                "condition": "performance_obligations 为空或数量 < 1",
                "risk_level": "high",
                "description": "合同未识别出明确的履约义务，可能导致收入确认错误",
                "audit_procedure": "重新评估合同条款，识别所有履约义务",
            },
            {
                "id": "RR-002",
                "name": "时段履约判断存疑",
                "condition": "is_over_time = true 但 progress_method 为空",
                "risk_level": "medium",
                "description": "合同判断为时段履约，但未确定进度确认方法",
                "audit_procedure": "评估履约进度确认方法的合理性",
            },
            {
                "id": "RR-003",
                "name": "交易价格分摊不合理",
                "condition": "sum(allocated_price) != transaction_price",
                "risk_level": "high",
                "description": "履约义务价格分摊之和与交易价格不一致",
                "audit_procedure": "重新计算价格分摊",
            },
        ],
    },
    
    # 合同完整性风险
    "contract_completeness": {
        "rules": [
            {
                "id": "CC-001",
                "name": "合同当事人缺失",
                "condition": "parties 数量 < 2",
                "risk_level": "high",
                "description": "合同当事人不完整",
                "audit_procedure": "核实合同各方身份",
            },
            {
                "id": "CC-002",
                "name": "合同期限不明确",
                "condition": "start_date 或 end_date 为空",
                "risk_level": "medium",
                "description": "合同期限不明确，影响收入确认期间",
                "audit_procedure": "确认合同执行期限",
            },
            {
                "id": "CC-003",
                "name": "付款条款缺失",
                "condition": "payment_terms 为空",
                "risk_level": "medium",
                "description": "合同未明确付款条款",
                "audit_procedure": "确认付款安排",
            },
        ],
    },
    
    # 合同执行风险
    "contract_execution": {
        "rules": [
            {
                "id": "CE-001",
                "name": "合同延期风险",
                "condition": "end_date < now() AND completion_percentage < 100",
                "risk_level": "high",
                "description": "合同已到期但未完成",
                "audit_procedure": "评估合同延期原因及影响",
            },
            {
                "id": "CE-002",
                "name": "履约进度异常",
                "condition": "completion_percentage 与实际付款进度差异 > 20%",
                "risk_level": "medium",
                "description": "履约进度与付款进度不匹配",
                "audit_procedure": "核实履约进度真实性",
            },
        ],
    },
}
```

## 6. 向量化标签存储

### 6.1 设计理念

**所有原始文件都应当有一部分 tag 存放在向量数据库中，便于后期任务中时刻提取相关 tag 辅助判断是否存在风险或关联事务。**

### 6.2 标签向量化架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    原始文件标签向量化架构                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   原始文件解析                                                               │
│       │                                                                     │
│       ↓                                                                     │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  结构化数据 → SQLite/PostgreSQL                                   │     │
│   │  - 合同编号、金额、日期、当事人等稳定字段                          │     │
│   │  - 支持复杂查询和关联                                             │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│       │                                                                     │
│       ↓                                                                     │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  语义标签 → Qdrant 向量数据库                                     │     │
│   │  - 业务类型标签                                                   │     │
│   │  - 风险标签                                                       │     │
│   │  - 关联标签                                                       │     │
│   │  - 时间标签                                                       │     │
│   │  - 金额标签                                                       │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│       │                                                                     │
│       ↓                                                                     │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  后期任务 → 向量检索辅助判断                                      │     │
│   │  - 风险识别：检索相似风险标签                                     │     │
│   │  - 关联事务：检索相关当事人/金额/时间标签                         │     │
│   │  - 异常检测：检索异常模式标签                                     │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.3 标签类型定义

```python
class DocumentTag:
    """原始文件标签"""
    
    # 业务类型标签
    BUSINESS_TAGS = {
        "业务类型:采购合同",
        "业务类型:销售合同",
        "业务类型:服务合同",
        "业务类型:框架协议",
        "业务类型:补充协议",
        "业务类型:增值税专用发票",
        "业务类型:普通发票",
        "业务类型:入库单",
        "业务类型:出库单",
        "业务类型:银行回单",
    }
    
    # 风险标签
    RISK_TAGS = {
        "风险:履约义务识别不完整",
        "风险:时段履约判断存疑",
        "风险:交易价格分摊不合理",
        "风险:合同当事人缺失",
        "风险:合同期限不明确",
        "风险:付款条款缺失",
        "风险:合同延期",
        "风险:履约进度异常",
        "风险:金额异常",
        "风险:日期异常",
        "风险:当事人关联异常",
    }
    
    # 关联标签
    RELATION_TAGS = {
        "关联:当事人:{当事人名称}",
        "关联:合同:{合同编号}",
        "关联:发票:{发票号码}",
        "关联:订单:{订单编号}",
        "关联:项目:{项目名称}",
    }
    
    # 时间标签
    TIME_TAGS = {
        "时间:年度:{年份}",
        "时间:季度:{年份}Q{季度}",
        "时间:月份:{年份}-{月份}",
        "时间:期间:{开始日期}至{结束日期}",
    }
    
    # 金额标签
    AMOUNT_TAGS = {
        "金额:区间:{区间}",
        "金额:级别:小额",      # < 1万
        "金额:级别:中额",      # 1万-10万
        "金额:级别:大额",      # 10万-100万
        "金额:级别:巨额",      # > 100万
    }
    
    # 状态标签
    STATUS_TAGS = {
        "状态:待处理",
        "状态:处理中",
        "状态:已完成",
        "状态:异常",
        "状态:需复核",
    }
```

### 6.4 标签向量化实现

```python
class DocumentTagIndexer:
    """原始文件标签向量化索引器"""
    
    def __init__(self, vector_store: QdrantClient, embedding_service):
        self.vector_store = vector_store
        self.embedding_service = embedding_service
    
    def index_document_tags(
        self, 
        document_id: int, 
        document_type: str, 
        parsed_data: dict
    ) -> List[str]:
        """
        为原始文件生成并索引标签
        """
        tags = []
        
        # 1. 业务类型标签
        tags.append(f"业务类型:{document_type}")
        
        # 2. 风险标签（基于规则识别）
        risk_tags = self._identify_risk_tags(document_type, parsed_data)
        tags.extend(risk_tags)
        
        # 3. 关联标签
        relation_tags = self._extract_relation_tags(document_type, parsed_data)
        tags.extend(relation_tags)
        
        # 4. 时间标签
        time_tags = self._extract_time_tags(parsed_data)
        tags.extend(time_tags)
        
        # 5. 金额标签
        amount_tags = self._extract_amount_tags(parsed_data)
        tags.extend(amount_tags)
        
        # 6. 向量化存储
        for tag in tags:
            self._index_tag(document_id, document_type, tag)
        
        return tags
    
    def _index_tag(self, document_id: int, document_type: str, tag: str):
        """向量化存储标签"""
        # 获取标签的 embedding
        embedding = self.embedding_service.embed_text(tag)
        
        # 存入向量数据库
        self.vector_store.upsert(
            collection_name="document_tags",
            points=[{
                "id": f"{document_type}_{document_id}_{hash(tag)}",
                "vector": embedding,
                "payload": {
                    "document_id": document_id,
                    "document_type": document_type,
                    "tag": tag,
                    "tag_type": self._get_tag_type(tag),
                    "created_at": datetime.now().isoformat(),
                }
            }]
        )
    
    def search_related_tags(
        self, 
        query: str, 
        top_k: int = 10,
        filter_conditions: dict = None
    ) -> List[dict]:
        """
        检索相关标签
        """
        # 获取查询的 embedding
        query_embedding = self.embedding_service.embed_text(query)
        
        # 向量检索
        results = self.vector_store.search(
            collection_name="document_tags",
            query_vector=query_embedding,
            limit=top_k,
            query_filter=filter_conditions,
        )
        
        return results
    
    def search_by_tag(self, tag: str, top_k: int = 10) -> List[dict]:
        """
        根据标签检索相关文档
        """
        # 获取标签的 embedding
        tag_embedding = self.embedding_service.embed_text(tag)
        
        # 向量检索
        results = self.vector_store.search(
            collection_name="document_tags",
            query_vector=tag_embedding,
            limit=top_k,
        )
        
        return results
    
    def find_similar_documents(
        self, 
        document_id: int, 
        document_type: str,
        top_k: int = 5
    ) -> List[dict]:
        """
        查找相似文档（基于标签相似度）
        """
        # 获取该文档的所有标签
        doc_tags = self._get_document_tags(document_id, document_type)
        
        # 基于标签向量检索相似文档
        similar_docs = []
        for tag in doc_tags:
            results = self.search_by_tag(tag, top_k=top_k + 1)
            for result in results:
                if result.payload["document_id"] != document_id:
                    similar_docs.append({
                        "document_id": result.payload["document_id"],
                        "document_type": result.payload["document_type"],
                        "matched_tag": tag,
                        "similarity": result.score,
                    })
        
        # 去重并排序
        return self._deduplicate_and_sort(similar_docs, top_k)
```

### 6.5 向量检索辅助判断

```python
class VectorAssistedJudgment:
    """向量检索辅助判断"""
    
    def __init__(self, tag_indexer: DocumentTagIndexer):
        self.tag_indexer = tag_indexer
    
    def check_risk_association(
        self, 
        document_id: int, 
        document_type: str
    ) -> List[dict]:
        """
        检查风险关联
        """
        # 检索相似的风险标签
        risk_tags = self.tag_indexer.search_related_tags(
            query="风险 异常 可疑",
            filter_conditions={"tag_type": "risk"},
            top_k=20,
        )
        
        # 获取当前文档的标签
        doc_tags = self.tag_indexer._get_document_tags(document_id, document_type)
        
        # 检查是否有匹配的风险标签
        risk_associations = []
        for risk_tag in risk_tags:
            if any(self._is_similar(risk_tag.payload["tag"], t) for t in doc_tags):
                risk_associations.append({
                    "risk_tag": risk_tag.payload["tag"],
                    "related_document_id": risk_tag.payload["document_id"],
                    "similarity": risk_tag.score,
                })
        
        return risk_associations
    
    def find_related_transactions(
        self, 
        counterparty: str,
        amount_range: tuple = None,
        time_range: tuple = None
    ) -> List[dict]:
        """
        查找关联事务
        """
        # 构建查询
        query_parts = [f"关联:当事人:{counterparty}"]
        if amount_range:
            query_parts.append(f"金额:区间:{amount_range}")
        if time_range:
            query_parts.append(f"时间:期间:{time_range}")
        
        # 向量检索
        related_docs = []
        for query in query_parts:
            results = self.tag_indexer.search_by_tag(query, top_k=20)
            related_docs.extend(results)
        
        return self._deduplicate_and_sort(related_docs)
    
    def detect_anomaly_patterns(
        self, 
        document_type: str,
        parsed_data: dict
    ) -> List[dict]:
        """
        检测异常模式
        """
        anomalies = []
        
        # 1. 金额异常检测
        amount = parsed_data.get("amount") or parsed_data.get("contract_amount")
        if amount:
            # 检索相似金额的历史记录
            similar_amount_docs = self.tag_indexer.search_by_tag(
                f"金额:区间:{self._get_amount_range(amount)}",
                top_k=10,
            )
            
            # 检查是否有风险标记
            for doc in similar_amount_docs:
                if "风险" in doc.payload.get("tag", ""):
                    anomalies.append({
                        "type": "amount_anomaly",
                        "description": f"相似金额 {amount} 的历史记录存在风险标记",
                        "related_document_id": doc.payload["document_id"],
                    })
        
        # 2. 当事人异常检测
        counterparty = parsed_data.get("counterparty") or parsed_data.get("party_name")
        if counterparty:
            related_docs = self.find_related_transactions(counterparty)
            
            # 检查是否有风险标记
            for doc in related_docs:
                if "风险" in doc.payload.get("tag", ""):
                    anomalies.append({
                        "type": "counterparty_anomaly",
                        "description": f"当事人 {counterparty} 存在历史风险记录",
                        "related_document_id": doc.payload["document_id"],
                    })
        
        return anomalies
```

### 6.6 数据库表设计

```sql
-- 文档标签表（关系数据库备份）
CREATE TABLE document_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    document_id INTEGER NOT NULL,
    document_type VARCHAR(50) NOT NULL,
    
    tag VARCHAR(500) NOT NULL,
    tag_type VARCHAR(50),              -- business/risk/relation/time/amount/status
    
    -- 向量存储信息
    vector_id VARCHAR(200),            -- Qdrant 中的 ID
    vector_stored BOOLEAN DEFAULT FALSE,
    
    -- 元数据
    confidence DECIMAL(3, 2),
    source VARCHAR(50),                -- rule/ai/manual
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (document_id) REFERENCES source_files(id)
);

CREATE INDEX idx_document_tags_document ON document_tags(document_id, document_type);
CREATE INDEX idx_document_tags_tag ON document_tags(tag);
CREATE INDEX idx_document_tags_type ON document_tags(tag_type);
```

## 7. 企业登记信息管理

### 7.1 设计理念

**合同解析时需要补充企业的登记信息，包括一般纳税人/小规模、注册资本、法人、股东、财务负责人等，以便于在整个审计过程中保持对关联交易的谨慎识别。**

### 7.2 企业信息数据库设计

```sql
-- 企业基本信息表
CREATE TABLE companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 基本信息
    company_name VARCHAR(500) NOT NULL,           -- 企业名称
    unified_social_credit_code VARCHAR(100),      -- 统一社会信用代码
    company_type VARCHAR(50),                     -- 类型：有限责任公司/股份有限公司/个人独资等
    
    -- 税务信息
    taxpayer_type VARCHAR(50),                    -- 纳税人类型：一般纳税人/小规模纳税人
    tax_registration_no VARCHAR(100),             -- 税务登记号
    tax_authority VARCHAR(200),                   -- 主管税务机关
    
    -- 注册信息
    registered_capital DECIMAL(18, 2),            -- 注册资本
    paid_in_capital DECIMAL(18, 2),               -- 实收资本
    establishment_date DATE,                      -- 成立日期
    business_term VARCHAR(100),                   -- 营业期限
    registration_status VARCHAR(50),              -- 登记状态：存续/吊销/注销
    
    -- 经营信息
    business_scope TEXT,                          -- 经营范围
    registered_address VARCHAR(500),              -- 注册地址
    actual_address VARCHAR(500),                  -- 实际经营地址
    
    -- 联系信息
    phone VARCHAR(50),                            -- 电话
    email VARCHAR(100),                           -- 邮箱
    website VARCHAR(200),                         -- 网站
    
    -- 行业信息
    industry_code VARCHAR(50),                    -- 行业代码
    industry_name VARCHAR(200),                   -- 行业名称
    
    -- 元数据
    data_source VARCHAR(50),                      -- 数据来源：企查查/天眼查/工商系统/手工录入
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 企业人员表（法人、股东、财务负责人等）
CREATE TABLE company_personnel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    
    -- 人员信息
    person_name VARCHAR(100) NOT NULL,            -- 姓名
    person_type VARCHAR(50) NOT NULL,             -- 类型：法人/股东/财务负责人/监事/董事/高管
    id_card_no VARCHAR(50),                       -- 身份证号（脱敏）
    
    -- 职务信息
    position VARCHAR(100),                        -- 职务
    appointment_date DATE,                        -- 任职日期
    resignation_date DATE,                        -- 离职日期
    
    -- 股东信息
    shareholding_ratio DECIMAL(5, 2),             -- 持股比例
    subscribed_capital DECIMAL(18, 2),            -- 认缴出资
    paid_capital DECIMAL(18, 2),                  -- 实缴出资
    
    -- 联系信息
    phone VARCHAR(50),                            -- 电话
    email VARCHAR(100),                           -- 邮箱
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE INDEX idx_company_personnel_company ON company_personnel(company_id);
CREATE INDEX idx_company_personnel_name ON company_personnel(person_name);
CREATE INDEX idx_company_personnel_type ON company_personnel(person_type);

-- 关联方关系表
CREATE TABLE related_party_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 关联双方
    company_a_id INTEGER NOT NULL,                -- 企业A
    company_b_id INTEGER NOT NULL,                -- 企业B
    
    -- 关联关系
    relation_type VARCHAR(100) NOT NULL,          -- 关联类型：母子公司/兄弟公司/同一控制/关键管理人员亲属等
    relation_description TEXT,                    -- 关系描述
    
    -- 关联人（如果是人员关联）
    person_a_id INTEGER,                          -- 企业A关联人
    person_b_id INTEGER,                          -- 企业B关联人
    person_relation VARCHAR(100),                 -- 人员关系：配偶/父母/子女/兄弟姐妹等
    
    -- 有效性
    is_active BOOLEAN DEFAULT TRUE,               -- 是否有效
    start_date DATE,                              -- 关联开始日期
    end_date DATE,                                -- 关联结束日期
    
    -- 发现来源
    discovery_source VARCHAR(50),                 -- 发现来源：工商比对/股东重合/地址重合/人工识别
    confidence_score DECIMAL(3, 2),               -- 置信度
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (company_a_id) REFERENCES companies(id),
    FOREIGN KEY (company_b_id) REFERENCES companies(id),
    FOREIGN KEY (person_a_id) REFERENCES company_personnel(id),
    FOREIGN KEY (person_b_id) REFERENCES company_personnel(id)
);

CREATE INDEX idx_related_party_company_a ON related_party_relations(company_a_id);
CREATE INDEX idx_related_party_company_b ON related_party_relations(company_b_id);
```

### 7.3 关联方识别规则

```python
class RelatedPartyIdentifier:
    """关联方识别引擎"""
    
    # 关联方识别规则（基于企业会计准则第36号）
    IDENTIFICATION_RULES = {
        # 控制关系
        "control": {
            "name": "母子公司关系",
            "condition": "持股比例 > 50% 或 实际控制",
            "risk_level": "high",
        },
        
        # 共同控制
        "joint_control": {
            "name": "合营企业/联营企业",
            "condition": "持股比例 20%-50%",
            "risk_level": "medium",
        },
        
        # 重大影响
        "significant_influence": {
            "name": "重大影响",
            "condition": "持股比例 20%-50% 或 派出董事/高管",
            "risk_level": "medium",
        },
        
        # 关键管理人员
        "key_management": {
            "name": "关键管理人员关联",
            "condition": "同一法人/同一财务负责人/同一高管",
            "risk_level": "high",
        },
        
        # 关键管理人员亲属
        "key_management_family": {
            "name": "关键管理人员亲属关联",
            "condition": "法人/股东/高管的配偶/父母/子女/兄弟姐妹控制的企业",
            "risk_level": "high",
        },
        
        # 受同一控制
        "same_control": {
            "name": "受同一方控制",
            "condition": "同一母公司/同一实际控制人",
            "risk_level": "high",
        },
        
        # 地址/电话重合
        "contact_overlap": {
            "name": "联系方式重合",
            "condition": "注册地址/电话/邮箱重合",
            "risk_level": "medium",
        },
    }
    
    def identify_related_parties(
        self, 
        company: Company, 
        all_companies: List[Company]
    ) -> List[RelatedPartyRelation]:
        """
        识别关联方
        """
        relations = []
        
        # 1. 股权关系识别
        relations.extend(self._identify_equity_relations(company, all_companies))
        
        # 2. 人员关系识别
        relations.extend(self._identify_personnel_relations(company, all_companies))
        
        # 3. 控制关系识别
        relations.extend(self._identify_control_relations(company, all_companies))
        
        # 4. 地址/电话重合识别
        relations.extend(self._identify_contact_overlap(company, all_companies))
        
        return relations
    
    def _identify_personnel_relations(
        self, 
        company: Company, 
        all_companies: List[Company]
    ) -> List[RelatedPartyRelation]:
        """
        识别人员关联
        """
        relations = []
        
        # 获取当前企业的关键人员
        key_personnel = self._get_key_personnel(company)
        
        for other_company in all_companies:
            if other_company.id == company.id:
                continue
            
            # 获取对方企业的关键人员
            other_key_personnel = self._get_key_personnel(other_company)
            
            # 检查是否有重合
            for person_a in key_personnel:
                for person_b in other_key_personnel:
                    if self._is_same_person(person_a, person_b):
                        relations.append(RelatedPartyRelation(
                            company_a_id=company.id,
                            company_b_id=other_company.id,
                            relation_type="key_management",
                            relation_description=f"关键管理人员重合：{person_a.person_name}",
                            discovery_source="人员重合",
                            confidence_score=0.95,
                        ))
                    
                    # 检查亲属关系
                    if self._is_family_relation(person_a, person_b):
                        relations.append(RelatedPartyRelation(
                            company_a_id=company.id,
                            company_b_id=other_company.id,
                            relation_type="key_management_family",
                            relation_description=f"关键管理人员亲属关系：{person_a.person_name}与{person_b.person_name}",
                            discovery_source="亲属关系识别",
                            confidence_score=0.85,
                        ))
        
        return relations
    
    def check_transaction_risk(
        self, 
        transaction: Transaction, 
        related_parties: List[RelatedPartyRelation]
    ) -> List[dict]:
        """
        检查交易是否存在关联方风险
        """
        risks = []
        
        counterparty = transaction.counterparty
        
        # 检查交易对手是否为关联方
        for relation in related_parties:
            if relation.company_b.company_name == counterparty:
                risks.append({
                    "type": "related_party_transaction",
                    "severity": "high",
                    "description": f"交易对手 {counterparty} 为关联方（{relation.relation_type}）",
                    "relation": relation,
                    "audit_procedure": "核实关联交易定价公允性，检查是否履行审批程序",
                })
        
        return risks
```

### 7.4 企业信息集成到合同解析

```python
class ContractParserWithCompanyInfo:
    """带企业信息的合同解析器"""
    
    def parse(self, file_path: str) -> Contract:
        """
        解析合同并关联企业信息
        """
        # 1. 解析合同基本信息
        contract = self._parse_basic_info(file_path)
        
        # 2. 提取当事人信息
        parties = self._extract_parties(contract)
        
        # 3. 查询/补充企业信息
        for party in parties:
            company_info = self._get_or_fetch_company_info(party)
            party.company_info = company_info
            
            # 判断纳税人类型影响
            if company_info.taxpayer_type == "小规模纳税人":
                contract.risk_flags.append({
                    "type": "taxpayer_type",
                    "description": f"{party.party_name} 为小规模纳税人，注意发票税率",
                    "severity": "medium",
                })
        
        # 4. 检查关联方关系
        related_parties = self._check_related_parties(parties)
        if related_parties:
            contract.risk_flags.append({
                "type": "related_party",
                "description": f"合同当事人存在关联关系：{related_parties}",
                "severity": "high",
                "audit_procedure": "核实关联交易定价公允性，检查是否履行审批程序",
            })
        
        return contract
    
    def _get_or_fetch_company_info(self, party: ContractParty) -> Company:
        """
        获取或抓取企业信息
        """
        # 先查询本地数据库
        company = self.db.query(Company).filter(
            Company.company_name == party.party_name
        ).first()
        
        if company:
            return company
        
        # 调用第三方API获取企业信息
        company_info = self._fetch_company_info_from_api(party.party_name)
        
        if company_info:
            # 保存到数据库
            company = Company(**company_info)
            self.db.add(company)
            self.db.commit()
            return company
        
        return None
    
    def _fetch_company_info_from_api(self, company_name: str) -> dict:
        """
        从第三方API获取企业信息
        """
        # 可以对接企查查、天眼查等API
        # 这里返回示例数据
        return {
            "company_name": company_name,
            "taxpayer_type": "一般纳税人",  # 或 "小规模纳税人"
            "registered_capital": 1000000,
            "legal_representative": "张三",
            # ...
        }
```

### 7.5 关联方交易审计提示

```python
class RelatedPartyTransactionAuditor:
    """关联方交易审计"""
    
    AUDIT_PROCEDURES = {
        "pricing_check": {
            "name": "定价公允性检查",
            "description": "比较关联交易价格与市场公允价格",
            "methods": ["可比非受控价格法", "再销售价格法", "成本加成法"],
        },
        
        "disclosure_check": {
            "name": "披露完整性检查",
            "description": "检查关联交易是否在财务报表中充分披露",
            "requirements": ["关联方名称", "交易性质", "交易金额", "定价政策"],
        },
        
        "approval_check": {
            "name": "审批程序检查",
            "description": "检查关联交易是否履行必要的审批程序",
            "requirements": ["董事会决议", "股东大会决议", "独立董事意见"],
        },
        
        "substance_check": {
            "name": "实质重于形式检查",
            "description": "检查交易是否具有商业实质",
            "indicators": ["交易是否有合理商业目的", "交易是否真实发生", "资金是否实际流转"],
        },
    }
    
    def audit_related_party_transaction(
        self, 
        transaction: Transaction, 
        relation: RelatedPartyRelation
    ) -> AuditFinding:
        """
        审计关联方交易
        """
        findings = []
        
        # 1. 定价公允性检查
        pricing_finding = self._check_pricing_fairness(transaction, relation)
        if pricing_finding:
            findings.append(pricing_finding)
        
        # 2. 披露完整性检查
        disclosure_finding = self._check_disclosure_completeness(transaction, relation)
        if disclosure_finding:
            findings.append(disclosure_finding)
        
        # 3. 审批程序检查
        approval_finding = self._check_approval_procedure(transaction, relation)
        if approval_finding:
            findings.append(approval_finding)
        
        # 4. 商业实质检查
        substance_finding = self._check_commercial_substance(transaction, relation)
        if substance_finding:
            findings.append(substance_finding)
        
        return AuditFinding(
            finding_type="related_party_transaction",
            title=f"关联方交易审计发现：{transaction.counterparty}",
            description=f"与{relation.relation_type}关联方的交易",
            severity="high" if findings else "medium",
            details=findings,
            suggestion="核实关联交易定价公允性，检查是否履行审批程序，确保充分披露",
        )
```

## 8. 总结

### 8.1 设计原则

1. **稳定框架**：核心字段存入关系数据库，支持复杂查询和关联
2. **灵活映射**：字段别名支持多级匹配，最终由大模型判断
3. **准则视角**：从收入准则等审计准则出发设计解析引擎
4. **多方支持**：合同支持三方或多方当事人
5. **分时段履约**：支持合同分阶段执行和进度跟踪
6. **履约义务识别**：基于收入准则五步法识别履约义务

### 6.2 实现优先级

| 优先级 | 功能 | 说明 |
|-------|------|------|
| P0 | 合同解析引擎 | 收入准则核心 |
| P0 | 字段别名映射 | 灵活解析基础 |
| P1 | 履约义务识别 | 收入确认关键 |
| P1 | 发票解析 | 债权确认 |
| P2 | 入库单/出库单解析 | 存货确认 |
| P2 | 银行回单解析 | 资金流水 |
