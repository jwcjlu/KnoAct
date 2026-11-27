# 知识点复习模块（遗忘曲线 SRS）

日期：2026-11-27  
状态：设计已定稿，待实现  
范围：后端新表 + `/api/knowledge-review/*` + 自动入队挂钩（mastery / 进度）+ `task_gen`；`parent-web` 队列管理（复用已有进度面板）；Flutter `student-app` 复习会话与每日任务。  
非范围：生词 SRS 合并、旧版 `frontend/`、复习方案容器、严格探究证据门槛、SM-2/Anki、重做进度 UI。

## 背景与目标

学习需要间隔复习。仓库已有半套遗忘曲线与家长「学习进度」调节（`LearningProgress` + `/api/progress/adjust`）。缺口是：

1. **没有按进度驱动的知识点复习队列**——达标点不会自动进入有频率的巩固。  
2. 现有 `/api/review/questions` 按学科随意抽点 + AI 出题，**不读调度与进度**。  
3. `_gen_review` 只服务生词；知识点掌握后缺少遗忘曲线巩固入口。

目标：在**学习进度范围内**，已达标（v1：mastery）的知识点**自动入队**；家长调进度向前时批量补齐；按遗忘曲线到期；孩子用「轻量自测 → 忘了再展开」复习。家长用现有面板调进度，复习页只管暂停/移出。

对齐学习第一性原理：

- 本模块属**原料层自动化之后的巩固**（想通 → 再间隔检索），**不得宣称**复习完 = 新理解。  
- v1 门槛用 `KnowledgeMastery.mastered` / `mastery>=0.9`；严格 guide/trap 证据链列为后续。  
- 家长端给**决策**（进度调到哪、队里有什么、下次到期），不用掌握度百分比当考核。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 复习对象 | 仅知识点（`KnowledgePoint`），不含生词 |
| 入队方式 | **自动入队**（达标且进度内）；家长调进度**向前**时批量补齐；**不**以家长手选为主路径 |
| 进度范围 | 同教材内，KP 所属课在课序上 `≤` 当前 `LearningProgress.current_lesson_id`（课序 = 该书 `Lesson.id` 升序，与现 `lesson_index` 一致） |
| 进度调回 | **不**自动移出/暂停已在队项；仅家长手动 pause/remove |
| 学习进度 UI | **复用**现有家长「学习进度」面板 / `/api/progress/adjust`（及 `advance` 推进） |
| 入队门槛 | v1：`mastered==True` 或 `mastery>=0.9`；未达标不入队；超前于进度不入队 |
| 孩子做什么 | 轻量混合：有题先作答；答错/「忘了」再展开讲解；无题则三档自评 |
| 触达 | 每日任务 + 独立复习模块（同一套 complete 逻辑） |
| 间隔动作 | 记得升档；有点忘同档再测；忘了回第 0 档（1 天） |
| 出题 | 尽力复用已有题 → `generate_knowledge_questions` → 仅自评（见 §2.3；**不**假设 `Question.knowledge_point_id` FK） |
| 客户端 | `parent-web` + Flutter `student-app`（新 feature，勿与现有 `knowledge` 基础知识页混名） |
| 架构 | **独立复习队列表**，与 `KnowledgeMastery` 解耦 |
| 每日任务 | **按学科拆分** `kp_review`，对齐 `(user_id, subject, date, task_type)` |
| 任务结案 | 会话内到期条全部 complete → `submit_status=approved`（v1 **不经家长确认**） |
| 任务可见性 | 生成时 `content_status=published`（孩子端 `list_tasks` 只见 published） |
| 学年桶 | 一律 `resolve_bucket_id(db, user_id, …)` 的 **active 桶**；门槛/队列/due 同桶 |
| 暂停语义 | 冻结：`next_review_at` 不变；paused 不进 due；恢复后若已过期则立即到期 |
| 每日上限 | `task_kp_review_count`，默认 **6**，**每科各自**截断；`/due` 与 `task_gen` 共用选集函数 |
| 快照 vs 暂停 | 快照项被 pause/remove 后视为已了结，任务仍可结案（§2.6） |
| 幂等「自然日」 | 与现网一致用 **UTC 日期**（`datetime.utcnow().date()`） |

## 成功标准

1. 达标且进度内的点自动入队；家长进度前推后，新范围内已达标点被补入队。  
2. 家长能暂停 / 恢复 / 移出队列项，并用现有面板调整学习进度。  
3. 到期项出现在当日 `kp_review` 任务与复习模块 `/due`。  
4. `complete` 按三档（及客观题对错覆盖）正确更新 `interval_index` / `next_review_at`。  
5. 完成文案不宣称「已掌握 / 已理解」。  
6. 生词 `review` 任务与本模块并存、互不吞并。

---

## §1 数据模型与调度

### 1.1 新表 `knowledge_review_items`

| 字段 | 类型 / 含义 |
|------|-------------|
| `id` | PK |
| `user_id` | 孩子 |
| `knowledge_point_id` | FK → knowledge_points |
| `bucket_id` | 学年桶；入队时**必写** `resolve_bucket_id` 得到的 active 桶 |
| `enrolled_by` | 可空；进度前推补齐时写家长 id；答题达标自动入队可为 `null`（系统） |
| `enroll_source` | `mastery` \| `progress_adjust`（可选，便于审计；也可用 `enrolled_by` 空/非空区分） |
| `enrolled_at` | 入队时间 |
| `status` | `active` \| `paused` \| `removed` |
| `interval_index` | 0-based，对应 `INTERVALS` |
| `next_review_at` | 下次到期 |
| `last_result` | `remember` \| `fuzzy` \| `forgot`，可空 |
| `updated_at` | 最近一次结果时间 |

约束：

- `(user_id, knowledge_point_id, bucket_id)` 普通唯一约束（兼容 MySQL）；**优先复活同一行**（`removed`→`active`），避免 partial unique。  
- 重入队：档位从 0、`next_review_at=now+1day`。

### 1.2 学年桶解析

- 自动入队 / `queue` / `due` / `complete` / `task_gen` **一律**先 `bid = resolve_bucket_id(db, user_id, None)`。  
- 门槛查 `KnowledgeMastery` 时带同一 `bucket_id`；队列读写过滤同一 `bucket_id`。  
- 无 active 桶时跳过自动入队（不写跨桶数据）。

### 1.3 与 `KnowledgeMastery` / 进度的分工

| 职责 | 归属 |
|------|------|
| 是否「够格」 | 同桶 `KnowledgeMastery`（v1：`mastered` 或 `mastery>=0.9`） |
| 是否「该学过了」 | `LearningProgress`：KP 的 `lesson` 与进度同 `document_id`，且课序 ≤ 当前课 |
| 是否在复习计划中、多久复习一次 | `knowledge_review_items` |
| 听写/生词到期 | 继续 `WordMastery` + 现有 `_gen_review` |

本模块**不**用 `KnowledgeMastery.next_review_at` 驱动到期。

**进度范围内**判定（`in_progress_scope(user_id, kp)`）：

1. KP 无 `lesson_id` → **不入队**（无法锚定教材进度）。  
2. 取该课的 `document_id` + `subject`，读 `get_progress(user_id, document_id, subject)`。  
3. 无进度或 `current_lesson_id` 空 → 视为未开课，**不入队**。  
4. 该书该科按 `Lesson.id` 升序；KP 课的下标 ≤ 当前课下标 → 在范围内。

### 1.4 自动入队规则

共享内部函数 `try_enroll(user_id, knowledge_point_id, *, enrolled_by=None, source=...)`：

- 条件全满足才写入/复活：同桶达标 + `in_progress_scope` + 当前非 active/paused。  
- 成功时：`status=active`，`interval_index=0`，`next_review_at = now + 1 day`，`bucket_id=bid`。  
- 已在 active/paused → no-op。  
- `removed` → 复活并从 0 档重来。

**触发 A — 达标瞬间**（挂在 `record_attempt` 之后，仅 `target_type=knowledge`）：

- 若本次后刚达标（或已达标），调用 `try_enroll(..., source=mastery)`。  
- 超进度 / 未达标 → 静默跳过。

**触发 B — 进度前推**（挂在 `POST /api/progress/adjust` 与 `advance_lesson` 成功写库之后）：

- 比较调整前后的当前课下标；仅当**新下标 ≥ 旧下标**（前推或不动）时执行补齐。  
- 扫描该 `document_id` 上课序 ∈ (旧下标, 新下标]（若旧为空则 ≤ 新下标）的全部 KP，对已达标者 `try_enroll(..., enrolled_by=操作家长, source=progress_adjust)`。  
- **往后调**（新下标 < 旧下标）：**不**调用补齐，也**不**自动 pause/remove。  
- `adjust` 响应可附 `review_enrolled_count`（新增入队条数），供家长端 toast。

### 1.5 三档 → 间隔

沿用 `services/scheduler.py` 的 `INTERVALS = [1, 2, 4, 7, 15, 30, 60]`。

| 结果 | 来源 | 动作 |
|------|------|------|
| `remember` | 自评「记得」或客观题答对 | `interval_index = min(i+1, len-1)`，`next_review_at = now + INTERVALS[new]` |
| `fuzzy` | 自评「有点忘」 | `interval_index` 不变，`next_review_at = now + INTERVALS[i]`（同档全长） |
| `forgot` | 自评「忘了」或客观题答错 | `interval_index=0`，`next_review_at = now + 1 day`；UI 进入展开讲解 |

客观题若提交了作答：服务端判分后**覆盖**客户端自评（对→`remember`，错→`forgot`）。

### 1.6 到期选集

- 今日到期：`status=active` 且 `next_review_at <= now`。  
- **每科**上限 `task_kp_review_count`（默认 6）：先按 `KnowledgePoint.subject` 分组，组内按 `next_review_at` 升序（次级 `interval_index` 升序）截断；超出仍保持到期，次日优先，不丢队。  
- `GET /due` 与 `task_gen` **共用同一选集函数**（同桶、同排序、同每科上限）；`due` 可带 `?subject=` 过滤，不传则返回各科截断后的并集。  
- `status=paused` 的项**永不**进入 due / 新任务快照。

### 1.7 暂停 / 恢复

| 操作 | 行为 |
|------|------|
| `pause` | `status=paused`；**不改** `next_review_at`（冻结时钟，不顺延）。允许对已进当日任务快照的项操作。 |
| `resume` | `status=active`；若 `next_review_at <= now`，下一次 due/任务即出现；未到期则按原时间 |
| 与当日任务 | 见 §2.6：快照内项被 pause/remove/删点后，**不再要求**对其 complete 才能结案 |

---

## §2 API 与任务生成

旧 `/api/review/questions`、`/api/review/submit` **不作为**本模块主路径（可后续废弃或转调）。新前缀：`/api/knowledge-review`。

### 2.1 家长 API 与进度挂钩

| 方法 | 路径 | 作用 |
|------|------|------|
| `GET` | `/api/knowledge-review/queue?user_id=` | 队列列表（含档位、下次到期、最近结果、来源） |
| `POST` | `/api/knowledge-review/item/{id}/pause` | 暂停（§1.7） |
| `POST` | `/api/knowledge-review/item/{id}/resume` | 恢复（§1.7） |
| `POST` | `/api/knowledge-review/item/{id}/remove` | 软删 `removed` |

进度调节（**已有，扩展行为**）：

| 方法 | 路径 | 本模块增量 |
|------|------|------------|
| `POST` | `/api/progress/adjust` | 前推后调用 §1.4 触发 B；响应增加 `review_enrolled_count` |
| `POST` | `/api/progress/advance` | 推进成功后同样触发 B（`enrolled_by` 可为 null） |
| `GET` | `/api/progress/overview` | 不变；家长仍用此面板调进度 |

内部服务：`try_enroll` / `enroll_due_to_progress(...)` **不**作为家长主 UI 的手选入队入口。  
可选保留 `POST /api/knowledge-review/enroll` 仅供运维/测试；**v1 家长端不暴露「可加入」多选**。

### 2.2 孩子 API

| 方法 | 路径 | 作用 |
|------|------|------|
| `GET` | `/api/knowledge-review/due?user_id=` | 今日到期 + 每条题目载荷 |
| `POST` | `/api/knowledge-review/complete` | 提交单条结果并推进间隔 |

`complete` 请求体：

```json
{
  "user_id": 1,
  "item_id": 12,
  "result": "remember|fuzzy|forgot",
  "question_id": null,
  "student_answer": null,
  "duration_ms": 8000
}
```

行为：

- 写 `AnswerRecord`（`source_type=knowledge_review`，`source_id=knowledge_point_id`）。  
- `forgot` 可写入 `Mistake`（带 `knowledge_point_id`）。  
- **可判分题**才调用 `record_attempt` 更新 mastery；**纯自评不改 mastery**。  
- 「可判分题」= 服务端能用库内标准答案/`keywords` 判定对错（见 §2.3 持久化）。无 `question_id` 或题无答案 → 按客户端 `result` 三档。  
- 同一 `item_id` 在 **UTC 自然日**内重复 complete：**幂等**（`updated_at` 的 UTC 日期 == 今日且已有 `last_result`）不二次升档。

### 2.3 题目载荷降级链与判分持久化

现状：`Question` **没有** `knowledge_point_id` 列。v1 **不新增该 FK**。

对每个到期 KP 构造 `prompt`，按序：

1. `source=reuse`：尽力查找已有可判分 `Question`（`extra`/`tags` 含该 KP id，或 tags 与 `content` 精确匹配）；找到则在载荷里带 `question_id`（指向已有行）。  
2. `source=generated`：调用 `generate_knowledge_questions` 出 1 题，并**立即写入 `questions` 表**（与 `_gen_knowledge` 类似：`qtype`/`task_type` 可用 `knowledge` 或专用标记；`extra` JSON **必须**含 `knowledge_point_id` + `keywords` + 标准 `answer`）。载荷只下发 `question_id` + 题干/选项，**不下发标准答案给客户端作权威**（讲解展开可用内容文案，判分只信服务端读库）。  
3. `source=self_rate`：无 `question_id`；讲解文案 = `KnowledgePoint.content`（可附课名）。

`complete` 若带 `question_id`：服务端载入该题 → `grade_knowledge_answer` / `grade_answer` → 覆盖 `result`。客户端篡改自评无效。

### 2.4 due / 任务 content 最小 JSON 契约

每条 item：

```json
{
  "item_id": 12,
  "knowledge_point_id": 55,
  "title": "本体+比喻词+喻体…",
  "content": "本体+比喻词+喻体…",
  "lesson_title": "第3课…",
  "prompt": {
    "source": "reuse|generated|self_rate",
    "question_id": 901,
    "question": "题干…",
    "options": [],
    "qtype": "short|choice"
  }
}
```

- `title`：`KnowledgePoint` 无独立标题字段 → **截断 `content` 前 40 字**（实现可微调长度）。  
- `self_rate` 时 `question_id` 为 null，可无 `question`。

### 2.5 每日任务

- 新 `task_type`：`kp_review`。  
- **按学科拆分**一条 `Task(subject=…, task_type=kp_review)`，满足唯一约束。  
- 生成时显式：`content_status="published"`，`submit_status="not_started"`，`bucket_id=bid`（**不要**落默认 `pending_review`，否则孩子 `list_tasks` 看不见）。  
- content 快照 = §1.6 选集中该科那一段（与 `/due?subject=` 一致）。  
- **生成时快照**；当日该四元组已存在则不重复生成。  
- 接入 `task_gen` 时：若现有逻辑是「同科当日已有**任意** Task 则整科 skip」，须为 `kp_review` **单独**判断幂等（只看同 type 是否已有），避免被听写等任务挡住。  
- 该科无到期 → 不生成。

### 2.6 任务结案与双入口

结案条件（满足即 `submit_status=approved`，跳过家长确认）：

对任务快照内**每一条** `item_id`，下列之一成立即可：

1. 该 item 今日 UTC 已成功 `complete`，或  
2. 该 item 当前 `status ≠ active`（家长已 pause/remove，或 KP 删除导致 removed）

因此：快照生成后家长 pause/remove **不会**造成任务永久卡死；孩子也**不必**再对已非 active 的快照条调用 complete（若误调 → 400，可忽略）。

- 独立模块 complete / pause 旁路：每次 complete 成功或检测到快照项变非 active 后，检查同科当日 `kp_review` 是否已满足上式并结案。  
- 与 `_gen_knowledge` **允许同日重复曝光同一 KP**（v1 接受）。

---

## §3 家长端与孩子端交互

### 3.1 `parent-web`

1. **学习进度**（已有）：教材进度面板继续用；调到更前的课后，若有自动入队，toast 如「已自动加入 M 个达标知识点到复习」。  
2. **知识点复习**页：  
   - **在队清单**：标题、学科/课、档位、下次到期、最近结果、入队来源；暂停 / 恢复 / 移出。  
   - 今日到期数、本周将到期数。  
   - 短说明：「复习列表随学习进度与掌握情况自动加入；往后调进度不会移出，需要请暂停或移出。」  
   - **无**「可加入」多选手动入队区。

禁止：用掌握度百分比逼加量；未达标/超进度强行入队。

### 3.2 Flutter `student-app`

双入口同一会话逻辑：

- 首页 `kp_review` 任务 → 用任务快照开练。  
- 独立「复习」入口 → `GET /due`；与任务重叠时以 `item_id` + 当日 complete 幂等避免双计。  
- Flutter：**新建** feature（建议名 `kp_srs` / `knowledge_srs`），**不要**复用现有 `features/knowledge_review`（那是 `task_type=knowledge` 基础知识简答页）。

单条流程：

```
展示知识点标题
  → 有题：作答；对=remember；错=forgot → 展开原文/要点
  → 无题：记得 / 有点忘 / 忘了
       记得 → remember
       有点忘 → fuzzy（可短展要点）
       忘了 → forgot → 展开讲解 → 结束本条
```

结束页：今日复习 N 条；文案偏「按计划复习完了」，不写「已掌握」。

### 3.3 空态与降级

- 无到期：模块提示「今天没有要复习的知识点」；不生成空任务。  
- AI 失败：静默降级自评。  
- 知识点已删：due 跳过并标记 `removed`（或等价清理）。

---

## §4 边界、测试、非目标

### 4.1 边界

| 情况 | 行为 |
|------|------|
| 达标但超进度 | 自动入队跳过；等进度前推后再补 |
| 进度往后调 | 队列不变 |
| 已在 active/paused | 自动入队 no-op |
| removed 后再满足条件 | 可复活入队，档位从 0、明日开始 |
| KP 无 lesson_id | 永不自动入队 |
| 非本人 complete | 403 |
| 非 active（含 paused/removed）complete | 400；当日任务结案按 §2.6 把该条视为已了结 |
| 题无标准答案 | 按自评三档处理 |
| 学年桶 | 一律 active 桶（§1.2）；无桶则入队失败 |
| 暂停中 | 不进 due；`next_review_at` 不变 |
| 生成题判分 | 只信库内 `Question`；无 `question_id` 则走自评 |

### 4.2 测试要点

- 达标 + 进度内 → 自动入队；超进度 → 不入  
- 进度前推 → 批量补齐已达标点；往后调 → 队列不变  
- 三档调度与客观题覆盖自评  
- due + 每日上限；`/due` 与 task_gen 选集一致  
- `kp_review` 与生词 `review` 并存  
- complete 幂等；快照项 pause 后仍可结案  
- Flutter：空态、有题/无题路径 smoke  

### 4.3 v1 不做

- 生词并进本模块  
- guide/trap 严格门槛  
- 家长「复习方案」容器 / 手选入队主路径  
- 重做学习进度 UI（复用现有）  
- 进度调回时自动 pause 超出范围的项  
- 旧 `frontend/`  
- 积分/时长当复习效果  
- 未想通强制入队  
- SM-2 / 完整 Anki  
- 教 AI / L1 收口  

### 4.4 学习第一性原理自检（9 问摘要）

1. 类别：识记巩固（想通后的检索自动化），非新探究。  
2. 关系：无新关系教学；巩固已有知识点的可提取性。  
3. 变换：无；明写「不得宣称理解」。  
4. 通过：间隔后仍能答对/自评记得；可被「照搬」的是检索本身，符合原料巩固定位。  
5. 产出主体：孩子作答/自评。  
6. 通道：语言作答 + 自评（v1）；低年级后续可扩动作/图形。  
7. 年龄：全年级可用；冲突型 trap 不在本模块。  
8. 测不准：纯自评不改 mastery；客观题才更新 attempt。  
9. 影响：主要「愿不愿按计划复习」+ 巩固节奏；进度调节影响**学到哪 / 复习池多大**，不把完成当学会了。

---

## 实现落点（供计划引用）

| 区域 | 路径 |
|------|------|
| 模型 | `backend/app/models.py` |
| 调度复用 | `backend/app/services/scheduler.py` |
| 服务 | 新建 `backend/app/services/knowledge_review.py`（try_enroll / progress 补齐 / due / complete） |
| 挂钩 | `mastery.record_attempt`；`routers/progress.py` 的 `adjust` / `advance` |
| 进度复用 | `backend/app/services/learning_progress.py`（课序判定） |
| 路由 | 新建 `backend/app/routers/knowledge_review.py` |
| 任务 | `backend/app/services/task_gen.py` |
| 家长端 | `parent-web/app.js`（复习队列页 + 进度 toast；不新建进度面板） |
| 学生端 | `student-app/lib/features/kp_srs/`（新 feature；勿扩展旧 `knowledge_review`） |
| 测试 | `backend/tests/test_knowledge_review.py` + Flutter smoke |
