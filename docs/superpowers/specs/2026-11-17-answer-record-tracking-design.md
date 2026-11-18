# 当天做题明细跟踪与监管设计

日期：2026-11-17
状态：待评审

## 背景与目标

家长看不到「孩子今天做了哪些题、做了几道、对错如何」。现有「报告」Tab 只有
错题报告（`Mistake`）与掌握度报告（`mastery`），是**结果/掌握度**视角，缺少
「当天做题行为」的逐题明细视角。

目标：家长端「报告」Tab 新增「当天做题明细」，按科目/模块分组，逐题展示
题目、孩子答案、标准答案、对错、耗时、难度，并保留「先错后对」的完整作答轨迹。

## 现状（已核实）

| 数据源 | 题目 | 孩子答案 | 标准答案 | 时间戳 | 稳定主键 |
| --- | --- | --- | --- | --- | --- |
| `Mistake`（错题） | ✅ question | ✅ your_answer | ✅ correct_answer | ❌ 无 date | `word_bank_id`/`knowledge_point_id` |
| `Quiz`（边读边问） | ✅ questions JSON | ❌ 只存 score | ✅ correct_index | ✅ created_at | quiz 内临时 `q["id"]` |
| 每日任务（听写等） | 来自 WordBank | ❌ | ❌ | ✅ Task.date | `WordBank.id` |
| `TrainingItem`（专项） | ✅ primary | ❌ | ✅ common_mistake | ❌ | `TrainingItem.id` |
| 题库 `Question` | ✅ question | 提交时判分 | ✅ answer/answer_json | ✅ created_at | `Question.id` |

核心矛盾：只有 `Mistake` 完整存了「题目+孩子答案+标准答案」，其它入口要么只存
总分/掌握度，要么没时间戳。要做「逐题明细」，需新建统一明细表 + 各入口埋点。

## 决策记录（已与用户确认）

- **覆盖范围**：所有做题入口（题库练习 / 边读边问 / 每日任务 / 专项训练）。
- **数据方案**：新建统一「做题明细」表 `AnswerRecord`，各入口提交时写入。
- **作答轨迹**：每次作答记一行（保留完整轨迹，先错后对 = 两行），靠 `source_type`+
  `source_id` 关联同一题；跨天关联仅对「有稳定主键」的入口（题库/听写/专项）成立，
  边读边问的题是 AI 现场生成，跨 quiz 不强行关联。
- **补充字段**：存 `lesson_id`（有就存）、`difficulty`（难度）、`duration_ms`（耗时）。
- **耗时来源**：前端做题页计时，提交答案时带上 `duration_ms`。
- **视图位置**：并入家长端「报告」Tab（新增「当天做题明细」区块）。
- **查看角色**：家长。

## 设计

### 数据模型 `AnswerRecord`

每次作答一行：

```python
class AnswerRecord(Base):
    __tablename__ = "answer_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16), default="")        # 语文/英语/数学
    module: Mapped[str] = mapped_column(String(32), default="")          # dictation/reading/listening/quiz/drill/practice
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"), nullable=True)
    question: Mapped[str] = mapped_column(LongText)
    student_answer: Mapped[str] = mapped_column(LongText, default="")
    correct_answer: Mapped[str] = mapped_column(LongText, default="")
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    difficulty: Mapped[str] = mapped_column(String(16), default="")      # easy/medium/hard，可空
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)     # 前端计时
    source_type: Mapped[str] = mapped_column(String(16), default="")     # question|word_bank|training_item|quiz|task
    source_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- `module` 语义沿用现有 `task_type`/`source_type` 的取值（听写/阅读/听力/边读边问/专项训练/题库练习）。
- `source_type`+`source_id` 关联同一题的多次作答：题库→`Question.id`，听写→`WordBank.id`，
  专项→`TrainingItem.id`，边读边问→quiz 内 `q["id"]`（跨 quiz 不关联，可接受）。
- 建表走 `Base.metadata.create_all`（启动时自动建），无需手写迁移（全新表）。

### 埋点写入（四个入口）

| 入口 | 接口 | 写入时机 | source_type/source_id |
| --- | --- | --- | --- |
| 题库练习 | `routers/bank.py` submit | `grade_question` 判分后逐题写 | `question` / `Question.id` |
| 边读边问 | `routers/quiz.py` submit | 判分后逐题写（补上现在只写 Mistake 的缺口） | `quiz` / quiz 内题 id |
| 每日任务（听写等） | 交答案接口 | 写 AnswerRecord（听写词有 `word_bank_id`） | `word_bank` / `WordBank.id` |
| 专项训练 | `routers/drill.py` 作答 | 写 AnswerRecord | `training_item` / `TrainingItem.id` |

- 每个入口的提交请求体额外带 `duration_ms`（前端计时，可空）。
- 写明细是「追加」而非「替换」：错题仍照旧写 `Mistake`（供错题本），同时额外写 `AnswerRecord`
  （供明细监管）。两者并存，不破坏现有错题本/掌握度逻辑。

### 家长端视图

家长端「报告」Tab 新增「当天做题明细」区块：

- 按 `subject`（科目）→ `module`（模块）两层分组。
- 逐题展示：题目、孩子答案、标准答案、对错标记、耗时、难度。
- 同一题多次作答（轨迹）折叠展示为「第 1 次错 → 第 2 次对」（按 `created_at` 排序）。
- 顶部可切换日期（默认当天），查看任意一天。
- 数据来源：新增接口 `GET /api/answer-records?user_id=<child>&date=<date>`，返回当天该孩子的
  全部明细（按 subject/module 分组或前端分组）。

### 后端接口

新增 `routers/answer_records.py`：
- `GET /api/answer-records?user_id=&date=`：家长/管理员查某孩子某天的做题明细。
  按 `user_id` + `created_at` 当天范围（东八区）过滤，返回逐题列表。
- （写入不单独暴露接口，由各做题入口埋点直接调 service。）

## 文件改动

- `backend/app/models.py`：新增 `AnswerRecord` 表。
- `backend/app/services/answer_record.py`（新增）：`record_answer(db, ...)` 写入 helper。
- `backend/app/routers/answer_records.py`（新增）：查询接口。
- `backend/app/main.py`：`include_router` 注册。
- `backend/app/routers/bank.py` / `quiz.py` / `drill.py` / 任务交答案入口：埋点写入 + 请求体加 `duration_ms`。
- `parent-web/app.js`：报告 Tab 加「当天做题明细」区块。
- 学生端（Flutter `student-app/`）：各做题页计时 + 提交带 `duration_ms`。
- `backend/tests/`：`AnswerRecord` 模型 + 查询接口 + 埋点单测。

## 范围与非目标

**做**：`AnswerRecord` 表 + 四入口埋点 + 家长端报告明细视图 + 前端计时。

**不做**（后续）：孩子端自查明细、做题趋势图表、耗时/难度的深度分析、跨入口统一题目的精确去重
（边读边问 AI 题跨 quiz 不关联）。

## 测试

- 单测：`AnswerRecord` 模型字段；`record_answer` 写入；`GET /api/answer-records` 按当天过滤、
  按科目/模块分组、轨迹（同题多行）。
- 手工：孩子端做几道题（题库/边读边问/听写），家长端报告查看当天明细，确认题目/答案/标准答案/
  对错/耗时/难度齐全、先错后对折叠展示正确。
