# 印章识别系统开发 Spec

## Why

当前系统在处理合同等财务文档时，已集成多模态大语言模型（LLM）进行文字内容与语义识别。然而，对于合同中仅以印章形式存在、未在正文中重复说明的主体信息（如合同专用章、财务章、法人章等），多模态 LLM 存在识别率低、关联主体失败的问题，直接影响合同审计证据的完整性与内部控制评价。因此，需要建设一套"检测 → 识别 → 校验 → 知识库匹配"的印章智能识别与校验系统，分阶段提升印章检出率、识别准确率与合规校验能力。

## What Changes

- **新增印章检测与识别后端模块**：基于传统 CV 与现有 OCR 框架实现印章区域定位、提取、文字识别与坐标关联。
- **新增 ContractSeal 数据模型与数据库表**：持久化印章位置、图片、文字、坐标、置信度等信息。
- **新增后端 API**：印章提取、印章列表分页查询、印章详情查询。
- **新增前端"印章证据"展示区域**：在合同详情页预留印章高亮、结果列表、动态叠加的 UI 与 TS 类型。
- **制定三阶段演进路线**：MVP（OCR 检测识别）→ LLM 关联校验 → 规则引擎与知识库匹配。
- **配套数据安全与审计机制**：权限隔离、审计日志、人工复核入口、受控访问。

## Impact

- Affected specs:
  - `document-parsing-engine`（文件解析引擎）
  - `contract-validation-service`（合同校验服务）
  - `business-cycle-audit`（业务循环审计）
- Affected code:
  - `backend/app/services/` — 新增 `seal_detection_service.py`、`seal_extraction_service.py`、`seal_ocr_service.py`
  - `backend/app/models/` — 新增 `contract_seal.py`
  - `backend/app/api/` — 新增 `routes_seals.py`
  - `frontend/src/` — 新增或修改合同详情页组件、TS 类型、API client
  - `backend/app/db/models.py` — 新增 `ContractSeal` 表映射

## ADDED Requirements

### Requirement: 印章区域检测（MVP）

The system SHALL detect seal regions in contract images or PDF-converted images using traditional computer vision, with PaddleOCR seal detection as an optional fallback.

#### Scenario: 成功检测到印章
- **GIVEN** 用户上传了一份包含红色圆形公章的合同扫描页
- **WHEN** 系统调用印章区域检测模块
- **THEN** 返回一个或多个印章边界框（bounding box，像素坐标）、检测置信度、印章外形类型初判（circle / ellipse / rectangle）

#### Scenario: 复杂背景下的 fallback 检测
- **GIVEN** 传统 CV 在复杂背景或低对比度场景下未能检出印章
- **WHEN** 系统启用 PaddleOCR 印章检测模型作为 fallback
- **THEN** 返回检测到的印章区域，并标记本次检测使用了 fallback 方案

### Requirement: 印章区域提取与预处理（MVP）

The system SHALL crop, denoise, correct skew, and enhance contrast of detected seal regions to prepare them for OCR recognition.

#### Scenario: 印章子图标准化
- **GIVEN** 检测模块返回了一个印章边界框
- **WHEN** 系统执行提取与预处理
- **THEN** 输出标准化印章子图：红色/蓝色通道增强、背景漂白、二值化、轻微透视校正、尺寸归一化

### Requirement: 印章文字识别与坐标关联（MVP）

The system SHALL recognize text inside seal regions using EasyOCR or PaddleOCR, and associate each recognized text with its original pixel coordinates.

#### Scenario: 环形印章文字识别
- **GIVEN** 一个经过预处理的圆形印章子图
- **WHEN** 系统执行 OCR 识别
- **THEN** 返回识别文字列表，每个文字项包含 text、x、y、width、height、confidence，且文字按环形角度重组为完整字符串

#### Scenario: 文字坐标与原始页面对应
- **GIVEN** OCR 返回印章内各文字坐标
- **WHEN** 系统保存结果
- **THEN** 文字坐标基于原始合同页面像素坐标系，能够与原始文件预览叠加对齐

### Requirement: ContractSeal 数据模型（MVP）

The system SHALL persist seal extraction results in a structured `ContractSeal` model.

#### Scenario: 保存印章识别结果
- **GIVEN** 系统完成一次印章提取
- **WHEN** 结果写入数据库
- **THEN** 记录至少包含：id、contract_id、source_file_id、page_no、bbox、seal_image_path、recognized_text、text_items（JSON）、seal_type、confidence、detection_method、created_at、updated_at

### Requirement: 印章提取后端 API（MVP）

The system SHALL expose an API to trigger seal extraction for a given contract.

#### Scenario: 触发印章提取
- **GIVEN** 合同文件已上传并关联到 contract_id
- **WHEN** 调用 `POST /api/v1/contracts/{contract_id}/seals/extract`
- **THEN** 系统异步执行检测、提取、识别、持久化，并返回任务状态或提取结果摘要

### Requirement: 印章列表与详情后端 API（MVP）

The system SHALL expose APIs to query seal results.

#### Scenario: 分页查询印章列表
- **GIVEN** 一个合同已存在印章识别记录
- **WHEN** 调用 `GET /api/v1/contracts/{contract_id}/seals?page=1&size=20`
- **THEN** 返回该合同下的印章分页列表

#### Scenario: 查询单个印章详情
- **GIVEN** 一个印章记录已存在
- **WHEN** 调用 `GET /api/v1/seals/{seal_id}`
- **THEN** 返回该印章的完整信息，包括 bbox、文字项、子图 URL、置信度等

### Requirement: 合同详情页"印章证据"区域（MVP）

The system SHALL reserve a "印章证据" section in the contract detail page for future and current seal result display.

#### Scenario: 展示印章证据区域
- **GIVEN** 用户进入合同详情页
- **WHEN** 页面渲染完成
- **THEN** 页签中出现"印章证据"标签；切换后左侧显示原始文件预览与印章边界框高亮，右侧显示印章列表与识别文字

#### Scenario: 无印章数据时的兼容展示
- **GIVEN** 当前合同暂无印章识别结果
- **WHEN** 用户切换到"印章证据"标签
- **THEN** 页面显示友好提示（如"未检测到印章，请确认文件清晰度或联系管理员"），不出现报错或空白

### Requirement: 多模态 LLM 关联校验（第二阶段）

The system SHALL use multimodal LLM to verify seal information against contract context after OCR extraction.

#### Scenario: 印章类型与主体关联
- **GIVEN** 一个印章子图、识别文字、合同甲方/乙方列表
- **WHEN** 系统调用 LLM 校验服务
- **THEN** 返回 JSON：seal_type、associated_party、confidence、anomalies，且低置信度结果标记为需人工复核

### Requirement: 规则引擎与知识库匹配（第三阶段）

The system SHALL validate seals against configurable rules and master data.

#### Scenario: 印章合规规则校验
- **GIVEN** 印章识别结果与合同金额
- **WHEN** 系统执行规则校验
- **THEN** 检查印章类型与合同金额/合同类型是否匹配、印章名称是否与甲方/乙方一致、财务章是否误用于采购合同等

#### Scenario: 主数据匹配
- **GIVEN** 印章中的企业名称或统一社会信用代码
- **WHEN** 系统与主数据（客户/供应商/往来单位）匹配
- **THEN** 返回匹配结果、匹配置信度、未匹配风险提示

### Requirement: 数据安全与审计

The system SHALL enforce permission isolation, audit logging, manual review workflow, and controlled access for seal data.

#### Scenario: 权限隔离
- **GIVEN** 不同团队/项目的用户访问印章数据
- **WHEN** 用户查询印章列表或详情
- **THEN** 仅返回该用户有权限访问的合同所属印章

#### Scenario: 审计日志
- **GIVEN** 用户触发印章提取或修改印章复核状态
- **WHEN** 操作完成
- **THEN** 系统记录操作人、时间、合同 ID、操作类型、结果摘要到审计日志

#### Scenario: 人工复核入口
- **GIVEN** 系统识别出低置信度或异常印章
- **WHEN** 结果展示给审计人员
- **THEN** 提供"确认正确"、"标记异常"、"人工修正"入口，复核结论单独持久化

## MODIFIED Requirements

### Requirement: 合同详情页页签结构

The contract detail page SHALL include a new "印章证据" tab alongside existing tabs such as "合同内容" and "解析结果".

#### Scenario: 页签切换
- **WHEN** 用户点击"印章证据"标签
- **THEN** 页面切换到印章证据视图，其他合同信息保持不变

## REMOVED Requirements

无移除需求。
