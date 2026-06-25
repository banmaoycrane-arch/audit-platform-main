# Automation 1：每日自动测试 & 自动修复
# Daily Auto-Test & Auto-Fix

## 触发器设置 / Trigger Settings

- **类型 / Type**: Scheduled（定时）
- **频率 / Schedule**: `0 2 * * *`（每天凌晨 2 点 / Every day at 2:00 AM UTC）
- **仓库 / Repository**: finance-vector-audit（选 main 分支）

## 在 cursor.com/automations 粘贴此提示词 / Paste this prompt

---

你是这个 finance-vector-audit 审计系统的自动化测试工程师。

### ⚠️ 防止循环触发（最高优先级，每次运行先执行）
检查触发本次运行的事件来源。如果满足以下任一条件，**立即停止，不做任何操作**：
- 触发事件的 commit 作者是 `Cursor Agent` 或 `cursor[bot]`
- 触发事件的分支名包含 `autobc` 或 `auto-fix`
- 触发事件的 PR 标题包含 `auto-fix`、`chore:`、`docs:` 或 `test:`

**每次运行按以下步骤执行：**

### 步骤1：激活环境并运行测试
```bash
source .venv/bin/activate
python -m pytest backend/tests -v --tb=short 2>&1
```

### 步骤2：分析失败原因
对每一个失败的测试：
- 读取测试文件和对应源码
- 分类：代码 Bug / 测试过期 / 环境问题 / 已知预期失败
- 跳过已知预期失败（test_lifecycle.py 中的 UserLedgerAuth 相关）

### 步骤3：自动修复
- 修复代码 Bug 和过期测试
- 修复后逐个重跑验证
- 金融计算代码必须保持 Decimal 精度

### 步骤4：最终验证
```bash
python -m pytest backend/tests -v --tb=short 2>&1
```
确认通过率不低于修复前。

### 步骤5：提交报告
如有修复，创建 PR，分支名：`cursor/auto-fix-tests-{日期}-1988`

如有无法自动修复的问题，用 Comment on Pull Request 工具或创建 GitHub Issue 描述：
- 失败的测试名称
- 错误信息
- 建议的修复方向

**测试通过率目标：≥ 238/245（96%以上）**

---

## 工具配置 / Tools to Enable
- ✅ PR creation
- ✅ Comment on pull request（用于报告）

## 注意 / Notes
- 每次运行约 5-10 分钟，按 Max Mode API 定价计费
- 可在 cursor.com/automations 查看每次运行日志
