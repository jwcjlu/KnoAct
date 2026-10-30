# 基础知识主动复习（简答 + 遗忘曲线闭环）设计

日期：2026-10-30
状态：已确认，待实现
范围：把「基础知识复习」从主观自评改为主动回忆（简答），判分结果驱动遗忘曲线

## 背景与目标

现有「基础知识复习」（`frontend/app.js` `startKnowledge` / `renderKnowledge`，`tasks.py` `knowledge-review`）是**逐条自评**：把知识点列出来，孩子对每个点「记住了 / 还不熟」。这极其主观——孩子可能高估自己、随便勾、或根本没真正回忆就凭感觉选。

记忆科学的核心结论：被动重读 + 主观自评 ≠ 有效复习。有效复习需要**主动回忆（retrieval practice / testing effect）**——让孩子主动从脑子里把知识点提取出来，而不是「看一眼觉得自己会」。

目标：把自评改为**逐题简答**，孩子凭记忆作答，判分结果（对/错）驱动 `KnowledgeMastery` 的遗忘曲线（答错很快再复习，答对拉长间隔），形成「主动回忆 + 即时反馈 + 遗忘曲线」闭环。

## 需求参数（已确认）

| 项 | 值 |
|----|-----|
| 复习形态 | 逐题简答（主动回忆），非自评 |
| 出题 | 每个知识点转成一道简答题 |
| 出题时机 | 预生成（每日任务生成时） |
| 判分 | 混合：先规则（关键词/相似度），拿不准走 AI |
| 交互 | 逐题作答 → 判分 → 展示标准答案 + 对错 → 下一题 |
| 答错处理 | 展示标准答案 → 再答一次巩固 |
| 掌握度 | 答对 `next_review_at` 变长，答错变短，驱动遗忘曲线 |

## 第一部分：出题（预生成）

改造 `task_gen.py` 的 `_gen_knowledge`：选定知识点后，把每个知识点转成一道简答题，存进 `task.content`。

### 新建出题函数

新建 `backend/app/services/knowledge_quiz.py`：

```python
def generate_knowledge_questions(db, points: list[dict], subject: str) -> list[dict]:
    """把知识点列表转成简答题，返回 [{id, question, answer, keywords}]。
    points 每项含 id / content / category。任何异常回退「知识点原文 + 空题目」。"""
```

- AI 可用时：注入知识点列表，让 AI 对每个知识点返回 `{question, answer, keywords}`（`keywords` 是判分关键词数组）
- AI 失败 / fake provider：回退为「知识点原文 + 空 question」，判分退化为「答对 = 复述出知识点关键词」或直接标记待人工

### `_gen_knowledge` 改造

选定 `new_pts + due_pts` 后，调 `generate_knowledge_questions` 转成问答，`task.content` 存：

```json
[{"id": 1, "content": "圆的周长公式", "category": "公式", "question": "圆的周长怎么算？", "answer": "周长 = π × 直径", "keywords": ["π", "直径", "周长"]}, ...]
```

## 第二部分：判分（混合）

新建判分逻辑（可放在 `knowledge_quiz.py` 或复用 `mastery.grade_answer`）：

1. **规则判分**（优先）：用 `mastery.grade_answer(user_answer, expected_answer, question_type='open')` —— 关键词命中 ≥60% 判对。
2. **AI 兜底**：规则判分「拿不准」时（如关键词命中 <60% 但答案不短、可能同义改写），交给 LLM 判「孩子的答案是否回答了问题」。

判分「拿不准」的判定：关键词命中率落在中间区间（如 0 < 命中 < 0.6）且答案非空时，走 AI 复核。

## 第三部分：交互（前端）

改造 `renderKnowledge`：

- 逐题显示「题目」，孩子输入答案（textarea/input）
- 提交 → 后端判分 → 返回 `{is_correct, answer(标准答案)}`
- 展示对/错 + 标准答案
- 答错 → 展示标准答案后，让孩子「再答一次」（巩固），重答结果只记最终一次，避免刷高掌握度
- 全部答完 → 提交，结果落掌握度

## 第四部分：落掌握度（遗忘曲线闭环）

`tasks.py` 的 `knowledge-review` 接口改造：

- 接收孩子每题的**最终判定结果**（答对/答错，而非「记住了/还不熟」自评）
- 对每题：`record_attempt(db, user_id, 'knowledge', knowledge_point_id, is_correct)`
  - 答对 → `next_review_at` 变长（`next_review_after(streak)`）
  - 答错 → `next_review_at` 变短（streak 归零，间隔回到第 1 档）
- 写回 `task.content`（记录每题对错），提交待家长确认

## 数据模型

无需新表。`KnowledgeMastery` 已有 `attempts` / `mastery` / `next_review_at`（上一阶段已建）。

## 接口

```
# 出题（预生成内部调用，不对外）
generate_knowledge_questions(db, points, subject) -> [{id, question, answer, keywords}]

# 判分（新增或改造）
POST /api/tasks/{task_id}/knowledge-review
  body: {user_id, answers: [{id, user_answer}]}
  → 后端对每题判分（混合），落掌握度，返回 {results: [{is_correct, answer}], ...}
```

## 明确不做（本阶段）

- 不做选择题/判断题形态（保持简答）
- 不做自适应出题（难度/题型不动态调整）
- 不做语音作答（打字即可）
- 判分 AI 兜底若未配置 AI，则纯规则判分（关键词命中），不阻塞

## 测试

- `backend/tests/test_knowledge_quiz.py`（新建）：
  - `generate_knowledge_questions`：AI 可用转简答；fake 回退
  - 混合判分：关键词命中判对、命中不足判错、中间态走 AI（mock）
- `backend/tests/test_task_gen.py`（扩展）：`_gen_knowledge` 的 content 结构含 question/answer/keywords
- `backend/tests/test_tasks_router.py`（扩展）：`knowledge-review` 接收 answers 判分落掌握度
- 前端 `node --check`

## 后续

- 判分 AI 兜底的「拿不准」阈值可配置化
- 知识点出题质量可随难度档位扩展（复用 `difficulty_{subject}` 配置）
