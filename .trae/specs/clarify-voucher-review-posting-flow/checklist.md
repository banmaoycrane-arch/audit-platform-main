# Checklist

## 上下文与边界
- [x] 已回顾当前上下文和角色分工
- [x] 已确认本 spec 不重复 `unify-voucher-input-modes`
- [x] 已确认本 spec 不重复 `accounting-step4-real-review`
- [x] 已确认本 spec 不建设复杂审批流或正式总账过账引擎

## Step3 草稿语义
- [x] Step3 页面标题或说明明确输出为“待复核凭证草稿”
- [x] Step3 不在复核前使用“正式入账”“过账完成”等最终状态文案
- [x] Step3 下一步按钮表达为保存草稿并进入复核

## Step4 复核语义
- [x] Step4 页面明确当前对象为待复核凭证草稿
- [x] Step4 说明复核内容包括摘要、科目、金额、往来单位、借贷平衡等
- [x] Step4 下一步表达为进入确认入账 / 导出

## Step5 确认入账与导出语义
- [x] Step5 页面标题包含确认入账与导出语义
- [x] Step5 说明凭证已完成复核，可进行确认入账和导出
- [x] Step5 保持现有导出能力不变

## 验证
- [x] 前端 TypeScript / lint 检查通过
- [x] 改动文件无 IDE 诊断错误
