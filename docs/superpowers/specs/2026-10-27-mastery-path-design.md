# 精通之路 · 双层掌握度 设计（阶段 3）

日期：2026-10-27
状态：已确认，待实现
范围：四阶段中的**阶段 3**，依赖阶段 2 的测验结果作为答题证据

## 背景与目标

KnoAct 现有两处「学习进度」的粗粒度记录：

- `WordMastery`（词级）：`correct_count` / `mistake_count` / `is_weak` / `next_review_at`，**无 `user_id`**、无掌握度分数
- `KnowledgePoint`（知识点级）：**完全没有掌握度记录**

本阶段借鉴 DeepTutor 的「精通之路」，补齐**双层掌握度**：

1. **词级**：扩展 `WordMastery`，补 `user_id` + 答题历史 + 掌握度分数
2. **知识点级**：新建 `KnowledgeMastery` 表，记录答题历史 + 掌握度分数 + 达标状态

核心算法逐字复制 DeepTutor 的 `compute_mastery`（recency 加权 + 低置信度上限）与 `grade_answer`（确定性判分）。

## 复用策略：抄算法，裁类型

DeepTutor 采用 Apache-2.0 许可。掌握度核心是**纯函数**，可逐字复制；但其类型系统（`KnowledgeType` 四分类、`ErrorType` 错误分类）是 DeepTutor 特有的 LLM 诊断框架，KnoAct 不采用。

**逐字复制：**

1. `compute_mastery`（`deeptutor/learning/mastery.py`，40 行）—— recency 加权 + 置信度上限
2. `grade_answer`（`deeptutor/learning/grading.py`）—— choice / short / open 三题型确定性判分

**不复制 / 简化：**

| DeepTutor 组件 | KnoAct 处理 |
|---|---|
| `KnowledgeType`（MEMORY/CONCEPT/PROCEDURE/DESIGN） | 统一用 0.9 门槛，不分类 |
| `ErrorType`（METACOGNITIVE/APPLICATION_ERROR 等） | 不做错误分类 |
| `QUANTITATIVE_GATE` 按类型区分 | 统一 `GATE = 0.9` |

## 明确不做（本阶段）

- 不改现有复习队列的**出题逻辑**（队列改动留阶段 4）；只记录掌握度分数与达标状态
- 不做「定性通过」的 CONCEPT/DESIGN 分支
- 不做错误诊断（LLM 分析错因）
- 不做家长端掌握度报告（阶段 4）

## 数据模型

### 新建 `KnowledgeMastery`

```python
class KnowledgeMastery(Base):
    __tablename__ = "knowledge_mastery"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    knowledge_point_id: Mapped[int] = mapped_column(ForeignKey("knowledge_points.id"))
    attempts: Mapped[str] = mapped_column(TextCls, default="[]")  # JSON：[true, false, ...] 时序
    mastery: Mapped[float] = mapped_column(Float, default=0.0)    # 缓存列，0..1
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    next_review_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

### 扩展 `WordMastery`

在现有表上新增三列（迁移）：

```python
# 新增
user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)  # 迁移回填真实 id
attempts: Mapped[str] = mapped_column(TextCls, default="[]")
mastery: Mapped[float] = mapped_column(Float, default=0.0)
```

现有 `correct_count` / `mistake_count` / `is_weak` / `next_review_at` 保留（供旧复习调度继续用）。

**取舍：**

- **`attempts` 存 JSON 数组**（不是单列分数）：`compute_mastery` 需要最近 5 次答题的时序做 recency 加权，存历史才能重算。与阶段 1 `options`、阶段 2 `Quiz.questions` 同风格。
- **`mastery` 是缓存列**，每次答题后重算落库；`mastered` 是 `mastery >= 0.9` 的物化标记。
- **`WordMastery.user_id` 补列 + 迁移**：老数据回填默认孩子（id=4 金宇轩）。这是阶段 1 就标记的架构缺口，本阶段一并修。

## 评分算法

### compute_mastery（逐字复制）

```python
_RECENCY_WEIGHTS = (0.5, 0.7, 0.85, 0.95, 1.0)
_CONFIDENCE_CAP = {1: 0.5, 2: 0.8}

def compute_mastery(correctness: list[bool | float]) -> float:
    if not correctness:
        return 0.0
    recent = correctness[-len(_RECENCY_WEIGHTS):]
    weights = _RECENCY_WEIGHTS[-len(recent):]
    score = sum(w * max(0.0, min(1.0, float(c)))
                for c, w in zip(recent, weights, strict=True)) / sum(weights)
    return min(score, _CONFIDENCE_CAP.get(len(recent), 1.0))
```

语义：最近答对权重高（答错后纠正能快速回升）；前 2 次封顶（1 次答对最多 0.5、2 次最多 0.8，防止蒙对达标）。

### grade_answer（逐字复制，裁掉 ErrorType）

```python
def grade_answer(user_answer: str, expected_answer: str, question_type: str = "choice") -> bool:
    # choice: 归一化去空格后相等
    # short: 相等，或 ≤30 字时 SequenceMatcher ≥ 0.85
    # open: 关键词命中 ≥ 60%
```

三题型对应 KnoAct：阶段 2 测验是 `choice`，听写是 `short`（比对拼写），`open` 留给将来。

### 门槛

```python
GATE = 0.9
def is_mastered(mastery: float) -> bool:
    return mastery >= GATE
```

### 更新流程

```
record_attempt(row, is_correct):
    attempts.append(is_correct)
    mastery = compute_mastery(attempts)
    mastered = mastery >= GATE
    next_review_at = now + (长间隔 if mastered else 短间隔)
```

**达标后复习间隔**：`mastered=True` 用 `next_review_after(6)`（`INTERVALS` 末档 60 天）；未达标用 `next_review_after(streak)`。复用现有 `scheduler.py` 的艾宾浩斯间隔 `[1,2,4,7,15,30,60]`，不新造。

## 接口

```
GET  /api/mastery/overview?user_id&subject
  → [{knowledge_point_id, title, category, mastery, mastered, due}]

POST /api/mastery/record
  {user_id, target_type: 'knowledge'|'word', target_id, is_correct}
  → 内部 append attempt → compute_mastery → 更新 mastery/mastered/next_review_at
```

## 接入点

### 测验 → 知识点掌握度

出题时（`generate_quiz`），除课文文本外，把当前课的 `KnowledgePoint` 列表（`id + category + content`）注入提示词，让 AI 每道题额外返回 `knowledge_point_id`（从列表选，无匹配则 `null`）。

- `Quiz.questions` JSON 存 `knowledge_point_id`（可空）
- 判分后（`quiz_submit`），对每题：`knowledge_point_id` 非空 → `record_mastery(target_type='knowledge', target_id=..., is_correct=...)`
- `null` 的题只算测验分数，不驱动掌握度（保留灵活性，阶段 2 与阶段 3 解耦）

### 听写 → 词掌握度

`dictation_grade` 判分后，对每个词：`record_mastery(target_type='word', target_id=word_bank_id, is_correct=...)`。

## 迁移

`WordMastery` 加三列（`user_id` / `attempts` / `mastery`）：

- 新列带默认值，SQLite 直接 `ALTER TABLE ADD COLUMN` 即可（或 `create_all` + 数据回填脚本）
- 老行 `user_id` 回填为默认孩子 id（金宇轩 = 4）
- `attempts` 老行初始 `[]`（历史不可回溯，从零开始累积）

## 测试

- `backend/tests/test_mastery.py`：
  - `compute_mastery`：空历史 0.0；1 次答对 0.5（封顶）；2 次 0.8（封顶）；3 次全对 0.9+；答错后纠正回升
  - `grade_answer`：choice 归一化相等；short 相似度 ≥0.85；open 关键词 ≥60%
  - `record_attempt`：append + 重算 + mastered 翻转 + next_review_at 更新
  - 接口：overview 按 subject 过滤；record 正确落库
- `backend/tests/test_quiz.py`（扩展）：出题返回 `knowledge_point_id`；判分后驱动掌握度
- 前端 `node --check`

## 后续阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 4 | 打通与打磨：掌握度接进错题本/任务生成/家长报告，复习队列按 mastered 拉长间隔 | 阶段 3 |
