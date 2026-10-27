# 打通与打磨（掌握度接入错题本/报告）设计 · 阶段 4

日期：2026-10-27
状态：已确认，待实现
范围：四阶段中的**阶段 4（收尾）**，依赖阶段 2 的测验、阶段 3 的掌握度

## 背景与目标

阶段 1-3 已交付：7 角色模型配置层、测验+主动提问、双层掌握度。本阶段把掌握度**串进**错题本与家长报告，使整个「借鉴 DeepTutor」工程闭环。

三块工作：

1. **错题本 ↔ 掌握度**：错题的移出判定改用掌握度分数（而非裸计数）
2. **家长掌握度报告**：报告页新增掌握度维度
3. **测验错题收录 + 复习队列确认**：答错的测验题收进错题本（去重），确认复习队列已通过 `next_review_at` 避已掌握

## 现状（阶段 4 前）

- `Mistake` 表：`user_id`/`source_type`/`question`/`your_answer`/`correct_answer`/`mistake_count`/`consecutive_correct`，**无词/知识点关联字段**
- `mark_correct`：`consecutive_correct` 累计到 `REMOVE_AFTER=3` 就删除
- `dictation_complete` 收错词：`WrongWord` 只有 `word`/`your_answer`，**无 `word_id`**
- `quiz_submit`：判分 + 驱动知识点掌握度，**不收录错题本**
- 复习生成 `_gen_review`：按 `WordMastery.next_review_at <= now` 筛选到期词（阶段 3 已让 mastered 词用 60 天间隔，**已自然避已掌握**）

## 明确不做

- 不改 `_gen_review` 的筛选逻辑（已通过 `next_review_at` 实现避已掌握）
- 不做家长端独立的新 tab（复用现有「报告」tab）
- 不做学习报告/积分商城（仍为占位）

## 数据模型

### 扩展 `Mistake`

```python
class Mistake(Base):
    # 新增两列（迁移，可空）
    word_bank_id: Mapped[int] = mapped_column(ForeignKey("word_banks.id"), nullable=True)
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"), nullable=True)
```

不加 DB 唯一约束（`question` 是长文本，历史数据可能有重复，加约束会迁移失败；去重靠查询判断）。

### 扩展 `WrongWord`（dictation 的错词结构）

```python
class WrongWord(BaseModel):
    word: str
    your_answer: str = ""
    word_id: int = 0   # 新增：关联 WordBank，写入 Mistake.word_bank_id
```

## 接口改动

### 1. 错题本 ↔ 掌握度

`mark_correct`（`routers/mistakes.py`）：改为

```
m = get(Mistake)
if m.word_bank_id:
    mastery = record_attempt(db, m.user_id, 'word', m.word_bank_id, True)
    removed = mastery >= GATE
elif m.knowledge_point_id:
    mastery = record_attempt(db, m.user_id, 'knowledge', m.knowledge_point_id, True)
    removed = mastery >= GATE
else:
    # 无关联 id：保留旧逻辑（consecutive_correct 累计到 3）
    m.consecutive_correct += 1
    removed = m.consecutive_correct >= REMOVE_AFTER
if removed: db.delete(m)
```

`mark_wrong` 同样：有 id 时 `record_attempt(..., False)`，无 id 时走旧逻辑（`consecutive_correct=0`）。

**取舍**：保留 `consecutive_correct` 作为无关联 id 时的兜底，不破坏老数据/无关联题型的既有行为。

### 2. 测验错题收录

`quiz_submit`（`routers/quiz.py`）判分后，对每题答错的：

```
existing = Mistake.where(user_id, knowledge_point_id, question).first()
if existing:
    existing.mistake_count += 1
    existing.consecutive_correct = 0
else:
    Mistake(user_id, source_type="reading", question=题干,
            your_answer=孩子选项, correct_answer=正确选项,
            knowledge_point_id=kp_id)
```

去重键：`(user_id, knowledge_point_id, question)`；`knowledge_point_id` 为 None 时退化为 `(user_id, question)`。

### 3. 家长掌握度报告

新增 `GET /api/mastery/report?user_id&subject`（挂在 `routers/mastery.py`）：

```
→ {
    mastered: int,     # mastered=True 的知识点数
    weak: int,         # 有过答题但未达标的知识点数
    total: int,        # 该学科知识点总数（有掌握度记录的 + 未答过的）
    rows: [{knowledge_point_id, title, category, mastery, mastered, attempts_count}]
  }
```

- `weak` = 有 `KnowledgeMastery` 记录且 `mastered=False`
- 未答过题的知识点不计入 `weak`（避免「全部薄弱」误导）
- `total` = 该 subject 下所有 `KnowledgePoint` 数（含未答过的）

## 前端改动

### 报告页（`renderReportTab`）

在现有「薄弱环节报告」下方，增加「掌握度报告」区块：

- 顶部：`已掌握 N · 薄弱 M · 共 K` + 进度条（`mastered/total`）
- 列表：每条知识点显示 `category · title`、掌握度分数、`mastery` 进度条、`✓` 标记（mastered）
- 按学科切（复用现有 subject 筛选）
- 视觉复用现有 token（`--green-soft`/`--orange-soft`/`--blue-soft`）

### 错题本页

错题列表若 `word_bank_id`/`knowledge_point_id` 非空，显示「已关联掌握度」标记（可选，轻量）。移出逻辑已由后端 `mark_correct` 处理，前端只展示 `removed` 结果。

## 迁移

`Mistake` 加两列（可空，无默认值问题）：

- SQLite `ALTER TABLE ADD COLUMN`（幂等）
- 老行 `word_bank_id`/`knowledge_point_id` 保持 `NULL`（走旧逻辑兜底）

## 测试

- `backend/tests/test_mistakes.py`（或扩展）：
  - `mark_correct` 有 `word_bank_id`：mastery 达标才移出；未达标不移出但掌握度上升
  - `mark_correct` 无关联 id：走旧逻辑（consecutive_correct 到 3 移出）
  - `quiz_submit` 答错收错题本：去重累加 `mistake_count`
  - `/api/mastery/report`：mastered/weak/total 计数正确
- 前端 `node --check`

## 完成标准

- [ ] `Mistake` 加 `word_bank_id`/`knowledge_point_id`，`WrongWord` 加 `word_id`
- [ ] `mark_correct`/`mark_wrong` 用掌握度分数判定移出（保留旧逻辑兜底）
- [ ] `quiz_submit` 答错收错题本，按 `(user, kp, question)` 去重
- [ ] `/api/mastery/report` 接口 + 报告页掌握度区块
- [ ] 复习队列确认已避已掌握（不改代码，端到端验证）
- [ ] 全套测试仅剩两条既有失败
