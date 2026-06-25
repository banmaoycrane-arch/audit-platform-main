# Cursor Automations 设置指南 / Setup Guide

本文档说明如何为 audit-platform-main 项目在 Cursor 中配置三个自动化任务。

This document explains how to configure three Cursor Automations for the audit-platform-main project.

---

## 前置条件 / Prerequisites

1. **GitHub 仓库已连接到 Cursor** / GitHub repo connected to Cursor
   - 打开 [cursor.com](https://cursor.com) → Settings → Integrations → GitHub → 授权
   - Open [cursor.com](https://cursor.com) → Settings → Integrations → GitHub → Authorize
   - **完整逐项说明**（含 PR 权限、分支命名 `cursor/auto*`、保护 `main`）：见 [CURSOR_GITHUB_SETUP.md](./CURSOR_GITHUB_SETUP.md)

2. **已启用 Cloud Agents** / Cloud Agents enabled
   - cursor.com → 左侧菜单 → Agents → 确认已开启

3. **仓库名称** / Repository name
   - 本仓库 GitHub 路径：`banmaoycrane-arch/audit-platform-main`（下文 Automation 仓库选择请选此项，而非旧名 `finance-vector-audit`）

---

## Automation 1：每日自动测试 & 修复
## Daily Auto-Test & Auto-Fix

**目的**：每天凌晨自动跑测试，失败时自动修复并提 PR  
**Purpose**: Run tests daily at 2 AM, auto-fix failures and create a PR

### 设置步骤 / Setup Steps

```
1. 打开 https://cursor.com/automations/new
   Open https://cursor.com/automations/new

2. 触发器 / Trigger:
   类型选 "Scheduled"
   Schedule: 0 2 * * *（每天凌晨 2 点 UTC）

3. 仓库 / Repository:
   选择 audit-platform-main，分支选 main

4. 提示词 / Prompt:
   复制 .cursor/automation-prompts/1-daily-test-and-fix.md 中 "---" 之间的内容

5. 工具 / Tools:
   ✅ 勾选 PR creation
   ✅ 勾选 Comment on pull request

6. 名称 / Name: "Daily Test Runner & Auto-Fix"

7. 点击 Save，切换 Active 开关为开启
```

---

## Automation 2：Issue 自动开发
## Auto-Develop from GitHub Issues

**目的**：有新 Issue 提交时，Agent 自动分析并写代码  
**Purpose**: When a new Issue is created, Agent analyzes and implements the code

### 前置：在 GitHub 创建 label
### Pre-step: Create GitHub label

在 GitHub 仓库的 Issues → Labels 页面，创建标签：
- 名称：`auto-dev`
- 颜色：`#0075ca`（蓝色）
- 说明：供 Agent 自动开发的 Issue

### 设置步骤 / Setup Steps

```
1. 打开 https://cursor.com/automations/new

2. 触发器 / Trigger:
   类型选 "GitHub"
   事件选 "Issue created"（Issue 创建）

3. 仓库 / Repository:
   选择 audit-platform-main

4. 提示词 / Prompt:
   复制 .cursor/automation-prompts/2-issue-auto-develop.md 中 "---" 之间的内容

5. 工具 / Tools:
   ✅ 勾选 PR creation
   ✅ 勾选 Comment on pull request

6. 名称 / Name: "Issue Auto-Developer"

7. 点击 Save，切换 Active 开关为开启
```

### 使用方法 / How to Use

```
1. 在 GitHub 创建新 Issue，描述需要实现的功能或修复的 Bug
2. 给 Issue 打上 "auto-dev" 标签
3. Cursor Agent 自动触发，约 10-20 分钟后创建 PR
4. 审查 PR，满意后合并
```

---

## Automation 3：PR 合并后自动更新文档
## Auto-Update Docs & Changelog on PR Merge

**目的**：有 PR 合并到 main 时，自动更新 README 和 CHANGELOG  
**Purpose**: When a PR is merged to main, auto-update README and CHANGELOG

### 设置步骤 / Setup Steps

```
1. 打开 https://cursor.com/automations/new

2. 触发器 / Trigger:
   类型选 "GitHub"
   事件选 "PR merged"（PR 合并）

3. 仓库 / Repository:
   选择 audit-platform-main，目标分支选 main

4. 提示词 / Prompt:
   复制 .cursor/automation-prompts/3-pr-merge-changelog.md 中 "---" 之间的内容

5. 工具 / Tools:
   ✅ 勾选 PR creation

6. 名称 / Name: "PR Merge Doc Updater"

7. 点击 Save，切换 Active 开关为开启
```

---

## 三个 Automation 的协同流程 / How They Work Together

```
开发者 or Agent 提交代码
        ↓
  新 Issue 创建
        ↓
[Automation 2] Issue-Developer 自动实现代码，创建 PR
        ↓
  代码审查后 PR 合并到 main
        ↓
[Automation 3] Doc-Updater 自动更新 README & CHANGELOG
        ↓
  每天凌晨 2 点
        ↓
[Automation 1] Test-Runner 自动跑测试，失败自动修复
```

---

## 自定义 Agent 角色文件 / Custom Agent Files

以下文件已在项目中创建，Automation 和手动对话都可以调用：

| 文件 | 角色 | 调用方式 |
|------|------|---------|
| `.cursor/agents/test-runner-fixer.md` | 测试专家 | `/test-runner-fixer` 或 Agent 自动判断 |
| `.cursor/agents/issue-developer.md` | 全栈开发专家 | `/issue-developer` 或 Automation 2 触发 |
| `.cursor/agents/changelog-doc-updater.md` | 文档维护专家 | `/changelog-doc-updater` 或 Automation 3 触发 |

手动调用示例 / Manual invocation:
```
/test-runner-fixer 运行所有测试并修复失败项
/issue-developer 实现风险识别规则的金额阈值可配置化
/changelog-doc-updater 为上一个 PR 更新文档
```

---

## 费用说明 / Billing Notes

- 所有 Automation 运行都按 **Max Mode** API 用量计费
- Automation 1（每日测试）：约 $0.5-2 / 次，取决于测试量和修复复杂度
- Automation 2（Issue 开发）：约 $2-10 / 次，取决于功能复杂度
- Automation 3（文档更新）：约 $0.2-0.5 / 次
- 可在 cursor.com/automations 查看每次运行的 token 用量和费用
