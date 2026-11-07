# Flutter 个性化学习：PDF 页内划选（对齐 Web）

> 日期：2026-11-07  
> 状态：已与用户确认设计（第 1、2 节）  
> 范围：子项目 4「个性化学习」— 沉浸阅读 `/reader/view`

## 背景与目标

旧 Web 学生端（`frontend/app.js`）用 **pdf.js** 在教材 PDF 上渲染文字层，孩子**在页面上拖选** → 浮动气泡（划线 / 下划线 / 笔记 / 生词 / 追问）→ 墨迹按 `page_number` + `rects` 叠回页面。

Flutter 学生端当前用 **预渲染 PNG + 下方提取课文 `SelectableText`**，无法在「看到的正文」上划选，体验与 Web 脱节，也不符合「Flutter 接替冻结 `frontend/`」的路线。

**产品决策（已确认）**

| 决策 | 结论 |
|------|------|
| 端覆盖 | **Web + Android** 均须在 PDF 页面上划选（选项 B） |
| 体验对标 | 以 Web 沉浸阅读为北极星；扫描版无文字层时与 Web 相同兜底策略 |
| 技术主线 | **pdfrx**（PDFium，单一代码路径），不用 Web 嵌 pdf.js 双栈 |

## 现状与差距

| 维度 | Web | Flutter（当前） |
|------|-----|----------------|
| 渲染 | pdf.js + TextLayer | PNG `Image.network` |
| 划选 | `window.getSelection` on `.pdf-text-layer` | 仅 `texts` 课文块（且在页图下方） |
| 气泡 | `#reader-popover` 色板 + 标注 + 追问 chip | 选中后顶部 TextButton，无浮动气泡 |
| 落库 | `quote`, `kind`, `color`, `page_number`, `rects` | 仅 `quote`, `kind` |
| 回看 | `renderAnnotationHighlights` 页上墨迹 | 「我的笔记」列表，页上无墨迹 |
| PDF 源 | `GET` 列表项 `storage_path` → `${API}/${storage_path}` | `PdfDoc` 未解析 `storage_path` |

后端已具备：`PdfDocument.storage_path`、静态 `/uploads` 挂载、`annotations` 全字段（见 `backend/app/routers/annotations.py`）。**无需改表**；Flutter 数据层与 UI 需补齐。

## 方案对比（纪要）

1. **pdfrx（选用）** — 单 Widget，`PdfViewer` + `PdfTextSelectionParams`，双端同构。  
2. **Web pdf.js + Android pdfrx** — Web 1:1 但双倍维护成本，否决。  
3. **Syncfusion 等商业控件** — 许可与依赖策略不符，否决。

**扫描 / 无文字层**：pdfrx 无法选字时，显示说明 + 可选 PNG 只读对照（与 Web「pdf.js 未加载 → PNG」一致）；OCR 页上文字层另开 spec。

---

## 第 1 节：阅读器与划选（已确认）

### 目标行为

- 沉浸页**主区域**展示本课 PDF（`start_page`…`end_page`），不再依赖下方「课文区」作为主交互面。
- 页内拖选 → **选区气泡** → 标注 / 生词 / 追问。
- 标注携带 **`page_number`（PDF 绝对页码，与 Web `.pdf-page` 的 `dataset.page` 一致，落在 `lesson.start_page`…`end_page` 范围内）**、**`rects`（归一化坐标 JSON 字符串）**、**`color`**。
- 加载标注后在对应页 **overlay** 重绘墨迹。

### 数据流

```
loadDocuments / loadLessons / prepareView（savedDocId）
  → GET /api/pdf/documents[].storage_path（lessons 接口不含 path）
  → ReaderState：currentDocumentId + storagePath（由文档列表解析）
  → PdfViewer.networkUrl(resolveApiAssetUrl(storage_path))
  → 初始滚动/渲染 page range [start_page, end_page]
onTextSelectionChange (pdfrx)
  → quote, PDF 绝对 page_number, rects (selection_geometry)
  → show ReaderSelectionBar
POST /api/annotations | /api/annotations/glossary
  → loadAnnotations → overlay repaint
setSelected(quote) → Ask 侧栏
```

### API / 模型（Flutter）

- `PdfDoc.fromJson` 增加 `storage_path`。
- `AnnotationItem` 增加 `color`, `page_number`, `rects`（字符串 JSON）。
- `POST /api/annotations`：`lesson_id`, `kind`, `quote`, `note`, **`color`**（默认 `yellow`）, **`page_number`**, **`rects`（JSON 字符串，非数组）**, `user_id?`。
- `POST /api/annotations/glossary`：`quote`, `page_number`, `rects`；`color` 由后端固定 `green`。

### 组件边界

| 模块 | 职责 |
|------|------|
| `pdf_lesson_reader.dart` | pdfrx 容器、页范围、标注 overlay、无文字层兜底 |
| `selection_geometry.dart` | pdfrx `getSelectedTextRanges()` 页内 bounds ÷ 页宽高 → 归一化 rects（行合并、clamp 0~1，对齐 Web `normaliseRects` 语义，非 DOM `getClientRects`） |
| `reader_selection_bar.dart` | 气泡 UI、作业锁对话时隐藏追问行 |
| `reader_view_page.dart` | 布局壳：顶栏、分栏拖拽、组合 reader + 侧栏 |
| `reader_controller.dart` | 打开 PDF、刷新标注、调 repository |

**移除 / 降级**：主路径不再展示大块 `SelectableText`；仅在无 `storage_path` 或无文字层兜底时保留简化课文提示。

### 错误处理与兜底（分列）

| 场景 | 行为 |
|------|------|
| **(A) 无 `storage_path`** | 提示「教材 PDF 不可用」→ 教材列表；不可用课节划选 |
| **(B) PDF 下载/解析失败** | 重试 + 顶栏错误条；不白屏 |
| **(C) PDF 有、无文字层**（扫描版） | 说明文案 + 可选 **PNG 只读**对照；**仍不可页上划选**（对齐 Web 无 text layer） |
| 标注 API 失败 | toast；保留选区直至用户取消 |
| JWT 过期 | 沿用 `api_client` |

墨迹绘制：**有 `rects` 用 overlay**；**空 `rects` 时按 `quote` 在页内文字回退定位**（对齐 Web `renderAnnotationHighlights`），避免 Web 存量标注在 Flutter 不可见。

---

## 第 2 节：选区气泡与分期（已确认）

### 一期（MVP）

**气泡 `ReaderSelectionBar`**

- pdfrx：`showContextMenuAutomatically: false`（或等价），避免与系统选区菜单双气泡。
- 松手选区后显示；锚点由选区 bounds + 当前缩放/滚动映射；点空白关闭；翻页关闭。
- 第一行：五色板（`yellow|green|blue|pink|purple`）+ 划线 + 下划线 + 笔记 + 生词。
- 第二行（`!chatDisabled`）：追问、解释、翻译（后两者为预置 prompt 走现有 Ask SSE，无新接口）。
- 笔记：内联输入 → `kind=note` + `note`。

**墨迹**

- 高亮 / 下划线 / 生词色区分；解析 `rects` 为 `[[x0,y0,x1,y1],...]` 画在页 overlay。
- 页底可保留折叠「我的标注」列表（简版）。

**侧栏**

- 选中即 `askController.setSelected(quote)`，展开对话区。

### 二期

- `readMode=book` 整本懒加载。
- 气泡动效、移动端放大镜。
- Ask 出处 ↔ PDF 页跳转（依赖锚点，无后端数据则不做）。

### 明确不做（本 spec）

- 不改 `frontend/`、不改拆课流水线。
- 扫描 OCR 文字层（独立 spec）。
- Syncfusion 除非 pdfrx 双端验收不通过再议。

---

## 第 3 节：依赖与平台

- 新增依赖：`pdfrx`（版本在实现时锁定；Web 注意 WASM 体积与 `--no-web-resources-cdn` 共存）。
- **Web**：Chrome 验收为主；记录 pdfrx Web 选区 known issues（多栏行尾等），允许 ±2px 墨迹漂移。
- **Android**：`flutter build apk` + 模拟器/真机同一流程验收。
- CORS / 鉴权：PDF URL 与现有 `/uploads` 静态资源一致；若需 Bearer，实现时确认静态路由是否仅 JWT 路由保护（今日 PDF 与页图同路径策略）。

### pdfrx spike 退出标准（实现第 2 步前）

在 Chrome Web **与** Android 各跑通：

1. 中文教材样 PDF 可选字（含常见 CJK 内嵌字体样张，若有）。
2. 课节仅展示/跳转 `[start_page, end_page]` 页窗。
3. 选区回调能给出页码 + 可用于归一化的 bounds。
4. Web 记录 WASM/首包体积是否可接受；构建仍可用 `--no-web-resources-cdn`。

不通过则暂停主线，评估 Syncfusion 或缩小范围（仅 Android 原生等）再开评审。

---

## 第 4 节：测试

| 层级 | 内容 |
|------|------|
| 单元 | `selection_geometry`：空选区、单行、多行、越界 clamp 0~1 |
| Widget | 气泡在 `chatDisabled` 时隐藏追问行；无选区不显示气泡 |
| 集成 | 有 `storage_path` 的 fixture lesson：mock API 创建带 rects 的 annotation，overlay 解析不抛错 |
| 手工 | 验收标准见下 |

### 验收标准（B：Web + Android）

1. 有 `storage_path` 的课：页上拖选 ≥2 字 → 气泡出现。  
2. 划线后刷新：墨迹在同页近似位置重现。  
3. 追问：选区进入 Ask，分句 `sentences` 仍来自 `texts`。  
4. Chrome Web + Android 完成 1–3。  
5. 无文字层：兜底文案 + 不崩溃。

---

## 第 5 节：实现顺序（供 writing-plans 展开）

1. `pdf_repository` + `PdfDoc.storage_path` + annotation 全字段。  
2. Spike：`pdf_lesson_reader` 单页加载 + 选区回调（Web + Android 各测一次）。  
3. `selection_geometry` + 创建标注带 rects。  
4. `ReaderSelectionBar` + `reader_view_page` 重组。  
5. Annotation overlay 绘制 + 加载刷新。  
6. 扫描兜底与空 `storage_path` UX。  
7. 测试 + 手工验收清单。

---

## 关联文档

- `docs/superpowers/specs/2026-11-01-student-app-foundation-design.md`（Flutter 接替 frontend）  
- `docs/superpowers/specs/2026-10-27-read-and-ask-design.md`（边读边问 / Ask）  
- `AGENTS.md` 沉浸阅读与 annotations 字段说明
