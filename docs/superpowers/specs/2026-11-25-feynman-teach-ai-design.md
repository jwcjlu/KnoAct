# 孩子讲一遍（表达练习）设计

日期：2026-11-25
状态：已确认（brainstorming），v6 — 最简版
范围：`2026-11-24-learning-first-principles-design.md` 待整改 #19「教 AI」的**最小可行版本**。
前五轮完整设计的失败记录见 §附：为什么没做完整版。

## 一句话

> **孩子对一个知识点写一段解释，家长能看到这段解释。没有 AI、没有判定、没有掌握度。**

## 背景

孩子学完一个知识点，现有系统**没有「用自己的话讲一遍」的环节**。所有交互都是被动应答：选答案、填空、默写。

「讲一遍」本身有价值：

| 价值 | 说明 |
| --- | --- |
| 逼孩子组织语言 | 讲一次比听三遍更费脑 |
| **暴露缺口** | 讲不下去的地方就是没想清的地方，**家长能看到** |
| 留痕 | 家长知道孩子是怎么理解这个知识点的 |

**但「讲得好不好」不是一个能自动判定的量**（见附录）。所以本版**不判定**，只采集。

## 为什么是最简版

前五轮尝试了五种自动判定机制（差分对比、锚点复现、纠正检测、AI 出题判分、效果指标对比），**全部被证明不可靠**：

- 前四种：判据都能被「背诵定义 + 拒绝明显错误」绕过
- 第五种：`KnowledgePointPool` 与 `KnowledgePoint` 无映射，指标**物理上算不出来**

而每加一层机制，成本都在涨。所以本版只保留**能确定产生价值**的部分：**孩子写，家长看**。

---

# 一、做什么

## 1.1 流程

```
① 孩子在知识点列表里挑一个（或从已完成的任务进来）
② 看到题目：「用你自己的话讲讲这个知识点，讲给一个完全不懂的人听」
③ 写一段文字（无字数硬要求，占位提示「随便说，说多少都行」）
④ 提交
⑤ 家长端能看到这段文字
```

**就这些。** 没有对话、没有追问、没有评分。

## 1.2 界面形态

```
┌─────────────────────────────────────┐
│ ← 讲一遍                             │
│                                     │
│ 比喻                                 │
│ ─────────────────────────────────── │
│                                     │
│ 用你自己的话讲讲这个知识点，          │
│ 就当讲给一个完全不懂的人听。          │
│                                     │
│ ┌─────────────────────────────────┐ │
│ │ 随便说，说多少都行…              │ │
│ │                                 │ │
│ │                                 │ │
│ └─────────────────────────────────┘ │
│                                     │
│            [ 讲完了 ]               │
└─────────────────────────────────────┘
```

提交后：

```
┌─────────────────────────────────────┐
│         ✓                           │
│                                     │
│    记下来了                         │
│                                     │
│  你讲的这段话，爸爸/妈妈能看到。      │
│                                     │
│         [ 再讲一个 ]  [ 返回 ]      │
└─────────────────────────────────────┘
```

**关键**：结束页**不评价**。没有「讲得好」「讲得不完整」「正确率」。

## 1.3 家长端

在现有掌握度报告页下方加一栏「孩子讲的」：

```
┌─────────────────────────────────────┐
│ 孩子讲的                             │
│ ─────────────────────────────────── │
│ 比喻                   11-25 19:30  │
│ 「比喻就是把一个东西说成另一个东西，   │
│   但它们要有相似点，比如月亮像小船」   │
│                                     │
│ 拟人                   11-24 20:10  │
│ 「拟人是把不是人的东西写得像人一样，   │
│   会说话会做事」                     │
└─────────────────────────────────────┘
```

**不做的事**：不标记对错、不给分数、不做「讲得是否完整」的判断。**只展示孩子写的原话。**

---

# 二、数据模型

单表，无状态机，无 AI 字段。

```python
class ExpressionNote(Base):
    """孩子用自己的话讲一个知识点的记录。

    本表刻意不含 verdict / score / ai_* 字段：
    本功能不做判定，也不做 AI 交互。
    """
    __tablename__ = "expression_notes"
    __table_args__ = (
        Index("ix_expression_notes_user_created", "user_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int | None] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)

    # 讲的是哪个知识点：两个来源二选一
    knowledge_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_points.id"), nullable=True)
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_items.id"), nullable=True)

    # 冗余存一份标题，便于家长端展示（知识点可能被删）
    title: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(LongText)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**为什么用 `knowledge_point_id` 而不是 `point_pool_id`**：家长端展示的是「任务里出现过的知识点」（`tasks.py:255` 写 `AnswerRecord` 时 `source_type="knowledge_point", source_id=p["id"]` 用的是 `KnowledgePoint.id`），用同一个 ID 体系便于对账。`item_id` 作为备选来源（手工创建的 `explore` 条目），两者都允许为空但**至少要有一个**（服务层校验）。

### 2.1 `title` 快照规则

`KnowledgePoint` 没有 `title` 列，正文是 `content`；`TrainingItem` 的正文是 `primary`。写入时按来源取：

| 来源 | `title` 取值 |
| --- | --- |
| `knowledge_point_id` | `KnowledgePoint.content[:255]` |
| `item_id` | `TrainingItem.primary[:255]`（为空则退回 `block_title`） |

冗余存一份是为了**知识点被删后家长端仍能显示**。

### 2.2 外键删除策略

`knowledge_point_id` / `item_id` 用 `ondelete="SET NULL"`。

**为什么**：`cleanup.py` 删除课件时会处理 `Note.knowledge_point_id`，**不会**知道有 `expression_notes` 这张新表。若用默认 `RESTRICT`，删课/删专项会失败。用 `SET NULL` + 冗余 `title`，历史记录仍可读。

### 2.3 `bucket_id`

写入时用 `resolve_bucket_id(db, user_id, None)`（取 active 桶），与其他表一致。

**读取时不按桶过滤**——家长想看「孩子以前怎么讲的」，按桶过滤会丢掉历史学年的记录，而这些内容没有调度含义，不需要按桶隔离。

---

# 三、接口

```
GET  /api/expression/topics?user_id=
  → {topics: [{kind: "knowledge_point"|"training_item", id, title}]}

POST /api/expression/notes
  body: {user_id, knowledge_point_id?, item_id?, text}
  → {id, created_at}
  错误：400 / 403 / 404

GET  /api/expression/notes?user_id=&limit=
  → {notes: [{id, title, text, created_at}]}

DELETE /api/expression/notes/{id}
  → {ok: true}
```

**就四个端点。没有 AI，没有状态机。**

## 3.1 `GET /topics` 的两个数据源

### knowledge_point

与 `routers/mastery.py` 的 `overview` 完全一致（同 JOIN、同桶过滤）：

```python
bid = resolve_bucket_id(db, user_id, None)
q = (db.query(KnowledgeMastery, KnowledgePoint)
     .join(KnowledgePoint, KnowledgeMastery.knowledge_point_id == KnowledgePoint.id)
     .filter(KnowledgeMastery.user_id == user_id))
if bid is not None:
    q = q.filter(KnowledgeMastery.bucket_id == bid)
```

`title` 取 `KnowledgePoint.content`。

### training_item

`TrainingGroup.owner_id` 存的是**家长**的 `user.id`（见 `drill.py` 的 `create_group`）。孩子通过 `User.parent_id` 关联到家长：

```python
child = db.get(User, user_id)
parent_id = child.parent_id if child else None
if parent_id:
    group_ids = [g.id for g in db.query(TrainingGroup.id).filter_by(owner_id=parent_id)]
    items = db.query(TrainingItem).filter(TrainingItem.group_id.in_(group_ids)).all()
```

`title` 取 `TrainingItem.primary`（空则 `block_title`）。

**只返回 `kind == "explore"` 的条目**——与本功能「讲一条规则」的定位一致。`phrase` / `drill_item` 是识记型，没有规则可讲。

## 3.2 年级门槛（服务端强制）

**四个端点全部校验**：目标孩子的 `User.grade`。

```python
if (child.grade or 3) < 3:   # None 视为 3（与桶的缺省年级一致）
    raise HTTPException(403, "该功能暂未开放")
```

前端隐藏入口只是体验优化，**不作为安全边界**。

## 3.3 `POST /notes` 的可见性校验

`/topics` 可枚举 ≠ POST 任意 id 合法。写入前必须校验：

| 来源 | 校验 |
| --- | --- |
| `knowledge_point_id` | 该孩子（该桶）有 `KnowledgeMastery` 记录 |
| `item_id` | 属于 `child.parent_id` 名下的 group，且 `kind == "explore"` |

不满足 → 403。

## 3.4 谁能写

**只有孩子本人能 POST**（`actor.id == target_user_id`）。家长只能读和删，不能代写——代写会让「孩子怎么想的」这个记录失去意义。

---

# 四、权限

沿用现有机制，不新造。参照 `routers/goals.py` 的写法：

| 端点 | 校验 |
| --- | --- |
| `GET /topics` | `resolve_target_user_id` + `require_learning_user` + `ensure_user_access` |
| `POST /notes` | 同上 + **`actor.id == user_id`**（只有孩子本人能写） |
| `GET /notes` | 同上 |
| `DELETE /notes/{id}` | 同上；只能删该孩子的记录（家长可删自己孩子的） |

**不新增权限模型**——`ensure_user_access`（已有）已覆盖「孩子看自己 / 家长看孩子 / admin 全部」。

`DELETE` 时：`assert_writable(db, note.user_id, note.bucket_id)`（历史学年只读），与 `mistakes.py` 的写法一致。

---

# 五、输入校验

| 情况 | 处理 |
| --- | --- |
| `text` 为空 / 只有空白 | 400 |
| `text` 长度 > 5000 字 | 400（防止粘贴整篇课文） |
| 两个 id 都没给 | 400 |
| 两个 id 都给 | 400（一次只讲一个） |
| 目标 id 不存在或无权访问 | 404 / 403 |

**不要求最小字数**——「随便说，说多少都行」是刻意的。要求字数会让孩子为了凑字数而写废话。

---

# 六、为什么不做 AI（这一节是决定的理由，不是待办）

| 想加的功能 | 为什么不做 |
| --- | --- |
| AI 追问 | 无法证明追问质量；且需要跨轮会话层（`UnifiedContext` 无历史、`TurnEngine` 单轮闭合） |
| AI 判定讲得好不好 | **五轮尝试全部失败**（见附录），判据可被「背诵 + 拒绝明显错误」绕过 |
| AI 出题验证 | AI 同时出题和给答案 = 没有真值；且题目无课文 `grounded` 校验，比现有 `quiz.py` 更不可信 |
| 写掌握度 | 没有可写的判定；「讲清楚」和「做对题」是不同能力，混入会污染 SRS |
| 效果指标对比 | `KnowledgePointPool` 与 `KnowledgePoint` 无映射，物理上算不出来；且有严重选择偏差 |

**这些不是「以后再说」，是「已经证明做不好」。** 附录记录了每一轮的具体失败原因，避免以后重复踩坑。

---

# 七、测试要点

**后端**

1. `POST /notes` 正常写入，`GET /notes` 能读回。
2. 空 `text` → 400；`text` 只有空白 → 400；超 5000 字 → 400。
3. 两个 id 都不给 → 400；都给 → 400。
4. 越权：不能给别的孩子的 `user_id` 写；不能读别的孩子的 notes。
5. **家长不能代写**：家长 token POST → 403。
6. `DELETE`：只能删自己的（或自己孩子的）；历史学年桶 → 只读。
7. `GET /topics`：只返回该孩子 active 桶下有 `KnowledgeMastery` 的 `KnowledgePoint`，以及 `parent_id` 名下 group 的 `explore` 条目。
8. `POST` 可见性：传一个不属于该孩子的 `knowledge_point_id` → 403。
9. **模型层断言**：`ExpressionNote` 没有 `verdict` / `score` / `ai_*` 字段（防止未来偷偷加判定）。
10. 年级门槛：`grade < 3` 或 `grade is None` → 四个端点全部 403。
11. 外键 `SET NULL`：删掉 `KnowledgePoint` 后，`GET /notes` 仍能返回该条记录（`title` 快照保留）。

**Flutter**

8. 输入页：空文本时「讲完了」按钮置灰。
9. 结束页：**不显示任何评价语**（断言不含「好」「棒」「正确」「完整」等词）。
10. 家长端列表：显示原文，不显示对错标记。

---

# 八、改动文件清单

| 文件 | 改动 |
| --- | --- |
| `backend/app/models.py` | 新增 `ExpressionNote` |
| `backend/app/routers/expression.py` | 新增：topics / notes CRUD |
| `backend/app/main.py` | include_router |
| `backend/tests/test_expression.py` | 新增 |
| `student-app/lib/features/expression/` | 新增：输入页 + controller + repository |
| `student-app/lib/core/router.dart` | 新增路由 + redirect 白名单 |
| `parent-web/app.js` | 在 `renderReportTab()` 的掌握度区块之后、「当天做题明细」之前插入「孩子讲的」；并在该 Tab 的 `Promise.all([...])` 里加 `loadExpressionNotes()` |
| `student-app/test/features/expression/` | 新增 |

**不改动**：`mastery.py`、`task_gen.py`、`TurnEngine`、`UnifiedContext`、任何 AI 服务。

---

# 九、成本与工作量

| 项 | 量 |
| --- | --- |
| 后端 | 1 张表 + 4 个端点（都是简单 CRUD） |
| Flutter | 1 个输入页 + 1 个列表项 |
| 家长端 | 1 个展示区块 |
| **AI 调用** | **0** |
| 可运行成本 | 可忽略 |

对比前五轮的完整设计（2 张表 + 8 个端点 + 对话状态机 + 每题 5–12 次 AI 调用），本版是它的零头。

---

# 十、已知局限（诚实标注）

| 局限 | 影响 | 为什么不解决 |
| --- | --- | --- |
| **不判定** | 系统不知道孩子讲得对不对 | 做不出可信判定（五轮验证） |
| **没有反馈** | 孩子写完不知道好不好 | 不判定就不该假装评价 |
| **依赖家长读** | 家长不看就等于没发生 | 这是本版的定位：**给家长一个看的窗口**，不是给孩子自动反馈 |
| 不写掌握度 | 不影响复习调度 | 没有判定可写 |
| 只有文字 | 低年级表达能力弱的用不上 | 年级门槛设为 3 以上（服务端强制） |
| 主题列表取决于现有数据 | 方案发布的条目是 `drill_item`，不进列表 | 只开放 `explore` 条目；现状下可选范围有限 |

**这个功能的价值完全取决于「家长会不会看」。** 如果家长不看，它就只是多了一个没人读的输入框。这是它最大的风险，且不是技术能解决的。

---

# 十一、明确定位

> **这不是学习功能，是「家长了解孩子怎么想」的窗口。**

因此：
- 不进每日任务
- 不计积分
- 不参与掌握度
- **成功指标是「家长打开看的次数」**，不是「孩子学会了多少」

---

# 附录：为什么没做完整版（五轮失败记录）

保留这段是为了**避免以后重复踩坑**。每一轮都经过了独立的对抗性审查。

## v1 差分判定

**机制**：同一个判断跑两次（带/不带孩子的解释），答案不同就算通过。

**死于**：**没有真值**。「A 对 B 错」无从计算——判断的正确答案从哪来？如果要系统判对错，就需要标注好的标准答案；如果要 AI 判，AI 的答案就是它自己的知识，不是孩子规则的推论。

## v2 锚点复现

**机制**：孩子给规则 + 造正例；系统给反例；孩子判断反例；AI 只按孩子的规则判断同一反例。两者一致 → 通过。

**死于**：**单一反例可被过拟合**。

审查给出的击穿构造：

> 规则：「只要不是『他长得像他爸爸』，就是比喻。」
> 反例：「他长得像他爸爸」→ AI 答「不符合」→ **通过**。

这条明显是垃圾规则，但单反例测不出。补多个反例也没用——**总能针对有限反例集构造过拟合规则**。

## v3 纠正判定

**机制**：AI 按孩子的话做荒谬推论，孩子能否纠正。

**死于**：**背诵者也能纠正**。

审查指出：孩子背下「比喻是两个不同类的东西有相似点」，AI 说「那『今天星期天』也是比喻，对吧？」——**孩子不需要理解，凭常识就知道不对**，然后照背一遍定义。判「纠正成功」。

这不是反检索检验——它只测到「拒绝明显错误 + 复述定义」。而且 v3 用「显然荒谬」的例子，恰好让信号更弱。

## v4 AI 出题 + 纯比较判分

**机制**：对话不判定，讲完让 AI 出 2 道变式题，用 `grade_answers`（纯比较）判分。

**死于**：**AI 同时出题和给答案 = 仍无真值**。

审查指出：这只是一次「确定性判分」，不是「客观正确答案」——信任问题从判分器移到了出题器。而且题目从孩子的话生成，**没有课文可对照**，比现有 `quiz.py`（有 `_grounded` 逐字校验）**更不可信**。

另外两题随机猜通过率 1/16（6.25%），但一题 AI 出坏题就误判失败（若坏题率 10%，至少踩一题的概率 19%）。

## v5 效果指标对比

**机制**：不判定，改成「讲过之后该知识点的首次正确率是否高于讲之前」。

**死于**：两处硬伤。

1. **关联不可实现**：`FeynmanSession` 要记 `knowledge_point_pool_id`（指向 `KnowledgePointPool`），但 `AnswerRecord.source_type="knowledge_point"` 的 `source_id` 存的是 `KnowledgePoint.id`（见 `tasks.py:255`）。**两张表没有映射关系**，数值偶然相等也无语义。
2. **指标不可归因**：孩子自选要讲的知识点（选择偏差）、后测天然更晚（练习效应、成熟）、`task_gen.py` 的自适应调度让前后题目难度不同、对照组没有共同起点。

## 共同教训

| 教训 | 说明 |
| --- | --- |
| **「理解」不是可自动判定的量** | 这是 spec「允许未决」早就写过的原则，我连续违反了五次 |
| **每次失败都是把信任问题挪位置** | 从判分器 → 出题器 → 指标，从没解决它 |
| **写指标前必须查代码事实** | v5 的指标如果先查 `source_type` 存什么，本可以当场发现不可实现 |
| **不要用更大的机制弥补判据的弱** | 每加一层（对话、出题、指标），成本涨，可信度没涨 |

## 如果以后还想做完整版，前提是

1. **统一知识点身份**：建立 `KnowledgePointPool` ↔ `KnowledgePoint` 的显式映射（带外键）。
2. **做真正的对照实验**：随机分组（A 直接做题 / B 先讲再做题），比较后续迁移题首次正确率。
3. **判定用已审核的题库**：AI 只出题面，答案来自 canonical 内容并像 `_grounded` 一样校验。

三条都没做之前，任何「自动判定理解」的机制都只是换个地方骗自己。
