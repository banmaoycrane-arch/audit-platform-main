# L6 人工验收路径（阶段 1）

> **用途**: 阶段 1 收敛章程要求的「记账 + 审计各一条 L6 路径」签字记录  
> **状态**: 待执行（模板已就绪）  
> **执行人**: __________ **日期**: __________

---

## 路径 A — 记账主线 L6

**目标**: 项目 → 账簿 → 序时簿导入 → 复核 → 过账 → 期间 → 报表

| 步骤 | 操作 | URL / API | 通过 □ | 备注 |
|------|------|-----------|--------|------|
| A1 | 登录 | `/login` | | |
| A2 | 选择账簿 | 账簿管理 | | ledger_id=____ |
| A3 | Step1 选「结构化 · 序时簿」 | `/ledger/vouchers/step/1` | | |
| A4 | 维度中心确认 tag 规则 | `/ledger/dimensions?tab=parse-mapping` | | 点击「确认规则已审阅」 |
| A5 | Step2 上传序时簿 | `step/2?inputMode=day_book_import` | | 未审阅应被拦截；表头含制单人列 |
| A6 | 解析成功 | process/sync total_entries>0 | | |
| A7 | Step4 维度复核 → 凭证复核 | `step/4?reviewPhase=dimensions` | | verified 后 staging 有 cross_reviewed_by |
| A8 | Step5 确认入账 | confirm API | | approved_by 为当前用户 |
| A9 | 凭证过账 | `/api/vouchers/{id}/post` | | |
| A10 | 损益结转（如适用） | 会计期间页 | | |
| A11 | 报表核对 | 资产负债表/试算平衡 | | 签章字段可在凭证详情核对 |

**签字**: __________ **结论**: □ 通过 □ 不通过

---

## 路径 B — 审计主线 L6

**目标**: 审计任务 → 序时簿导入 → 测试/底稿 → 导出

| 步骤 | 操作 | URL / API | 通过 □ | 备注 |
|------|------|-----------|--------|------|
| B1 | 创建/打开审计项目 | 项目页 | | project_id=____ |
| B2 | 创建审计任务并绑定账簿 | 审计任务 | | |
| B3 | Step1 选审计范围 | `/audit/.../step/1` | | |
| B4 | Step3 上传序时簿并导入 | 审计 Step3 | | 文案应显示「结构化自适应导入」 |
| B5 | 分录/报告生成 | day_book report | | entry_count>0 |
| B6 | 运行审计测试或查看底稿 | 工作底稿/测试 | | |
| B7 | 导出审计包（如有） | 导出 | | |

**签字**: __________ **结论**: □ 通过 □ 不通过

---

## 阶段 1 技术门禁（与 L6 并行）

| 项 | 验收 | 状态 |
|----|------|------|
| S1-1 deprecated API | `unified-import`、`/api/parse` OpenAPI deprecated | ✅ 已标记 |
| S1-3 文案三分法 | Step1/2/3 无「统一解析引擎」泛称 | ✅ 已改 |
| S1-4 superseded 文档 | `debug-parser-engine-unification.md` | ✅ |
| S1-5 pytest 全绿 | `pytest tests -q` 0 failed | 见 code-truth-status |
| 前端无新调 deprecated API | grep unified-import, /api/parse | ✅ 0 存量 |

完成两条 L6 路径签字后，在 [code-truth-status.md](./code-truth-status.md) §三 更新「L6 人工验收记录」。  
**记账 v1.0 发布范围与「先验收再修」顺序**：[bookkeeping-v1-decision-record.md](../../backend/docs/bookkeeping-v1-decision-record.md)。
