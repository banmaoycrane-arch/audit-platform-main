# 企业级模块信息架构与序时簿闭环 Spec

## Why

当前工作台虽然已具备基础导航，但一级页面仍偏“开发测试入口”，没有形成企业财务软件常见的业务模块体系。用户明确要求将系统重构为 Agent 助手、财务总账、审计系统、自定义模块、基础资料、银行、税务等一级页面，并补齐序时簿导入后没有形成会计分录、映射和分析的问题。

## What Changes

- 重构工作台一级导航架构：
  - Agent 助手
  - 财务总账
  - 审计系统
  - 自定义模块
  - 基础资料
  - 银行模块
  - 税务模块
  - 固定资产模块（预留）
  - 进销存模块（预留）
- 财务总账二级页面：
  - 凭证管理
  - 账簿管理
  - 总账
  - 明细账
  - 科目余额表
  - 试算平衡表
- 自定义模块支持把常用二级页面挂到一级展示，例如默认展示“凭证管理”。
- 基础资料扩展二级页面：
  - 会计科目
  - 企业组织架构
  - 员工/协作人员
  - 往来单位
  - 期初数据
  - SKU / 商品 / 成品 / 半成品 / 原材料（预留入口）
  - 仓库 / 总仓 / 中转仓 / 虚拟仓（预留入口）
- 基础资料要求：所有虚拟核算单位必须依托至少一个实体核算对象。
- 银行模块：
  - 银行账户
  - 三方支付账户
  - 聚合账户
  - 银行账户下设：日记账、账户设置、自动对账
- 税务模块：
  - 发票管理
  - 涉税助手
  - 涉税助手复用 Agent 的轻量模型能力，并预留税务知识库 DAG。
- 修复审计 Step3 序时簿导入：
  - 序时簿导入后必须形成 `AccountingEntry`
  - 返回导入质量报告
  - 生成 EntryTag 映射
  - 允许进入 Step4 执行审计测试

## Impact

- Affected specs:
  - `workspace-navigation-continuity`
  - `dashboard-home-and-day-book-import`
  - `basic-data-pages`
  - `internal-accounting-unit`
  - `agent-lightweight-llm-api`
  - `adaptive-import-engine`
- Affected code:
  - `frontend/src/layout/MainShell.tsx`
  - `frontend/src/pages/WorkspacePage.tsx`
  - `frontend/src/App.tsx`
  - `frontend/src/pages/AuditMode/Step3ImportEntries.tsx`
  - `frontend/src/pages/BasicData/*`
  - `backend/app/services/import_service.py`
  - `backend/tests/test_*day_book*.py` 或新增序时簿导入测试

## ADDED Requirements

### Requirement: 企业级一级导航

系统 SHALL 以企业经营模块组织一级页面，而不是只按开发测试页面组织。

#### Scenario: 查看一级菜单
- **WHEN** 用户进入工作台 Shell
- **THEN** 左侧一级菜单包含 Agent 助手、财务总账、审计系统、自定义模块、基础资料、银行模块、税务模块等入口

### Requirement: 财务总账模块

系统 SHALL 在财务总账下组织凭证、账簿、总账、明细账、科目余额表、试算平衡表等二级页面。

#### Scenario: 进入凭证管理
- **WHEN** 用户点击“财务总账 / 凭证管理”
- **THEN** 系统进入现有 `/entries` 页面

### Requirement: 自定义模块

系统 SHALL 提供“自定义模块”一级页面，用于展示常用二级功能入口。默认 SHALL 包含凭证管理。

#### Scenario: 默认自定义入口
- **WHEN** 用户点击“自定义模块 / 凭证管理”
- **THEN** 系统进入 `/entries`

### Requirement: 基础资料组织架构

系统 SHALL 在基础资料中提供企业组织架构、员工/协作人员等入口，支持实体组织与虚拟组织概念。

#### Scenario: 虚拟核算单位说明
- **WHEN** 用户进入企业组织架构页面
- **THEN** 页面说明虚拟核算单位必须依托至少一个实体核算对象

### Requirement: 银行与税务一级模块

系统 SHALL 提供银行模块和税务模块一级入口，并展示其二级/三级页面结构。

#### Scenario: 银行模块入口
- **WHEN** 用户打开银行模块
- **THEN** 可看到银行账户、三方支付账户、聚合账户、日记账、账户设置、自动对账等入口

#### Scenario: 税务模块入口
- **WHEN** 用户打开税务模块
- **THEN** 可看到发票管理和涉税助手入口，并说明涉税助手复用轻量模型能力

### Requirement: 序时簿导入形成分录闭环

系统 SHALL 让审计 Step3 的序时簿导入与凭证导入一样形成 `AccountingEntry`、质量报告、标签映射，并允许进入下一步审计测试。

#### Scenario: 导入序时簿 CSV
- **WHEN** 用户在 `/audit/step/3` 的“序时簿导入”上传标准或中文表头 CSV
- **THEN** 系统处理文件并创建会计分录
- **AND** 展示已导入分录列表
- **AND** 下一步执行测试按钮可用

#### Scenario: 序时簿导入后生成映射
- **WHEN** 序时簿成功导入
- **THEN** 系统为分录生成 EntryTag 映射，包括凭证字、科目、往来单位等可识别标签

## MODIFIED Requirements

### Requirement: 工作台导航连贯性

原工作台导航从“测试入口 + 流程菜单”升级为“企业级一级模块 + 流程入口 + 可自定义模块”。

### Requirement: 审计 Step3 序时簿导入

原序时簿入口仅作为上传入口，修改为必须参与真实导入、分录生成、质量分析、标签映射与审计测试流转。

## REMOVED Requirements

无。

## 财务视角说明

- 财务总账是会计核算主线，凭证、账簿、总账、明细账、科目余额表、试算平衡表必须归到同一一级模块下。
- 银行模块独立为一级模块，是因为银行账户、第三方支付、聚合账户和自动对账具有独立业务流程，但最终仍要与总账凭证、日记账、分录关联。
- 税务模块独立为一级模块，是因为发票和涉税风险识别既依赖总账，也需要专属税务知识库。
- 组织架构、人员、SKU、仓库等基础资料是内部核算和绩效考核的底层对象。虚拟对象本质是管理便利，必须依托实体对象，避免形成没有责任主体的“空中楼阁”核算单位。
