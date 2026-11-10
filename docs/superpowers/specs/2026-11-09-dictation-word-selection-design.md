# 听写出词：已学课范围 + 无限循环复习 + 孩子级可配置 设计

日期：2026-11-09
状态：已确认（brainstorming），待实现
范围：`task_type=dictation` 每日听写任务的**生词选取算法**重写，以及听写参数的孩子级配置化（后端 + 家长端 UI）。

## 背景与问题

当前 `_gen_dictation`（`backend/app/services/task_gen.py:37`）的取词规则是：

```python
new_words = db.query(WordBank).filter_by(lesson_id=lesson.id) \
    .order_by(WordBank.id).limit(new_ratio).all()          # 当前课按 id 盲取前 N 个
due_words = ... WordMastery.next_review_at <= now ...      # 其他课到期词
words = new_words + due_words                              # 凑不满不补
```

两个缺陷：

1. **新课词盲取**：按 `WordBank.id` 升序取前 `new_ratio`（默认 5）个，完全不看该孩子的掌握度（`WordMastery.mastery` / `attempts`）。已经会写的字反复考，真正该巩固的字迟迟轮不到——与「听写为了巩固字形、驱动遗忘曲线」的目的矛盾。
2. **锁死「当前课」**：新课只从当前课取、复习只从「其他课」取，各锁一方；进度跳课时，中间课的未掌握词既不是「当前课新词」又没过到期线，被两不管。

附加发现：家长端「学习配置」当前写的是**全局 `ModelConfig`**（`POST /api/config`），但后端读的是 `get_child_config_int`（**孩子级 `ChildConfig` 优先**）。UI 标注「仅对当前孩子生效」，实际写全局、影响所有孩子，且孩子级无写入口。本设计一并修复。

## 目标（已确认）

1. **不再「当前课盲取前 N」**：生词池覆盖孩子「已学到」的所有课，向前扩展、向后循环。
2. **学过的词反复练习（无限循环）**：所有词永不移出，已掌握的词也会周期性轮转回来。
3. **优先级 + 护栏防堵死**：到期词/错词/新词按序优先，同时设护栏保证新词能进、老词能轮转、顽固错词不无限占位。
4. **孩子级可配置**：每天听写总量、各档名额/比例护栏，家长端按孩子配置。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 取词范围 | `current_lesson_id` 及之前的、`audit_status=approved` 的课的生词（**已学课范围**，向前扩展、未学课不进池、已学课永不踢出） |
| 排序 | 到期词 → 错词 → 新词 → 轮转补位，四档按序 |
| 无限循环 | **所有词永不移出**（B2）；已掌握的词靠「轮转补位」周期性回来 |
| 到期词上限 | 比例 `due_cap`（默认 0.5）——到期词最多占总量一半，防顽固错词无限占位 |
| 新词下限 | 比例 `new_floor`（默认 0.3）——每天至少留 30% 名额给未考过的词（含刚进池的新课词），保证进度滚动 |
| 补位 | 到期+错词+新词未凑满总量时，用「已考过、没到期、没错」的词按**最久没考**补位；仍凑不满不硬补 |
| 配置粒度 | 孩子级 `ChildConfig`（新增写入口），回落全局 `ModelConfig`，再回落默认 |
| 废弃键 | `task_new_ratio`（旧「新课固定名额」）废弃，由 `due_cap` + `new_floor` 取代 |

## 取词算法（重写 `_gen_dictation`）

**输入**：孩子 `user_id`、学科 `subject`、当日总量 `count`、比例 `due_cap` / `new_floor`。

**候选池**：孩子绑定教材（`UserDocument`）下、`audit_status=approved`、`subject` 匹配、且 **`id <= current_lesson_id`**（即「当前课及之前」）的所有 `Lesson` 的全部 `WordBank`。

> 注意：「当前课及之前」按 `Lesson.id` 升序截断（`Lesson.id <= current_lesson.id`）。这是「已学课」范围的判定，与孩子进度（`LearningProgress.current_lesson_id`）解耦——`_gen_dictation` 的入参 `lesson` 即当前课，直接用它做上界。

**分类**（对每个词，联 `WordMastery`，无记录视为「新词」）：

- **到期词**：`WordMastery.next_review_at <= now`。
- **错词**：`WordMastery.mistake_count > 0` 且未到期。
- **新词**：无 `WordMastery` 记录，或 `attempts == "[]"`（从未考过）。
- **轮转词**：其余（已考过、没错、未到期）——含已掌握（`mastery >= 0.9`）的词，靠这一档循环回来。

**填充顺序（数量用 `ceil`/`floor` 保证整数）**：

```
count   = 当日总量（task_dictation_count_{subject}，默认 7）
due_n   = ceil(count * due_cap)              # 到期词上限名额
new_n   = max(1, floor(count * new_floor))   # 新词下限名额（至少 1）

1. 取到期词（按 next_review_at 升序）最多 due_n 个
2. 取错词（按 mistake_count 降序）补到 due_n 之内或紧随其后
3. 取新词（按 WordBank.id 升序）目标 new_n 个
4. 若 1+2+3 < count，用轮转词（按最久没考排）补到 count
5. 仍凑不满 count 则不硬补（保持现状「凑不满不补」语义）
```

> 优先级语义：到期词与错词同属「复习优先」，合计受 `due_n` 上限约束；新词受 `new_n` 下限保障；剩余名额给轮转词。已掌握的词**不排除**，落在第 4 档轮转补位。

**输出**：`Task` 的 `content` 仍为 `[{"id", "word", "extra"}]` JSON（结构不变，前端 `parseDictContent` 无需改）。`detail` 文案体现构成，例如 `今日听写 · 7 个（复习 3 + 新课 2 + 轮转 2）`。

### 轮转补位的「最久没考」判定

`WordMastery` 无独立的「上次考过时间」字段。用 `next_review_at` 作为近似：轮转词里 `next_review_at` 越早（或为 NULL 表示从未有复习安排）越先。已掌握词的 `next_review_at` 因遗忘曲线拉长而落在远期，会在「新词/错词/到期词都不足」时按此序轮转回来，实现 B2 的无限循环。

### 护栏防堵死（内在保证）

- 到期词 + 错词合计受 `due_n` 上限，顽固错词不无限占位。
- 新词下限 `new_n` 始终保留，进度滚动、新课词能进。
- 已掌握词靠轮转档回来，不因「已掌握」而永久消失。

## 配置项（比例 + 孩子级）

### 键定义

| 键名 | 类型 | 默认 | 含义 |
|------|------|------|------|
| `task_dictation_count_{subject}` | int | 7 | 每日听写总量（保留现状，按科） |
| `task_dictation_due_cap` | float 0~1 | 0.5 | 到期+错词复习上限比例 |
| `task_dictation_new_floor` | float 0~1 | 0.3 | 新词下限比例 |
| ~~`task_new_ratio`~~ | — | — | 废弃，改用 `due_cap` + `new_floor` |

### 读取（后端）

新增 `services/child_config.py` 的 `get_child_config_float(db, child_id, key, fallback)`，与现有 `get_child_config_int` 同构（孩子级 > 全局 > 默认），并做 `0..1` 夹取。

### 写入（新增孩子级入口，修复「写全局」bug）

- 新增 `PUT /api/learning/preferences` 的扩展（或新端点 `PUT /api/learning/dictation-config`）：
  - Body：`{ user_id, task_dictation_count_语文?, task_dictation_count_英语?, task_dictation_due_cap?, task_dictation_new_floor? }`
  - Auth：`require_role("parent")` + 孩子归属校验（`child.parent_id == user.id`）
  - 仅对传了的键 `set_child_config_str(db, user_id, key, value)` upsert 到 `ChildConfig`。
  - 与 `dictation_input_mode` 走同一 `ChildConfig` 存储，家长端统一读取回显。
- 保留 `GET /api/config`（全局 ModelConfig）作为默认值来源，不动其既有语义。

## 家长端 UI（`parent-web/app.js`）

- 在 `renderLearningConfigTab()` 的「学习配置」面板：
  - 移除 `task_new_ratio` 行。
  - 新增 `task_dictation_due_cap`（输入 0~1，步长 0.1，提示「到期/错词复习最多占多少比例」）。
  - 新增 `task_dictation_new_floor`（输入 0~1，步长 0.1，提示「至少留多少比例给未听写过的生词」）。
  - `task_dictation_count_语文/英语` 保留。
- `saveLearningConfig()` 拆分：听写相关键（含 count / due_cap / new_floor）改走**孩子级**新端点；其余键维持 `POST /api/config`（全局）。
- 回显：进入 Tab 时读孩子级值（新端点 GET，或复用 `get_child_config_*` 暴露的 GET），孩子级无值时显示全局/默认。

## 变更文件

| 文件 | 改动 |
|------|------|
| `backend/app/services/task_gen.py` | 重写 `_gen_dictation` 取词（候选池 + 三分类 + 护栏填充）；`generate_tasks_for_user` 读新配置键 |
| `backend/app/services/child_config.py` | 新增 `get_child_config_float` |
| `backend/app/routers/learning.py` 或新 router | 孩子级配置写入口（GET + PUT） |
| `backend/app/routers/tasks.py` | （仅当 detail 文案 / content 结构有依赖时核对，预期无改） |
| `parent-web/app.js` | 配置 UI 增删键 + `saveLearningConfig` 分流 |
| `backend/tests/test_task_gen.py` | 更新/新增：新取词行为、护栏、跨用户隔离、配置覆盖 |
| `backend/tests/test_child_config.py` | 新增 `get_child_config_float`、孩子级写读 |

## 测试要点

1. **已学课范围**：池只含 `current_lesson_id` 及之前的课，未学课（`Lesson.id > 当前课`）的词不进池。
2. **到期+错词优先 + 上限**：构造 > due_cap 比例的到期词/错词，验证合计只取 due_n 个。
3. **新词下限**：构造到期词占满场景，验证新词仍至少进 new_n 个。
4. **轮转补位 + 无限循环**：已掌握（`mastery>=0.9`）的词**不移出**，在到期/错词/新词不足时按「最久没考」补位回来。
5. **凑不满不补**：候选不足时 total < count，不硬凑。
6. **跨用户隔离**：B 孩子的到期词不混入 A 的听写（复用现有 `test_dictation_isolates_due_words_across_users` 语义）。
7. **配置覆盖**：孩子级 `ChildConfig` 值覆盖全局 `ModelConfig` 默认；`due_cap`/`new_floor` 越界夹取到 0..1。
8. **废弃键**：删除 `task_new_ratio` 后，旧值不再影响取词。

## 明确不做（本阶段）

- 不改 `_gen_review`（`task_type=review`，本课到期词复习，语义独立）。
- 不改 `WordMastery` / `WordBank` / 模型 schema（现有 `mastery` / `attempts` / `next_review_at` / `mistake_count` 够用；「上次考过时间」用 `next_review_at` 近似，不新增字段）。
- 不改 `select_words`（`scheduler.py`，仅被已废弃的实时听写接口引用，暂不动，留待后续清理）。
- 不改前端 Flutter 学生端（`content` 结构不变，`parseDictContent` 无感）。
- 不做听写词的全量落库 / 历史回放。
- 不新增「学习进度 vs 复习进度」两个独立字段（本阶段生词池只按 `current_lesson_id` 判定「已学课」范围）。
