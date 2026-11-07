# Flutter PDF 页内划选（对齐 Web）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Flutter 学生端 `/reader/view` 用 pdfrx 打开教材 PDF，在页面上划选并弹出与 Web 等价的标注/追问气泡，标注带 `page_number`/`rects`/`color` 并在页上回看墨迹。

**Architecture:** 阅读核心拆为 `pdf_lesson_reader`（pdfrx + overlay）、`selection_geometry`（纯函数 rects）、`reader_selection_bar`（气泡 UI）；`reader_controller` 维护 `storagePath` 与标注列表；`pdf_repository` 对齐后端 annotations 全字段。`reader_view_page` 只负责布局壳（顶栏、分栏、侧栏）。

**Tech Stack:** Flutter 3 / Dart 3.13、`pdfrx`（新增）、Riverpod 3、go_router、现有 `dio` + `resolveApiAssetUrl`。

**Spec:** `docs/superpowers/specs/2026-11-07-flutter-reader-pdf-selection-design.md`

**通用约定**

- 仓库 `D:\workspace\github\KnoAct`；Flutter：`E:\dev\flutter\bin\flutter.bat`；在 `student-app/` 执行 `flutter test` / `flutter analyze`。
- 后端：`cd backend && python -m uvicorn app.main:app --port 8010`（从 `backend/` 起，避免空库）。
- Web 手测：`flutter run -d web-server --web-port=60372 --web-hostname=127.0.0.1 --no-web-resources-cdn`。
- 每个 Task 结束可提交（用户未要求则不 push）。提交信息用英文或中文均可，聚焦 why。

---

## 文件结构（本计划创建/修改）

| 文件 | 职责 |
| --- | --- |
| `student-app/pubspec.yaml` | 增加 `pdfrx` 依赖 |
| `student-app/lib/features/reader/data/pdf_repository.dart` | `PdfDoc.storage_path`；`AnnotationItem` 全字段；`createAnnotation`/`glossary`/`addHighlight` 传 `page_number`/`rects`/`color` |
| `student-app/lib/features/reader/logic/selection_geometry.dart` | 像素矩形 → 归一化 `rects` JSON（对齐 Web `normaliseRects`） |
| `student-app/lib/features/reader/ui/pdf_lesson_reader.dart` | pdfrx 查看器、课节页窗、选区回调、标注 overlay、无文字层/无 path 兜底 |
| `student-app/lib/features/reader/ui/reader_selection_bar.dart` | 浮动气泡：色板、划线、下划线、笔记、生词、追问 chip |
| `student-app/lib/features/reader/ui/reader_view_page.dart` | 用 `PdfLessonReader` 替换 PNG+课文主路径；接线气泡与侧栏 |
| `student-app/lib/features/reader/reader_controller.dart` | `storagePath` 解析；`openLesson`/`prepareView` 保证文档路径；标注刷新 |
| `student-app/test/features/reader/selection_geometry_test.dart` | rects 纯函数单测 |
| `student-app/test/features/reader/pdf_repository_test.dart` | 模型 JSON 解析单测（可选 fake client） |

参考只读：`frontend/app.js`（`normaliseRects`、`showPopover`、`renderAnnotationHighlights`、`mountPdfReader`）。

---

### Task 0: pdfrx spike（门禁）

**通过前不合并 Task 3+ 的大改。**

**Files:**
- Create: `student-app/lib/features/reader/ui/pdf_reader_spike_page.dart`（临时，验收后可删或 `@visibleForTesting`）
- Modify: `student-app/pubspec.yaml`

- [ ] **Step 1: 添加依赖**

```powershell
cd D:\workspace\github\KnoAct\student-app
E:\dev\flutter\bin\flutter.bat pub add pdfrx
```

- [ ] **Step 2: 最小 spike 页**

用真实账号登录后，从 `GET /api/pdf/documents` 取第一本有 `storage_path` 的 PDF URL，`PdfViewer.uri` 打开，启用 `PdfTextSelectionParams(onTextSelectionChange: …)`，`debugPrint` 选中文本与页码。

路由可临时挂 `/reader/spike` 或 `main.dart` 开关，**不要**改生产 `/reader/view`。

- [ ] **Step 3: Web 验证**

Run web-server 60372，Chrome 打开，拖选中文 ≥2 字。

Expected: 控制台有 quote；无崩溃；WASM 加载成功（记录首屏耗时）。

- [ ] **Step 4: Android 验证（可选但 spec 要求）**

`flutter run` 真机/模拟器，同样拖选。

- [ ] **Step 5: 记录 spike 结论**

在 spec 同目录或 PR 描述写：CJK 样张是否可选字、页窗是否可行、是否继续 pdfrx。

若失败：停止本计划，回报用户走 Syncfusion 或缩小范围。

---

### Task 1: 数据层对齐后端

**Files:**
- Modify: `student-app/lib/features/reader/data/pdf_repository.dart`
- Test: `student-app/test/features/reader/pdf_repository_models_test.dart`

- [ ] **Step 1: 写失败测试 — `PdfDoc` 解析 `storage_path`**

```dart
test('PdfDoc parses storage_path', () {
  final d = PdfDoc.fromJson({
    'id': 1,
    'filename': 'a.pdf',
    'subject': '语文',
    'lesson_count': 3,
    'storage_path': 'uploads/1_a.pdf',
  });
  expect(d.storagePath, 'uploads/1_a.pdf');
});
```

- [ ] **Step 2: 跑测试 — 应 FAIL**

Run: `E:\dev\flutter\bin\flutter.bat test test/features/reader/pdf_repository_models_test.dart`

- [ ] **Step 3: 实现 `PdfDoc.storagePath`；`AnnotationItem` 增加 `color`, `pageNumber`, `rects`**

`createAnnotation` body 示例：

```dart
await _api.post('/api/annotations', body: {
  'lesson_id': lessonId,
  'kind': kind,
  'quote': quote,
  'note': note,
  'color': color,
  'page_number': pageNumber,
  'rects': rects,
  if (userId != null) 'user_id': userId,
});
```

`glossary` 同样传 `page_number` / `rects`。

- [ ] **Step 4: 测试 PASS + analyze**

Run: `flutter test test/features/reader/pdf_repository_models_test.dart`  
Run: `flutter analyze`

---

### Task 2: `selection_geometry`（TDD）

**Files:**
- Create: `student-app/lib/features/reader/logic/selection_geometry.dart`
- Test: `student-app/test/features/reader/selection_geometry_test.dart`

- [ ] **Step 1: 从 Web 抄语义写测试**

用例至少包括：

1. 空输入 → `[]`
2. 单矩形 → 一条 `[x0,y0,x1,y1]`，值在 0~1
3. 同一行两个碎片 → 合并为一行（模拟 Web 行合并）
4. 超出页框 → clamp

接口建议：

```dart
List<List<double>> normaliseRects(
  List<Rect> clientRects,
  Size pageSize,
);
String encodeRects(List<List<double>> rects) => jsonEncode(rects);
```

`Rect` 可用 `dart:ui`；若 spike 用 pdfrx bounds，在调用侧先转成 `Rect` 列表。

- [ ] **Step 2: 实现并跑通测试**

参考 `frontend/app.js` 函数 `normaliseRects`（约 2218–2253 行）。

- [ ] **Step 3: Commit（可选）**

---

### Task 3: `reader_controller` — `storagePath`

**Files:**
- Modify: `student-app/lib/features/reader/reader_controller.dart`

- [ ] **Step 1: `ReaderState` 增加 `storagePath`（或可空）**

- [ ] **Step 2: `loadDocuments` 后缓存列表；`loadLessons(docId)` 时从列表取 `storagePath`**

`prepareView` 路径：若仅有 `savedDocId` + `lessonId`，先 `loadDocuments` 再 `loadLessons`。

- [ ] **Step 3: `openLesson` 不改变 path（属 document 级）**

- [ ] **Step 4: `addHighlight` / `addNote` / `glossary` 扩展参数** `pageNumber`, `rects`, `color`

- [ ] **Step 5: `flutter analyze`**

---

### Task 4: `PdfLessonReader` 组件

**Files:**
- Create: `student-app/lib/features/reader/ui/pdf_lesson_reader.dart`

- [ ] **Step 1: 构造参数**

```dart
PdfLessonReader({
  required String pdfUrl,
  required int startPage,
  required int endPage,
  required List<AnnotationItem> annotations,
  required void Function(ReaderSelection selection) onSelection,
  required ValueChanged<String?> onLoadError,
});
```

`ReaderSelection` 数据类：`quote`, `pageNumber`, `rectsJson`, `anchor`（用于气泡 `Offset`/`Rect`）。

- [ ] **Step 2: pdfrx 集成**

- `PdfViewerParams.textSelectionParams`: `enabled: true`, `onTextSelectionChange`
- 禁用/覆盖系统 context menu（`buildContextMenu` 返回空或自定义）
- 初始定位 `startPage`（`PdfViewerController.goToPage` 或等价 API，以 spike 为准）

- [ ] **Step 3: 标注 overlay**

`CustomPaint` 或 `Positioned` 子层：解析 `annotation.rects`；空 rects 时 **按 quote 跳过或调用简单 text-search 回退**（一期可先仅 rects + 列表，quote 回退在 Task 6 补全）。

- [ ] **Step 4: 兜底 UI**

- `pdfUrl` 空 → `SizedBox` + 文案
- onLoadError → `ErrorCard`

---

### Task 5: `ReaderSelectionBar`

**Files:**
- Create: `student-app/lib/features/reader/ui/reader_selection_bar.dart`

- [ ] **Step 1: UI 布局对齐 Web 两行**

色板：`yellow|green|blue|pink|purple`；默认 `_annotColor = yellow`。

- [ ] **Step 2: 回调** `onHighlight`, `onUnderline`, `onNote`, `onGlossary`, `onAsk`, `onExplain`, `onTranslate`, `chatDisabled`

- [ ] **Step 3: 笔记展开** — 内联 `TextField` + 保存

- [ ] **Step 4: 在 `reader_view_page` 用 `Stack` + `Positioned` 锚定**（根据 `ReaderSelection.anchor` 与 `LayoutBuilder` 夹取边距）

---

### Task 6: 组装 `reader_view_page`

**Files:**
- Modify: `student-app/lib/features/reader/ui/reader_view_page.dart`
- Modify: `student-app/lib/features/ask/ask_controller.dart`（若需 `askExplain(quote)` 等辅助）

- [ ] **Step 1: 删除主路径 PNG 列表 + 大块 `SelectableText`**

保留：侧栏、分栏拖拽、`prepareView`。

- [ ] **Step 2: 有 `storagePath` 时展示 `PdfLessonReader`**

URL: `resolveApiAssetUrl(storagePath)`。

- [ ] **Step 3: 选区 → 气泡 → controller / ask**

```dart
onSelection: (sel) {
  setState(() => _selection = sel);
  ref.read(askControllerProvider.notifier).setSelected(sel.quote);
  if (sel.quote.length >= 2) setState(() => _chatOpen = true);
};
```

标注：`readerController.create…(quote: sel.quote, pageNumber: sel.pageNumber, rects: sel.rectsJson, color: _color)`

- [ ] **Step 4: 无文字层 fallback**

pdfrx 无法选字时（`onSelection` 永不触发 + 文档加载成功）：页内横幅 + 可选只读 PNG（`lesson.pages`）**不**作为主划选面。

- [ ] **Step 5: 手工验收清单**（spec §4）

---

### Task 7: quote 回退墨迹（与 Web parity）

**Files:**
- Modify: `student-app/lib/features/reader/ui/pdf_lesson_reader.dart`

- [ ] **Step 1: 阅读 Web `renderAnnotationHighlights` 中无 rects 分支**

- [ ] **Step 2: 在 overlay 层对 `rects.isEmpty` 的 annotation，用页内文字搜索（pdfrx page text API）估矩形**

若 spike 证明 API 过重：文档记录「仅新标注有墨迹，旧 Web 标注仅列表」，需产品确认——默认仍应实现 quote 回退。

- [ ] **Step 3: 手测 Web 创建的划线在 Flutter 可见**

---

### Task 8: 测试与文档

**Files:**
- Test: 补齐 `selection_geometry` + models
- Modify: `AGENTS.md` 或 student-app README 一段「沉浸阅读」

- [ ] **Step 1: `flutter test` 全绿**

- [ ] **Step 2: `flutter analyze` 无 issue**

- [ ] **Step 3: 更新 `AGENTS.md` Key Files** 表增加 `pdf_lesson_reader.dart` / `selection_geometry.dart`

- [ ] **Step 4: 删除或隐藏 spike 路由**

---

## 手工验收脚本（B：Web + Android）

1. 账号 `金宇轩_9` / `ChangeMe123`（或任意 `parent_bound` 孩子）。
2. 选有 PDF 的教材 → 沉浸阅读。
3. 在**页图文字上**拖选 → 气泡 → 划线 → 刷新页面墨迹仍在。
4. 追问：选区进入 Ask 并可发送。
5. Android 重复 3–4。

---

## 风险登记

| 风险 | 缓解 |
| --- | --- |
| pdfrx Web 选区不齐 | Task 0 门禁；记录 known issue |
| 扫描版无文字 | PNG 只读 + 文案 |
| rects 与缩放漂移 | 归一化坐标 + 验收 ±2px |
| WASM 体积 | `--no-web-resources-cdn`；Docker 构建测体积 |
