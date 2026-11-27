# 知识点复习模块（遗忘曲线 SRS）

日期：2026-11-27  
状态：设计已定稿，待实现  
范围：后端新表 + `/api/knowledge-review/*` + `task_gen` 扩展；`parent-web` 入队管理；Flutter `student-app` 复习会话与每日任务入口。  
非范围：生词 SRS 合并、旧版 `frontend/`、复习方案容器、严格探究证据门槛、SM-2/Anki。

## 背景与目标

学习需要间隔复习。仓库已有半套遗忘曲线：`INTERVALS = [1,2,4,7,15,30,60]`、`WordMastery` / `KnowledgeMastery.next_review_at`、每日生词「到期复习」、听写混入到期词。缺口是：

1. **没有独立的知识点复习队列**——家长无法主动「加入要复习的知识点」。  
2. 现有 `/api/review/questions` 按学科随意抽点 + AI 出题，**不读调度状态**。  
3. `_gen_review` 只服务生词；知识点掌握后缺少有频率的巩固入口。

目标：家长把**已想通（v1 用 mastery 达标近似）**的知识点加入复习队列，按遗忘曲线到期；孩子在每日任务 + 独立复习模块中用「轻量自测 → 忘了再展开」完成复习，并正确推进间隔。

对齐学习第一性原理：

- 本模块属**原料层自动化之后的巩固**（想通 → 再间隔检索），**不得宣称**复习完 = 新理解。  
- v1 门槛用 `KnowledgeMastery.mastered` / `mastery>=0.9`；严格 guide/trap 证据链列为后续。  
- 家长端给**决策**（在队 / 到期 / 下次），不用掌握度百分比当考核。

## 已锁定决策

| 项 | 决定 |
|----|------|
| 复习对象 | 仅知识点（`KnowledgePoint`），不含生词 |
| 谁入队 | 家长（`parent-web`） |
| 入队门槛 | v1：`mastered==True` 或 `mastery>=0.9`；未达标不可入队 |
| 孩子做什么 | 轻量混合：有题先作答；答错/「忘了」再展开讲解；无题则三档自评 |
| 触达 | 每日任务 + 独立复习模块（同一套 complete 逻辑） |
| 间隔动作 | 记得升档；有点忘同档再测；忘了回第 0 档（1 天） |
| 出题 | 已有关联题 → AI → 仅自评 |
| 客户端 | `parent-web` + Flutter `student-app` |
| 架构 | **独立复习队列表**，与 `KnowledgeMastery` 解耦 |

## 成功标准

1. 家长能对达标知识点入队 / 暂停 / 恢复 / 移出，并看到档位与下次到期。  
2. 到期项出现在当日 `kp_review` 任务与复习模块 `/due`。  
3. `complete` 按三档（及客观题对错覆盖）正确更新 `interval_index` / `next_review_at`。  
4. 完成文案不宣称「已掌握 / 已理解」。  
5. 生词 `review` 任务与本模块并存、互不吞并。

---

## §1 数据模型与调度

### 1.1 新表 `knowledge_review_items`

| 字段 | 类型 / 含义 |
|------|-------------|
| `id` | PK |
| `user_id` | 孩子 |
| `knowledge_point_id` | FK → knowledge_points |
| `bucket_id` | 学年桶，可空但入队时尽量写入 |
| `enrolled_by` | 家长 user id |
| `enrolled_at` | 入队时间 |
| `status` | `active` \| `paused` \| `removed` |
| `interval_index` | 0-based，对应 `INTERVALS` |
| `next_review_at` | 下次到期 |
| `last_result` | `remember` \| `fuzzy` \| `forgot`，可空 |
| `updated_at` | 最近一次结果时间 |

约束：

- `(user_id, knowledge_point_id, bucket_id)` 在 `status ∈ {active, paused}` 时至多一条。  
- `removed` 后允许重新入队（新行或复活行均可；实现选一种并在计划里写死），档位从 0 起。

### 1.2 与 `KnowledgeMastery` 的分工

| 职责 | 归属 |
|------|------|
| 是否「够格入队」 | `KnowledgeMastery`（v1：`mastered` 或 `mastery>=0.9`） |
| 是否在复习计划中、多久复习一次 | `knowledge_review_items` |
| 听写/生词到期 | 继续 `WordMastery` + 现有 `_gen_review` |

本模块**不**用 `KnowledgeMastery.next_review_at` 驱动到期，避免两套调度打架。

### 1.3 入队初始值

- 校验门槛通过后：`status=active`，`interval_index=0`，`next_review_at = now + 1 day`（明日开始，避免刚加入当天挤占）。

### 1.4 三档 → 间隔

沿用 `services/scheduler.py` 的 `INTERVALS = [1, 2, 4, 7, 15, 30, 60]`。

| 结果 | 来源 | 动作 |
|------|------|------|
| `remember` | 自评「记得」或客观题答对 | `interval_index = min(i+1, len-1)`，`next_review_at = now + INTERVALS[new]` |
| `fuzzy` | 自评「有点忘」 | `interval_index` 不变，`next_review_at = now + INTERVALS[i]`（同档全长） |
| `forgot` | 自评「忘了」或客观题答错 | `interval_index=0`，`next_review_at = now + 1 day`；UI 进入展开讲解 |

客观题若提交了作答：服务端判分后**覆盖**客户端自评（对→`remember`，错→`forgot`）。

### 1.5 到期选集

- 今日到期：`status=active` 且 `next_review_at <= now`。  
- 每日上限：默认 5～8（`child_config` 可配）；超出仍保持到期，次日优先，不丢队。  
- 按 `next_review_at` 升序，必要时次级按 `interval_index` 升序（短间隔优先）。

---

## §2 API 与任务生成

旧 `/api/review/questions`、`/api/review/submit` **不作为**本模块主路径（可后续废弃或转调）。新前缀：`/api/knowledge-review`。

### 2.1 家长 API

| 方法 | 路径 | 作用 |
|------|------|------|
| `GET` | `/api/knowledge-review/eligible?user_id=` | 可入队：达标且非 active/paused |
| `GET` | `/api/knowledge-review/queue?user_id=` | 队列列表（含档位、下次到期、最近结果） |
| `POST` | `/api/knowledge-review/enroll` | `{user_id, knowledge_point_ids[]}` |
| `POST` | `/api/knowledge-review/item/{id}/pause` | 暂停 |
| `POST` | `/api/knowledge-review/item/{id}/resume` | 恢复 |
| `POST` | `/api/knowledge-review/item/{id}/remove` | 软删 `removed` |

鉴权：家长可操作绑定孩子；入队失败返回 400 + 原因（未掌握 / 已在队）。

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

- 写 `AnswerRecord`（`source_type=knowledge_review`，`source_id=item_id` 或 `knowledge_point_id`）。  
- `forgot` 可写入 `Mistake`（带 `knowledge_point_id`）。  
- **客观题**才调用 `record_attempt` 更新 mastery；**纯自评不改 mastery**（防刷分）。  
- 同一 `item_id` 在短窗口内重复 complete：**幂等**，不二次升档（以 `updated_at` 当日已结算或结果指纹判断，实现计划写死一种）。

### 2.3 题目载荷降级链

对每个到期 KP，在 `due`（及任务 content）中附 `prompt`：

1. `source=bank`：已有关联题（课内 Question / 题库挂该 `knowledge_point_id`）。  
2. `source=ai`：即时出一题；失败则降级。  
3. `source=self_rate`：仅知识点内容 + 三档按钮。

### 2.4 每日任务

- 新 `task_type`：`kp_review`（与生词 `review` 并列）。  
- `task_gen` 生成器：取 due 截断到每日上限，**生成时快照**写入 `Task.content`；当日已有未完成同类型任务则不重复生成。  
- 标题示例：「知识点复习」；detail 含条数。  
- 无到期 → 不生成该任务。

---

## §3 家长端与孩子端交互

### 3.1 `parent-web`

「知识点复习」页（或挂在孩子学习安排下）：

1. **在队清单**：标题、学科/课、档位、下次到期、最近结果；暂停 / 恢复 / 移出；今日到期数、本周将到期数。  
2. **可加入**：仅达标且不在 active/paused；多选加入。未达标不出现或灰显说明。

禁止：用掌握度百分比逼加量；未达标强行入队。

### 3.2 Flutter `student-app`

双入口同一会话逻辑：

- 首页 `kp_review` 任务 → 用任务快照开练。  
- 独立「复习」入口 → `GET /due`；与任务重叠时以 `item_id` + complete 幂等避免双计。

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
| 入队未达标 | 整批或逐条拒绝，不写不合格项 |
| 已在 active/paused | 返回已在队列，不重复插入 |
| removed 后重入队 | 允许，档位从 0 |
| 非本人 complete | 403 |
| 非 active complete | 400 |
| 客观题无标准答案 | 按自评三档处理 |
| 学年桶 | 按 `bucket_id` 隔离 |

### 4.2 测试要点

- enroll 门槛通过/失败  
- 三档调度与客观题覆盖自评  
- due + 每日上限  
- `kp_review` 与生词 `review` 并存  
- complete 幂等  
- Flutter：空态、有题/无题路径 smoke  

### 4.3 v1 不做

- 生词并进本模块  
- guide/trap 严格门槛  
- 家长「复习方案」容器  
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
9. 影响：主要「愿不愿按计划复习」+ 巩固节奏；不把完成当学会了。

---

## 实现落点（供计划引用）

| 区域 | 路径 |
|------|------|
| 模型 | `backend/app/models.py` |
| 调度复用 | `backend/app/services/scheduler.py` |
| 服务 | 新建 `backend/app/services/knowledge_review.py`（enroll/due/complete） |
| 路由 | 新建 `backend/app/routers/knowledge_review.py` |
| 任务 | `backend/app/services/task_gen.py` |
| 家长端 | `parent-web/app.js` (+ 样式) |
| 学生端 | `student-app/lib/features/` 下新 feature 或扩展 `knowledge_review` |
| 测试 | `backend/tests/test_knowledge_review.py` + Flutter smoke |
