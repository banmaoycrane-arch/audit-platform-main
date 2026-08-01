# 技术债处理进度（Loop）

> **启动**: 2026-07-29 · `/loop` 动态节奏  
> **停法**: 对话里说「停止 loop / stop loop」  
> **清单真源**: [../backend/TECH_DEBT.md](../../backend/TECH_DEBT.md) · [code-truth-status.md](./code-truth-status.md)

---

## 识别出的债（分层）

| ID | 项 | 风险 | 本轮 |
|----|-----|------|------|
| TD-004 | `services/` 根目录**假实现存根**（超管恒 False、授权 stub） | **高** | ✅ 已改为转发真实模块 |
| TD-005 | 非法 Ant 图标导致登录白屏 `AlertTriangleOutlined` | 高（已现网） | ✅ 已改 `WarningOutlined` |
| TD-006 | 前端 `VoucherQueryFilters` 缺 `period_ids` / 合规流类型不一致 | 中 | ✅ 已补类型 |
| TD-007 | 临时测试日志未 ignore / 易误提交 | 低 | ✅ `.gitignore` 加规则 |
| TD-001 | mypy ~351 | 中长期 | ⏳ 下轮分批 |
| TD-002 | 前端 Money / parseFloat | 中 | ⏳ 下轮 |
| TD-003 | 覆盖率 ~39% | 低 | ⏳ 后置 |
| TD-008 | Alembic：Git 尖端 0027 vs 本机未跟踪 0028/0029 vs 生产 stamp 0028 | 高（运维） | ⏳ 下轮收口文档+入库 |
| TD-009 | API 双轨（entries/vouchers、多导入链路） | 高（架构） | ⏳ L6 后按章程 |
| TD-010 | OS/排期/事件规格未进 origin/main | 中 | ⏳ 建议单独 commit |

---

## Tick 日志

| 时间 | 动作 |
|------|------|
| 2026-07-29 Tick0 | 扫描 + 处理 TD-004/005/006/007 |
| 2026-07-29 Tick1 | TD-008 评估完成；pytest 7 passed（tax+seal） |
| 2026-07-29 Tick2 | TD-011：税务模型 `utcnow`→`_utc_now_naive`；服务层此前已改；mypy 未装进 venv 暂缓 TD-001 |
| 2026-07-30 Tick3 | 仅复查：仍阻塞在「是否 commit 0028/装 mypy」；**暂停自动续跑**，等人指示 |

---

## TD-008 评估结论（Tick1 · 勿强推生产）

| 层 | 状态 |
|----|------|
| Git `HEAD` 迁移文件 | 尖端 **`0027_cash_flow_item`**；税务池 **模型已在** `4d8dd89`，但 **无 0028 文件** |
| 本机未跟踪 | **`0028`**（幂等建税务池表，Revises 0027）· **`0029`**（contracts.deep_analysis） |
| 工作区 models | 相对 HEAD 含 `Contract.deep_analysis` + Tax 时间默认值修复 |
| 生产（7/21 记录） | stamp **`0028`**；表已由迁移或 fix_legacy 存在 |

**建议收口顺序（等人点头再 commit / 部署）：**

1. 先把 **`0028` 单独入库**（与已发布税务池代码对齐；生产 upgrade 应因幂等直接跳过建表）  
2. **`0029` + models.deep_analysis** 可同批或第二批；生产未用 deep_analysis 前可不急着 stamp  
3. 收口后更新 `code-truth`：Git head / 生产 stamp 写清同一句话  
4. **本次未** 对生产执行任何 migrate / deploy  

**TD-011（Tick2）**：`tax_egress_service` 已用 `datetime.now(timezone.utc)`；Tax* 四表默认值改为 `_utc_now_naive()`。全库其余 `datetime.utcnow` 仍大量存在 → 记为 TD-011b 分批。

**TD-001**：当前 backend `.venv` **无 mypy 模块**，消错需先 `pip install mypy`（等人同意）或用 CI 环境。

---

## 下轮（已暂停自动 wake）

需要你任选其一再说一声即可恢复：

1. **commit** `0028`（±0029 / 文档）  
2. **安装 mypy** 后开 TD-001  
3. **继续 loop**（指定下一项）  
4. 保持暂停  
