# 财务软件向量库审计风险识别开发规划

## 1. Summary

本规划面向一个从零开发的 Web SaaS 财务软件，第一阶段聚焦“导入 + 风险识别”。核心目标是：支持导入其他企业的会计凭证与原始文件，自动解析会计分录，对分录重新打标签，并将原始分录、凭证附件、发票/合同/银行流水等原始文件内容向量化入库，用向量检索、规则引擎与大模型分析识别潜在审计风险。

用户已确认的关键方向：

- 产品形态：开发阶段暂定 Web SaaS。
- 第一阶段 MVP：优先实现导入 + 风险识别。
- AI 部署策略：混合模式。
- 当前优先级：功能实现优先，权限控制与敏感控制后续随项目成熟度增强。

## 2. Current State Analysis

### 2.1 当前工作区状态

已对工作区进行只读探索，当前路径为：

```text
e:\创业项目管理目录\山西岚县尚德鑫有限公司\wroksapce20260616
```

探索结论：

- 当前工作区未发现已有代码文件。
- 未发现 README、package.json、pyproject.toml、requirements.txt、Dockerfile、数据库 schema、前后端入口文件等项目文件。
- 未发现现有财务软件模块。
- 未发现数据库、ORM、向量数据库、RAG、embedding 或 AI 分析相关实现。
- 因此本项目应按“空白项目从零初始化”进行规划。

### 2.2 对规划的影响

由于没有现有代码约束，技术栈、目录结构、数据模型、导入流程、向量库方案和风险识别流程都需要在第一阶段建立基础架构。规划将以最小可用闭环为目标，避免一开始覆盖完整财务软件全功能。

## 3. Proposed Architecture

### 3.1 推荐技术栈

第一阶段建议采用以下技术栈：

- 前端：React + TypeScript + Vite。
- 后端：Python FastAPI。
- 关系型数据库：PostgreSQL。
- 向量数据库：Qdrant。
- 异步任务：Celery + Redis，或先用 FastAPI BackgroundTasks 起步，后续再升级 Celery。
- 文件存储：开发阶段使用本地对象存储目录，接口上抽象为 Object Storage，后续可切换 MinIO / S3。
- 文档解析：
  - Excel / CSV：pandas、openpyxl。
  - PDF：pypdf / pdfplumber。
  - 图片 OCR：后续接入 PaddleOCR 或云 OCR。
- Embedding：混合模式，优先通过可替换接口封装。
  - 本地 embedding 模型用于敏感原文向量化。
  - 云端大模型用于脱敏后的复杂风险解释、摘要和标签建议。
- AI 编排：先不引入重型框架，采用自定义 service 层；如后续复杂度上升，再考虑 LangChain / LlamaIndex。

### 3.2 MVP 核心闭环

第一阶段只实现以下闭环：

1. 企业账簿/项目创建。
2. 上传凭证文件、分录 Excel/CSV、原始附件。
3. 解析导入会计分录。
4. 抽取原始文件文本内容。
5. 将分录与原始文件切片后生成 embedding。
6. 写入向量库，并在关系库中保存元数据。
7. 自动生成或推荐标签。
8. 基于规则 + 向量相似检索 + AI 分析生成审计风险提示。
9. 在 Web 页面展示导入批次、分录列表、文件列表、风险列表和风险详情。
10. 支持人工确认风险、修改标签、标记误报。

## 4. Proposed Changes

由于当前工作区为空，执行阶段需要新增以下项目结构和文件。

### 4.1 根目录项目文件

建议新增：

```text
package.json
pnpm-workspace.yaml
README.md
.env.example
docker-compose.yml
```

用途：

- `package.json`：统一管理前端脚本和项目级命令。
- `pnpm-workspace.yaml`：预留前端 workspace 管理。
- `README.md`：记录本地启动、环境变量和模块说明。
- `.env.example`：列出数据库、Redis、Qdrant、AI 服务等环境变量。
- `docker-compose.yml`：启动 PostgreSQL、Redis、Qdrant 等开发依赖。

说明：README 与配置文件仅在执行阶段创建，规划阶段不创建业务文件。

### 4.2 前端目录

建议新增：

```text
frontend/
  package.json
  index.html
  vite.config.ts
  tsconfig.json
  src/
    main.tsx
    App.tsx
    api/client.ts
    pages/DashboardPage.tsx
    pages/ImportPage.tsx
    pages/EntriesPage.tsx
    pages/RisksPage.tsx
    pages/RiskDetailPage.tsx
    components/Layout.tsx
    components/FileUploader.tsx
    components/RiskBadge.tsx
```

前端第一阶段功能：

- 导入页：上传凭证分录文件和原始附件。
- 分录页：查看导入后的会计分录、标签、关联原始文件。
- 风险页：查看审计风险列表、风险等级、命中原因。
- 风险详情页：展示相关分录、相似历史分录、原始文件片段、AI 解释。
- 仪表盘：展示导入批次、风险数量、待复核数量。

### 4.3 后端目录

建议新增：

```text
backend/
  pyproject.toml
  app/
    main.py
    core/config.py
    db/session.py
    db/models.py
    schemas/
      import_job.py
      accounting_entry.py
      risk.py
    api/
      routes_imports.py
      routes_entries.py
      routes_files.py
      routes_risks.py
    services/
      import_service.py
      file_parser_service.py
      tagging_service.py
      embedding_service.py
      vector_store_service.py
      risk_rule_service.py
      risk_analysis_service.py
      redaction_service.py
    storage/local_storage.py
```

后端第一阶段职责：

- 提供 REST API。
- 管理企业、导入批次、会计分录、原始文件、标签、风险结果。
- 解析上传文件。
- 调用 embedding 服务生成向量。
- 写入 Qdrant。
- 执行规则风险识别。
- 通过向量检索找相似分录和相关原始文件片段。
- 对脱敏内容调用云端大模型生成风险解释。

### 4.4 数据库模型

PostgreSQL 第一阶段建议包含以下核心表：

```text
organizations
import_jobs
source_files
accounting_entries
entry_tags
document_chunks
audit_risks
risk_evidence
review_actions
```

#### organizations

保存企业或账簿信息。

关键字段：

- id
- name
- industry
- fiscal_year
- created_at

#### import_jobs

保存每次导入任务。

关键字段：

- id
- organization_id
- status
- source_type
- file_count
- entry_count
- error_message
- created_at

#### source_files

保存原始文件元数据。

关键字段：

- id
- organization_id
- import_job_id
- filename
- file_type
- storage_path
- text_extract_status
- created_at

#### accounting_entries

保存会计分录。

关键字段：

- id
- organization_id
- import_job_id
- voucher_no
- voucher_date
- summary
- account_code
- account_name
- debit_amount
- credit_amount
- counterparty
- original_row
- normalized_text
- created_at

#### entry_tags

保存自动标签和人工标签。

关键字段：

- id
- entry_id
- tag_name
- tag_source
- confidence
- reviewed_by_user
- created_at

#### document_chunks

保存分录和原始文件的切片元数据。

关键字段：

- id
- organization_id
- source_type
- source_id
- chunk_text
- chunk_hash
- vector_collection
- vector_point_id
- created_at

#### audit_risks

保存风险识别结果。

关键字段：

- id
- organization_id
- import_job_id
- risk_type
- risk_level
- title
- description
- status
- confidence
- created_at

#### risk_evidence

保存风险证据链。

关键字段：

- id
- risk_id
- evidence_type
- source_id
- source_text
- similarity_score
- reason

#### review_actions

保存人工复核记录。

关键字段：

- id
- risk_id
- action
- comment
- created_at

### 4.5 向量库设计

建议 Qdrant collection：

```text
accounting_chunks
```

每个 point 的 payload 建议包含：

```text
organization_id
import_job_id
source_type
source_id
voucher_no
voucher_date
account_name
amount
counterparty
tags
chunk_hash
```

source_type 可取值：

- `accounting_entry`
- `source_file_chunk`

向量库用途：

1. 查找与当前分录相似的历史分录。
2. 查找与某个原始文件片段相似的分录。
3. 查找高风险模式相似样本。
4. 辅助判断异常摘要、异常科目、异常金额、重复报销、关联方交易、跨期确认等风险。

### 4.6 风险识别策略

第一阶段采用三层识别：

#### 第一层：规则引擎

实现确定性规则，便于解释和测试。

建议首批规则：

- 大额整数金额。
- 摘要为空或过于简单。
- 同一金额、同一摘要、相近日期重复出现。
- 非经营性支出进入主营业务成本或费用。
- 费用科目金额异常集中在期末。
- 往来科目长期挂账。
- 借贷方向与科目性质明显不一致。

#### 第二层：向量相似检索

用于发现规则不容易覆盖的相似异常：

- 与历史异常分录相似。
- 与同类企业异常样本相似。
- 凭证摘要与原始附件语义不一致。
- 同一供应商/客户存在高度相似但不同凭证编号的文件片段。

#### 第三层：AI 风险解释

对规则和向量检索命中的候选风险，组织脱敏上下文后调用大模型生成：

- 风险原因。
- 涉及分录。
- 证据摘要。
- 建议审计程序。
- 需要人工确认的问题。

### 4.7 自动标签策略

第一阶段标签来源分三类：

1. 规则标签：根据科目、金额、摘要关键词直接生成。
2. 向量标签：根据相似分录的历史标签推荐。
3. AI 标签：对脱敏分录摘要和上下文生成建议标签。

推荐初始标签：

- 大额交易
- 期末交易
- 重复交易疑似
- 关联方疑似
- 发票缺失
- 合同缺失
- 摘要异常
- 科目异常
- 跨期风险
- 往来挂账
- 人工复核

### 4.8 数据安全与混合 AI 决策

第一阶段功能优先，但需要保留安全边界设计：

- 原始文件和完整分录默认保存在本地/自有数据库。
- embedding 可优先走本地模型接口。
- 调用云端模型前通过 `redaction_service.py` 做基础脱敏。
- 脱敏字段包括企业名称、纳税识别号、银行账号、身份证号、手机号、精确供应商名称等。
- 保存 AI 调用日志，但不保存敏感原文到第三方响应中。

## 5. Implementation Phases

### Phase A：项目初始化

目标：搭建可运行的前后端与开发依赖。

任务：

1. 创建前端 React + Vite 项目结构。
2. 创建后端 FastAPI 项目结构。
3. 创建 Docker Compose，包含 PostgreSQL、Redis、Qdrant。
4. 创建基础环境变量样例。
5. 实现后端健康检查接口。
6. 实现前端基础路由和布局。

### Phase B：导入与解析

目标：实现上传文件并生成结构化分录。

任务：

1. 实现导入任务 API。
2. 实现文件上传接口。
3. 实现 Excel/CSV 会计分录解析。
4. 保存 source_files、import_jobs、accounting_entries。
5. 前端展示导入任务状态和分录列表。

### Phase C：向量化入库

目标：将分录和原始文件内容进入向量库。

任务：

1. 实现文本标准化和切片。
2. 实现 embedding_service 抽象接口。
3. 实现 Qdrant 写入和检索服务。
4. 保存 document_chunks 与 vector_point_id 映射。
5. 为每条分录生成 normalized_text 并入库。

### Phase D：自动标签

目标：自动给分录添加初始标签。

任务：

1. 实现基于科目、摘要、金额、日期的规则标签。
2. 实现基于向量相似分录的标签推荐。
3. 保存 entry_tags。
4. 前端支持查看与人工调整标签。

### Phase E：风险识别

目标：生成审计风险列表和证据链。

任务：

1. 实现首批规则风险。
2. 实现向量相似检索风险候选。
3. 实现风险结果合并去重。
4. 保存 audit_risks 和 risk_evidence。
5. 前端展示风险列表和详情。

### Phase F：AI 风险解释

目标：让风险结果可读、可复核。

任务：

1. 实现 redaction_service 基础脱敏。
2. 实现 risk_analysis_service 组织上下文。
3. 接入云端大模型或预留兼容 OpenAI API 风格接口。
4. 为风险生成解释、建议审计程序和人工复核问题。
5. 前端风险详情展示 AI 解释。

## 6. API Plan

第一阶段建议后端 API：

```text
GET    /health
POST   /api/import-jobs
GET    /api/import-jobs
GET    /api/import-jobs/{job_id}
POST   /api/import-jobs/{job_id}/files
POST   /api/import-jobs/{job_id}/process
GET    /api/entries
GET    /api/entries/{entry_id}
PATCH  /api/entries/{entry_id}/tags
POST   /api/entries/{entry_id}/similar-search
GET    /api/risks
GET    /api/risks/{risk_id}
PATCH  /api/risks/{risk_id}/review
```

## 7. Assumptions & Decisions

已确定：

- 从空白项目开始开发。
- 第一阶段不做完整财务核算系统，只做导入、分录管理、向量分析、标签和审计风险识别。
- 暂定 Web SaaS，但权限、租户隔离、敏感数据治理先保留架构位置，不作为第一阶段重点。
- AI 采用混合模式。
- 向量库作为核心能力，不是附属功能。

规划假设：

- 导入格式第一阶段优先支持 Excel / CSV。
- 原始文件第一阶段优先支持 PDF 和常见文本文件，图片 OCR 可后置。
- MVP 阶段可以先用单组织或轻量 organization_id 隔离，后续再扩展完整多租户权限模型。
- 风险识别结果先作为“审计提示”，不自动形成最终审计结论。

## 8. Verification Steps

执行阶段完成后建议验证：

1. 启动依赖服务：PostgreSQL、Redis、Qdrant。
2. 启动后端，访问 `GET /health` 返回正常。
3. 启动前端，确认页面可访问。
4. 上传一份会计分录 Excel/CSV，确认生成导入任务。
5. 确认数据库中生成 accounting_entries。
6. 确认 Qdrant 中写入 accounting_chunks points。
7. 对一条分录执行相似检索，确认返回相关结果。
8. 执行风险识别，确认 audit_risks 与 risk_evidence 有记录。
9. 在前端风险页查看风险列表和详情。
10. 修改标签或复核风险状态，确认数据库更新。
11. 运行后端测试、前端 lint/typecheck/build。

建议执行命令在项目生成后确定，初步预计包括：

```text
cd backend && pytest
cd frontend && npm run lint
cd frontend && npm run build
```

## 9. Out of Scope for MVP

第一阶段暂不实现：

- 完整总账、明细账、科目余额表、资产负债表、利润表。
- 完整多租户计费和 SaaS 商业化后台。
- 复杂 RBAC 权限体系。
- 电子发票验真。
- 银企直连。
- 全量 OCR 工作流。
- 审计底稿自动生成。
- 模型训练平台。
- 数据血缘可视化。

这些能力可在导入 + 风险识别闭环稳定后逐步扩展。
