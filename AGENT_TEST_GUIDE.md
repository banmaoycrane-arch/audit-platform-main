# Agent 治理流程交互测试指南

## 一、环境准备

### 1.1 启动后端服务

```bash
# 进入项目目录
cd e:\projects\finance-vector-audit\wroksapce20260616

# 启动后端服务
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8010 --reload
```

### 1.2 启动前端服务

```bash
# 新开一个终端，进入项目目录
cd e:\projects\finance-vector-audit\wroksapce20260616

# 启动前端服务
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### 1.3 验证服务启动

后端健康检查：
```bash
curl http://127.0.0.1:8010/api/agent/config/status
```

预期响应：
```json
{
  "ai_local_model_enabled": false,
  "ai_fallback_to_rules": true,
  "model_provider": "cloud",
  "api_key_configured": false,
  "status": "ready"
}
```

---

## 二、测试账户信息

| 用户名 | 手机号 | 角色 |
|--------|--------|------|
| `agent_draft_review_user` | `13800139019` | 测试用户 |

---

## 三、完整测试流程

### Step 1: 登录系统

1. 打开浏览器访问: `http://127.0.0.1:5173/login`
2. 输入用户名: `agent_draft_review_user`
3. 输入密码: `password` (或任意密码，测试环境不校验)
4. 点击「登录」按钮

### Step 2: 进入 Agent 控制台

1. 登录后，在左侧导航栏找到「Agent 控制台」菜单
2. 点击进入 Agent 控制台页面

### Step 3: 查看模型配置状态

1. 在 Agent 控制台页面，找到「模型配置状态」卡片
2. 验证显示内容：
   - 模型供应商：cloud
   - API Key 状态：未配置（测试环境正常）
   - 是否启用本地模型：否
   - 回退规则：已启用

### Step 4: 查看尽调审计案例模板

1. 找到「尽调审计案例模板」卡片
2. 点击「查看模板」按钮
3. 验证模板包含：
   - 案例名称
   - 参与角色（主 Agent、会计文员、质量复核、审计师）
   - 任务分解步骤
   - 人工确认点标记

### Step 5: 查看多 Agent 协同计划

1. 找到「多 Agent 协同计划」卡片
2. 点击「生成计划」按钮
3. 验证计划包含：
   - 主 Agent 任务（文件读取、任务分解）
   - 辅助 Agent 任务（资料收集、底稿编制）
   - 需要人工确认的步骤标记

### Step 6: 申请工具确认（高风险动作）

1. 在「工具执行」区域，选择工具：`generate_audit_draft`（生成审计初稿）
2. 点击「申请确认」按钮
3. 验证：系统记录申请，状态为「待确认」

### Step 7: 人工确认

1. 在「确认记录列表」中找到刚创建的申请记录
2. 点击「确认」按钮
3. 在弹出的确认框中输入意见：`同意生成审计初稿草稿`
4. 点击「确认执行」按钮
5. 验证：记录状态变为「已确认」

### Step 8: 执行草稿生成

1. 在已确认的记录右侧，点击「生成草稿」按钮
2. 等待执行完成（模拟执行）
3. 验证：
   - 草稿执行结果显示
   - 状态变为「已生成草稿」
   - `output_type` 显示为 `draft`
   - `review_required` 显示为 `true`

### Step 9: 创建草稿复核记录

1. 在草稿结果下方，点击「创建复核记录」按钮
2. 验证：
   - 自动创建待复核记录
   - 复核状态显示为「待复核」

### Step 10: 填写复核意见并提交（通过）

1. 在「草稿人工复核记录」区域，找到待复核记录
2. 在文本框中输入复核意见：`已复核草稿内容，符合审计准则要求，允许进入正式交付设计阶段。`
3. 点击「复核通过」按钮
4. 验证：
   - 复核状态变为「已通过」
   - 显示复核人信息
   - 显示复核时间
   - 「允许进入正式交付设计」标签显示为绿色
   - `allow_formal_delivery_design` = `true`

### Step 11: 验证退回重做流程（可选）

1. 重复 Step 6-9 创建新的草稿记录
2. 在复核阶段，输入意见：`底稿内容不完整，需要补充更多审计证据。`
3. 点击「退回重做」按钮
4. 验证：
   - 复核状态变为「已退回」
   - 「退回重做」标签显示为橙色/红色
   - `returned_for_rework` = `true`
   - `allow_formal_delivery_design` = `false`

---

## 四、验证点清单

### 4.1 功能验证

| 验证项 | 预期结果 | 状态 |
|--------|----------|------|
| 模型配置状态展示 | 正确显示配置信息 | □ |
| 案例模板加载 | 显示尽调审计案例结构 | □ |
| 协同计划生成 | 显示多 Agent 任务分解 | □ |
| 工具申请 | 创建待确认记录 | □ |
| 人工确认 | 记录状态变为已确认 | □ |
| 草稿执行 | 生成草稿输出 | □ |
| 复核记录创建 | 创建待复核记录 | □ |
| 复核通过 | 允许进入正式交付设计 | □ |
| 退回重做 | 禁止进入正式交付设计 | □ |

### 4.2 业务规则验证

| 规则 | 验证方法 |
|------|----------|
| 未确认记录不能执行草稿 | 尝试对「待确认」记录点击「生成草稿」，应提示错误 |
| 退回重做时不能允许正式交付 | 选择「退回重做」同时勾选「允许正式交付」，应提示错误 |
| 复核意见必填 | 不填写意见直接提交，应提示错误 |
| 已复核记录不能重复提交 | 对已通过记录再次提交，应提示错误 |

### 4.3 执行留痕验证

通过数据库查询验证执行留痕：

```sql
-- 查询 Agent 相关审计日志
SELECT * FROM execution_audit_logs 
WHERE execution_source = 'agent_assisted'
ORDER BY created_at DESC;
```

验证日志包含：
- 工具调用记录
- 审批确认记录
- 草稿执行记录
- 复核提交记录

---

## 五、测试数据清理

测试完成后可清理测试数据：

```sql
-- 清理测试数据
DELETE FROM agent_draft_reviews WHERE id > 0;
DELETE FROM agent_approvals WHERE id > 0;
DELETE FROM execution_audit_logs WHERE execution_source = 'agent_assisted';
```

---

## 六、技术支持

如遇问题，请检查：

1. **后端服务状态**：确认 `http://127.0.0.1:8010/docs` 可访问
2. **前端控制台**：打开浏览器开发者工具查看控制台错误
3. **网络请求**：检查 Network 面板中 API 请求状态
4. **数据库连接**：确认 SQLite 数据库文件存在且可读写

---

## 附录：API 端点清单

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/agent/config/status` | GET | 获取模型配置状态 |
| `/api/agent/tools` | GET | 获取工具白名单 |
| `/api/agent/roles` | GET | 获取 Agent 角色列表 |
| `/api/agent/case-template` | GET | 获取尽调审计案例模板 |
| `/api/agent/orchestration-plan` | GET | 获取多 Agent 协同计划 |
| `/api/agent/approvals/request` | POST | 申请工具确认 |
| `/api/agent/approvals/{id}/confirm` | POST | 人工确认 |
| `/api/agent/approvals/{id}/execute-draft` | POST | 执行草稿生成 |
| `/api/agent/approvals/{id}/draft-review` | POST | 创建复核记录 |
| `/api/agent/draft-reviews/{id}/submit` | POST | 提交复核意见 |