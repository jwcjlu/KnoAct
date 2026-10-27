# KnoAct 第 5 步实现计划：收编 AI 调用点

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 收编剩余 AI 调用点：B 类（出题/材料）抽成工具挂 ToolRegistry，A 类（`ask_reply` 对话讲解）改走 TurnEngine，C 类保持现状。响应契约全兼容，前端零改动。

**Architecture:** 新建 `tools/generation.py` 放 `generate_listening`、`generate_quiz_questions` 两个工具；`ask_questions` endpoint 改调 `generate_diagnostic_questions` 工具（结构化出题，仍单次）；`ask_reply` endpoint 改走 `route_to_capability`（复用 chat capability）。

**Tech Stack:** FastAPI + SQLAlchemy + pytest。工具在 `run` 内开 SessionLocal + get_provider（与 `lookup_word` 一致）。

---

## 文件结构总览

**新增：**
- `backend/app/tools/generation.py` — `generate_listening` / `generate_quiz_questions` / `generate_diagnostic_questions` 3 个工具

**修改：**
- `backend/app/routers/learning.py` — `listening_material` 改调 `generate_listening` 工具；删除死代码 `review_questions`
- `backend/app/routers/quiz.py` — `ask_questions` 改调 `generate_diagnostic_questions` 工具；`ask_reply` 改走 `route_to_capability`；`quiz_generate` 改调 `generate_quiz_questions` 工具

**测试新增：**
- `backend/tests/test_generation_tools.py`

**测试修改：**
- `backend/tests/test_learning.py`（如 `review_questions` 有测试则删/改）
- `backend/tests/test_ask_questions.py`（`ask_reply` 契约验证）

---

## Task 1: 新增 tools/generation.py（3 个出题工具）

**Files:**
- Create: `backend/app/tools/generation.py`
- Test: `backend/tests/test_generation_tools.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_generation_tools.py`：

```python
from app.core.context import UnifiedContext
from app.tools.generation import generate_listening, generate_quiz_questions, generate_diagnostic_questions


def _ctx():
    return UnifiedContext(user_id=1, lesson_id=1, question="")


def test_generate_listening_returns_structure():
    # fake provider 返回 [fake] 前缀，非合法 JSON，工具应走兜底返回默认对话
    result = generate_listening.run({}, _ctx())
    assert "dialogue" in result
    assert "question" in result
    assert "answer" in result


def test_generate_diagnostic_questions_returns_questions():
    result = generate_diagnostic_questions.run({"context": "白鹭是一首精巧的诗。"}, _ctx())
    # fake provider 走兜底：返回 questions 列表（可为空，但结构正确）
    assert "questions" in result
    assert isinstance(result["questions"], list)
```

注意：`generate_quiz_questions` 依赖 `services/quiz.py generate_quiz`，fake provider 下会 `raise QuizGenerationError("AI 未配置")`，所以它的测试要 mock provider 或断言它抛错。这里先不测 `generate_quiz_questions` 的 fake 路径（见 Task 3 的 endpoint 测试）。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_generation_tools.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.tools.generation'`）

- [ ] **Step 3: 写实现**

创建 `backend/app/tools/generation.py`：

```python
"""出题/材料生成工具：generate_listening / generate_quiz_questions / generate_diagnostic_questions。"""
import json

from ..core.context import UnifiedContext
from ..core.tool_protocol import BaseTool, ToolParameter


def _get_provider():
    from ..database import SessionLocal
    from ..services.ai import get_provider
    db = SessionLocal()
    try:
        return get_provider(db)
    finally:
        db.close()


def _get_db_session():
    from ..database import SessionLocal
    return SessionLocal()


class GenerateListeningTool(BaseTool):
    name = "generate_listening"
    description = "用小学生已学单词编一段英语对话，并出一道理解题"
    parameters = []

    def run(self, args, ctx: UnifiedContext) -> dict:
        provider = _get_provider()
        try:
            text = provider.generate(
                prompt='用小学生已学单词编一段 3 句的英语对话，并出 1 道理解题。'
                       '只返回 JSON，格式：{"dialogue":"对话内容","question":"题目","answer":"答案"}',
                system="你是英语老师。",
                json_mode=True,
            )
            data = json.loads(text)
            return {
                "dialogue": (data.get("dialogue") or "").strip(),
                "question": (data.get("question") or "").strip(),
                "answer": (data.get("answer") or "").strip(),
            }
        except Exception:
            # 兜底：默认对话
            return {
                "dialogue": "A: What can you do? B: I can sing.",
                "question": "对话里 B 会做什么？",
                "answer": "唱歌",
            }


class GenerateQuizQuestionsTool(BaseTool):
    name = "generate_quiz_questions"
    description = "针对课文出选择题（带证据校验）"
    parameters = [
        ToolParameter(name="text", type="string", description="课文内容"),
        ToolParameter(name="n", type="integer", description="题目数量", required=False),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        from ..services.quiz import generate_quiz, QuizGenerationError
        db = _get_db_session()
        try:
            text = (args.get("text") or "").strip()
            n = args.get("n") or 3
            questions = generate_quiz(db, text, n=n)
            return {"questions": questions}
        except QuizGenerationError as e:
            return {"questions": [], "error": str(e)}
        finally:
            db.close()


class GenerateDiagnosticQuestionsTool(BaseTool):
    name = "generate_diagnostic_questions"
    description = "针对一段课文，提出 1-4 个高信息量诊断性问题（选项可为空）"
    parameters = [
        ToolParameter(name="context", type="string", description="课文内容"),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        provider = _get_provider()
        context = (args.get("context") or "").strip()
        if not context:
            return {"intro": "", "questions": []}
        system = (
            "你是小学生的学习助手，正在主动提问。请针对下面这段课文，"
            "一次性提出 1-4 个只有学生能补充的高信息量诊断性问题，不要重复已知信息。"
            '只返回 JSON：{"intro":"简短引导语","questions":[{"id":"q1","prompt":"问题",'
            '"options":[{"label":"选项"}]}]}。选项可为空数组，表示自由作答。'
        )
        try:
            raw = provider.generate(prompt=f"课文：\n{context[:6000]}", system=system, json_mode=True)
            data = json.loads(raw)
            return {"intro": data.get("intro", ""), "questions": data.get("questions") or []}
        except Exception:
            return {"intro": "", "questions": []}


generate_listening = GenerateListeningTool()
generate_quiz_questions = GenerateQuizQuestionsTool()
generate_diagnostic_questions = GenerateDiagnosticQuestionsTool()
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_generation_tools.py -v`
Expected: PASS（2 个测试；fake provider 下 `generate_listening` 走兜底、`generate_diagnostic_questions` 走兜底返回空 questions）

- [ ] **Step 5: 提交**

```bash
git add backend/app/tools/generation.py backend/tests/test_generation_tools.py
git commit -m "feat: 出题/材料生成工具（generate_listening/quiz_questions/diagnostic_questions）"
```

---

## Task 2: learning.py 收编（listening_material + 删 review_questions 死代码）

**Files:**
- Modify: `backend/app/routers/learning.py`
- Test: `backend/tests/test_learning.py`

- [ ] **Step 1: 检查现有测试**

先看 `backend/tests/test_learning.py` 是否有 `review_questions` 或 `listening_material` 的测试。运行：

Run: `cd backend && python -m pytest tests/test_learning.py -v`
Expected: 确认当前通过情况，以及是否有涉及 `review_questions`/`listening_material` 的测试。

（本任务的测试改动依赖现有测试内容，需先看 `test_learning.py` 里有没有这两个端点的测试。如果 `listening_material` 有测试，其断言应是 `{"text": ..., "questions": [...]}`，而工具返回 `{"dialogue", "question", "answer"}`——需在 endpoint 里做字段映射，保持响应契约不变。）

- [ ] **Step 2: 改 listening_material 端点**

修改 `backend/app/routers/learning.py` 的 `listening_material`（line 116-139），改为调工具并映射回原契约：

```python
@router.get("/api/listening/material")
def listening_material(user_id: int, db: Session = Depends(get_db)):
    from ..tools.generation import generate_listening
    from ..core.context import UnifiedContext
    ctx = UnifiedContext(user_id=user_id, lesson_id=0, question="")
    result = generate_listening.run({}, ctx)
    # 映射回原响应契约：{text, questions:[{question, answer}]}
    return {
        "text": result["dialogue"],
        "questions": [{"question": result["question"], "answer": result["answer"]}],
    }
```

- [ ] **Step 3: 删除 review_questions 死代码**

删除 `backend/app/routers/learning.py` 的 `review_questions`（line 80-97）整个函数。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_learning.py tests/test_ask_questions.py -v`
Expected: PASS（`listening_material` 契约不变；`review_questions` 删除后若无测试引用则无影响）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/learning.py backend/tests/test_learning.py
git commit -m "refactor: listening_material 改调工具 + 删 review_questions 死代码"
```

---

## Task 3: quiz.py 收编（ask_questions/ask_reply/quiz_generate）

**Files:**
- Modify: `backend/app/routers/quiz.py`
- Test: `backend/tests/test_ask_questions.py`

- [ ] **Step 1: 写/改测试**

先看 `backend/tests/test_ask_questions.py` 现有测试，确认 `ask_questions`/`ask_reply` 的契约断言。

`ask_reply` 改走 TurnEngine 后，fake provider 走降级，返回 `{answer, citations, mode}`（`answer` 是「抱歉…」文案）。需确认现有测试是否兼容。

（本任务先读现有测试，再决定是否需调整断言。核心：`ask_reply` 返回契约 `{answer, citations}` 不变，`ask_questions` 返回 `{intro, questions}` 不变。）

- [ ] **Step 2: 改 ask_questions 调工具**

修改 `backend/app/routers/quiz.py` 的 `ask_questions`（line 87-107），改为调 `generate_diagnostic_questions` 工具：

```python
@router.post("/ask/questions")
def ask_questions(req: AskQuestionsReq, db: Session = Depends(get_db)):
    from ..tools.generation import generate_diagnostic_questions
    from ..core.context import UnifiedContext
    ctx_text = req.context or _lesson_text(db, req.lesson_id)
    if not ctx_text:
        raise HTTPException(status_code=400, detail="该课文暂无内容")
    ctx = UnifiedContext(user_id=0, lesson_id=req.lesson_id, question="")
    result = generate_diagnostic_questions.run({"context": ctx_text}, ctx)
    if not result["questions"]:
        raise HTTPException(status_code=503, detail="AI 未配置")
    return {"intro": result["intro"], "questions": result["questions"]}
```

- [ ] **Step 3: 改 ask_reply 走 TurnEngine**

修改 `backend/app/routers/quiz.py` 的 `ask_reply`（line 110-127），改为走 `route_to_capability`：

```python
@router.post("/ask/reply")
async def ask_reply(req: AskReplyReq, db: Session = Depends(get_db)):
    from ..core.context import UnifiedContext
    from ..runtime.orchestrator import route_to_capability
    ctx_text = req.context or _lesson_text(db, req.lesson_id)
    replies_text = json.dumps(req.replies, ensure_ascii=False)
    ctx = UnifiedContext(
        user_id=0, lesson_id=req.lesson_id,
        question=f"学生对这些诊断性问题的回答：{replies_text}，请基于回答继续用小学生能懂的话讲解课文，涉及原文某句时在那句后标 [第N句]。",
        text=ctx_text,
        mode="chat",
    )
    return await route_to_capability(ctx)
```

- [ ] **Step 4: 改 quiz_generate 调工具**

修改 `backend/app/routers/quiz.py` 的 `quiz_generate`（line 43-59），改为调 `generate_quiz_questions` 工具：

```python
@router.post("/quiz/generate")
def quiz_generate(req: QuizGenerateReq, db: Session = Depends(get_db)):
    from ..tools.generation import generate_quiz_questions
    from ..core.context import UnifiedContext
    text = _lesson_text(db, req.lesson_id)
    if not text:
        raise HTTPException(status_code=400, detail="该课文暂无内容，无法出题")
    kps = [{"id": k.id, "category": k.category, "content": k.content}
           for k in db.query(KnowledgePoint).filter_by(lesson_id=req.lesson_id).all()]
    ctx = UnifiedContext(user_id=req.user_id, lesson_id=req.lesson_id, question="")
    result = generate_quiz_questions.run({"text": text, "n": 3}, ctx)
    if not result.get("questions"):
        raise HTTPException(status_code=503, detail=result.get("error", "AI 未配置"))
    quiz = Quiz(lesson_id=req.lesson_id, user_id=req.user_id,
                questions=json.dumps(result["questions"], ensure_ascii=False))
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return {"quiz_id": quiz.id, "questions": strip_key(result["questions"])}
```

注意：`knowledge_points`（kps）在工具版里暂时没用上（`generate_quiz_questions` 工具签名没有 knowledge_points 参数）。若需保留知识点关联，需给工具加参数——但设计里 `generate_quiz` 的 knowledge_points 是可选的，且 `quiz_generate` 的 kps 目前是为了出题时关联知识点。**为保持行为一致，需给工具加 `knowledge_points` 参数**，或在 endpoint 里先不做知识点关联（原逻辑是传 kps 给 generate_quiz）。

**修正**：给 `generate_quiz_questions` 工具加 `knowledge_points` 参数（JSON 文本），并在 `run` 里解析。见本任务 Step 5 的补充。

- [ ] **Step 5: 补充 generate_quiz_questions 的 knowledge_points 支持**

回到 `backend/app/tools/generation.py`，给 `GenerateQuizQuestionsTool` 加参数：

```python
class GenerateQuizQuestionsTool(BaseTool):
    name = "generate_quiz_questions"
    description = "针对课文出选择题（带证据校验，可选知识点关联）"
    parameters = [
        ToolParameter(name="text", type="string", description="课文内容"),
        ToolParameter(name="n", type="integer", description="题目数量", required=False),
        ToolParameter(name="knowledge_points", type="string", description="知识点 JSON 数组文本", required=False),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        from ..services.quiz import generate_quiz, QuizGenerationError
        db = _get_db_session()
        try:
            text = (args.get("text") or "").strip()
            n = args.get("n") or 3
            kps_raw = args.get("knowledge_points") or ""
            kps = json.loads(kps_raw) if kps_raw else None
            questions = generate_quiz(db, text, n=n, knowledge_points=kps)
            return {"questions": questions}
        except QuizGenerationError as e:
            return {"questions": [], "error": str(e)}
        finally:
            db.close()
```

然后 `quiz_generate` 里传 `knowledge_points=json.dumps(kps)`：

```python
    result = generate_quiz_questions.run(
        {"text": text, "n": 3, "knowledge_points": json.dumps(kps, ensure_ascii=False)}, ctx)
```

- [ ] **Step 6: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_quiz.py tests/test_ask_questions.py tests/test_generation_tools.py -v`
Expected: PASS（契约不变，`ask_reply` 走 TurnEngine 降级仍返回 `{answer, citations}`）

- [ ] **Step 7: 提交**

```bash
git add backend/app/routers/quiz.py backend/app/tools/generation.py backend/tests/test_ask_questions.py backend/tests/test_generation_tools.py
git commit -m "refactor: quiz 三端点收编（ask_questions/quiz_generate 调工具 + ask_reply 走 TurnEngine）"
```

---

## Task 4: 全量回归 + 文档

**Files:**
- Modify: `AGENTS.md`（roadmap 第 5 步标注）

- [ ] **Step 1: 全量回归**

Run: `cd backend && python -m pytest -v`
Expected: 全绿（应 160+ 测试）。

- [ ] **Step 2: 更新 AGENTS.md**

把「Agent-Native Roadmap」第 5 步改为「✅ DONE」，并说明收编结果：

```
5. ✅ **DONE — 收编散落的 prompt 调用点**：出题/材料生成抽成工具
   （`tools/generation.py`：generate_listening / generate_quiz_questions /
   generate_diagnostic_questions），`ask_reply` 改走 TurnEngine（chat capability）；
   生词释义已是 `lookup_word` 工具。OCR / 拆课 / 后台出题（C 类单次确定性调用）
   保持现状，`review_questions`（死代码）已删除。
```

- [ ] **Step 3: 提交**

```bash
git add AGENTS.md
git commit -m "docs: roadmap 第 5 步（收编调用点）已落地"
```

---

## 自审记录

- **Spec 覆盖**：设计 5 节 → Task 1（新工具）、Task 2（learning.py）、Task 3（quiz.py 三端点）、Task 4（回归+文档）。全覆盖。
- **Placeholder 扫描**：无 TBD/TODO。每个代码步骤含完整代码。Task 2 Step 1 和 Task 3 Step 1 有「先读现有测试」的步骤（因测试内容依赖现有文件，需运行时确认），但实现代码已完整给出。
- **类型一致性**：3 个工具（Task 1 定义）在 Task 2/3 被 `run({...}, ctx)` 调用，签名一致；`generate_quiz_questions` 的 `knowledge_points` 参数（Task 3 Step 5 补充）在 `run` 里 `json.loads`，与 `generate_quiz` 的 `knowledge_points: list[dict]` 签名一致；`ask_reply` 走 `route_to_capability` 返回 `{answer, citations, mode}`，与原 `{answer, citations}` 兼容（多 mode 字段）。
- **注意点**：`learning.py` 和 `quiz.py` 需确认是否在用户未提交改动列表——据 session 开始时的 git status，`learning.py` 和 `quiz.py` 都**不在**未提交列表（只有 pdf.py/lesson_extract/pdf_split/index.html 在），所以安全。
