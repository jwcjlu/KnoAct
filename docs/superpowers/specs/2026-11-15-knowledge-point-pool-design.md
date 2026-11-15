# 学习材料管理中心：知识点库 + 训练方案

日期：2026-11-15
状态：设计已定稿，待实现
范围：`backend/app`（新增 `KnowledgePointPool` / `TrainingPlan` 两张表、一个新 router、`TrainingItem` 加一个溯源字段、复用 `drill_rule` 解析）；`parent-web/app.js`（专项训练 Tab 内扩「知识点库」与「训练方案」两个子视图）。

## 背景与目标

家长手上有《第 6 单元知识点归纳》（7 页，`handout_kind=outline`）和《必备固定短语搭配》（10 页，`handout_kind=phrase`）这类讲义 PDF，希望**先把它们解析成可复用的知识点存起来**，之后**勾选组合**生成专项训练给孩子练，而不是每次上传都一次性、不可复用地产出一组 `TrainingItem`。

现有专项训练（`2026-11-11-teacher-handout-learning-design.md`）已落地「讲义 → OCR → 直接建 `TrainingGroup`/`TrainingItem`」的一条龙链路，中间**没有独立的知识点池层**，条目被组独占、不可跨组复用。本设计在其**上游补一层**「知识点库 + 训练方案」：

```
讲义 PDF（handout）
   → 上传（content_kind=handout，跳过自动拆课，复用现有）
   → OCR 提取（复用 drill_rule.extract_items_from_pages）
   → 写 KnowledgePointPool（可复用知识点池，本设计新增）
        ↓ 家长勾选组合
   TrainingPlan（可保存/编辑的训练方案，本设计新增）
        ↓ 发布
   TrainingGroup / TrainingItem（复用现有闯关 + SRS 掌握度）
```

## 已锁定决策

| 项 | 决定 |
|----|------|
| 存储对象 | **新建知识点库表 `KnowledgePointPool`**（不复用 `KnowledgePoint`，后者语义是「按课拆的课文知识点」） |
| 归属 | **按家长隔离**（`owner_id`），他人不可见 |
| 训练方案 | **新建方案表 `TrainingPlan`**，`point_ids` 存 JSON 数组（不做多对多关联表） |
| 发布成组 | 发布时把勾选知识点**物化**成 `TrainingItem`（复制字段值），并**加溯源字段** `point_pool_id` 指向源知识点（层次 1，便于溯源） |
| 发布幂等 | 同一方案重复「发布」**更新同一个** `TrainingGroup`，不新建重复组 |
| 复用 | 解析复用 `drill_rule.extract_items_from_pages`；闯关/掌握度复用现有 `TrainingItem`/`TrainingItemMastery` 全套，**零改动** |
| 面向对象 | **仅家长端**；孩子只看发布后生成的专项训练 |
| 入口 | 扩建现有「专项训练」Tab，不新建一级 Tab |
| 进每日任务 | **本阶段不做**（Phase 2 再议，见「非目标」） |

## 成功标准

1. 上传《知识点归纳》《固定短语》两本 PDF，能 OCR 提取出知识点并存进「知识点库」，家长可查看/编辑/增删。  
2. 家长在库中勾选若干知识点，保存成一个「训练方案」，可再编辑、再发布。  
3. 方案发布后生成一个 `TrainingGroup`，孩子能在专项训练里闯关，掌握度走现有 SRS。  
4. 同一方案重复发布会更新同一个组，不产生重复组。  
5. 知识点库、方案均按家长隔离，B 家长看不到 A 家长的内容。

---

## §1 数据模型（`backend/app/models.py`）

### 1.1 `KnowledgePointPool`（新表，知识点库）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK | |
| `owner_id` | FK `users.id` | 归属家长（隔离） |
| `subject` | `String(16)` | 语文/英语/数学 |
| `category` | `String(32)` | 短语/句型/语法/生字/古诗…（宽松分类，来自 `handout_kind` 或 OCR 归类） |
| `content` | `LongText` | 知识点主体（如 `look after`、`比喻的定义`） |
| `extra` | `LongText` | 释义/例句/音标/作者等，JSON 文本 |
| `source` | `String(16)` | `pdf` \| `manual` |
| `document_id` | FK `pdf_documents.id`，nullable | 来源 PDF（仅 `source=pdf`） |
| `created_at` | `DateTime` | |

> 与 `TrainingItem` 的映射（发布时物化）：`content → primary`，`extra` 里的释义/例句 → `secondary`/`example`，`category` → 辅助 `kind` 推断。`extra` 用 JSON 保留完整字段，避免为每种讲义形态开新列。

### 1.2 `TrainingPlan`（新表，训练方案）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | PK | |
| `owner_id` | FK `users.id` | 归属家长 |
| `subject` | `String(16)` | 学科 |
| `title` | `String(255)` | 方案名 |
| `point_ids` | `LongText` | JSON 数组，勾选的知识点 id（如 `[3,7,12]`） |
| `group_id` | FK `training_groups.id`，nullable | 发布后回填已生成/更新的组 id（幂等关键） |
| `status` | `String(16)` | `draft` \| `published` |
| `created_at` / `updated_at` | `DateTime` | |

> `group_id` 既是「发布幂等」的锚点（重复发布更新同一组），也让方案↔训练可追溯。方案未发布时 `group_id=null`、`status=draft`。

### 1.3 `TrainingItem` 扩展（加一个溯源字段，其余零改动）

| 字段 | 类型 | 说明 |
|------|------|------|
| `point_pool_id` | FK `knowledge_point_pool.id`，nullable | 溯源：本条由哪个池子知识点物化而来；手工录入的 `TrainingItem` 为 null |

> 内容字段（`primary`/`secondary`/`example`/`kind`）**照旧物化存储**，闯关/判分/掌握度全部读 `TrainingItem` 自身，**不读池子**。改池子不影响已发布训练；`point_pool_id` 仅作溯源与未来「改池子→提示受影响训练」的钩子。

---

## §2 后端接口（新增 `backend/app/routers/knowledge_pool.py`）

鉴权统一 `require_role("parent", "admin")`；`owner_id` 隔离（admin 可见全部，家长仅自己）。复用现有 `ensure_user_access` / `get_db`。

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/knowledge-pool/from-pdf` | 上传讲义 PDF（`subject` + `handout_kind`）→ OCR → 提取知识点 → 写 `KnowledgePointPool`（**不建训练**）。复用 `drill.pdf-groups` 的 OCR 逻辑，落点改为池子 |
| GET | `/api/knowledge-pool` | 列出家长知识点，按 `subject`/`category` 可选筛选 |
| POST | `/api/knowledge-pool` | 手动新增单条 |
| PUT | `/api/knowledge-pool/{id}` | 编辑单条（content/extra/category） |
| DELETE | `/api/knowledge-pool/{id}` | 删除单条（已被方案引用的点，删除时提示或一并从方案移除，见 §4 风险） |
| POST | `/api/plans` | 新建方案（`subject` + `title` + `point_ids`） |
| GET | `/api/plans` | 列出方案（含 `point_ids`、`group_id`、`status`） |
| GET | `/api/plans/{id}` | 方案详情（展开 `point_ids` 为知识点全文，供前端展示） |
| PUT | `/api/plans/{id}` | 编辑方案（改标题/加减 `point_ids`；若已发布，下次 `publish` 生效） |
| DELETE | `/api/plans/{id}` | 删方案（不动已生成的 `TrainingGroup`） |
| POST | `/api/plans/{id}/publish` | 发布 → 按 `point_ids` 物化 `TrainingItem`，新建或**更新** `group_id` 指向的 `TrainingGroup`，回填 `group_id`、`status=published` |

### 2.1 `POST /api/plans/{id}/publish`（核心，幂等）

```
1. 校验方案归属、point_ids 非空
2. 拉取 point_ids 对应的 KnowledgePointPool 行（过滤他人/不存在的点）
3. 若方案 group_id 已存在 → 更新该 TrainingGroup 的条目（删旧 TrainingItem，按当前 point_ids 重建）
   否则 → 新建 TrainingGroup(source=custom, kind 按 subject 推断)，audit_status=pending
4. 每条知识点物化成 TrainingItem(primary=content, secondary/example 取自 extra, point_pool_id=池子id)
5. 复用 drill_rule.generate_group_content / review_group_items 生成 intro/group_rule/ai_review
6. 回填方案 group_id、status=published，commit
7. 返回 {group_id, item_count}
```

> 更新已发布组时，`TrainingItemMastery` 的历史掌握度按 `item_id` 关联，条目重建会导致旧 `item_id` 失效、掌握度断层。**因此：更新组时保留「知识点未变」的条目（按 `point_pool_id` 匹配，命中则保留原 `TrainingItem` 及 mastery），只增删变化的条目。** 这样改方案加/减知识点不会误清空既有掌握度。（见 §4 风险）

---

## §3 家长端 UI（`parent-web/app.js`）

复用现有「专项训练」Tab 的状态机（`drillTab`），新增两个子视图：

### 3.1 知识点库（`drillTab='pool'`）

- 列表：subject/category 筛选 + 每条知识点（content + 释义/例句摘要）。
- 上传讲义 PDF：复用现有 `uploadDrillPdf` 的表单，改调 `/api/knowledge-pool/from-pdf`。
- 单条：手动新增、编辑（content/extra/category）、删除。
- 「勾选」列：checkbox 供下一步组合。

### 3.2 训练方案（`drillTab='plans'`）

- 列表：方案名 + 已选知识点数 + 状态（草稿/已发布）+ 关联组。
- 新建：从知识点库勾选（或在新方案编辑态里勾选）→ 命名 → 保存。
- 编辑：改标题、加减勾选的点。
- 「发布」：调 `publish`，成功后 toast「已生成/更新专项训练」，可在「专项训练」列表看到对应组。

### 3.3 现有「专项训练」列表

保持原样（展示 `TrainingGroup`）。发布产生的组 `audit_status=pending`，家长审过后孩子可见——与现有链路一致。

---

## §4 数据流

```
上传讲义 PDF
   → POST /api/knowledge-pool/from-pdf  (OCR → KnowledgePointPool)
   → 家长在「知识点库」查看/编辑/增删
   → 勾选 → POST /api/plans  (TrainingPlan, point_ids)
   → POST /api/plans/{id}/publish
   → 物化 TrainingItem(带 point_pool_id) + TrainingGroup(audit_status=pending)
   → 家长审组 → 布置 drill 任务 → 孩子闯关 → TrainingItemMastery(SRS)
```

---

## §5 非目标 / 风险

- **进每日任务（Phase 2）**：`TrainingPlan` 加「纳入每日任务」开关 + `_gen_plan_drill` 按 SRS 自动选题，本阶段**不做**（与用户已确认的「先只做解析管理」一致）。
- **引用不复制（层次 2，实时读池子）**：明确**不做**。内容仍物化到 `TrainingItem`，`point_pool_id` 仅溯源。
- **删知识点 vs 已引用**：删除被方案引用的知识点时，前端提示「该点已被 N 个方案引用」；后端删除时可选级联从方案 `point_ids` 移除（实现选：删除时检测并软提示，不强制级联，保持简单）。
- **发布更新 vs 掌握度断层**：见 §2.1——按 `point_pool_id` 匹配保留未变条目的 `TrainingItem` 及 mastery，只增删变化条目，避免改方案误清掌握度。
- **OCR 解析复用**：`from-pdf` 直接复用 `drill_rule.extract_items_from_pages` 的提取结果（`primary/secondary`），不改解析逻辑本身。
- **孩子端**：无改动。

---

## §6 实现顺序建议

1. 模型：`KnowledgePointPool` + `TrainingPlan` + `TrainingItem.point_pool_id`（`models.py` + 迁移）
2. 后端 router `knowledge_pool.py`：pool CRUD + `from-pdf`（复用 drill OCR）+ plans CRUD + `publish`（含按 `point_pool_id` 幂等更新）
3. pytest：池子隔离、from-pdf 写库不建训练、publish 幂等更新同组、改方案保留未变条目的 mastery
4. 前端：知识点库子视图 + 训练方案子视图 + 发布接线
5. 手工验证：上传两本 PDF → 库里见知识点 → 勾选组合 → 发布 → 专项训练列表见组 → 审组 → 孩子闯关
