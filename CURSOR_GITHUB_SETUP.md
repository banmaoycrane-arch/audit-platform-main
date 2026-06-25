# Cursor GitHub 集成配置指南

本文档说明如何为 **audit-platform-main** 配置 Cursor 与 GitHub 的完整集成，使 Cloud Agent 能**创建 PR、评论 PR、合并前审查**，而不是只能 `git push`。

相关文档：[AUTOMATIONS_SETUP.md](./AUTOMATIONS_SETUP.md)（三个 Automation 的配置）

---

## 一、为什么有时 Agent 能 push 但不能建 PR？

Cloud Agent 环境里通常有**两套不同的 GitHub 凭证**：

| 能力 | 典型状态 | 说明 |
|------|----------|------|
| `git push` / `git pull` | ✅ 通常可用 | Git 远程 URL 使用 `x-access-token`，可推送分支甚至 `main` |
| `gh pr create` / 创建 Issue | ❌ 可能 403 | GitHub API 报 `Resource not accessible by integration` |
| Cursor `ManagePullRequest` 工具 | ⚠️ 需满足条件 | 分支名须以 `cursor/auto` 开头，且集成权限完整 |
| 读 PR 列表 | ✅ 通常可用 | 只读 API 一般不受限 |

**结论**：Agent 写代码、跑测试、推分支没问题；缺的是「PR 写入」权限或分支命名不符合平台规范。按本文逐项配置即可恢复标准 PR 流程。

---

## 二、逐项配置清单（在 cursor.com 操作）

### 步骤 1：连接 GitHub 账号

1. 打开 [https://cursor.com/settings](https://cursor.com/settings)
2. 左侧进入 **Integrations**（集成）
3. 找到 **GitHub**，点击 **Connect** / **Authorize**
4. 在 GitHub 授权页确认：
   - 授权给 Cursor GitHub App
   - 若仓库为私有，选择 **Only select repositories**，勾选 `banmaoycrane-arch/audit-platform-main`
   - 或选择 **All repositories**（仅当你信任该范围时）

**检查点**：Integrations 页 GitHub 显示 **Connected**，且仓库列表里能看到 `audit-platform-main`。

---

### 步骤 2：确认 Cursor GitHub App 在仓库上的权限

1. 打开 GitHub 仓库：[audit-platform-main → Settings → Integrations → Applications](https://github.com/banmaoycrane-arch/audit-platform-main/settings/installations)
2. 找到 **Cursor**（或 `cursor[bot]` 对应的应用），点击 **Configure**
3. 确认该仓库已授权，且权限至少包含：
   - **Contents**：Read and write（读写代码）
   - **Pull requests**：Read and write（创建/更新 PR）
   - **Issues**：Read and write（若要用 Issue 驱动 Automation）
   - **Metadata**：Read（默认）

若 Pull requests 仅为 Read，Agent 会出现 `gh pr create` 403。

---

### 步骤 3：启用 Cloud Agents

1. [cursor.com](https://cursor.com) 左侧 **Agents**
2. 确认 Cloud Agents 已开启
3. 新建 Agent 任务时，**Repository** 选择 `banmaoycrane-arch/audit-platform-main`，**Base branch** 选 `main`

---

### 步骤 4：Agent / Automation 勾选 PR 相关工具

创建或编辑 **Cloud Agent 任务**、**Automation** 时，在 **Tools** 区域勾选：

- ✅ **PR creation**（创建 Pull Request）
- ✅ **Comment on pull request**（在 PR 上评论，可选但建议开）

参考：[AUTOMATIONS_SETUP.md](./AUTOMATIONS_SETUP.md) 中三个 Automation 的第 5 步。

未勾选时，Agent 可能只能改代码和 push，无法调用平台的 PR 管理工具。

---

### 步骤 5：分支命名规范（Cloud Agent 必遵）

Cursor 平台 PR 工具要求 feature 分支以 **`cursor/auto`** 为前缀，例如：

```text
cursor/auto-ai-step2-period-picker-70f0
cursor/autoissue-b909          # Issue 自动化常用
cursor/autobc-<agent-id>-<hash> # Bugfix 自动化常用
```

**不要**使用仅 `cursor/<name>-70f0` 的命名去走 `ManagePullRequest`，否则会报错：

```text
The head branch does not start with the required prefix `cursor/auto`
```

人工/文档类补充说明可用：

```text
cursor/auto-docs-<描述>-70f0
```

项目内另有语义化分支规范（`phase-a/...`、`fix/...`），见 [.trae/documents/branch-naming-convention.md](./.trae/documents/branch-naming-convention.md)。**Cloud Agent 走 Cursor PR 工具时，优先满足 `cursor/auto*`。**

---

### 步骤 6：（推荐）保护 `main` 分支

在 GitHub → **Settings → Branches → Branch protection rules** 为 `main` 添加规则：

| 规则 | 建议 |
|------|------|
| Require a pull request before merging | ✅ 开启 |
| Require approvals | 可选（1 人） |
| Restrict who can push to matching branches | 可选，禁止直接 push |
| Require status checks to pass | 有 CI 时开启 |

这样即使 Agent 的 Git token 能 push `main`，也会被 GitHub 拒绝，**强制走 PR**。

---

### 步骤 7：验证集成是否生效

在 Cloud Agent 会话中，Agent 应能完成：

```text
1. git checkout -b cursor/auto-test-integration-70f0
2. 做小改动 → commit → git push -u origin cursor/auto-test-integration-70f0
3. ManagePullRequest create_pr（或 Automation 自动创建）
4. GitHub 上出现由 cursor[bot] 创建的 PR
5. 你在 GitHub UI 审查后 Merge
```

**失败对照**：

| 现象 | 处理 |
|------|------|
| `Resource not accessible by integration` | 回到步骤 2，给 Cursor App 开 **Pull requests: Read and write** |
| `head branch does not start with cursor/auto` | 重命名分支为 `cursor/auto-*` 后重新 push |
| `git push` 成功但无 PR | 步骤 4 勾选 PR creation；勿依赖 `gh pr create` 单独建 PR |
| Agent 直接推上了 `main` | 步骤 6 启用 branch protection |

---

## 三、推荐的标准工作流

```text
需求 / Issue
    ↓
Cloud Agent 创建分支 cursor/auto-<功能>-70f0
    ↓
开发 + 测试 + push
    ↓
ManagePullRequest 创建 PR（标题 + 说明 + 验证结果）
    ↓
你在 GitHub Review → Merge
    ↓
（可选）Automation 3 更新 CHANGELOG / README
```

**不要**在集成未验证前让 Agent「合并 PR」或「直接 push main」，除非是你明确授权的 hotfix。

---

## 四、已合入但未经 PR 的记录

以下变更已直接进入 `main`，CHANGELOG 中已备注，便于审计追溯：

| 日期 | 提交 | 说明 |
|------|------|------|
| 2026-06-25 | [`3d88bdc`](https://github.com/banmaoycrane-arch/audit-platform-main/commit/3d88bdc) | AI Step2 期间下拉与自动选期（分支 `cursor/ai-step2-period-picker-70f0`） |

后续同类情况应优先走 PR；若必须直推，请在 CHANGELOG 的合并说明中注明原因。

---

## 五、与本仓库 Automation 的衔接

| Automation | 触发 | 依赖的本指南步骤 |
|------------|------|------------------|
| 每日测试修复 | 定时 | 步骤 1–4 |
| Issue 自动开发 | Issue + `auto-dev` 标签 | 步骤 1–4 + Issues 写权限 |
| PR 合并更新文档 | PR merged | 步骤 1–4 + PR 读权限 |

完整 Automation 提示词见 `.cursor/automation-prompts/`。

---

## 六、常见问题

**Q：Trae 本地和 Cursor Cloud 分支名不一致怎么办？**  
A：以 Cloud Agent 使用的 `cursor/auto-*` 为准推远端；本地可用 `git fetch` 后 `git checkout` 跟踪分支。

**Q：`gh` 在 Agent 里能用吗？**  
A：可读 PR；创建 PR 常失败。以 Cursor 平台 **PR creation** 工具为准，不要依赖 VM 里的 `gh pr create`。

**Q：私有仓库要特别注意什么？**  
A：步骤 1 必须显式授权 `audit-platform-main`；否则 Agent 克隆/推送可能成功但 API 写 PR 失败。

---

*文档版本：2026-06-25 · 随集成策略变更由 Agent 或维护者更新*
