# Git 版本控制与分支管理策略

> 本文档定义了「财务向量审计系统」项目的 Git 分支管理规范、提交规范、代码审查流程和分支保护规则。
> 所有团队成员必须遵循此策略，以确保代码版本的统一管理和追踪。

---

## 一、分支模型

本项目采用简化的 Git Flow 模型，包含以下长期分支和临时分支：

### 1.1 长期分支（永久存在）

| 分支 | 用途 | 保护级别 |
|------|------|----------|
| `main` | 生产环境代码，始终可部署 | 严格保护：禁止直接推送，必须通过 PR 合并 |
| `develop` | 开发集成分支，最新功能在此合并 | 中度保护：禁止直接推送，必须通过 PR 合并 |

### 1.2 临时分支（用完即删）

| 分支前缀 | 用途 | 命名格式 | 示例 |
|----------|------|----------|------|
| `feature/` | 新功能开发 | `feature/<简短描述>-<issue编号>` | `feature/voucher-import-102` |
| `bugfix/` | 非紧急 Bug 修复 | `bugfix/<简短描述>-<issue编号>` | `bugfix/balance-sheet-rounding-105` |
| `hotfix/` | 生产环境紧急修复 | `hotfix/<简短描述>-<issue编号>` | `hotfix/auth-crash-110` |
| `release/` | 发布准备 | `release/<版本号>` | `release/v1.2.0` |
| `refactor/` | 代码重构 | `refactor/<简短描述>` | `refactor/entry-service-cleanup` |
| `docs/` | 文档更新 | `docs/<简短描述>` | `docs/api-reference-update` |
| `test/` | 测试相关 | `test/<简短描述>` | `test/e2e-import-flow` |
| `chore/` | 构建/工具/依赖 | `chore/<简短描述>` | `chore/upgrade-antd-v5` |

### 1.3 分支命名规则

1. **全部小写**，单词间用连字符 `-` 分隔
2. **包含 Issue 编号**（如有），放在分支名末尾
3. **长度不超过 50 字符**
4. **禁止使用** `cursor/`、`auto-`、`backup/`、`local/` 等非标准前缀
5. **禁止使用中文**，统一使用英文

**正例**：
```
feature/unified-entry-page-115
bugfix/voucher-balance-error-116
hotfix/auth-token-expiry-117
release/v1.3.0
```

**反例**：
```
feature/统一入口界面
cursor/auto-fix-something
fix-voucher-import-rebased
backup/sandbox-merge-20260625
我的分支
```

---

## 二、分支生命周期管理

### 2.1 创建分支

```bash
# 1. 确保本地 main 最新
git checkout main
git pull origin main

# 2. 基于 main 创建功能分支
git checkout -b feature/unified-entry-page-115

# 3. 推送到远程
git push -u origin feature/unified-entry-page-115
```

**规则**：
- 所有功能分支必须从最新的 `main`（或 `develop`）创建
- 创建前先 `git pull` 确保本地代码最新
- 分支创建后立即推送到远程，建立跟踪关系

### 2.2 合并分支

合并通过 **Pull Request（PR）** 完成，禁止直接 `git push` 到 `main`。

**PR 合并流程**：

1. **提交 PR**：从功能分支向 `main` 发起 PR
2. **自动检查**：CI 自动运行（类型检查、单元测试、Lint）
3. **代码审查**：至少 1 名审查者批准
4. **合并方式**：使用 **Squash and Merge**（压缩提交历史）
5. **删除分支**：合并后自动删除源分支

**合并方式说明**：

| 方式 | 适用场景 | 说明 |
|------|----------|------|
| Squash and Merge | 默认方式 | 将多个提交压缩为一个，保持 main 历史简洁 |
| Rebase and Merge | 需保留提交历史 | 变基后逐个提交，适合有意义的分步提交 |
| Create Merge Commit | 发布分支合入 | 保留合并节点，用于 release 合入 main |

### 2.3 删除分支

```bash
# 合并后删除本地分支
git branch -d feature/unified-entry-page-115

# 删除远程分支
git push origin --delete feature/unified-entry-page-115

# 清理本地已删除的远程分支引用
git fetch --prune
```

**规则**：
- PR 合并后**立即删除**源分支
- **每周一次**分支清理：删除已合并、已关闭的陈旧分支
- 30 天未活动的分支将被自动标记为 stale 并通知创建者
- 60 天未活动的分支将被自动删除

### 2.4 分支同步

```bash
# 功能分支定期同步 main 的更新
git checkout feature/unified-entry-page-115
git fetch origin
git rebase origin/main  # 推荐 rebase 保持线性历史
# 如有冲突，解决后继续
git rebase --continue
git push --force-with-lease  # 安全的强制推送
```

**注意**：禁止使用 `git push --force`，必须使用 `--force-with-lease` 避免覆盖他人提交。

---

## 三、提交规范

### 3.1 Commit Message 格式

采用 **Conventional Commits** 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 3.2 Type 类型

| Type | 说明 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(voucher): 添加凭证批量审核功能` |
| `fix` | Bug 修复 | `fix(report): 修复资产负债表不平衡问题` |
| `docs` | 文档更新 | `docs(api): 更新凭证接口文档` |
| `style` | 代码格式（不影响逻辑） | `style(entry): 统一缩进为4空格` |
| `refactor` | 重构（无功能变化） | `refactor(import): 提取公共解析逻辑` |
| `test` | 测试相关 | `test(voucher): 添加凭证生成单元测试` |
| `chore` | 构建/工具/依赖 | `chore(deps): 升级 antd 到 5.20` |
| `perf` | 性能优化 | `perf(query): 优化科目余额查询性能` |
| `ci` | CI 配置 | `ci: 添加前端构建检查工作流` |
| `revert` | 回滚提交 | `revert: 回滚凭证导入功能` |

### 3.3 Scope 范围（可选）

| Scope | 对应模块 |
|-------|----------|
| `voucher` | 凭证管理 |
| `entry` | 会计分录 |
| `import` | 数据导入 |
| `report` | 财务报表 |
| `audit` | 审计模块 |
| `ledger` | 账簿管理 |
| `period` | 会计期间 |
| `auth` | 认证授权 |
| `parser` | 解析引擎 |
| `frontend` | 前端整体 |
| `backend` | 后端整体 |
| `db` | 数据库/迁移 |
| `api` | API 接口 |

### 3.4 提交信息规则

1. **Subject 行**：
   - 不超过 72 字符
   - 使用祈使句（如「添加」而非「添加了」）
   - 首字母不大写（英文）
   - 结尾不加句号

2. **Body（可选）**：
   - 解释「为什么」做这个改动，而非「做了什么」（代码本身说明做了什么）
   - 每行不超过 100 字符
   - 使用空行分隔段落

3. **Footer（可选）**：
   - 关联 Issue：`Closes #123`、`Fixes #456`、`Refs #789`
   - 标注 BREAKING CHANGE：`BREAKING CHANGE: 凭证接口返回格式变更`

### 3.5 提交信息示例

```
feat(voucher): 添加凭证批量审核功能

支持在凭证列表页多选凭证后批量审核，减少逐张操作的重复劳动。
复用现有审核服务，保持借贷平衡校验和审计日志记录。

Closes #115
```

```
fix(report): 修复资产负债表期末余额计算错误

损益结转后未更新留存收益科目余额，导致资产负债表不平衡。
在 pl_transfer 完成后同步更新 4103 科目期末余额。

Fixes #116
```

```
refactor(import): 提取序时簿解析公共逻辑

将 audit_day_book_service 和 import_service 中重复的
CSV 表头识别逻辑提取到 day_book_parser 模块，
降低后续维护成本。
```

### 3.6 禁止事项

- 禁止提交信息只写 `fix`、`update`、`wip` 等无意义内容
- 禁止一个提交包含多个不相关的功能改动
- 禁止提交含调试代码（`console.log`、`print`、`debugger`）
- 禁止提交 `.env`、`*.db`、`node_modules/` 等应被忽略的文件

---

## 四、Pull Request 规范

### 4.1 PR 标题

与最终 squash merge 的 commit message 一致，遵循 Conventional Commits 格式：

```
feat(voucher): 添加凭证批量审核功能
```

### 4.2 PR 描述模板

参见 `.github/PULL_REQUEST_TEMPLATE.md`，必须包含：

1. **变更说明**：做了什么、为什么做
2. **变更类型**：新功能 / Bug 修复 / 重构 / 文档
3. **测试说明**：如何验证此改动
4. **关联 Issue**：Closes #xxx
5. **检查清单**：自检项确认

### 4.3 代码审查要求

| 目标分支 | 最低审查人数 | CI 要求 | 说明 |
|----------|-------------|---------|------|
| `main` | 1 人 | 必须通过 | 所有 PR 必须经过审查 |
| `develop` | 1 人 | 必须通过 | 开发分支同样需要审查 |
| `release/*` | 2 人 | 必须通过 | 发布分支需更严格审查 |

### 4.4 审查标准

审查者应重点检查：

1. **财务逻辑正确性**（最高优先级）
   - 金额计算是否使用 Decimal 类型
   - 借贷平衡校验是否完整
   - 会计期间状态校验是否正确
2. **代码质量**
   - 命名规范（snake_case、完整英文单词）
   - 注释完整性（函数注释、会计口径说明）
   - 单函数不超过 80 行
3. **安全性**
   - 无硬编码密钥/密码
   - 敏感操作有审计日志
   - 输入校验完整
4. **测试覆盖**
   - 新功能有对应单元测试
   - 金额计算测试误差不超过 0.01 元

---

## 五、分支保护规则

### 5.1 main 分支保护规则

通过 GitHub 仓库 Settings → Branches 配置：

| 规则 | 设置 |
|------|------|
| Require pull request before merging | ✅ 开启 |
| Required approvals | 至少 1 个 |
| Dismiss stale pull request approvals when new commits are pushed | ✅ 开启 |
| Require review from Code Owners | ✅ 开启 |
| Require status checks to pass before merging | ✅ 开启 |
| Require branches to be up to date before merging | ✅ 开启 |
| Required status checks | `ci-frontend`, `ci-backend`, `lint` |
| Require conversation resolution before merging | ✅ 开启 |
| Do not allow bypassing the above settings | ✅ 开启 |
| Restrict who can push to matching branches | 仅管理员 |
| Allow force pushes | ❌ 禁止 |
| Allow deletions | ❌ 禁止 |

### 5.2 配置方法

> **注意**：当前仓库为私有仓库，分支保护规则需要 GitHub Pro 账户。
> 升级到 GitHub Pro 后可通过以下方式配置，或将仓库设为公开后配置。

**方法一：GitHub 网页手动配置（推荐）**

1. 打开仓库页面 → Settings → Branches
2. 点击 "Add branch protection rule"
3. Branch name pattern 填入 `main`
4. 按上表逐项勾选设置
5. 点击 "Create" 保存

**方法二：通过 gh CLI 配置**

```bash
# 配置 main 分支保护规则（需要 GitHub Pro 或公开仓库）
gh api repos/banmaoycrane-arch/audit-platform-main/branches/main/protection \
  --method PUT \
  --field required_pull_request_reviews='{"required_approving_review_count":1,"dismiss_stale_reviews":true,"require_code_owner_reviews":true}' \
  --field required_status_checks='{"strict":true,"contexts":["ci-frontend","ci-backend","lint"]}' \
  --field enforce_admins=true \
  --field restrictions=null \
  --field allow_force_pushes=false \
  --field allow_deletions=false
```

**当前临时措施**（分支保护生效前）：
- 团队约定所有变更必须通过 PR 合并，禁止直接 `git push` 到 main
- PR 合并前至少 1 人 Code Review 并 approve
- CI 检查通过后再合并

---

## 六、CI/CD 配置

### 6.1 必须通过的 CI 检查

每个 PR 必须通过以下 CI 检查才能合并：

1. **ci-frontend**：前端类型检查 + 构建
2. **ci-backend**：后端单元测试
3. **lint**：代码风格检查

### 6.2 CI 触发条件

- **PR 创建/更新**：运行全部检查
- **推送到 main**：运行全部检查 + 部署准备
- **定时任务**：每天凌晨运行完整测试套件

---

## 七、发布流程

### 7.1 创建发布分支

```bash
# 从 main 创建发布分支
git checkout main
git pull origin main
git checkout -b release/v1.3.0

# 更新版本号
# 修改 package.json、pyproject.toml 中的版本号

# 提交版本更新
git commit -m "chore(release): 准备 v1.3.0 发布"

# 推送到远程
git push -u origin release/v1.3.0
```

### 7.2 合并发布分支

```bash
# 发布分支测试通过后，通过 PR 合入 main
# 使用 "Create Merge Commit" 方式保留合并节点

# 合并后打标签
git checkout main
git pull origin main
git tag -a v1.3.0 -m "Release v1.3.0: 统一入口界面与P1缺陷修复"
git push origin v1.3.0
```

### 7.3 紧急修复（Hotfix）

```bash
# 从 main 创建 hotfix 分支
git checkout main
git pull origin main
git checkout -b hotfix/auth-crash-110

# 修复后通过 PR 合入 main
# 合并后打 patch 版本标签
git tag -a v1.3.1 -m "Hotfix v1.3.1: 修复认证崩溃问题"
git push origin v1.3.1
```

---

## 八、分支清理与维护

### 8.1 定期清理

- **每周一次**：检查并删除已合并的本地和远程分支
- **每月一次**：审计所有活跃分支，关闭长期不活动的分支
- **自动清理**：CI 工作流自动关闭 `cursor/autobc-*` 等自动生成的陈旧 PR

### 8.2 清理脚本

```bash
# 删除本地已合并的分支（排除 main 和 develop）
git branch --merged main | grep -v -E "main|develop" | xargs git branch -d

# 清理本地已删除的远程分支引用
git fetch --prune

# 查找 30 天未活动的远程分支
git for-each-ref --sort=-committerdate --format='%(refname:short) %(committerdate:relative)' refs/remotes/origin/ | head -30
```

### 8.3 陈旧分支处理

| 不活动时长 | 处理方式 |
|-----------|----------|
| 0-30 天 | 正常保留 |
| 30-60 天 | 标记为 stale，通知创建者 |
| 60-90 天 | 自动关闭关联的 PR |
| 90 天以上 | 自动删除分支 |

---

## 九、团队协作指南

### 9.1 日常开发流程

```
1. 接到任务 → 在 GitHub 创建 Issue（如已有则跳过）
2. git checkout main && git pull  # 确保最新
3. git checkout -b feature/xxx-issue编号
4. 开发 + 本地测试
5. git add 具体文件  # 禁止 git add -A
6. git commit -m "feat(scope): 描述"
7. git push -u origin feature/xxx-issue编号
8. 在 GitHub 创建 PR → 填写 PR 模板
9. 等待 CI 通过 + 代码审查
10. 审查通过 → Squash and Merge
11. 删除本地和远程分支
```

### 9.2 多人协作注意事项

1. **避免长期分支**：功能分支生命周期不超过 1 周，大功能拆分为多个小 PR
2. **频繁同步**：每天从 main rebase 一次，减少最终合并冲突
3. **小步提交**：每个 PR 控制在 500 行改动以内，便于审查
4. **及时回应**：PR 审查意见 24 小时内回应
5. **不可重写公共分支**：已推送的分支如需 rebase，先通知协作者

### 9.3 冲突解决

```bash
# rebase 遇到冲突
git rebase origin/main
# 解决冲突文件
git add <冲突文件>
git rebase --continue
# 中止 rebase
git rebase --abort

# 安全推送
git push --force-with-lease
```

**冲突解决原则**：
- 财务逻辑冲突：以业务负责人意见为准
- 代码风格冲突：以项目规范为准
- 无法判断时：双方讨论，必要时拉入第三方

### 9.4 紧急情况处理

**生产环境出现紧急 Bug**：
1. 立即在 `main` 上创建 `hotfix/xxx-issue编号` 分支
2. 最小化修复，不做额外重构
3. 快速 PR + 加急审查
4. 合并后立即部署
5. 部署验证后打 tag

---

## 十、版本号规范

采用 **语义化版本**（Semantic Versioning）：`MAJOR.MINOR.PATCH`

| 版本位 | 含义 | 示例 |
|--------|------|------|
| MAJOR | 不兼容的 API 变更 | 1.0.0 → 2.0.0 |
| MINOR | 向下兼容的功能新增 | 1.0.0 → 1.1.0 |
| PATCH | 向下兼容的 Bug 修复 | 1.0.0 → 1.0.1 |

**Tag 命名**：`v1.3.0`（带 `v` 前缀）

---

## 附录 A：快速参考命令

```bash
# === 日常操作 ===
git checkout main && git pull                    # 切回主分支并更新
git checkout -b feature/xxx-105                  # 创建功能分支
git add backend/app/services/voucher_service.py  # 添加指定文件
git commit -m "feat(voucher): 添加批量审核"       # 提交
git push -u origin feature/xxx-105               # 推送并建立跟踪

# === 同步与更新 ===
git fetch origin                                 # 获取远程更新
git rebase origin/main                           # 变基到最新 main
git push --force-with-lease                      # 安全强制推送

# === 清理 ===
git branch -d feature/xxx-105                    # 删除本地分支
git push origin --delete feature/xxx-105         # 删除远程分支
git fetch --prune                                # 清理远程引用

# === 查看 ===
git log --oneline -10                            # 查看最近提交
git branch -a --sort=-committerdate              # 按活动时间排序分支
git diff main...feature/xxx-105 --stat           # 查看分支差异
```

---

## 附录 B：本策略的生效与更新

- **生效日期**：2026-07-02
- **更新方式**：修改本文档后通过 PR 合入 main
- **适用范围**：本项目所有贡献者（含 AI 辅助开发工具）
- **解释权**：项目负责人
