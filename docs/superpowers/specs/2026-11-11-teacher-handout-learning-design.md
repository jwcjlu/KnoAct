# 专项训练（Drill Training）设计

日期：2026-11-12  
状态：已确认（brainstorming），由「讲义型资料自学」v5 泛化升级而来（专项训练 + SRS 真掌握 + 引导思考/发现规律 + 趣味性），待实现  
范围：家长布置**识记型专项训练**（固定短语 / 单元归纳 / 必背古诗 / 易错字等），孩子以**闯关四步**自学 + 间隔复习。内容来源第一批为**讲义（handout）**与**家长自定义条目（custom）**两种。

> **定位变化**：本文由 `2026-11-11-teacher-handout-learning-design.md`（讲义专用）泛化而来。
> 「讲义」从主角降为专项训练的**一种内容来源**（`source=handout`）；新增 `source=custom`
> （家长手动录入条目，不依赖 PDF）。两者共用同一套 `TrainingItem` / 闯关引擎 / SRS 掌握模型。
> 讲义专用的原页对照、PDF 划节保留为 `source=handout` 的特有细节。

## 背景与问题

典型识记型资料（已抽样验证）：

| 资料 | 页数 | 形态 | source |
|------|------|------|--------|
| 《必备固定短语搭配》 | 10 | 每页整页位图，无可选文字 | handout（phrase） |
| 《第 6 单元知识点归纳》 | 7 | 多图拼版，无可选文字 | handout（outline） |
| 家长自录「必背古诗 20 首」 | — | 手动粘贴行文本 | custom |

目标用户：**小学高段（5–6 年级）**、**孩子自学**、单次 **10–15 分钟**。

核心诉求：**识记型内容「记得住 + 用得出来」**，且要**真掌握**（排除蒙对/短时记忆/靠提示），不是「最近几次答对就毕业」。

## 目标

1. 入口是「今日一组」，不是翻完整本资料。  
2. 固定流程（短语：认 → 记 → 用 → 快测；归纳：结构卡 → drill → apply → closure），每步有完成态；**每题最多 2 次提示**。  
3. 掌握度与间隔复习走**独立表**，**不写入 `WordBank`**（避免听写池污染、`word` 64 字截断）。  
4. 讲义 / 自录共用同一 Flutter 壳层与 SRS 引擎，仅步序配置不同。  
5. **真掌握判定**：条目必须在 `mastery_interval_days`（默认 15 天）的间隔上、**无提示独立答对**才毕业；提示通过不升级、答错重置间隔。  
6. **分期明确**：Phase 1 家长布置单组任务；Phase 2 才接每日自动生成。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 学习场景 | 孩子自学 |
| 效果 | 记得住 + 用得出来（真掌握，非最近对） |
| 内容来源 | 第一批 `handout` + `custom`（不做教材知识点子集，`source` 字段预留扩展位） |
| 新任务类型 | `task_type=drill`（与 `dictation`/`knowledge`/`math`/`practice`/`custom` 并列，扩展 `Task` 注释与 `home_logic` 路由） |
| 数据抽象 | 方案 1：统一 `TrainingItem`，讲义/自录共用一套，闯关/SRS/复习池只实现一次 |
| 每日唯一约束 | 沿用 `UniqueConstraint(user_id, subject, date, task_type)`：**每科每天至多 1 条 `drill` 任务**；多专项排队，按进度依次推下一组 |
| 审核粒度 | **审「组」不审「任务」**：`TrainingGroup.audit_status` 通过后，由它生成的任务 `content_status=published` 直接可见 |
| 完成与家长确认 | 组末调现有 `submitTask` → `submit_status=submitted`（与 `knowledge` 一致，家长在运营端确认；自学不阻塞孩子看完成屏） |
| 间隔天数 | **建专项时定**，挂在 `TrainingGroup.mastery_interval_days` / `interval_max_days`，默认 15 / 60（不运行时读全局配置） |
| 真掌握判定 | `mastered = interval >= mastery_interval_days 且 最近一次通过无提示`；**实时判定不落库**，可逆（答错回退） |
| 结束语义 | 单条目 mastered 才毕业；专项**全部条目 mastered 才「完成」**、不再自动推 |
| 重新激活 | 家长显式触发：**整组重来、间隔清零、mastered 清除**，专项重新进入可布置状态 |
| 引导思考 | 组级 `group_rule`（结构化：观察示例+引导提问+揭晓结论，孩子**自己发现规律**）+ 条目 `secondary` 释义，AI 建组时生成、家长审组时顺带审；「记」前加「为什么」引导 |
| 趣味性 | 连击 ×N + 星级（后端算，答错/用提示各扣 1）+ 通关庆祝动画；不做道具/皮肤/排行榜 |
| 造句判分 | 专用 `drill-sentence` 包装 LLM，返回结构化 `{pass, feedback}`，**不走开放式 chat UI** |

## 数据模型（与教材链隔离）

### `PdfDocument` 扩展（仅 source=handout 涉及）

| 字段 | 类型 | 说明 |
|------|------|------|
| `content_kind` | `textbook` \| `handout` | 默认 `textbook` |
| `handout_kind` | `phrase` \| `outline` \| null | 上传时家长选择 |
| `handout_meta` | JSON | 如 `{"section_count":12}`（Phase 1 手划组不消费此值，仅占位；Phase 2 OCR 自动拆条后回填，勿在 MVP 依赖） |

### `TrainingGroup`（新表，= 一次专项的最小单元）

讲义里它是「节」，自录里它是「一组条目」。**不复用自动拆课 `Lesson`**（避免 `detect_lessons_from_pdf` 与 `extract_status` 语义冲突）。

| 字段 | 说明 |
|------|------|
| `id` | PK |
| `owner_id` | 归属家长（custom）/ admin（handout 上传者） |
| `subject` | 学科 |
| `title` | 如「固定短语 · 第 2 节」「必背古诗 20 首」 |
| `source` | `handout` \| `custom` |
| `kind` | `phrase` \| `outline`（决定四步 vs 归纳步序） |
| `document_id` | FK `pdf_documents`，仅 handout 有，custom 为 null |
| `start_page`, `end_page` | PDF 页码（对照原页），仅 handout 有 |
| `mastery_interval_days` | 判定「真掌握」的门槛间隔（天），建组时家长定，默认 15 |
| `interval_max_days` | 间隔递增封顶（天），建组时定，默认 60 |
| `group_rule` | 这组条目的**规律引导**（结构化三段：观察示例 + 引导提问 + 揭晓结论），AI 建组时生成，家长审组时顺带审 |
| `audit_status` | `pending` \| `approved` \| `rejected`，默认 `pending`；`approved` 才可进任务池 |
| `sort_order` | 学习顺序 |

### `TrainingItem`（新表，= 最小记忆单元）

| 字段 | 说明 |
|------|------|
| `id` | PK |
| `group_id` | FK `TrainingGroup` |
| `source` | 继承 group（`handout` \| `custom`） |
| `kind` | `phrase` \| `outline_point` \| `drill_item` |
| `primary` | 主记忆内容：短语原文 / 古诗正文 / 生字 |
| `secondary` | 中文释义 / 作者 / 拼音 |
| `block_title` | 归纳型的分组标题（可选） |
| `example` | 例句 / 可选解释句 |
| `keywords` | JSON，判分关键词 |
| `source_page` | int，仅 handout 有（原页对照），custom 为 null |

### `TrainingItemMastery`（新表，SRS 掌握度）

| 字段 | 说明 |
|------|------|
| `user_id` + `item_id` | 联合 |
| `interval` | 当前间隔天数（1→2→4→7→15→30→60） |
| `lapse` | 累计遗忘（答错）次数 |
| `last_hinted` | 最近一次通过是否用了提示 |
| `attempts` | JSON，历史对错序列（审计） |
| `next_review_at` | 下次复习时间 |

> **`mastered` 不落库**，查询时实时判定：`interval >= group.mastery_interval_days 且 最近一次通过无提示`。
> 家长改了间隔配置立即生效，无需迁移；答错回退（interval 重置）即自动脱离 mastered。

### `TrainingProgress`（新表，Phase 2）

`user_id` + `group_id`：`next_group_id`（下一未完成组）、`updated_at`。多专项各一行；**每日任务只推当前活跃专项**。

> ⚠️ **绑定时间戳缺口（Phase 2）**：若复用 `UserDocument` 表示「专项绑定」，其现表（`models.py:366`）只有 `uq(user_id, document_id)`，**无绑定时间字段、无「一科一本 active」约束**。Phase 2 要「取最早绑定的专项」，需加 `created_at`（或用主键 id 序）。custom 专项不涉及 document，需另定「孩子 ↔ 专项」的绑定方式（建议 `DrillBinding(user_id, group_id)`，或直接由任务 `user_id` 归属，Phase 1 不建此表）。

**明确不做**：讲义短语写入 `WordBank`；`_gen_dictation` 查询加 `Lesson`/`WordBank` 时保持仅 `content_kind=textbook` 的课。

## SRS 掌握模型（`services/drill_scheduler.py`，新）

独立于现有 `mastery.py`（那是「最近几次对加权」，会假掌握）。识记型专项用标准间隔重复：

```
无提示答对 → interval × 2（封顶 interval_max_days，默认 60），lapse 不变
有提示答对 → interval 不变，last_hinted = true（这次不算升级）
答错       → interval 重置 1 天，lapse + 1，last_hinted = false

mastered = (interval >= group.mastery_interval_days) 且 (最近一次通过无提示)
```

- 递增序列 `1→2→4→7→15→30→60` 复用 `scheduler.INTERVALS` 的节奏，但**答错重置 interval**（现有 `mastery._append` 答错不降间隔，这里要降）。
- 提示通过的条目**不升级 interval**，杜绝「靠提示蒙混毕业」。
- `mastered` 可逆：已毕业条目被重新拉出测、又答错 → interval 重置、自动回池。

## 内容来源与建组（`POST /api/drill/groups`）

统一建组入口，`source` 区分两种：

### source=handout（讲义）

1. `POST /api/pdf/upload` 增参 `content_kind=handout`、`handout_kind=phrase|outline`；**跳过** `detect_lessons_from_pdf`（不自动建 `Lesson`），返回 `document_id`。  
2. 家长调 `POST /api/drill/groups` 批量建组（节）与条目，`document_id` + `start_page`/`end_page`/`source_page` 供原页对照。MVP 接受家长粘贴行文本；Phase 2 服务端 OCR+AI 填充 `items`。

### source=custom（家长自录）

家长直接调 `POST /api/drill/groups`，`source=custom`、无 `document_id`、无页码，`items` 手动录入（如必背古诗：`primary`=诗句、`secondary`=作者/释义）。

```json
POST /api/drill/groups
{
  "source": "custom",
  "subject": "语文",
  "title": "必背古诗 20 首",
  "kind": "outline",
  "mastery_interval_days": 15,
  "interval_max_days": 60,
  "items": [
    {"kind":"drill_item","primary":"床前明月光","secondary":"李白《静夜思》","example":"...","keywords":["李白","明月"]}
  ]
}
```

响应：`{ "group_ids": [10, ...] }`。

## 审核链路（审「组」，任务免审）

审核落在**组**上（`TrainingGroup.audit_status`），不在 `Task.content_status` 上；组审过一次，内容即可信，由它生成的任务免重复审核。

- 建组后 `audit_status` 默认 `pending`，孩子不可见。
- 新增 `POST /api/drill/groups/{id}/audit`（`action=通过|拒绝`，对齐 `POST /api/pdf/lessons/{id}/audit`，见 `routers/pdf.py:228`）。
- `POST /api/drill/tasks` 仅接受 `audit_status=approved` 的组；创建的 `Task.content_status="published"`（组已审，任务免审，孩子立即可见）。
- **不复用** `POST /api/tasks/approve-all`（它按 `(user_id, date)` 全量发布，会误发当天其它类型 pending 任务）。

## 任务生成

### Phase 1（MVP）

- **不实现** `_gen_drill`，**不建** `TrainingProgress` 表。  
- 家长调 **`POST /api/drill/tasks`** 指定 `group_id` + `user_id` + `date`：服务端校验条目、截断至 8 条、生成 `items_snapshot` / `quiz`，创建 `Task(task_type=drill, content=...)`。  
  - `subject` 取自 `TrainingGroup.subject`——请求体不含 subject，勿让任务 subject 为空（否则首页 `groupForSubject` 分组错乱）。  
  - `content_status="published"`（组已审，任务免审，见「审核链路」）。  
  - 同 `(user_id, subject, date, task_type=drill)` 已存在 → 幂等返回既有 `task_id`（不 409，避免家长重复点报错）。  
  - **可选 `include_due=true`**：把该孩子该组下 `TrainingItemMastery.next_review_at <= now` 的到期条目追加进 `review_item_ids`（复用 Phase 2 的到期抽取逻辑，手动触发），受 `ceil(new_slots/2)` 复习上限。Phase 1 即接通「时常复习」的最小闭环。  
- 孩子首页点进 `/drill`。

### Phase 2

- `task_gen._gen_drill`：读 `TrainingProgress.next_group_id`，生成当日 `drill` 任务；**同一天任务内混排**「新组条目 + 到期复习条目」（对齐 `_gen_dictation` 四档混排）。到期条目从 `TrainingItemMastery` 到期池抽取，护栏：`ceil(new_slots/2)` 复习上限，新组条目至少 1；复习条进 `review_item_ids`。  
- 挂点：在 `generate_tasks_for_user`（`task_gen.py:409`）按科循环内追加 `_gen_drill`；subject 取专项的 `subject`，讲义无 `Lesson` 时 `_current_lesson` 返回 None，`_gen_drill` 须独立于 `_current_lesson`。  
- 若当日已有 `task_type=drill`，幂等跳过。

## 结束与重新激活

### 专项「完成」

- 单条目 `mastered=true`（实时判定）→ 毕业，离开主动复习池。  
- 专项（组）**全部条目 mastered** → 该专项「完成」，不再自动推新任务（家长仍可手动重新布置）。  
- 已答错/到期条目在 `mastered` 前持续以「复习」形态混入每日任务（`review_item_ids`）。

### 重新激活（家长显式触发）

专项完成后，家长在运营端对某 `TrainingGroup` 点「重新激活」：

1. 该组所有条目 `interval` **清零回 1 天**（整组重来）。  
2. `mastered` 清除（实时判定自然回 false）。  
3. 专项重新进入「可布置/可自动推」状态，孩子重新做一轮。

> 触发需家长显式确认（会改变孩子首页任务列表，对齐现有家长「布置/审核」权限边界）。
> 与「单条目答错自动回退」互补：前者自动、后者手动、前者按条、后者整组。

## `Task.content` JSON Schema（创建时写入）

```json
{
  "schema_version": 2,
  "group_id": 10,
  "source": "custom",
  "kind": "phrase",
  "document_id": null,
  "group_rule": {
    "examples": [{"oe":"look after","oc":"照顾"},{"oe":"look for","oc":"寻找"},{"oe":"look at","oc":"看"}],
    "question": "这些短语都以 look + ___ 开头，后面的词让意思发生了怎样的变化？",
    "reveal": "look + 不同介词 = 不同意思。after 跟在后面→照顾；for 寻找；at 看。"
  },
  "steps": ["recognize","recall","produce","quiz"],
  "item_ids": [101, 102, 103, 104, 105, 106],
  "review_item_ids": [55, 63],
  "items_snapshot": [
    {"id":101,"primary":"look after","secondary":"照顾","example":"...","source_page":null},
    {"id":55,"primary":"give up","secondary":"放弃","example":"...","source_page":3,"source":"review"}
  ],
  "quiz": [
    {"item_id":101,"qtype":"blank","prompt":"She ___ her brother.","answer":"looks after"},
    {"item_id":55,"qtype":"blank","prompt":"Don't ___!","answer":"give up","source":"review"}
  ],
  "progress": {
    "step": "recall",
    "item_index": 2,
    "hints_used": {"101": 1},
    "recall_results": {"101": true},
    "produce_results": {},
    "quiz_results": {}
  }
}
```

> **复习承载位（schema v2）**：`item_ids` 保留为**本新组**条目；`review_item_ids` 存**到期复习条目**（可跨组）。`items_snapshot` / `quiz` 里复习条目以 `"source":"review"` 标记。复习条走与新课相同的步序，`drill-complete` 一并写 mastery。

归纳 `kind=outline`：`steps` 为 `["structure","drill","apply","closure"]`；`drill` / `closure` 题在创建时调用 `generate_knowledge_questions()`（`knowledge_quiz.py` **服务函数**），题目塞进 `quiz` / `closure` 字段——**不复用** `KnowledgePage` 整页 UX。

> **归纳 apply 判分（已定）**：`apply` 是开放式题（如「写一句描写秋天的句子」），**用 LLM 判分**（复用 `grade_subjective_with_ai` 或专用短 prompt），**不套** `grade_knowledge_answer` 的 `0.6` 关键词命中阈值（孩子写得对但没踩中预设关键词会被误判错）。返回 `{pass, feedback}`，判分结果记入该条目 mastery。

## API 契约

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/pdf/upload` | 增参 `content_kind`, `handout_kind`（仅 handout） |
| POST | `/api/drill/groups` | 建组+条目（`source=handout|custom`），组 `audit_status` 默认 `pending`，间隔天数在此定 |
| POST | `/api/drill/groups/{id}/audit` | 审组（`action=通过\|拒绝`，对齐 `/api/pdf/lessons/{id}/audit`） |
| POST | `/api/drill/groups/{id}/reactivate` | **重新激活**：整组间隔清零、mastered 清除（家长显式触发） |
| POST | `/api/drill/tasks` | 由 `group_id` 组 `Task.content` 并创建任务（校验/截断/quiz）；subject 取自组、`content_status=published`、同科同天幂等返回 |
| GET | `/api/tasks/{id}` | 已有；`drill` 返回上述 `content` |
| POST | `/api/tasks/{id}/drill-step` | 步进式提交（记/测） |
| POST | `/api/tasks/{id}/drill-sentence` | 造句专用 |
| POST | `/api/tasks/{id}/drill-complete` | 写 mastery（SRS）、合并 `progress` 回写 content（**不动 `submit_status`**） |

### `POST .../drill-step`

请求：

```json
{
  "step": "recall",
  "item_id": 101,
  "answer": "look after",
  "request_hint": false
}
```

响应：

```json
{
  "correct": false,
  "hints_remaining": 1,
  "hint": "l___",
  "reveal_answer": false,
  "expected": null
}
```

第三次错误或 `hints_remaining=0` 且仍错：`reveal_answer=true`，写 `TrainingItemMastery` 答错记录（SRS 重置 interval），更新 `content.progress`。

服务端每次**回写** `Task.content.progress`（与多步状态机一致）。

### `POST .../drill-sentence`

```json
{ "item_id": 101, "sentence": "I look after my cat." }
```

响应：`{ "pass": true, "feedback": "搭配正确。" }`  
实现：内部短 prompt LLM 或规则（短语子串 + 最小长度）；**不**暴露通用 `/api/ask` 给 Flutter 步进流。`pass=false` 记掌握度答错，可重试 1 次。

> 语义澄清：`drill-sentence` 的「重试 1 次」与 `drill-step` 的「提示至多 2 次」（`hints_used`）是**两套独立计数**——前者是 produce 步的判分重答，后者是 recall 步的挖空提示。两者都写 `content.progress` 各自字段，**produce 重试不计入 `hints_used`**。

### `POST .../drill-complete`

校验步序 `progress` 齐全 → 批量写 `TrainingItemMastery`（含 `item_ids` + `review_item_ids`，按 SRS 规则推进 interval/lapse/last_hinted）→ 回写 `Task.content` → 返回 `{ "ok": true, "stars": 3, "review_due_tomorrow": 0 }`（Phase 1 无自动次日任务；`stars` 按「正确率 + 是否用提示」算，见「趣味性」）。

> 状态推进澄清：`Task` 表**无 `status` 字段**（只有 `content_status`/`submit_status`）。`drill-complete` **只写 mastery + 合并 progress 回写 content，不动 `submit_status`**。状态推进交给随后 Flutter 调的 `submitTask`（`not_started → submitted`），最终 `approved` 由家长在运营端 `confirm`（`tasks.py:347`）完成；`isDone`（`home_logic.dart:7`）只看 `approved`，任务此时才从 todo 移到 done（当天）/ 次日不在今日列表。

Flutter 随后调既有 **`POST /api/tasks/{id}/submit`**（`submitTask`，与 `KnowledgeController` 相同），`submit_status=submitted`。

Phase 2：`drill-complete` 额外推进 `TrainingProgress.next_group_id`。

## 学生端（Flutter）

| 项 | 约定 |
|----|------|
| 路由 | `/drill?taskId=123&returnTo=/home`（对齐 `taskRoute`） |
| 首页 | `home_logic` **两处**都要改：`taskAction()` 加 `openDrill` 枚举分支（`home_logic.dart:31`），`_metas` 加 `drill` 的 tag/分钟/icon/color（`home_logic.dart:56`）；否则落到 `comingSoon`、显示「自定义」样式。再在首页卡片 onClick 跳 `/drill`。 |
| 壳层 | 顶栏四步进度；底栏「查看原页」（仅 handout 有）；**连击 ×N 即时反馈 + 通关庆祝动画/音效 + 完成屏星级** |
| 原页 | 仅 `source=handout`：`/reader/view?documentId={id}&page={source_page}`——**增参 `documentId` + `page`**；勿将 `document_id` 传入现有 `lesson`（该 query 表示 **Lesson.id**）。讲义无 `Lesson` 时按 `documentId` 拉 PDF 页图，只读浏览。此为 reader 的**新只读分支**（现 `reader_view_page.dart` 以 `PdfLesson` 为中心渲染），非「增一个 query 参数」的小改，需评估 `pdf_lesson_reader.dart` 复用边界。`source=custom` 无原页，底栏不显示此入口。 |

## 步序（含引导思考 + 趣味性）

### 步序（不变的主体）

**短语**：认（规律引导 + 释义）→ 记（挖空+提示，先「为什么」引导）→ 用（drill-sentence）→ 快测（3 题，`drill-step`）。  

**归纳**：结构卡（规律引导 + 分组总览）→ drill（逐题 drill-step）→ apply（1 题）→ closure（句首填空）。

### 引导思考 / 发现规律（内容层）

把「死记」升级为「先懂规律再记」：

| 环节 | 做法 |
|------|------|
| 结构卡（归纳）/ 认（短语）第一步 | 先展示 **`group_rule`** 的「观察示例 + 引导提问」，让孩子**自己思考发现规律**，再点「揭晓」看结论（不直接喂规律），随后列条目 |
| 记（背） | 挖空前加一句「先想想为什么」的引导（如「after 是『跟在后面』，所以 look after 是照顾」） |

- **生成方式（已定 A）**：`group_rule` 由 AI 在**建组时**生成（`source` 任意），家长审组时顺带审这条规律。
- **结构化**：`group_rule` 不是纯文本，而是三段 JSON：`{"examples":[{oe,oc}...], "question":"引导提问", "reveal":"揭晓结论"}`。前端先渲染 examples + question，孩子自己思考后点「揭晓」才显示 reveal。
- 出题实现：扩展 `generate_knowledge_questions` 或新增「规律归纳」服务函数——给一组条目，让 LLM 生成「观察示例 + 引导提问 + 揭晓结论」三段；fake provider 回退为空结构（前端不显示规律引导块，步序照常）。
- **释义（了解意思）**：每个条目第一步必展示 `secondary`（意思/作者/拼音），引导孩子「先看懂再背」；古诗/短语的 `secondary` 由 AI 建组时批量补（家长审），不复用 `annotations.py` 的即时划词。

### 趣味性 / 游戏化（交互层）

基于现有「积分」体系往上加，**只做三项轻量**：

| 趣味点 | 做法 | 成本 |
|--------|------|------|
| **连击** | 连续答对显示「连击 ×N」，即时视觉反馈（纯前端状态） | 低 |
| **星级** | 每组完成按「正确率 + 是否用提示」给 1–3 星，完成屏展示 | 低（后端算，前端展示） |
| **通关庆祝** | 四步进度（已有）+ 完成时的庆祝动画/音效 | 低-中（前端动画） |

**明确不做**：道具、皮肤、排行榜、虚拟货币、复杂小游戏。

星级计算（后端 `drill-complete` 返回）：`stars = 3 - (用了提示的条目数>0 ? 1 : 0) - (答错条目数>0 ? 1 : 0)`，下限 1。

## 错误处理

| 场景 | 行为 |
|------|------|
| OCR 失败 | Phase 2；MVP 仅手动条目 |
| AI 造句不可用 | 规则 `pass` + `feedback` 固定文案；可选跳过 produce（`steps` 去掉 `produce`，配置在 group meta） |
| apply 判分不可用（fake/无 LLM） | 回落规则：若条目有 `keywords` 用关键词命中，否则给 `pass=false` + 固定文案「请家长/老师人工点评」（不编造通过） |
| 无条目 | 拒绝创建 task，400 |
| fake provider | `drill-sentence` 规则判 pass |

## 分期交付

### Phase 1（MVP，可验收）

- 模型：`PdfDocument` 扩展 + `TrainingGroup` / `TrainingItem` / `TrainingItemMastery`（无 `TrainingProgress`）；`Task` 注释 `task_type` 更新为真实全集（含 `math`/`practice`，见 `models.py:226` 现注释缺失）  
- `source=handout`（上传跳过自动拆课、划组、审组）+ `source=custom`（家长自录条目）  
- 家长布置 → `task_type=drill`（**手动**，组审后任务 `published`）  
- SRS 掌握引擎 `drill_scheduler.py`（无提示升级/提示不升级/答错重置/15 天门槛实时判定）  
- 引导思考：`group_rule` 规律引导 + `secondary` 释义（AI 建组时生成，家长审组时顺带审）  
- 趣味性：连击 ×N + 星级（后端算）+ 通关庆祝动画  
- 重新激活 `POST /api/drill/groups/{id}/reactivate`  
- Flutter：短语四步 + 归纳四步 + handout 原页 + `drill-step` / `drill-sentence` / `drill-complete`  
- 测试要点 **P1-1…P1-14**（见下）

### Phase 2

- 新增 `TrainingProgress` + `_gen_drill` + 复习护栏（多专项绑定时取最早且 audit 通过）  
- 归纳 OCR 拆条（讲义）  
- 测试要点 **P2-1**

### Phase 3

- 错题本联动、专项进度看板

## 测试要点

**Phase 1（P1-x）**

1. **P1-1** `content_kind=handout` 上传后不产生自动 `Lesson`。  
2. **P1-2** 无 `TrainingItem` 时 `POST /api/drill/tasks` 返回 400。  
3. **P1-3** `recall` 提示至多 2 次，第三次 `reveal_answer`。  
4. **P1-4** 条目 >8 时 `drill/tasks` **截断至 8**。  
5. **P1-5** `documentId`+`page` 打开 reader 正确页码（仅 handout）。  
6. **P1-6** fake provider 下走完四步 + `submit`。  
7. **P1-7** 未审组（`audit_status=pending`）时 `drill/tasks` 拒绝或不出任务；审过后任务 `content_status=published` 且孩子 `GET /api/tasks` 可见。  
8. **P1-8** 任务 `subject` 取自组；同 `(user_id, subject, date, task_type=drill)` 重复布置幂等返回同一 `task_id`。  
9. **P1-9** `include_due=true` 时到期条目进 `review_item_ids`，受 `ceil(new_slots/2)` 上限，且新组条目至少 1；`drill-complete` 对 `item_ids`+`review_item_ids` 一并写 mastery。  
10. **P1-10** SRS：无提示答对 interval×2；有提示答对 interval 不变；答错 interval 重置 1 天 + lapse+1。  
11. **P1-11** `mastered` 实时判定：interval 达门槛且无提示通过才 true；`reactivate` 后整组 interval 清零、mastered 回 false。  
12. **P1-12** 建组时 `group_rule` 生成结构化三段（examples/question/reveal，非 fake 时非空）；fake provider 下为空结构、前端不显示规律引导块、步序照常。  
13. **P1-13** `drill-complete` 返回 `stars`（答错/用提示各扣 1 星，下限 1）。  
14. **P1-14** 归纳 `apply` 用 LLM 判分返回 `{pass, feedback}`；fake/无 LLM 时回落规则（有 keywords 用关键词，否则 `pass=false` + 固定文案）。

**Phase 2（P2-x）**

1. **P2-1** `TrainingItemMastery` 到期条目出现在次日 `_gen_drill` 复习槽。

## 明确不做

- 教材知识点子集作为来源（`source` 字段预留，Phase 3 后评估）。  
- 讲义并入课文 quiz / 阅读链路。  
- 语音打分。  
- 一次学完整本 10 页。  
- Phase 1 自动拆条 / 每日自动生成。  
- 运行时读全局配置改间隔（间隔在**建组时定死**，改需重新激活或编辑组）。

## 参考

- Brainstorming：2026-11-11（自学、闯关+原页）→ 2026-11-12（泛化为专项训练 + SRS 真掌握 + 重新激活 + 引导思考/发现规律 + 趣味性）  
- 代码锚点：`routers/pdf.py` upload、`task_gen.py`、`knowledge_quiz.py`、`KnowledgeController.submitTask`、`ReaderViewPage`、`services/scheduler.py`（INTERVALS）、`services/mastery.py`（现有掌握，勿混用）、`services/grade_question.py`（`grade_subjective_with_ai`）
