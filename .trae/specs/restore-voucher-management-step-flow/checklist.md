# Checklist

- [x] 财务总账下“凭证管理”是父级菜单
- [x] 凭证管理下包含 Step 1 选择原始资料类型
- [x] 凭证管理下包含 Step 2 导入原始凭证
- [x] 凭证管理下包含 Step 3 AI 生成会计分录
- [x] 凭证管理下包含 Step 4 复核会计分录
- [x] 凭证管理下包含 Step 5 导出账簿
- [x] 凭证管理下包含凭证列表入口
- [x] `/ledger/vouchers/step/1` 可访问并显示 Step1 页面
- [x] `/ledger/vouchers/step/5` 可访问并显示 Step5 页面
- [x] `/accounting/step/1` 旧路径仍可访问
- [x] `/ledger/entries` 凭证列表仍可访问
- [x] 从 `/ledger/vouchers/step/3?jobId=1&periodId=2` 跳转下一步保留 query 参数
- [x] 工作台财务总账入口优先进入凭证管理 Step1
- [x] 前端 `npm run lint` 通过
