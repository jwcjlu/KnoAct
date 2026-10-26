# 边读边问（测验 + 主动提问）设计 · 阶段 2

日期：2026-10-27
状态：已确认，待实现
范围：四阶段中的**阶段 2**，依赖阶段 1 的 `resolve('llm')`

## 背景与目标

KnoAct 的沉浸式阅读已具备「边读边问」的骨架：`/api/ask` 三个模式（chat / visualize / solve）、按句切分 + `[第N句]` 出处跳转、选区捕获、mermaid 渲染。

本阶段借鉴 DeepTutor 的「边读边问」能力，补齐两个缺失、且可移植的模式：

1. **测验（quiz）**——出题 + 纯比较判分，答案 key 存服务端，证据校验防 AI 编造。
2. **主动提问（ask questions）**——AI 反问孩子诊断性问题，孩子回答后 AI 继续讲解。

## 复用策略：抄逻辑，换运行时

DeepTutor 采用 Apache-2.0 许可。其测验核心逻辑是**纯函数 + 常量**，可以逐字复制；但其外层（agent loop、SSE 流式、`ReadingContext` 扩展框架、session store）依赖 DeepTutor 的重运行时，KnoAct 不采用。

**逐字复制的部分**（写进 `backend/app/services/quiz.py`，文件头注明出处与许可）：

1. 提示词常量 `_SYSTEM_ZH`（`deeptutor/reading/quiz.py`）
2. `evidence_key` 与两个正则（`deeptutor/reading/_grounding.py`）：
   ```python
   _LINE_NUMBER = re.compile(r"^[ \t]*\d{1,4}[ \t]*$", re.MULTILINE)
   _SPACING    = re.compile(r"[\s\-­‐‑]+")
   def evidence_key(value): return _SPACING.sub("", _LINE_NUMBER.sub(" ", value.casefold()))
   ```
3. Pydantic 契约（`_QuizQuestion`：prompt 12-600、choices 恰 4 个且唯一、correct_choice_index 0-3、evidence 8-600）
4. 证据校验：`evidence_key(evidence)` 必须是 `evidence_key(全文)` 的子串
5. 判分逻辑：`is_correct = selected_index == correct_index` + 边界校验

**不复制、用 KnoAct 替代的部分**：

| DeepTutor 组件 | KnoAct 替代 |
|---|---|
| `ReadingContext` / `ReadingAction` / `ReadingExtensionManifest` | 直接传 lesson text |
| `services.llm.complete` / `json_with_reasoning_retry` | 阶段 1 的 `get_provider(db).generate(json_mode=True)` |
| session store / assessment 记录 | `Quiz` 表 + quiz_id 过期判断 |

## 明确不做（本阶段）

- 不碰 chat / visualize / solve（已能用，仅把能力 chip 补齐为 6 项入口）
- 不做「更多能力」的 deep_solve / deep_research（纯 agent 循环，无法单次同步调用移植）
- 不做可视化增强（svg / chartjs / html）——留待后续
- 不做自由文本答案的 LLM 判卷（DeepTutor 的 `quiz_judge.py`，走 WebSocket 流式）
- 不做精通之路（阶段 3）

## 数据模型

新增 `Quiz` 表（`backend/app/models.py`）：

```python
class Quiz(Base):
    __tablename__ = "quizzes"
    id: Mapped[int] = mapped_column(primary_key=True)       # 即 quiz_id
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id"))
    user_id: Mapped[int] = mapped_column(Integer, default=0)
    questions: Mapped[str] = mapped_column(TextCls)         # JSON：[{id,prompt,choices,correct_index,evidence}]
    score: Mapped[int] = mapped_column(Integer, nullable=True)  # None=未作答
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**取舍：**

- **答案 key 存服务端**：`questions` JSON 里含 `correct_index` 和 `evidence`，但 `GET` 出题时**剥离两者**，孩子永远拿不到答案。
- **题目用 JSON 文本存**，不拆子表（3 题 × 4 选项，拆表是过度设计，与阶段 1 的 `ModelProfile.options` 同风格）。
- **`evidence` 保留在服务端**，出题时校验它是课文子串，展示前移除，为将来「错题讲解指回原文」留锚点。
- **主动提问不持久化**，即时对话，两次调用之间用前端临时状态衔接。

## 后端接口

### 测验

```
POST /api/quiz/generate   {lesson_id, user_id?}
  → 取 lesson text → 出题提示词（json_mode）→ 校验 shape + evidence
  → 存 Quiz 表 → 返回 {quiz_id, questions:[{id, prompt, choices}]}  ← 无 correct_index / evidence

POST /api/quiz/submit     {quiz_id, answers:[{question_id, selected_index}]}
  → 查 Quiz → 逐题 is_correct = (selected_index == correct_index)
  → 写 score → 返回 {answers:[{question_id, is_correct}], score, total}
```

**判分零 LLM**：纯整数比较，无判分漂移。

**防重考 / 过期**：提交的 `question_id` 若不在当前 `quiz_id` 存的卷里 → 409「测验已过期」。重新生成换新 quiz_id，旧卷不可判分。

### 主动提问

```
POST /api/ask/questions   {lesson_id, context}
  → 提示词「只返回 1-4 个诊断性问题 JSON」→ 返回 {intro, questions:[{id, prompt, options:[{label}]}]}

POST /api/ask/reply       {lesson_id, context, replies:{q1:"...", q2:"..."}}
  → 提示词「基于学生回答继续讲解」→ 返回普通讲解（带 [第N句] 出处）
```

## 错误处理

| 场景 | 行为 |
|---|---|
| 证据校验失败（AI 编造原文没有的句子） | 500「出题失败，请重试」，不落库 |
| `question_id` 不在当前卷 | 409「测验已过期」 |
| `selected_index` 越界 | 422 |
| 缺课文（lesson 无 text） | 400「该课文暂无内容，无法出题」 |
| AI 返回无法解析的 JSON | 重试一次，仍失败则返回错误，不抛异常中断请求 |
| provider 是 fake（未配 key） | 503「AI 未配置」，前端提示去设置页 |

## 前端交互

### 入口（两处）

1. **对话栏能力 chip**：`CHAT_MODES` 从 3 项扩到 6 项，对齐 DeepTutor capability chip：

   ```javascript
   const CHAT_MODES = [
     {id:'chat', name:'对话', icon:'sparkles', desc:'普通问答'},
     {id:'quiz', name:'测验', icon:'list', desc:'3 道理解题'},
     {id:'questions', name:'主动提问', icon:'help', desc:'AI 考考你'},
     {id:'visualize', name:'可视化', icon:'grid', desc:'思维导图 / 流程图'},
     {id:'solve', name:'解题', icon:'pen', desc:'分步骤讲解'},
     {id:'more', name:'更多', icon:'menu', desc:'更多能力'},
   ];
   ```

2. **阅读页顶部工具栏**：沉浸式阅读 header 加「测验」「提问」两个快捷按钮，直接触发。

### 测验交互（3 题统一判分）

点「测验」→ `/api/quiz/generate` → 对话栏出现 3 道选择题卡 → 孩子勾选 → 点「提交」→ `/api/quiz/submit` → 每题标绿√红× + 「答对 N/3」。

### 主动提问交互（出题卡 → 答完继续）

点「主动提问」→ `/api/ask/questions` → 问题卡（intro + 1-4 题）→ 孩子作答 → 点「继续」→ `/api/ask/reply` → AI 返回讲解（带 `[第N句]` 跳转）。

### 复用现有 UI 资产

- 对话栏 `renderImmersiveChat` / `chatAsk` 已有一套，quiz/提问卡作为新消息类型插入
- `renderAnswer` 的 `[第N句]` 跳转、mermaid 渲染不动
- 问题卡复用现有「选词气泡」/ modal 的视觉风格

### 状态

```javascript
let quizState = {quiz_id, questions:[], answers:{}, submitted:false, results:[]};
let askState  = {questions:[], replies:{}};
```

## 测试

- `backend/tests/test_quiz.py`：
  - 出题：fake provider 返回固定 JSON → 校验落库、返回体剥离 `correct_index`/`evidence`
  - 证据校验：`evidence_key` 子串判定（含连字符断词 + 行号用例，验证抄来的代码行为一致）
  - 判分：全对 / 全错 / 部分对，`score` 正确写入
  - 过期：提交别的 quiz_id 的 `question_id` → 409
  - 越界 `selected_index` → 422
- `backend/tests/test_ask_questions.py`：提问返回 1-4 题、reply 带出处
- 前端：`node --check` + 浏览器走查

## 后续阶段

| 阶段 | 内容 | 依赖 |
|------|------|------|
| 3 | 精通之路：双层掌握度 + 门槛判定 | 阶段 2 的测验结果作为证据 |
| 4 | 打通与打磨：掌握度接进错题本/任务生成/家长报告 | 阶段 3 |
