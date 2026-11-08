# 学生端任务流返回导航 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让孩子从任务全屏页能按来源返回（pop / returnTo），且任意任务顶栏一键回首页（房子图标 D1）。

**Architecture:** 新增 `returnTo` 查询参数 + `task_nav.dart` 工具；入口 `push` 建栈；`TaskPageAppBar` 统一 leading/actions；`ReaderViewPage` 自定义顶栏复用同一套 pop 逻辑。Spec：`docs/superpowers/specs/2026-11-08-student-nav-back-design.md`。

**Tech Stack:** Flutter 3.47+、`go_router`、`flutter_riverpod`、既有 `AppShell` / `homeController`。

---

## File map

| 文件 | 职责 |
|------|------|
| `lib/features/shell/task_nav.dart` | `parseReturnTo`、`popOrReturn`、`goHome` |
| `lib/features/shell/task_page_app_bar.dart` | 统一 AppBar（返回 + 首页图标 + 扩展 actions） |
| `lib/features/home/ui/home_page.dart` | 任务入口 `push` + `returnTo=/home` |
| `lib/features/center/ui/center_page.dart` | 阅读入口 `push` + `returnTo=/center` |
| `lib/features/reader/ui/reader_home_page.dart` | AppBar 替换；进 view 用 `push` 并继承 `returnTo` |
| `lib/features/reader/ui/reader_view_page.dart` | 顶栏返回改 pop；空状态按钮保持栈语义 |
| `lib/features/dictation|math|knowledge|assignment/ui/*_page.dart` | 换 `TaskPageAppBar` |
| `test/features/shell/task_nav_test.dart` | 纯函数测试 |
| `test/features/shell/task_nav_widget_test.dart` | AppBar 按钮行为 |
| `test/app_flow_test.dart`（可选扩展） | 首页 → 阅读 → 返回 / 首页 |

---

### Task 1: `task_nav` 工具与测试

**Files:**
- Create: `student-app/lib/features/shell/task_nav.dart`
- Create: `student-app/test/features/shell/task_nav_test.dart`

- [ ] **Step 1: Write failing tests**

```dart
// task_nav_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/shell/task_nav.dart';

void main() {
  test('parseReturnTo 缺省为 /home', () {
    expect(parseReturnTo(null), '/home');
    expect(parseReturnTo(''), '/home');
  });
  test('parseReturnTo 白名单', () {
    expect(parseReturnTo('/home'), '/home');
    expect(parseReturnTo('/center'), '/center');
    expect(parseReturnTo('/evil'), '/home');
  });
}
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd student-app && flutter test test/features/shell/task_nav_test.dart
```

- [ ] **Step 3: Implement**

```dart
// task_nav.dart
const _allowedReturnTo = {'/home', '/center'};

String parseReturnTo(String? raw) {
  if (raw == null || raw.isEmpty) return '/home';
  return _allowedReturnTo.contains(raw) ? raw : '/home';
}

/// 构建带 returnTo 的 path（保留已有 query）
String withReturnTo(String path, String returnTo) {
  final uri = Uri(path: path, queryParameters: {'returnTo': returnTo});
  return uri.toString();
}
```

`popOrReturn` / `goHome` 依赖 `BuildContext` + `go_router`，放在同文件：

```dart
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../home/home_controller.dart';

void popOrReturn(BuildContext context, {String? returnTo}) {
  if (context.canPop()) {
    context.pop();
    return;
  }
  context.go(parseReturnTo(returnTo));
}

void goHome(WidgetRef ref, BuildContext context) {
  context.go('/home');
  ref.read(homeControllerProvider.notifier).reload();
}
```

- [ ] **Step 4: Run test — PASS**

- [ ] **Step 5: Commit**

```bash
git add student-app/lib/features/shell/task_nav.dart student-app/test/features/shell/task_nav_test.dart
git commit -m "feat(student-app): task nav returnTo helpers"
```

---

### Task 2: `TaskPageAppBar`

**Files:**
- Create: `student-app/lib/features/shell/task_page_app_bar.dart`
- Create: `student-app/test/features/shell/task_page_app_bar_test.dart`

- [ ] **Step 1: Widget test（需包一层 ProviderScope + GoRouter）**

断言：`find.byTooltip('首页')` 存在；点返回在无栈时 `go` 到 `returnTo`（可用 `GoRouter` 测试 harness 记录 location）。

- [ ] **Step 2: Implement**

```dart
class TaskPageAppBar extends ConsumerWidget implements PreferredSizeWidget {
  const TaskPageAppBar({
    super.key,
    required this.title,
    this.returnTo,
    this.actions = const [],
    this.backgroundColor = AppColors.bg,
  });

  final Widget title; // 或 String title → Text
  final String? returnTo;
  final List<Widget> actions;
  final Color? backgroundColor;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final rt = parseReturnTo(returnTo ?? GoRouterState.of(context).uri.queryParameters['returnTo']);
    return AppBar(
      backgroundColor: backgroundColor,
      scrolledUnderElevation: 0,
      leading: BackButton(onPressed: () => popOrReturn(context, returnTo: rt)),
      title: title is String ? Text(title as String) : title as Widget,
      actions: [
        ...actions,
        IconButton(
          tooltip: '首页',
          icon: const Icon(Icons.home_outlined),
          onPressed: () => goHome(ref, context),
        ),
      ],
    );
  }

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
}
```

（实现时 `title` 用 `Object` 或两个命名构造，与现有 `Text(s.title)` 对齐。）

- [ ] **Step 3: `flutter test test/features/shell/task_page_app_bar_test.dart`**

- [ ] **Step 4: Commit** `feat(student-app): TaskPageAppBar with home action`

---

### Task 3: 首页任务入口 `push`

**Files:**
- Modify: `student-app/lib/features/home/ui/home_page.dart`

- [ ] **Step 1: 替换 `onTask` 与个性化卡**

| taskType | 现行为 | 新行为 |
|----------|--------|--------|
| `reading` | `go('/reader')` | `push(withReturnTo('/reader', '/home'))` |
| `listening` | `go('/center')` | **保持 `go('/center')`**（Shell Tab，非全屏栈） |
| `math_exercise` / `math` | `go('/math')` | `push(withReturnTo('/math', '/home'))` |
| `knowledge` | `go('/knowledge')` | `push(...)` |
| `dictation` | `go('/dictation')` | `push(...)` |

听写若 query 需带 `taskId`：在 `withReturnTo` 上合并现有 query（扩展 `task_nav`：`appendQuery`）。

- [ ] **Step 2: 手动** `flutter run -d chrome`：首页点阅读 → 浏览器后退应回到 `/home`。

- [ ] **Step 3: Commit** `feat(student-app): push tasks from home with returnTo`

---

### Task 4: 学习中心阅读入口

**Files:**
- Modify: `student-app/lib/features/center/ui/center_page.dart`

- [ ] **Step 1:** `context.go('/reader')` → `context.push(withReturnTo('/reader', '/center'))`

- [ ] **Step 2: Commit**

---

### Task 5: 阅读目录与正文

**Files:**
- Modify: `student-app/lib/features/reader/ui/reader_home_page.dart`
- Modify: `student-app/lib/features/reader/ui/reader_view_page.dart`

- [ ] **Step 1:** `ReaderHomePage` 使用 `TaskPageAppBar(title: '个性化学习')`；从 `GoRouterState` 读 `returnTo`。

- [ ] **Step 2:** 进入课文：

```dart
final rt = GoRouterState.of(context).uri.queryParameters['returnTo'];
context.push(withReturnTo('/reader/view', parseReturnTo(rt)));
// 若需 lesson：Uri(path: '/reader/view', queryParameters: {'lesson': '$id', 'returnTo': rt})
```

- [ ] **Step 3:** `ReaderViewPage` 顶栏 `IconButton` back → `popOrReturn`；**删除** `go('/reader')` 作为默认返回（空状态「去选择教材」可 `pop` 或 `push` 到 `/reader` 保持体验，按 spec 优先 pop）。

- [ ] **Step 4:** 整页可选包 `PopScope(canPop: false, onPopInvokedWithResult: ...)` 与 `popOrReturn` 一致（Android）。

- [ ] **Step 5: Commit**

---

### Task 6: 听写 / 数学 / 知识 / 作业

**Files:**
- Modify: `student-app/lib/features/dictation/ui/dictation_page.dart` 及子视图 AppBar（若重复，只改最外层 `DictationPage`）
- Modify: `student-app/lib/features/math_exercise/ui/math_page.dart`
- Modify: `student-app/lib/features/knowledge_review/ui/knowledge_page.dart`
- Modify: `student-app/lib/features/assignment/ui/assignment_page.dart`

- [ ] **Step 1:** 将 `AppBar(...)` 换为 `TaskPageAppBar(title: ..., returnTo: GoRouterState.of(context).uri.queryParameters['returnTo'])`。

- [ ] **Step 2:** `flutter analyze && flutter test`

- [ ] **Step 3: Commit**

---

### Task 7: 集成测试与文档

**Files:**
- Modify: `student-app/test/app_flow_test.dart`（可选，时间紧可仅 widget 测）
- Modify: `student-app/README.md`（一句：任务页 `returnTo` + 首页图标）

- [ ] **Step 1:** 在 `app_flow_test` 登录后进首页，点阅读相关入口（需 mock 与 find 对齐 UI），`tester.pageBack` 或点 `BackButton`，expect router 在 `/home`。

- [ ] **Step 2:**

```bash
cd student-app && flutter analyze && flutter test
```

- [ ] **Step 3: Commit** `test(student-app): navigation back from reader`

---

## Verification checklist（发布前）

- [ ] Web：首页 → 阅读目录 → 课文 → 后退 ×2 → 首页
- [ ] Web：阅读页点房子 → 首页任务列表刷新
- [ ] 学习中心 → 个性化阅读 → 返回 → `/center`
- [ ] Android：系统返回键与顶栏返回一致
- [ ] 直接打开 `/reader/view?lesson=1` → 返回 → `/home`

## Out of scope（本计划不做）

- `/reader/spike` 开发页
- 听力 Tab 内 UI（仍 `go('/center')`）
- 提交 spec/plan 之外的 `config.dart` APK 地址改动（未提交工作区单独处理）
