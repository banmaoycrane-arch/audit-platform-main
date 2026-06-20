# Tasks

## Task 1：调整凭证管理 Step1 输入模式选择
- [x] 1.1 修改 `Step1SelectType.tsx` 标题为「选择凭证输入模式」
- [x] 1.2 将卡片调整为两种路径：
  - [x] 根据原始资料 AI 智能生成凭证
  - [x] 传统人工录入凭证
- [x] 1.3 Step1 下一步根据选择带上 `inputMode=ai_generated` 或 `inputMode=manual_entry`
- [x] 1.4 保留 `/ledger/vouchers/step/1` 与 `/accounting/step/1` 两套路由兼容

## Task 2：AI 智能生成路径保持并优化语义
- [x] 2.1 修改 `Step2ImportSource.tsx`，当 `inputMode=ai_generated` 时展示原始资料上传流程
- [x] 2.2 将原始资料类型说明改为 AI 识别辅助信息，不再作为 Step1 主选择
- [x] 2.3 上传后继续创建导入任务、选择会计期间、进入 Step3 AI 生成凭证草稿
- [x] 2.4 Step3 文案明确「AI 生成的是待复核的标准会计凭证草稿」

## Task 3：传统人工录入路径
- [x] 3.1 新增或改造人工录入页面/组件，用于录入标准凭证
- [x] 3.2 人工录入字段包含：凭证日期、凭证字号、摘要、科目代码/名称、借方金额、贷方金额、对方单位、行号
- [x] 3.3 人工录入前端校验借贷平衡
- [x] 3.4 人工录入提交后进入统一复核流程或直接形成同结构凭证草稿

## Task 4：统一标准凭证落库与来源标识
- [x] 4.1 复用现有 `AccountingEntry` / `commit-entries` 标准分录结构
- [x] 4.2 为 AI 生成凭证标识来源 `ai_generated`
- [x] 4.3 为人工录入凭证标识来源 `manual_entry`
- [x] 4.4 确保两种来源的凭证都可进入凭证列表、总账、报表、导出

## Task 5：测试与验证
- [x] 5.1 增加前端路径验证：Step1 选择 AI 路径后进入上传原始资料
- [x] 5.2 增加前端路径验证：Step1 选择人工路径后进入人工凭证录入
- [x] 5.3 增加后端测试：人工凭证提交后落为标准 `AccountingEntry`
- [x] 5.4 增加后端测试：AI 与人工两种来源凭证都可被凭证列表查询
- [x] 5.5 运行后端测试
- [x] 5.6 运行前端 lint / TypeScript 检查

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 2 and Task 3
- Task 5 depends on Task 1-4
