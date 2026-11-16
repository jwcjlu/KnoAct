# 知识点库：原句提取 + 多级目录 + 标签 设计

日期：2026-11-15
状态：设计定稿，待实现
范围：在已落地的「知识点库 + 训练方案」之上，补三件事：① 解析讲义时提取「原句」；② 知识点用「多级目录 + 标签」组织；③ 上传讲义自动建目录并归类，家长可手动调整。

## 背景与问题

知识点库（`KnowledgePointPool`）已能上传讲义 PDF → OCR 提取知识点，但目前：

1. **丢原句**：`extract_items_from_pages` 只返回 `primary`（原文）/`secondary`（释义）/`source_page`，讲义里的**原句/例句**没提取，家长核对时看不到知识点出处。
2. **扁平无结构**：知识点只有 `category` 一个扁平字段，无法按「单元/专题」组织，几十上百个知识点堆在一个列表里难找。
3. **不能归类**：上传后知识点直接进扁平列表，家长无法建目录、移动归类。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 原句来源 | **解析时提取**：OCR 时让模型额外返回 `example`（知识点所在的原句原文，非现造），存进 `extra` |
| 原句存储 | `extra` JSON 加 `原句` 键，不另开列 |
| 目录结构 | **文件夹树 + 标签并存**：新建 `KnowledgeFolder`（`parent_id` 多级）；`KnowledgePointPool` 加 `tags` 数组 |
| 自动归类 | **一本讲义 = 一个目录**：上传后自动建目录（名=文件名/讲义名），提取出的知识点归进去 |
| 手动调整 | 家长可手动建目录、移动知识点（改 `folder_id`）、改标签 |
| 归属隔离 | 目录与知识点均按 `owner_id` 家长隔离 |
| 范围 | 仅家长端；孩子端只看发布后的专项训练，不受影响 |

## 成功标准

1. 上传《第6单元知识点归纳》→ 自动建目录「第6单元知识点归纳」，知识点归入，每条带**原句**（可在列表/编辑里看到）。
2. 家长可新建子目录、把知识点移动/归类、加标签。
3. 知识点库界面按目录树浏览 + 标签筛选。
4. 原句/目录/标签不影响已有「组合成方案 → 发布专项训练」链路。

---

## §1 数据模型

### 1.1 `KnowledgeFolder`（新表，目录）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK | |
| `owner_id` | FK `users.id` | 家长隔离 |
| `name` | `String(128)` | 目录名（如「第6单元」「look 短语家族」） |
| `parent_id` | FK `knowledge_folders.id`，nullable | 父目录；null=顶级目录 |
| `subject` | `String(16)` | 学科 |
| `created_at` | `DateTime` | |

> 多级 = `parent_id` 自引用。删除目录时子目录/知识点处理见 §5 风险。

### 1.2 `KnowledgePointPool` 加字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `folder_id` | FK `knowledge_folders.id`，nullable | 所属目录；null=未分类 |
| `tags` | `LongText`，默认 `"[]"` | JSON 数组，如 `["易错","重点"]` |

> `extra` 加 `原句` 键（`{"释义":"...","原句":"..."}`）。不另开 `原句` 列——它是可选的、随讲义而变，JSON 更灵活。

---

## §2 解析改动（`services/drill_rule.py`）

### 2.1 `_extract_one_batch` 提取原句

prompt 的返回格式从 `{"primary","secondary","source_page"}` 扩展为加 `example`：

```
'只返回 JSON：{"items":[{"primary":"原文","secondary":"释义/作者/解释","example":"知识点所在的原文句子","source_page":页码}]}。'
```

`example` 要求是**讲义中该知识点所在的原句原文**（不是模型自己编的例句）。`out.append` 里补 `"example": (it.get("example") or "").strip()`。

> 兼容：旧调用点（`drill.py` 的 `pdf_groups`）也走 `extract_items_from_pages`，它们拿到的 dict 会多一个 `example` 键，但 `drill.py` 建 `TrainingItem` 时只取 `primary`/`secondary`，不受影响。

### 2.2 `from-pdf`（`routers/knowledge_pool.py`）写原句 + 建目录

上传后：
1. 自动建目录：`KnowledgeFolder(owner_id=user.id, name=文件名去后缀, subject=subject, parent_id=None)`，`flush()` 拿到 `folder_id`。
2. 每条知识点写 `extra = {"释义": secondary, "原句": example}`，`folder_id` 指向新建目录。

---

## §3 目录 / 标签接口（扩展 `routers/knowledge_pool.py`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/knowledge-folders` | 返回家长目录树（嵌套 JSON，含每个目录的知识点数） |
| POST | `/api/knowledge-folders` | 新建目录（`name` + `parent_id` + `subject`） |
| PUT | `/api/knowledge-folders/{id}` | 重命名 / 移动（改 `parent_id`） |
| DELETE | `/api/knowledge-folders/{id}` | 删目录（子目录/知识点处理见 §5） |
| PUT | `/api/knowledge-pool/{id}/move` | 移动知识点到某目录（`folder_id`） |
| PUT | `/api/knowledge-pool/{id}/tags` | 设置知识点标签（`tags` 数组） |

> 目录树返回形如：
> ```json
> [{"id":1,"name":"第6单元","subject":"语文","parent_id":null,"point_count":12,
>   "children":[{"id":2,"name":"字词","parent_id":1,"point_count":5,"children":[]}]}]
> ```

---

## §4 前端（`parent-web/app.js`）

### 4.1 知识点库布局改为「目录树 + 知识点列表」

- 左侧（或顶部折叠）：目录树，点目录筛选该目录下的知识点（含子目录）。
- 标签：顶部标签筛选条（点标签过滤）。
- 「上传讲义 PDF」仍保留；上传后自动建目录并在树里出现。

### 4.2 表单扩展

- 手动新增/编辑表单加：**原句**（输入框，存 extra）、**目录**（下拉选目录，可留空=未分类）、**标签**（逗号分隔输入）。
- 知识点列表行显示原句（截断）。

### 4.3 目录管理

- 目录树旁「新建目录」「重命名」「删除」；知识点行「移动到…」选择目录。

---

## §5 风险 / 非目标

- **删目录**：有子目录/知识点时，删除前提示；实现选**软删或拒绝**（推荐：非空拒绝，强制家长先移走，避免误删）。本轮不自动级联删除知识点。
- **目录与训练方案解耦**：目录/标签只影响浏览组织，**不影响**「勾选知识点组合方案」——方案仍按 `point_ids` 直接勾选知识点，与目录无关。
- **原句与 SRS 掌握度解耦**：原句存在 `extra`，发布成 `TrainingItem` 时若需要可把 `原句` 存进 `example`（可选增强，本轮先不做，发布仍走现有 primary/secondary）。
- **AI 识别章节结构**：明确不做，一本讲义=一个目录。
- **孩子端**：无改动。

---

## §6 实现顺序建议

1. 模型：`KnowledgeFolder` + `KnowledgePointPool.folder_id/tags`（`models.py` + create_all 自动建表）
2. 解析：`_extract_one_batch` 加 `example`；`from-pdf` 建目录 + 写原句
3. 路由：目录 CRUD + 树 + 知识点 move/tags
4. 前端：目录树 + 标签筛选 + 表单扩展（原句/目录/标签）
5. 测试 + 手工验证（上传两本 PDF，看原句/目录/归类）
