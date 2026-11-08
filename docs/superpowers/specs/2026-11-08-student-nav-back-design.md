# 学生端任务流返回导航 — 设计说明

**日期**：2026-11-08  
**范围**：Flutter `student-app/`（Web + Android）  
**状态**：待评审

## 背景与问题

- 首页/学习中心通过 `context.go()` 进入阅读、听写、数学等 **Shell 外全屏路由**，不形成导航栈。
- Web 浏览器后退、Android 系统返回无效或行为混乱。
- 阅读正文顶栏「返回」仅 `go('/reader')`，**无法回到首页打卡任务**。
- 用户期望：**B** — 返回到进入任务前的上一屏；并 **始终保持一键回首页** 的能力。

## 目标

| 目标 | 说明 |
|------|------|
| 上下文返回 | 从首页进 → 逐级返回首页；从学习中心进 → 返回学习中心 |
| 回首页 | 任意任务顶栏 **右侧房子图标**（D1），直达 `/home` |
| Web/Android | 依赖 `push`/`pop` 支持浏览器后退与系统返回键 |
| 深链/刷新 | `canPop == false` 时用 `returnTo` 查询参数兜底 |

## 非目标

- 任务页内嵌底部四 Tab Shell。
- 改造登录/注册等已有返回逻辑的公开页。
- 家长端 / 旧 `frontend/`。

## 路由策略

### 入口：由 `go` 改为 `push`

从 `home_page`、`center_page`（及今后同类入口）进入任务时：

```dart
context.push('/reader?returnTo=/home');   // 示例：首页
context.push('/reader?returnTo=/center'); // 示例：学习中心
```

听写、数学、基础知识、本课作业等顶层任务路由同理，携带对应 `returnTo`。

### 栈内导航

- 阅读：`/reader` → `push` → `/reader/view?lesson=…&returnTo=…`（`returnTo` 沿链传递或从上一级 query 继承）。
- 顶栏 **leading**：`if (context.canPop) context.pop(); else context.go(returnTo ?? '/home');`
- **Android**：任务根 `Scaffold` 使用 `PopScope`，`onPopInvoked` 与 leading 相同逻辑。

### 一键首页（D1）

- 任务顶栏 **actions**：`IconButton(icon: Icons.home_outlined, tooltip: '首页', onPressed: () => context.go('/home'))`
- 使用 `go` 清栈回到 Shell 首页分支，避免留在任务栈中间态。
- 若从 `/center` 离开需保持现有 `centerController.leave()` 等行为：在 `AppShell` 切换或 `go('/home')` 时由现有 Shell 监听处理；从任务页直接 `go('/home')` 不经过 Shell tab 切换时，需 **invalidate/reload home**（与切 Tab 到首页一致，可调用既有 `homeController.reload()` 或在 `go` 后首页 `onEnter`）。

### `returnTo` 约定

| 值 | 含义 |
|----|------|
| `/home` | 默认；首页任务入口 |
| `/center` | 学习中心个性化入口 |
| 缺省 | 视为 `/home` |

允许路径白名单：`/home`、`/center`（防开放重定向）；其它值回退 `/home`。

### 阅读正文现有行为变更

- `ReaderViewPage` 自定义顶栏 leading：由 `context.go('/reader')` 改为 **`pop` 优先**。
- 无课时的空状态：保留「去选择教材」，用 `push` 或 `pop` 与上一致，不破坏栈。

## UI 组件

### `TaskPageAppBar`（新建，建议路径 `lib/features/shell/task_page_app_bar.dart`）

参数：

- `title` / `titleWidget`
- `returnTo`：从 `GoRouterState.uri.queryParameters['returnTo']` 解析
- `backgroundColor`、`actions` 扩展（阅读页额外按钮接在 home 左侧）

行为：

- `automaticallyImplyLeading: true` 或自定义 leading 调用统一 `_popOrReturn(context, returnTo)`
- 固定 trailing：`home` 图标（D1），再拼接页面自定义 `actions`

不在 Shell 内的页面逐步替换零散 `AppBar`；**首批**：`reader_home_page`、`reader_view_page`（顶栏 Row）、`dictation_page`、`math_page`、`knowledge_page`、`assignment_page`（及听写子视图若独立 AppBar）。

## 数据流与副作用

- **无后端变更**。
- 进入学习中心听力仍走 Tab `/center`，不在此 spec；仅 **从 center 跳进阅读等全屏任务** 时带 `returnTo=/center`。
- `go('/home')` 后首页任务列表应刷新：复用 `homeController.reload()`（与 Shell 切 Tab 到首页相同）。

## 错误与边界

| 场景 | 行为 |
|------|------|
| 直接打开 `/reader/view?lesson=1` | 无栈；返回 → `go(returnTo ?? '/home')` |
| Web 刷新后栈丢失 | 同上 |
| `returnTo` 非法 | `go('/home')` |
| 阅读 spike `/reader/spike` | 开发页，同样挂 Task 顶栏或标注不在首批 |

## 测试

1. **单元/组件**：`returnTo` 解析与白名单；`_popOrReturn` 逻辑（`canPop` true/false）。
2. **Router 集成**（`app_flow_test` 或专用）：Home → push reader → push view → pop → pop 路径；home 图标 → 当前 location `/home`。
3. **手动**：Chrome 后退键；Android 返回键；从 center 进阅读再返回。

## 实现顺序（供 writing-plans 拆分）

1. `task_page_app_bar.dart` + `parseReturnTo` 工具
2. 改 `home_page` / `center_page` 入口为 `push` + query
3. 阅读链路 + `ReaderViewPage` leading
4. 听写/数学/知识/作业 AppBar 替换
5. 测试与 README 一句说明导航约定

## 决策记录

- **2026-11-08**：返回目标选 **B**（回到来源 Tab/页）+ 保留 **回首页**。
- **2026-11-08**：回首页入口选 **D1**（顶栏右侧房子图标）。
- **2026-11-08**：推荐 **push + pop** 为主，`returnTo` 兜底；不采用 Shell 内嵌任务页。
