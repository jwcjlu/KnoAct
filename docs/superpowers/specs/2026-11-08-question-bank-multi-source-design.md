# 题型统一化 + 多来源题库（人工 / 拍照 OCR / 第三方 adapter）

日期：2026-11-08
状态：设计已定稿，待实现
范围：后端 `models` / `routers` / `services` / `core`；`parent-web` 题库管理 + 审核；Flutter 学生端「题库练习」。

## 背景与目标

KnoAct 现有题目分两条独立线：`Question`（自由文本题干 + `answer` 字符串，挂 `lesson_id`，
`qtype` 仅 4 个粗粒度值 knowledge/reading/listening/math，走家长审核）与 `Quiz`（四选一 +
evidence 校验，纯 AI 生成，边读边问）。两者都无法表达「填空/判断/连线/应用题/作文」等
主客观题型，且 `Question` 被强制挂靠某课、无法承载脱离教材的独立卷子。

本设计在**现有 `Question` 上做加法**（方案 A），引入三件新能力：

1. **题型 taxonomy + 统一富答案结构**：主客观题型落到 schema 层，一套判分路由。
2. **独立题库**：题目可不挂课，按学科/年级/知识点标签检索；可选挂卷。
3. **三来源统一入库流水线**：人工录入、卷子拍照 OCR、第三方题库，经可插拔 `SourceAdapter`
   标准化后汇聚到同一张 `Question` 表 + 同一套 `pending→published/rejected` 审核流。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 整体方案 | 方案 A：现有 `Question` 加法，不新建并行题目体系 |
| 题型清单 | 由本设计整理（两级 taxonomy），学科不另立维度（`subject` 字段已有） |
| 覆盖范围 | 客观题 + 主观题都覆盖 |
| 第三方接入 | 可插拔 `ThirdPartyAdapter`；第一版只建基类 + registry + `tiku.cn` 占位，具体同步后续确认 |
| 拍照自动化 | 全自动提取（OCR → LLM 结构化 → 直接成题），家长仅审核校对 |
| 拍照落库 | 直接 `status=pending` 进统一审核队列 |
| 题目归属 | 独立题库 + 标签，不强制挂 lesson |
| 做题入口 | 独立「题库练习」+ 可勾选纳入每日任务（两者都要） |

## 成功标准

1. 一个 `grade_question()` 纯函数按题型正确判分：单选/多选/判断/填空/计算/连线精确判，主观题 AI 判分（未配置回落待批改）。
2. 家长端可建卷、人工录入富表单（含主客观全部题型）、拍照上传；拍照后题目自动结构化并进审核队列。
3. 审核通过后，孩子端「题库练习」能按题型渲染并作答，客观题即时判分，答错收错题本/更新掌握度。
4. 新增来源 = 新增一个 `SourceAdapter` 实现；新增题型 = taxonomy 加一行 + `grade_question` 加一个 case，均不改表结构。

---

## §1 题型 Taxonomy 与统一答案结构

### 1.1 两级 taxonomy

`category`（题型大类，决定判分方式）→ `qtype`（具体题型，决定展示/录入表单）。`subject`
（语文/英语/数学）与题型正交，不另立学科维度。

| category | 判分方式 | qtype |
|---|---|---|
| `choice` | 精确匹配 | `single_choice` 单选、`multi_choice` 多选、`true_false` 判断 |
| `blank` | 精确/容错匹配 | `fill_blank` 填空、`cloze` 完形填空、`calculation` 计算 |
| `match` | 匹配对校验 | `matching` 连线/配对 |
| `subjective` | AI 判分 / 人工批改 | `short_answer` 简答、`essay` 作文、`application` 应用题、`oral` 口语 |

taxonomy 以**代码常量**定义在 `core/question_types.py`（`CATEGORY_OF_QTYPE: dict[str,str]` +
`QTYPE_LABELS: dict[str,str]`），供后端判分路由与前端渲染/录入复用，不另建 DB 表（避免
「题型表」与代码漂移）。

### 1.2 `Question` 字段改造

| 字段 | 类型 | 说明 |
|---|---|---|
| `qtype` | String | 改为 taxonomy 值（`single_choice`/`fill_blank`/…）；旧 4 值迁移见 §6 |
| `qtype_category` | String | 冗余列（`choice`/`blank`/`match`/`subjective`），判分路由用 |
| `answer` | LongText | **保留**，标准答案的展示文本（兼容旧数据、家长速览） |
| `answer_json` | LongText（新增） | 机器判分依据：`{"correct_index":2}` / `{"blanks":[...]}` / `{"pairs":[[...]]}` / 主观题 `{"rubric":"…","sample":"…"}` |
| `options` | LongText（新增） | 选择/连线题选项 `[{label,value}]` |
| `analysis` | LongText（新增） | 解析/解题过程 |
| `difficulty` | String（新增） | `easy`/`medium`/`hard` |
| `tags` | LongText（新增） | `{grade, knowledge_points:[], source, …}` 自由标签 |
| `bank_id` | FK（新增，nullable） | 归属的卷，见 §2 |

`extra` 保留兜底（旧数据/边缘附加信息），核心结构走上面这些列。

### 1.3 `grade_question()` 判分路由

`services/grade_question.py` 提供纯函数 `grade_question(qtype_category, answer_json, student_answer) -> {is_correct, correct_answer_text, detail}`：

- `choice`：`student_answer` 是所选 index（单选）或 index 数组（多选），与 `answer_json.correct_index` 精确比较。
- `blank`：`answer_json.blanks` 逐空比对，`normalize_answer`（去空白/大小写/全半角）容错；`calculation` 数值化比较。
- `match`：`answer_json.pairs` 校验每对是否匹配。
- `subjective`：调用 `grade_subjective()`（走 `get_provider`，参考 `rubric`），AI 未配置/fake 返回 `pending`（待家长批改）。

主观题批改结果写回该次**作答记录**（`Question` 只存题目与标准答案/rubric，不存孩子作答；作答
记录沿用现有错题本/掌握度之外的轻量「练习作答」结构，或复用 `Mistake` 表 + `source_type=bank`
承载对错），对齐现有数学应用题照片批改（`2026-11-07-math-word-photo-design`）的「AI 不确定 →
待家长确认」约定。作答记录的具体承载表在实现计划中确定（优先复用 `Mistake`，避免新表）。

---

## §2 独立题库与统一入库流水线

### 2.1 `QuestionBank`（卷/题库）

新增表：`id, user_id(家长/老师), title, subject, grade, tags(JSON), source(manual|photo|third_party), status, created_at`。

`Question.lesson_id` 改 **nullable**，新增 `bank_id`（FK，可选）。一道题三种归属：

- 挂课（旧路径，教材拆课出题）；
- 挂卷（家长建的一册卷子）；
- 都不挂、只靠 `tags` 检索（纯独立题库）。

### 2.2 统一「导入 → 标准化 → 审核 → 发布」

所有来源汇聚到同一张 `Question` 表 + 同一套 `status` 流转（复用现有 `pending→published/rejected`）：

```
来源                 标准化器(SourceAdapter)            落库
─────────────────────────────────────────────────────────────
manual  家长表单  ──► ManualAdapter（表单直接产出富结构）────┐
photo   卷子拍照  ──► OcrAdapter（ocr_image→LLM结构化）──────┼──► Question(bank_id?, status=pending)
third   tiku.cn等 ─► ThirdPartyAdapter（同步→中间JSON）──────┘          │
                                                                       ▼ 家长审核(复用现有 UI)
                                                                     published → 孩子端可做
```

### 2.3 可插拔 `SourceAdapter`

`core/source_adapter.py` 定义接口：`SourceAdapter.normalize(raw) -> list[QuestionDraft]`，
`QuestionDraft` 是标准中间结构（`qtype, question, options, answer_json, answer, analysis,
difficulty, tags`）。三个来源各自实现：

- **`ManualAdapter`**：家长端「录入表单」直接产出 `QuestionDraft`，走扩展后的 `POST /api/questions`。
- **`OcrAdapter`**（拍照）：复用 `services/ai.ocr_image`（视觉模型）先 OCR 原始文字，再调 LLM
  （`json_mode`）把文字+版式结构化成一组 `QuestionDraft`（题干/选项/答案/解析 + 题型自动归类）。
  **全自动提取**，`status=pending` 直接进统一审核队列，家长在审核页校对确认。
- **`ThirdPartyAdapter`**：定义基类（`name` + `fetch(raw) -> 中间JSON` + `normalize`），每个题库
  一个子类注册到 `core/source_registry.py`。**第一版只建基类 + registry + `tiku.cn` 占位 stub**
  （tiku.cn 无公开 API，具体同步方式需商业授权/爬虫，后续单独确认后再实现子类）。

### 2.4 扩展性保证

- 新增来源 = 新增一个 `SourceAdapter` 实现，**不改落库/审核/判分**。
- 新增题型 = `question_types.py` 加一行 + `grade_question()` 加一个 case，**不改表结构**。

---

## §3 孩子端做题闭环

### 3.1 「题库练习」入口（Flutter 学生端新 feature）

- 拉题：按 `tags`（学科/年级/知识点）或某卷 `bank_id` 检索已 `published` 的题。
- 渲染：按 `qtype` 渲染对应控件（单选/多选/判断/填空/连线/简答/作文）。
- 提交：服务端调 `grade_question()`，客观题即时判分，主观题 AI 判分（未配置标「待批改」）。

### 3.2 纳入每日任务（可勾选）

- 家长在建卷/审核时可选「纳入每日任务」；`task_gen` 生成每日任务时，从该卷 `published` 题中
  抽取若干道混入当日练习（`task_type` 复用 `reading` 或新增 `practice`，走 `Task.content` JSON 快照，
  对齐现有每日任务机制）。此部分为 P2 增强，第一版先落地独立「题库练习」，纳入每日任务的抽取规则
  在实现计划里细化。

### 3.3 结果复用

- 客观题答错 → 收错题本（`Mistake`，`source_type` 新增 `bank`）+ 更新掌握度
  （`Mastery`/`KnowledgeMastery`，按 `tags.knowledge_points` 关联）。
- 主观题 AI 判分后按结果收错题本。

---

## §4 前端改动范围

- **`parent-web`**：新增「题库管理」页（建卷、人工录入富表单、拍照上传入口）；审核页扩展为
  多题型预览（复用并扩展现有 `QTYPE_LABEL` + `reviewGroups` UI）。
- **`student-app`（Flutter）**：新增 `features/bank_exercise/`（拉题 + 渲染 + 提交判分）。
- **旧 `frontend/`**：冻结，不动。

---

## §5 后端改动范围

| 层 | 改动 |
|---|---|
| `models.py` | `Question` 加列/`lesson_id` 改 nullable；新增 `QuestionBank` |
| `core/question_types.py` | 题型 taxonomy 常量（新增） |
| `core/source_adapter.py` + `core/source_registry.py` | 接口 + 来源注册表（新增） |
| `services/grade_question.py` | 多题型判分 + 主观题 AI 判分（新增） |
| `services/ocr_import.py` | 拍照 → OCR → LLM 结构化（新增） |
| `routers/bank.py` | 建卷/列卷/拉题（新增） |
| `routers/questions.py` | `add_question` 扩展富结构；审核流复用 |

---

## §6 数据迁移

- `Question.lesson_id` 改 nullable（SQLite/MySQL 均兼容）。
- 新增列 `answer_json`/`options`/`analysis`/`difficulty`/`tags`/`qtype_category`/`bank_id` 均带默认值。
- 旧 `qtype` 4 值迁移：`qtype` 统一映射到 taxonomy 最近项——`reading→short_answer`、
  `listening→single_choice`、`knowledge→short_answer`、`math→application`；`qtype_category` 相应
  回填（`subjective`/`choice`/`subjective`/`subjective`）。`answer` 不动（老数据仍可用 `answer`
  展示，`answer_json` 为空表示「无结构化判分依据」，判分时回落到仅展示、人工批改）。

---

## §7 测试要点

- 单测：`grade_question()` 各 category 判分正确性（含多选、填空容错、计算、连线）；三个 adapter
  的 `normalize()` 边界；taxonomy 常量完整性（每个 qtype 都有 category 映射）。
- 集成：手动录入 → 审核 → 发布 → 做题 → 判分 → 错题本全链路；OcrAdapter 用 fake vision 模型兜底
  验证结构化输出形状；旧 `Question`（无 `answer_json`）迁移后不破。

## 参考

- 数学应用题照片批改（主观题 AI 判分约定）：[2026-11-07-math-word-photo-design.md](./2026-11-07-math-word-photo-design.md)
- 每日任务系统：[2026-10-25-daily-task-system-design.md](./2026-10-25-daily-task-system-design.md)
- 现有实现：`services/quiz.py`（`grade_answers`）、`services/question_gen.py`、`routers/questions.py`、
  `routers/quiz.py`、`services/ai.py`（`ocr_image`）、`tools/generation.py`
