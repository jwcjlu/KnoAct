# 基础知识出题：已学课范围 + 无限循环取知识点 设计

日期：2026-11-10
状态：已确认（brainstorming），待实现
范围：`task_type=knowledge` 每日基础知识任务的**知识点选取算法**重写（仅 `_gen_knowledge`）。出题、判分、配置键、家长端 UI 均不动。

## 背景与问题

当前 `_gen_knowledge`（`backend/app/services/task_gen.py:133`）的取知识点规则与听写旧算法同构，存在同样的「锁死当前课」缺陷：

```python
new_pts = db.query(KnowledgePoint).filter_by(lesson_id=lesson.id) \
    .order_by(KnowledgePoint.id).limit(new_ratio).all()   # 当前课按 id 盲取前 N（硬编码 5）
due_pts = ... KnowledgeMastery.next_review_at <= now, lesson_id != lesson.id ...  # 旧课到期
pts = new_pts + due_pts
```

且 `count`（`task_knowledge_count`）默认 5、`new_ratio` 硬编码 5，导致 `count - new_ratio = 0`：**旧课到期知识点默认一个都不取**，遗忘曲线对「基础知识」形同虚设。

后果：孩子上到第 4 课、十天不更新新课时，每天的「基础知识」任务永远考第 4 课按 id 前 5 个知识点，从不推进、不看掌握度、到期知识点排不进来。

## 目标（已确认）

1. **已学课范围**：候选池 = 当前课及之前所有 `approved` 课的知识点（向前扩展、未学课不进池、已学课永不踢出）。
2. **无限循环**：已掌握的知识点永不移出，靠轮转档周期回来。
3. **内置护栏**（不暴露配置）：到期+错最多占一半、新知识点至少 1 个，防顽固知识点堵死。
4. **改动最小化**：出题（`generate_knowledge_questions`）、判分（`grade_knowledge_answer`）、配置键（复用 `task_knowledge_count`）、家长端 UI 均不动。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 取知识点范围 | `current_lesson_id` 及之前的、`audit_status=approved` 的课的知识点（已学课范围） |
| 排序 | 到期 → 错 → 新 → 轮转，四档按序 |
| 无限循环 | 已掌握（`mastered=True`）永不移出，靠轮转档回来 |
| 护栏 | 内置：到期+错最多 `ceil(count/2)`；新知识点至少 `max(1, ...)` 个；剩余给轮转；凑不满不硬补 |
| 「错」档判定 | `attempts` JSON 数组**最后一个元素是 False**（最近一次答错）；`KnowledgeMastery` 无 `mistake_count`，用此近似 |
| 数量 | `count = task_knowledge_count`（默认 5，沿用现有键，孩子级可配，无需新增） |
| 出题 / 判分 | 不动 |
| 配置 / UI | 不动 |

## 取知识点算法（重写 `_gen_knowledge` 的取点部分）

**输入**：`db`、`lesson`（当前课）、`user_id`、`count`。

**候选池**：孩子绑定教材（`UserDocument`）下、`audit_status=approved`、`subject` 匹配、`Lesson.id <= lesson.id` 的所有 `KnowledgePoint`，按 `KnowledgePoint.id` 升序。

**分类**（联 `KnowledgeMastery`，`knowledge_point_id` + `user_id`；无记录视为「新」）：

- **到期**：`next_review_at` 存在且 `<= now`
- **错**（未到期）：`attempts` 解析为数组且最后一个元素为 `False`
- **新**：无 `KnowledgeMastery`，或 `attempts` 解析为空数组
- **轮转**：其余（已考过、最近一次答对、未到期）——含 `mastered=True` 的

**填充（内置护栏）**：

```
count  = 当日总量（task_knowledge_count，默认 5）
review_n = ceil(count / 2)          # 到期 + 错 合计上限
new_n    = max(1, ...)              # 新知识点下限（至少 1）

1. 取到期（按 next_review_at 升序），最多 review_n
2. 若不足 review_n，取错（最近一次答错、未到期）补到 review_n
3. 取新（按 id 升序）目标 new_n
4. 若 1+2+3 < count，用轮转（按 next_review_at 升序，NULL 视为最早）补满 count
5. 凑不满不硬补
6. picked = picked[:count]（兜底防超）
```

**输出**：选中的 `pts` 列表传给现有的 `generate_knowledge_questions(db, raw, subject)`（`raw = [{id, content, category}]`），出题、落库、`Task` 的构造**保持现状不变**。`detail` 文案的「新课 X + 复习 Y」改成反映四档构成。

## 变更文件

| 文件 | 改动 |
|------|------|
| `backend/app/services/task_gen.py` | 重写 `_gen_knowledge` 的取点部分（候选池 + 四档 + 护栏）；`generate_tasks_for_user` 中 `_gen_knowledge` 调用改为只传 `count`（去掉硬编码 `new_ratio=5`） |
| `backend/tests/test_task_gen.py` | 新增/更新：已学课范围、四档优先级、护栏、轮转含已掌握、凑不满不补、跨用户隔离 |

## 测试要点

1. **已学课范围**：`Lesson.id > 当前课` 的知识点不进池。
2. **四档优先级**：到期 > 错 > 新 > 轮转。
3. **护栏**：到期+错不超过 `ceil(count/2)`；新知识点至少 1 个。
4. **无限循环**：`mastered=True` 的知识点在到期/错/新不足时按轮转回来。
5. **凑不满不补**：候选不足时 `total < count`。
6. **跨用户隔离**：B 孩子的到期知识点不混入 A 的任务。
7. **出题/判分回归**：`generate_knowledge_questions` / `grade_knowledge_answer` 行为不变（fake provider 下题目仍为空字符串，字段仍存在）。

## 明确不做（本阶段）

- 不改出题缓存/去重（Q2=b，保持实时调 AI）。
- 不改判分（Q4=a，关键词 ≥0.6 + AI 兜底保持现状）。
- 不加新配置键（Q3=b，复用 `task_knowledge_count`）。
- 不改家长端 UI。
- 不改 `KnowledgeMastery` / `KnowledgePoint` 模型 schema（不新增 `mistake_count`，「错」档用 `attempts` 末位近似）。
- 不改 `_gen_dictation` / `_gen_review` / `_gen_listening`。
