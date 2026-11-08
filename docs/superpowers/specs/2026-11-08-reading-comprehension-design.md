# 阅读理解组题（语文/英语）设计

日期：2026-11-08
状态：设计已定稿，待实现
范围：后端 `models` / `routers`；复用已建的多来源题库基础设施（`Question` 富结构、判分、`SourceAdapter`）。

## 背景与目标

上一套设计「题型统一化 + 多来源题库」（`2026-11-08-question-bank-multi-source-design.md`）把题型
落到 taxonomy（`choice`/`blank`/`match`/`subjective` 四大类），但漏掉了「阅读理解」——它是小学语文、
英语都有的高频题型。

**关键认知**：阅读理解**不是一种题型**，而是一种**组题结构**——一篇短文/语段 + 围绕它的若干道
小题（子题本身仍是选择/填空/简答）。因此不新增 `qtype`，而是用「材料表 + 子题外键」表达，子题
复用现有 taxonomy 与判分，阅读理解仅提供「先读材料、再逐题作答」的组织方式。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 表达方式 | 材料 + 子题组，不新增单一 qtype |
| 建模 | 新表 `ReadingPassage`（材料）+ `Question.passage_id` FK（子题复用现有判分） |
| 范围 | 只新增「题库里的阅读理解组题」；不统一收编现有 `Quiz`（边读边问）与 `question_gen` |
| 判分 | 零改动，复用 `grade_question()` / `grade_subjective_with_ai()` |
| 入题来源 | 人工录入 / 拍照 OCR / 第三方（后续）三来源都收敛到 ReadingPassage+子题 |

## 成功标准

1. 家长可建一篇阅读理解：填材料正文 + 逐条填子题（子题用现有题型控件），落成 `ReadingPassage` + N 道 `Question`（`passage_id` 关联）。
2. 孩子端拉题时，带 `passage_id` 的题先展示材料、再逐题作答；子题判分复用现有逻辑（客观即时、主观 AI/pending）。
3. 三来源（人工/OCR/第三方）都能产出「材料 + 子题」；不破坏现有独立题（`passage_id` 为 NULL 时行为不变）。
4. 不新增 qtype、不改 `grade_question()`。

---

## §1 数据模型

### 1.1 新表 `ReadingPassage`（阅读材料）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | PK | |
| `user_id` | FK `users.id` | 归属家长/老师 |
| `bank_id` | FK `question_banks.id` nullable | 归属卷（可选，独立可空） |
| `subject` | String(16) | 语文 / 英语 |
| `title` | String(255) | 材料标题 |
| `content` | LongText | 阅读材料正文（短文/语段） |
| `grade` | Integer nullable | 年级 |
| `status` | String(16) default "pending" | pending / published（走审核流） |
| `created_at` | DateTime default utcnow | |

### 1.2 `Question` 加列

- `passage_id`：FK `reading_passages.id`，nullable。子题挂此 FK；普通独立题为 NULL，行为不变。
- `passage_id` 与 `bank_id` 正交：一道子题可同时属于某篇阅读材料（`passage_id`）和某卷（`bank_id`），
  也可只挂其一、或都不挂（纯独立题）。两者互不排斥。

### 1.3 不新增 qtype

「阅读理解」不进 `CATEGORY_OF_QTYPE` / `QTYPE_LABELS`。子题的 `qtype` 仍是现有 taxonomy
（`single_choice`/`fill_blank`/`short_answer`/…），`qtype_category` 照常派生，判分照常路由。
材料存在 `ReadingPassage` 里，子题靠 `passage_id` 关联，天然表达「阅读理解组」。

---

## §2 入题来源与统一结构

三来源都收敛到「`ReadingPassage` + 子题 `Question`」：

- **人工录入**：家长端「录入表单」选「阅读理解」→ 填材料正文 + 逐条填子题（子题用现有题型控件）。
- **拍照 OCR**：`OcrAdapter`/`ocr_import` 的 LLM 结构化输出增加「材料 + 子题」形状，落成 ReadingPassage + 子题。
- **第三方**（后续）：tiku.cn 的阅读题同样是「文章 + 题目」，adapter 归一化时拆成材料 + 子题。

统一走 `pending → published` 审核流（复用现有 `/api/questions/review|approve|reject` 与题库审核 UI）。

---

## §3 孩子端展示与判分

- 拉题：子题带 `passage_id` → 先取 `ReadingPassage.content` 展示在顶部，再逐题作答。
- 判分：子题复用现有 `grade_question()`（客观即时）/ `grade_subjective_with_ai()`（主观 AI/pending）。
- 结果复用：答错收错题本 + 更新掌握度，与现有题库一致。

---

## §4 后端改动范围

| 层 | 改动 |
|---|---|
| `models.py` | 新增 `ReadingPassage`；`Question` 加 `passage_id` FK |
| `routers/bank.py`（或新 `routers/passages.py`） | 建材料、列材料、拉材料+子题 |
| `routers/questions.py` | `add_question` 加 `passage_id` |
| `services/` | 判分**零改动** |
| 迁移 | 现有库 `create_all` 不补列/表，需迁移脚本（见上套 `migrate_question_bank.py` 同模式） |

## §5 与上一套「多来源题库」的关系

本设计是 `2026-11-08-question-bank-multi-source` 的**自然延伸**：上一套已搭好 `Question` 富答案结构、
`QuestionBank`、`SourceAdapter`、判分。本设计只在其上**加一张 `ReadingPassage` 表 + `Question.passage_id`
一列**，全部复用已有基础设施，不冲突、不改判分。两条线并行：上一套的执行（Subagent-Driven）已完成后端
Task 1–8，还剩前端 Task 9–11；本套独立成 spec → plan → 实现，`Question.passage_id` 作为新任务叠加。

## §6 测试要点

- 单测：`ReadingPassage` + 子题 FK 建模；`add_question` 带 `passage_id`；拉材料返回材料 + 子题；子题判分复用（客观即时、主观 AI/pending）。
- 集成：人工录入一篇阅读（材料 + 3 子题）→ 审核 → 孩子端拉题作答 → 判分 → 错题本。

## 参考

- 题型统一化 + 多来源题库：[2026-11-08-question-bank-multi-source-design.md](./2026-11-08-question-bank-multi-source-design.md)
- 现有实现：`services/quiz.py`（边读边问，evidence 校验）、`services/question_gen.py`（`generate_reading_questions`）、
  `routers/learning.py`（阅读材料）、`core/question_types.py`（taxonomy）
