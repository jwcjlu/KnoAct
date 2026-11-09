# 听写出词：遗忘曲线动态挑词 + 掌握度护栏 + 孩子级可配置 设计

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

1. **遗忘曲线动态挑词**：不再「当前课盲取前 N」。
2. **学过的词反复练习**：掌握度驱动的复习，词随遗忘曲线滚动，而非「新课/旧课」二分锁死。
3. **护栏防堵死**：到期词上限 + 新词下限，保证进度能滚动、顽固错词不无限占位。
4. **孩子级可配置**：每天听写总量、到期上限比例、新词下限比例，家长端按孩子配置。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 取词范围 | 孩子绑定教材里所有 `audit_status=approved` 的课的生词（跨课全量） |
| 排序 | 到期词优先，掌握度低者优先（`mastery` 升序） |
| 到期词上限 | 按比例 `due_cap`（默认 0.5，即最多占总数一半） |
| 新词下限 | 按比例 `new_floor`（默认 0.3，即至少 30% 名额留给未考过的词） |
| 掌握移出 | `mastery >= 0.9`（`is_mastered` 门槛，复用现成）视为已掌握，不进日常听写 |
| 补位 | 到期 + 新词未凑满总量时，用「已学未掌握词」按 `mastery` 升序补位；仍凑不满不硬补（保留现状语义） |
| 配置粒度 | 孩子级 `ChildConfig`（新增写入口），回落全局 `ModelConfig`，再回落默认 |
| 废弃键 | `task_new_ratio`（旧「新课固定名额」）废弃，由 `due_cap` + `new_floor` 取代 |

## 取词算法（重写 `_gen_dictation`）

**输入**：孩子 `user_id`、学科 `subject`、当日总量 `count`、比例 `due_cap` / `new_floor`。

**候选池**：孩子绑定教材（`UserDocument`）下、`audit_status=approved`、`subject` 匹配的所有 `Lesson` 的全部 `WordBank`，按学科过滤。

**分类**（对每个词，联 `WordMastery`，无记录视为「新词」）：

- **到期词**：`WordMastery.next_review_at <= now`。
- **新词**：无 `WordMastery` 记录，或 `attempts == "[]"`（从未考过）。
- **已掌握词**：`mastery >= 0.9` → 排除（不进日常，仅等长间隔到期）。
- **补位词**：其余（已学过、未掌握、未到期）。

**填充顺序（数量用 `ceil`/`floor` 保证整数）**：

```
count   = 当日总量（task_dictation_count_{subject}，默认 7）
due_n   = ceil(count * due_cap)          # 到期词上限名额
new_n   = max(1, floor(count * new_floor))  # 新词下限名额（至少 1）

1. 取到期词（按 mastery 升序）最多 due_n 个
2. 取新词（按 WordBank.id 升序）目标 new_n 个
3. 若 1+2 < count，用补位词（mastery 升序）补到 count
   —— 但「已掌握(mastery>=0.9)」永不进入任何一步
4. 仍凑不满 count 则不硬补（保持现状「凑不满不补」语义）
```

**输出**：`Task` 的 `content` 仍为 `[{"id", "word", "extra"}]` JSON（结构不变，前端 `parseDictContent` 无需改）。`detail` 文案更新为体现三类构成，例如 `今日听写 · 7 个（到期复习 4 + 新课 2 + 巩固 1）`。

### 顽固错词降频（护栏内在保证）

- 连续答错的词 `mastery` 低，落在「到期词」档，受 `due_n` 上限约束；不会无限占位。
- 新词下限 `new_n` 始终保留，进度永不卡死。
- 长期未掌握的词最终 `mastery` 也难达 0.9，但只在到期档出现，且每天名额固定，不挤压新词。

## 配置项（比例 + 孩子级）

### 键定义

| 键名 | 类型 | 默认 | 含义 |
|------|------|------|------|
| `task_dictation_count_{subject}` | int | 7 | 每日听写总量（保留现状，按科） |
| `task_dictation_due_cap` | float 0~1 | 0.5 | 到期复习词上限比例 |
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
  - 新增 `task_dictation_due_cap`（输入 0~1，步长 0.1，提示「到期复习词最多占多少比例」）。
  - 新增 `task_dictation_new_floor`（输入 0~1，步长 0.1，提示「至少留多少比例给新课生词」）。
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

1. **到期优先 + 上限**：构造 > due_cap 比例的到期词，验证只取 due_n 个。
2. **新词下限**：构造到期词占满场景，验证新词仍至少进 new_n 个。
3. **掌握移出**：`mastery>=0.9` 的词不进入任何一步。
4. **补位**：到期 + 新词不足 count 时，用低 mastery 词补位。
5. **凑不满不补**：候选不足时 total < count，不硬凑。
6. **跨用户隔离**：B 孩子的到期词不混入 A 的听写（复用现有 `test_dictation_isolates_due_words_across_users` 语义）。
7. **配置覆盖**：孩子级 `ChildConfig` 值覆盖全局 `ModelConfig` 默认；`due_cap`/`new_floor` 越界夹取到 0..1。
8. **废弃键**：删除 `task_new_ratio` 后，旧值不再影响取词。

## 明确不做（本阶段）

- 不改 `_gen_review`（`task_type=review`，本课到期词复习，语义独立）。
- 不改 `WordMastery` / `WordBank` / 模型 schema（现有 `mastery` / `attempts` / `next_review_at` 够用）。
- 不改 `select_words`（`scheduler.py`，仅被已废弃的实时听写接口引用，暂不动，留待后续清理）。
- 不改前端 Flutter 学生端（`content` 结构不变，`parseDictContent` 无感）。
- 不做听写词的全量落库 / 历史回放。
