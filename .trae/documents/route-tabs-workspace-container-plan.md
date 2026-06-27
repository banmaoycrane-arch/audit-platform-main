# 顶部多页签工作区与页面内导航容器改造计划

## Summary

本计划回应用户关于页面跳转体验的需求：当前点击左侧或页面内功能入口后，系统会直接切换到新路径，用户希望参考传统财务软件的工作区模式，在系统内部形成“可见、可切换、可关闭”的页面标签页。

目标不是把每次点击都打开成浏览器新标签页，而是在当前系统页面内部形成一个工作容器：

```text
顶部主导航/系统栏
左侧功能模块导航
内容区顶部：已打开页面标签页，例如：首页 / 账套管理 / 批量打印 / 移交申请
内容区主体：当前标签对应的页面容器
```

推荐第一阶段采用“系统内顶部页签 + 当前路由页面容器”的轻量方案。这样可以快速达到截图中的体验，同时不改动凭证、解析、审计、台账等业务逻辑。

## 需求归属与边界

根据 [requirements-domain-index.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/requirements-domain-index.md)：

```text
Domain: D03 Shell、导航、工作台、模块入口
Status: active-increment
Owner Spec: saas-shell-and-navigation
Depends On: 当前 React Router 路由、MainShell、左侧菜单
Acceptance Level: L5 前端接入完成 + L6 基础交互验证完成
```

### In Scope

本次只做：

1. 在内容区顶部增加系统内页签栏。
2. 点击菜单或页面链接后，当前路由自动进入页签栏。
3. 左侧功能导航继续保留，不替代现有菜单。
4. 标签页支持切换、关闭、首页固定。
5. 当前页面显示在一个统一内容容器中，形成类似截图的小工作区。
6. 账套切换时清理账套相关业务标签，避免跨账套误操作。
7. 增加主要业务路由标题映射，让标签显示“账套管理”“支持性文件”“审计工作底稿”等业务名称。

### Out of Scope

本次明确不做：

1. 不修改登录、注册、验证码、权限逻辑。
2. 不修改凭证生成、凭证复核、结账、报表计算逻辑。
3. 不修改文件解析、LLM 配置、解析任务进度逻辑。
4. 不修改台账行级编辑、更正、归档、删除的业务接口。
5. 不默认打开浏览器新标签页。
6. 不做真正 keep-alive 页面缓存。
7. 不处理所有页面的未保存表单提醒。
8. 不重构全站路由系统。

## Current State Analysis

### 1. 当前主布局

当前主布局在 [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx)。

现状：

- 顶部 Header 显示系统名、账套选择器等。
- 左侧 Sider + Menu 显示模块导航。
- 内容区使用 React Router 的 `Outlet` 渲染当前页面。

现有结构类似：

```tsx
<Header />
<Layout>
  <Sider>
    <Menu />
  </Sider>
  <Layout>
    <Content>
      <Outlet />
    </Content>
  </Layout>
</Layout>
```

当前点击菜单项后，通过 `<Link to="...">` 或 `navigate(...)` 直接切换路由，所以视觉上像“跳走了”。

### 2. 当前路由总入口

路由定义在 [App.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/App.tsx)。

现状：

- 使用 `BrowserRouter` + `Routes` + `Route`。
- 大多数业务页面都挂在 `MainShell` 的子路由下。
- `AuthGuard` 保护登录态。
- `LedgerDataGuard` 保护需要账套上下文的页面。

这说明最合适的页签容器位置是 [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx) 内容区，而不是每个业务页面内部。

### 3. 当前没有全局多页签

只读探索未发现：

- 全局 `RouteTabs` 组件；
- 全局打开页面列表；
- 标签关闭逻辑；
- keep-alive 缓存容器。

项目中已有局部业务 Tabs，例如底稿详情页内部的标签，但它们不是全局工作区页签。

## 推荐交互方案

### 方案选择：系统内页签，而不是浏览器新标签页

用户提出两个可能方向：

1. 点击后默认打开浏览器新标签页。
2. 参考截图，在系统页面上方形成导航标签栏，左侧仍保留功能导航，内容区形成小容器。

本计划推荐第 2 种。

原因：

1. 财务系统强依赖当前账套、当前项目、当前用户权限。浏览器新标签页过多时，容易出现多个标签页上下文不一致。
2. 系统内页签可以统一处理账套切换、权限守卫和标签清理。
3. 更接近传统财务软件的“多功能窗口”体验。
4. 用户仍可以通过浏览器自身的右键“在新标签页打开”处理少量特殊场景，但系统默认不主动分散到浏览器标签。

### 目标视觉结构

第一阶段目标视觉如下：

```text
┌─────────────────────────────────────────────┐
│ 顶部系统栏：系统名称 / 当前账套 / 用户       │
├──────────────┬──────────────────────────────┤
│ 左侧模块菜单 │ 页签栏：首页 | 账套管理 | ... │
│              ├──────────────────────────────┤
│              │ 当前页面容器                  │
│              │                              │
└──────────────┴──────────────────────────────┘
```

标签页视觉规则：

1. 当前激活标签使用蓝色或主色边框/背景。
2. 非激活标签使用浅色背景。
3. 首页固定在第一个，不允许关闭。
4. 业务页面标签允许关闭。
5. 标签标题显示业务名称，不直接显示 URL。
6. 标签过多时允许横向滚动或由 Ant Design Tabs 自动收纳。

## Proposed Changes

### Change 1：新增轻量顶部路由页签组件

新增文件：

- `frontend/src/components/RouteTabs.tsx`

功能：

1. 根据当前 `location.pathname + location.search` 自动生成标签。
2. 标签显示页面标题。
3. 点击标签时调用 `navigate(tab.path)` 切换页面。
4. 关闭标签时移除标签。
5. 当前标签关闭后自动跳转到相邻标签。
6. 固定首页 `/workspace`，不可关闭。
7. 登录、注册、onboarding 等公开流程不进入标签。
8. 使用 Ant Design `Tabs`，不新增第三方依赖。

为什么：

- 用户希望点击页面后不是完全“跳丢”，而是在顶部留下一个可返回的业务标签。
- 组件放在 Shell 层，可以一次覆盖主要业务页面，不需要逐页改造。

### Change 2：在 MainShell 内容区顶部接入 RouteTabs

修改文件：

- [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx)

现有内容区：

```tsx
<Content>
  <Outlet />
</Content>
```

计划调整为：

```tsx
<RouteTabs />
<Content>
  <Outlet />
</Content>
```

显示层级：

```text
Header
Sider + Main Area
  ├─ RouteTabs 顶部页签栏
  └─ Content 当前页面容器
```

为什么：

- 改动集中在 Shell 层，不侵入业务页面。
- 左侧菜单仍然负责功能导航。
- 页面内容仍由原路由控制，风险较低。

### Change 3：建立路由标题映射

新增或内置在 `RouteTabs.tsx`：

```ts
const ROUTE_TITLE_MAP = [
  { pattern: /^\/workspace$/, title: '首页' },
  { pattern: /^\/ledger\/workspace$/, title: '财务工作台' },
  { pattern: /^\/ledger\/files$/, title: '支持性文件' },
  { pattern: /^\/ledger\/entries$/, title: '凭证查询' },
  { pattern: /^\/ledger\/books$/, title: '账簿管理' },
  { pattern: /^\/ledger-management$/, title: '账套管理' },
  { pattern: /^\/projects$/, title: '项目管理' },
  { pattern: /^\/audit\/workpapers$/, title: '审计工作底稿' },
  { pattern: /^\/audit\/tasks$/, title: '审计任务' },
  { pattern: /^\/audit\/review-requests$/, title: '复核请求' },
]
```

动态路径处理：

- `/audit/tasks/:taskId` → `审计任务详情`
- `/audit/review-requests/:reviewId` → `复核请求详情`
- `/ledger/vouchers/draft/:jobId` → `凭证草稿`
- `/registers/:moduleKey` → 根据 moduleKey 显示合同台账、发票台账、银行资金台账等。

为什么：

- 用户截图中的标签应显示“账套管理”“移交申请”这类业务名称。
- 不能直接把 URL 当作标签名。

### Change 4：标签 key 规则

规则：

1. 普通列表页按 pathname 合并。
   - `/ledger/entries?page=1` 和 `/ledger/entries?page=2` 视为同一标签。

2. 详情页、草稿页、复核页保留关键 ID。
   - `/audit/tasks/123`
   - `/audit/tasks/456`
   - 应该是两个不同标签。

3. 凭证流程带 jobId 的页面保留 search。
   - `/ledger/vouchers/step/3?jobId=100`
   - `/ledger/vouchers/step/3?jobId=101`
   - 应视为不同业务上下文。

为什么：

- 防止不同任务、不同草稿、不同复核请求混成一个标签。
- 同时避免普通查询页面打开过多重复标签。

### Change 5：账套切换时清理标签

涉及文件：

- [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx)
- [LedgerSelector.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/components/LedgerSelector.tsx)
- `frontend/src/components/RouteTabs.tsx`

第一阶段建议：

- 标签本身不缓存页面组件，因此账套切换后当前页面会按新账套重新加载。
- 但已打开标签的业务含义可能来自旧账套。
- 在 `RouteTabs` 中监听 `currentLedgerId`，当账套切换时：
  - 保留 `/workspace`；
  - 保留 `/team-management`、`/ledger-management`、`/projects` 等管理页；
  - 关闭账套数据页面标签，例如凭证、账簿、支持性文件、台账、审计底稿。

为什么：

- 财务系统最忌讳跨账套误操作。
- 即使不做 keep-alive，也应避免用户误以为某个标签仍属于原账套。

### Change 6：增加页签操作能力

第一阶段实现：

1. 点击标签：切换到该页面。
2. 关闭标签：关闭当前业务页。
3. 关闭当前激活标签后：自动跳转到左侧相邻标签；没有相邻标签则回到首页。
4. 首页不可关闭。

可选增强，如果实现成本可控：

1. 右键或下拉菜单：关闭当前。
2. 右键或下拉菜单：关闭其他。
3. 右键或下拉菜单：关闭全部业务页。
4. 刷新当前页。

第一阶段如需控制范围，可以先不做右键菜单，只做关闭按钮。

### Change 7：形成“小容器界面”样式

修改文件：

- [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx)
- `frontend/src/components/RouteTabs.tsx`

样式目标：

1. 页签栏紧贴内容区顶部。
2. 页签栏背景为浅灰或白色。
3. 当前页面内容区保留白色卡片容器。
4. 内容区不要占满到边缘，保留适度内边距。
5. 与截图类似，让用户知道“我打开了多个工作页面，现在正在其中一个页面内操作”。

### Change 8：暂不做真正 keep-alive

第一阶段不引入 keep-alive。

不做：

- 不缓存所有已打开页面组件。
- 不保留未提交表单状态。
- 不增加第三方 keep-alive 依赖。

后续如果用户确认需要“切换回来表单完全不丢”，再单独规划：

- 对凭证查询、审计任务、工作底稿等高频页面做局部缓存；
- 标签关闭时提示未保存内容；
- 缓存 key 包含 ledgerId、projectId、route。

为什么：

- 真正 keep-alive 会涉及账套安全、权限变化、表单未保存、内存占用等风险。
- 当前用户需求主要是“可见页签和容器导航”，轻量页签足够先解决。

## Implementation Steps

### Step 1：新增 RouteTabs 组件

文件：

- `frontend/src/components/RouteTabs.tsx`

实现内容：

- 使用 `useLocation`、`useNavigate`。
- 使用 Ant Design `Tabs`。
- 内部维护 `openTabs` 状态。
- 路由变化时添加当前标签。
- 支持关闭标签。
- 支持固定首页。
- 支持标题映射。

### Step 2：在 MainShell 接入 RouteTabs

文件：

- [MainShell.tsx](file:///e:/projects/finance-vector-audit/audit-platform-main/frontend/src/layout/MainShell.tsx)

实现内容：

- 引入 `RouteTabs`。
- 在 `Content` 上方渲染。
- 调整布局样式，形成“小容器界面”。

### Step 3：补充路由标题映射

文件：

- `frontend/src/components/RouteTabs.tsx`

实现内容：

- 覆盖主要菜单路径。
- 支持动态详情页。
- 支持模块台账标题。
- 对未知路径使用末级路径兜底。

### Step 4：处理账套切换

文件：

- `frontend/src/components/RouteTabs.tsx`

实现内容：

- 从 `useAuthStore` 读取 `currentLedgerId`。
- 监听账套变化。
- 清理需要账套上下文的标签。
- 保留首页和管理页。

### Step 5：构建验证

执行：

```powershell
pnpm.cmd build:frontend
```

验证：

- 前端构建通过。
- 打开多个菜单项后顶部显示标签。
- 点击标签可切换页面。
- 关闭当前标签后跳到相邻标签。
- 首页标签不能关闭。
- 账套切换后不会保留旧账套业务标签。

## Verification Steps

1. 打开 `http://127.0.0.1:5173/workspace`
   - 应显示固定“首页”标签。

2. 点击左侧菜单：
   - 支持性文件；
   - 账簿管理；
   - 凭证查询；
   - 账套管理；
   - 项目管理；
   - 审计工作底稿；
   - 复核请求。

   顶部应依次新增标签。

3. 点击顶部标签：
   - 页面应切换到对应路由。
   - 左侧菜单高亮应跟随当前 URL。

4. 关闭标签：
   - 当前标签关闭后跳到相邻标签。
   - 首页不能关闭。

5. 打开动态详情页：
   - 审计任务详情；
   - 复核请求详情；
   - 凭证草稿。

   标签标题应能区分详情页。

6. 切换账套：
   - 账套相关业务标签应被清理或重置。
   - 不应出现旧账套页面继续停留造成误解。

## 财务视角说明

从财务实务看，这个改造相当于给系统增加“工作窗口管理”。

- 左侧菜单：像财务软件的功能目录。
- 顶部页签：像已经打开的工作窗口。
- 当前内容区：像当前正在处理的一张凭证、一个台账、一份底稿或一个管理页面。

为什么账套切换要清理业务标签：

- 凭证、账簿、报表、台账、审计底稿都必须有明确账套归属。
- 如果切换账套后还保留旧账套标签，用户可能误以为当前页面仍属于旧账套，产生跨账套误操作风险。

## Risks

1. 账套切换后旧标签误导风险。
   - 通过清理账套相关标签降低风险。

2. 路由标题映射不完整。
   - 先覆盖高频页面，未知路径使用兜底标题。

3. 页面状态不缓存。
   - 第一阶段接受该限制；如用户后续要求，再规划 keep-alive。

4. 菜单 key 和路由 path 不一致。
   - RouteTabs 直接基于 location，而不是菜单 key。

## Recommended Acceptance Level

本计划属于 D03 导航体验增强，建议验收达到：

- L5 前端接入完成；
- L6 基础交互验证完成。

不要求后端变更。
