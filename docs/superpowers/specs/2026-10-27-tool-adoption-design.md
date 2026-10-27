# KnoAct 第 5 步设计：收编剩余 AI 调用点

日期：2026-10-27

## 背景

agent-native 运行时已落地（Tool + TurnEngine + Capability + 前端流式）。但除 `/api/ask` 外，仍有 7 处 AI 调用点是「构造 prompt → 单次 `generate()`」，未收编进 agent 运行时。本次收编它们。

## 收编边界（已确认）

按「是否交互式 / 是否多步推理」分三类：

- **A 类（交互式对话）**：改走 TurnEngine（chat capability）。
- **B 类（出题 / 材料生成）**：抽象为工具，挂到 ToolRegistry。
- **C 类（单次确定性调用）**：保持现状，不强行工具化。

## 8 处调用点分类与策略

| 调用点 | 分类 | 策略 |
| --- | --- | --- |
| `routers/annotations.py` glossary（生词释义） | 已收编 | 已是 `lookup_word` 工具，不动 |
| `routers/learning.py` `review_questions`（判断题） | **死代码** | 前后端均无调用方，删除（或保持不动，不工具化） |
| `routers/learning.py` `listening_material`（听力对话） | B | 抽成 `generate_listening` 工具 |
| `routers/quiz.py` `ask_questions`（主动提问） | B | 抽成 `generate_diagnostic_questions` 工具（结构化出题，非对话） |
| `routers/quiz.py` `ask_reply`（学生回答后讲解） | A | 改走 TurnEngine（chat capability） |
| `services/quiz.py` `generate_quiz`（选择题 + evidence 校验） | B | 抽成 `generate_quiz_questions` 工具 |
| `services/lesson_extract.py`（拆课提取） | C | 保持现状（后台批处理） |
| `services/pdf_split.py` `ocr_image`（OCR） | C | 保持现状（单次视觉调用） |
| `services/question_gen.py`（阅读理解题入库） | C | 保持现状（后台入库） |

注：`quiz_submit` 已是纯比较判分（`grade_answers`，无 LLM），不需收编。

## 设计

### 1. 新增出题工具（B 类，`tools/generation.py`）

新建 `backend/app/tools/generation.py`，含 2 个 `BaseTool` 子类 + 单例：

- `generate_listening`（听力对话，来自 `listening_material`）
- `generate_quiz_questions`（选择题 + evidence 校验，来自 `services/quiz.py generate_quiz`）

注：`review_questions` 是死代码，不工具化（见上表）。

**工具拿 provider / db 的方式**：`BaseTool.run(args, ctx)` 是同步签名、无 db 参数。与 `lookup_word` 一致——工具在 `run` 内开 `SessionLocal` + `get_provider(db)`，用完 `db.close()`。`generate_quiz_questions` 的 `services/quiz.py generate_quiz(db, text, n)` 需要 db，同样在工具内开 session 传入。

### 2. `ask_reply` 改走 TurnEngine（A 类）

`ask_reply`（学生答完诊断题后讲解）是对话场景，改走 `route_to_capability`：

```python
@router.post("/ask/reply")
async def ask_reply(req: AskReplyReq, db: Session = Depends(get_db)):
    ctx = UnifiedContext(
        user_id=0, lesson_id=req.lesson_id,
        question="学生回答如下，请继续讲解课文",  # 意图注入
        text=req.context or _lesson_text(db, req.lesson_id),
        mode="chat",
    )
    return await route_to_capability(ctx)
```

**问题**：`ask_reply` 需要把 `replies`（学生的诊断回答）拼进 question 或 context，让 LLM 知道学生答了什么。方案：把 `replies` 序列化进 `question` 字段（如 `question=f"学生对这些问题的回答：{json.dumps(replies)}，请继续讲解课文"`）。

**响应契约**：`route_to_capability` 返回 `{answer, citations, mode}`，与 `ask_reply` 现有返回 `{answer, citations}` **兼容**（多了 mode 字段，前端不读也不影响）。所以前端 `submitAskReplies` **不需要改**。

### 3. `ask_questions` 是否改走 TurnEngine？

**关键判断**：`ask_questions` 返回结构化 `{intro, questions:[{id,prompt,options}]}` 供前端渲染选择题卡片，**不是对话回答**。它有两条路：

- **路 A（保持 endpoint 单次调用，仅抽 prompt 到 service）**：最小改动，`ask_questions` 保持现状，只把 prompt 逻辑抽到 service 层（或保持原样，因为已经在 router 里且能工作）。
- **路 B（抽成 `generate_diagnostic_questions` 工具）**：严格「全部收编」，但工具返回结构化 questions，前端 `askCardHtml` 仍读 `d.questions`——所以 endpoint 仍需保留、只是内部改调工具。

**推荐路 B 的折中**：`ask_questions` endpoint 保留（响应契约不变、前端不动），内部从「拼 prompt + generate」改为「调用 `generate_diagnostic_questions` 工具」。这样逻辑统一到工具层，endpoint 只做「调工具 + 返回」。

### 4. 前端影响

| 端点 | 前端调用方 | 是否需改 |
| --- | --- | --- |
| `review_questions` | （查前端调用） | 契约不变则不需改 |
| `listening_material` | （查前端调用） | 契约不变则不需改 |
| `ask_questions` | `startAskQuestions`（line 1936） | 不需改（契约 `{questions}` 不变） |
| `ask_reply` | `submitAskReplies`（line 1949） | 不需改（契约 `{answer, citations}` 兼容） |

**关键原则**：收编是**后端重构**，响应契约全部保持不变，前端零改动。

### 5. 收编后的形态

收编后，7 处调用点的形态：

| 调用点 | 收编后形态 |
| --- | --- |
| `review_questions` | endpoint 调 `generate_review_question` 工具 |
| `listening_material` | endpoint 调 `generate_listening` 工具 |
| `ask_questions` | endpoint 调 `generate_diagnostic_questions` 工具 |
| `ask_reply` | endpoint 走 `route_to_capability`（TurnEngine） |
| `generate_quiz`（services） | 抽成 `generate_quiz_questions` 工具，`quiz_generate` endpoint 调它 |
| `lesson_extract` / `question_gen` / `ocr_image` | 保持现状（C 类） |

## 非目标

- C 类（OCR/拆课/后台出题）不工具化。
- 前端零改动（响应契约全兼容）。
- 不引入新的 capability（`ask_reply` 复用现有 `chat` capability；B 类都是工具，不是 capability）。
- 不做这些出题工具在 agent 循环里的「自主组合」优化（当前只需让端点能调工具即可，未来 LLM 在 TurnEngine 里也能调它们）。

## 测试

1. `test_generation_tools.py`：3 个出题工具的 `run` 返回正确结构（mock provider）。
2. `test_ask_reply_routes.py`：`ask_reply` 走 TurnEngine 返回 `{answer, citations}`（fake provider 走降级）。
3. 回归：现有 `test_learning.py`、`test_quiz.py`、`test_ask_questions.py` 全绿（响应契约不变）。
