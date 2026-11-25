# 答 + 指（答案与出处一起判定）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让孩子在选择题答完后指出「从哪里看出来的」，把二元对错升级为四态判定，同时识别「蒙对」与「理解对但表达弱」。

**Architecture:** 后端在 `/api/quiz/submit` 新增可选的 `evidence_sentence` 入参，用已有的 `evidence_key` 归一化与题目自带的 `evidence` 做包含比较，算出一个 `verdict` 随判分结果返回，并落到 `AnswerRecord` 两个新列。前端在 `ImmersiveQuizCard` 的每题下方加「点亮那一句」的句子选择区，提交后按 `verdict` 显示四种不同文案。

**Tech Stack:** FastAPI + SQLAlchemy (SQLite/MySQL)、pytest、Flutter + Riverpod、flutter_test

---

## 背景与设计约束

依据 `docs/superpowers/specs/2026-11-24-learning-first-principles-design.md` 第 5.1 节与「第五部分附」附.1：

- **只在思考层内容强制**：本计划**只改 `/api/quiz/submit`（边读边问测验）**，不动听写（原料层）。
- **出处不进前端**：`strip_key` 已剥离 `evidence`，前端拿不到正确答案的出处，只能拿到课文句子列表自己选。
- **四态而非二态**：`confirmed` / `lucky` / `expression_weak` / `not_understood`。
- **向后兼容**：`evidence_sentence` 不传时 `evidence_ok = None`、`verdict = "unknown"`，判分与现有一致。
- **`❌ + ✅` 不打红叉**：`expression_weak` 的 UI 必须是中性/绿色，不能是错误色。

### verdict 语义

| verdict | 答案 | 出处 | 含义 |
| --- | --- | --- | --- |
| `confirmed` | 对 | 对 | 真会 |
| `lucky` | 对 | 错 | 蒙对了 |
| `expression_weak` | 错 | 对 | 想对了，说错了 |
| `not_understood` | 错 | 错 | 没懂 |
| `unknown` | — | 未提供 | 未作答出处（兼容旧客户端） |

---

## File Structure

| 文件 | 职责 | 动作 |
| --- | --- | --- |
| `backend/app/services/quiz.py` | 新增纯函数 `grade_verdict`（出处比较 + 四态映射），供路由复用 | Modify |
| `backend/app/models.py` | `AnswerRecord` 加 `evidence_text` / `evidence_ok` | Modify |
| `backend/app/services/answer_record.py` | `record_answer` 透传两个新字段 | Modify |
| `backend/app/routers/quiz.py` | `/api/quiz/submit` 接收 `evidence_sentence`、算 verdict、落库、返回 | Modify |
| `backend/tests/test_quiz.py` | `grade_verdict` 单测 | Modify |
| `backend/tests/test_quiz_submit_evidence.py` | 端点级集成测试 | Create |
| `student-app/lib/features/ask/data/read_ask_cards_models.dart` | `ReaderQuizGradeRow` 加 `verdict` | Modify |
| `student-app/lib/features/ask/data/read_ask_cards_repository.dart` | `submitQuiz` 传 `sentences` / 回传 `evidence_sentence` | Modify |
| `student-app/lib/features/ask/immersive_quiz_controller.dart` | state 记 `evidencePicks`（题目 id → 句子下标） | Modify |
| `student-app/lib/features/ask/ui/immersive_quiz_cards.dart` | 句子选择区 + 四态文案 | Modify |
| `student-app/test/features/ask/quiz_evidence_test.dart` | 四态文案与选择交互测试 | Create |

---

## Task 1: 后端——`grade_verdict` 纯函数

**Files:**
- Modify: `backend/app/services/quiz.py`（在 `grade_answers` 之后追加）
- Test: `backend/tests/test_quiz.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_quiz.py` 顶部 import 改为：

```python
from app.services.quiz import evidence_key, grade_answers, grade_verdict, quiz_system_prompt
```

在文件末尾追加：

```python
def test_grade_verdict_confirmed_when_answer_and_evidence_correct():
    # 答案对、指出的句子就是支持答案的原文
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="弯弯的月亮像一条小船",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == "confirmed"


def test_grade_verdict_lucky_when_answer_right_but_evidence_wrong():
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="小鸟在枝头唱歌",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == "lucky"


def test_grade_verdict_expression_weak_when_answer_wrong_but_evidence_right():
    # 这是最要紧的一态：理解到位、表达没到位
    assert grade_verdict(
        answer_correct=False,
        chosen_evidence="弯弯的月亮像一条小船。",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == "expression_weak"


def test_grade_verdict_not_understood_when_both_wrong():
    assert grade_verdict(
        answer_correct=False,
        chosen_evidence="小鸟在枝头唱歌",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == "not_understood"


def test_grade_verdict_unknown_when_no_evidence_provided():
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == "unknown"


def test_grade_verdict_unknown_when_question_has_no_evidence():
    # 题库题可能没 evidence（Question.evidence 为空），此时无法判出处
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="随便一句",
        correct_evidence="",
    ) == "unknown"


def test_grade_verdict_evidence_match_ignores_whitespace_and_punctuation_spacing():
    # 归一化后比较：全角空格、换行、行号都不影响
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="弯弯的月亮\n像一条小船",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == "confirmed"


def test_grade_verdict_evidence_match_allows_partial_sentence():
    # 孩子可能只点到句中的短语，只要归一化后是子串就算对
    assert grade_verdict(
        answer_correct=True,
        chosen_evidence="像一条小船",
        correct_evidence="弯弯的月亮像一条小船。",
    ) == "confirmed"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_quiz.py -k grade_verdict -v`

Expected: FAIL，`ImportError: cannot import name 'grade_verdict'`

- [ ] **Step 3: 写最小实现**

在 `backend/app/services/quiz.py` 末尾追加：

```python
VERDICT_CONFIRMED = "confirmed"
VERDICT_LUCKY = "lucky"
VERDICT_EXPRESSION_WEAK = "expression_weak"
VERDICT_NOT_UNDERSTOOD = "not_understood"
VERDICT_UNKNOWN = "unknown"


def evidence_matches(chosen: str, correct: str) -> bool:
    """孩子指出的句子是否等价于（或包含于）支持答案的原文。

    两边都用 evidence_key 归一化（去空白、去行号、去连字符断词），再做双向包含：
    孩子可能只点中原文的一部分，也可能原文比孩子点的短。
    """
    chosen_key = evidence_key(chosen or "")
    correct_key = evidence_key(correct or "")
    if not chosen_key or not correct_key:
        return False
    return chosen_key in correct_key or correct_key in chosen_key


def grade_verdict(
    answer_correct: bool,
    chosen_evidence: str,
    correct_evidence: str,
) -> str:
    """四态判定：答案对错 × 出处对错。

    与 spec 5.1 的 2×2 一一对应。任一侧无法判定（孩子没指 / 题目没 evidence）
    都返回 unknown，不猜测——这与「允许未决」一致：证据不足时不强行判决。
    """
    if not (chosen_evidence or "").strip() or not (correct_evidence or "").strip():
        return VERDICT_UNKNOWN
    evidence_ok = evidence_matches(chosen_evidence, correct_evidence)
    if answer_correct and evidence_ok:
        return VERDICT_CONFIRMED
    if answer_correct and not evidence_ok:
        return VERDICT_LUCKY
    if not answer_correct and evidence_ok:
        return VERDICT_EXPRESSION_WEAK
    return VERDICT_NOT_UNDERSTOOD
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_quiz.py -v`

Expected: 全部 PASS（含原有的 evidence_key / grade_answers 测试）

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/quiz.py backend/tests/test_quiz.py
git commit -m "feat(quiz): 加 grade_verdict 四态判定（答案 x 出处）"
```

---

## Task 2: 后端——`AnswerRecord` 加出处两列

**Files:**
- Modify: `backend/app/models.py:630-638`（`AnswerRecord` 字段区）
- Modify: `backend/app/services/answer_record.py`（`record_answer` 签名与构造）
- Test: `backend/tests/test_answer_record.py`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_answer_record.py` 末尾追加（若文件已有 `record_answer` 的用法，保持同样风格）：

```python
def test_record_answer_persists_evidence_fields(db):
    from app.services.answer_record import record_answer

    row = record_answer(
        db,
        user_id=1,
        subject="语文",
        module="quiz",
        question="「月亮像一条小船」用了什么修辞？",
        student_answer="比喻",
        correct_answer="比喻",
        is_correct=True,
        source_type="quiz",
        source_id="q1",
        evidence_text="弯弯的月亮像一条小船。",
        evidence_ok=True,
    )
    db.commit()

    from app.models import AnswerRecord
    saved = db.get(AnswerRecord, row.id)
    assert saved.evidence_text == "弯弯的月亮像一条小船。"
    assert saved.evidence_ok is True


def test_record_answer_evidence_defaults_to_empty(db):
    from app.services.answer_record import record_answer

    row = record_answer(
        db, user_id=1, subject="语文", module="quiz",
        question="q", student_answer="a", correct_answer="a", is_correct=True,
    )
    db.commit()

    from app.models import AnswerRecord
    saved = db.get(AnswerRecord, row.id)
    assert saved.evidence_text == ""
    assert saved.evidence_ok is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_answer_record.py -k evidence -v`

Expected: FAIL，`TypeError: record_answer() got an unexpected keyword argument 'evidence_text'`

- [ ] **Step 3: 加模型列**

在 `backend/app/models.py` 的 `AnswerRecord` 里，`duration_ms` 之后、`source_type` 之前插入：

```python
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 答 + 指：孩子指出的出处原文与是否正确（None = 本次未指出处 / 题目无 evidence）
    evidence_text: Mapped[str] = mapped_column(LongText, default="")
    evidence_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), default="")
```

- [ ] **Step 4: 改 `record_answer` 透传**

在 `backend/app/services/answer_record.py` 的签名里，`duration_ms` 之后加两个参数：

```python
    duration_ms: int | None = None,
    evidence_text: str = "",
    evidence_ok: bool | None = None,
    source_type: str = "",
```

并把 `AnswerRecord(...)` 构造改为（在 `duration_ms=duration_ms,` 之后插入两行）：

```python
        duration_ms=duration_ms, evidence_text=evidence_text or "", evidence_ok=evidence_ok,
        source_type=source_type, source_id=source_id,
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_answer_record.py -v`

Expected: 全部 PASS

再跑一次全库建表校验（确认新列能被 `create_all` 建出来）：

Run: `cd backend && python -m pytest tests/test_schema_sync.py tests/test_models.py -v`

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models.py backend/app/services/answer_record.py backend/tests/test_answer_record.py
git commit -m "feat(answer-record): 加 evidence_text / evidence_ok 两列"
```

---

## Task 3: 后端——`/api/quiz/submit` 接收出处并返回 verdict

**Files:**
- Modify: `backend/app/routers/quiz.py:84-143`（`quiz_submit`）
- Test: `backend/tests/test_quiz_submit_evidence.py`（新建）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_quiz_submit_evidence.py`：

```python
"""答 + 指：/api/quiz/submit 接收 evidence_sentence 并返回 verdict。"""
import json

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AnswerRecord, Lesson, ModelConfig, PdfDocument, Quiz, Text, User
from conftest import parent_child

client = TestClient(app)

EVIDENCE = "弯弯的月亮像一条小船。"
OTHER = "小鸟在枝头唱歌。"


def _seed_quiz(questions):
    """建一套最小可提交的测验，返回 (quiz_id, headers)。

    `parent_child(session, prefix)` 返回 (parent, child, parent_h, child_h)，
    用它一次性拿到已绑定的孩子与 Bearer 头，省掉手工签 token。
    questions 里每题需含 id / prompt / choices / correct_index / evidence。
    """
    db = SessionLocal()
    for m in (AnswerRecord, Quiz, Text, Lesson, PdfDocument, User, ModelConfig):
        db.query(m).delete()
    db.commit()
    _p, u, _ph, child_h = parent_child(db, "ev")
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc)
    db.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title="第1课")
    db.add(lesson)
    db.flush()
    db.add(Text(lesson_id=lesson.id, content=f"{EVIDENCE}\n{OTHER}"))
    quiz = Quiz(lesson_id=lesson.id, user_id=u.id,
                questions=json.dumps(questions, ensure_ascii=False))
    db.add(quiz)
    db.commit()
    quiz_id = quiz.id
    db.close()
    return quiz_id, child_h


def _one_question():
    return [{
        "id": "q1",
        "prompt": f"哪一句用了比喻？",
        "choices": [EVIDENCE, OTHER, "云朵仿佛棉花糖。", "湖水很清很清。"],
        "correct_index": 0,
        "evidence": EVIDENCE,
    }]


def test_submit_returns_confirmed_when_answer_and_evidence_agree():
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0, "evidence_sentence": EVIDENCE}],
    }, headers=headers)
    assert r.status_code == 200
    row = r.json()["answers"][0]
    assert row["is_correct"] is True
    assert row["verdict"] == "confirmed"
    assert row["evidence_ok"] is True


def test_submit_returns_lucky_when_answer_right_but_evidence_wrong():
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0, "evidence_sentence": OTHER}],
    }, headers=headers)
    assert r.status_code == 200
    row = r.json()["answers"][0]
    assert row["is_correct"] is True
    assert row["verdict"] == "lucky"
    assert row["evidence_ok"] is False


def test_submit_returns_expression_weak_when_answer_wrong_but_evidence_right():
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 1, "evidence_sentence": EVIDENCE}],
    }, headers=headers)
    assert r.status_code == 200
    row = r.json()["answers"][0]
    assert row["is_correct"] is False
    assert row["verdict"] == "expression_weak"
    assert row["evidence_ok"] is True


def test_submit_returns_not_understood_when_both_wrong():
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 1, "evidence_sentence": OTHER}],
    }, headers=headers)
    assert r.status_code == 200
    assert r.json()["answers"][0]["verdict"] == "not_understood"


def test_submit_without_evidence_still_works_and_reports_unknown():
    # 旧客户端不传 evidence_sentence，判分必须与以前完全一致
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0}],
    }, headers=headers)
    assert r.status_code == 200
    row = r.json()["answers"][0]
    assert row["is_correct"] is True
    assert row["verdict"] == "unknown"
    assert row["evidence_ok"] is None


def test_submit_persists_evidence_to_answer_record():
    quiz_id, headers = _seed_quiz(_one_question())
    client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0, "evidence_sentence": OTHER}],
    }, headers=headers)
    db = SessionLocal()
    try:
        row = db.query(AnswerRecord).filter_by(module="quiz").order_by(AnswerRecord.id.desc()).first()
        assert row is not None
        assert row.evidence_text == OTHER
        assert row.evidence_ok is False
    finally:
        db.close()


def test_submit_score_unchanged_by_evidence():
    # 出处不参与对错：选了正确答案就该算对
    quiz_id, headers = _seed_quiz(_one_question())
    r = client.post("/api/quiz/submit", json={
        "quiz_id": quiz_id,
        "answers": [{"question_id": "q1", "selected_index": 0, "evidence_sentence": OTHER}],
    }, headers=headers)
    assert r.json()["score"] == 1
    assert r.json()["total"] == 1
```

- [ ] **Step 2: 确认 conftest 的 `parent_child` 行为**

Run: `cd backend && python -c "import inspect,conftest; print(inspect.signature(conftest.parent_child))"`

Expected: `(session, prefix='pc')`。它内部会 `commit`，返回 `(parent, child, parent_h, child_h)`——
测试里直接解包用第四个当 Bearer 头即可，不需要再手工签 token。

- [ ] **Step 3: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_quiz_submit_evidence.py -v`

Expected: FAIL，`KeyError: 'verdict'`（后端还没返回该字段）

- [ ] **Step 4: 改路由**

在 `backend/app/routers/quiz.py` 顶部 import 改为：

```python
from ..services.quiz import grade_answers, grade_verdict, strip_key
```

在 `quiz_submit` 里，找到 `results = grade_answers(questions, req.answers)` 这一行，替换为下面整段（到 `for q in questions:` 之前为止的原有 kp 校验保持不动）：

```python
    results = grade_answers(questions, req.answers)
    # 答 + 指：把每条答案的出处与题目 evidence 比较，产出四态 verdict
    chosen_by_qid = {a.get("question_id"): (a.get("evidence_sentence") or "").strip()
                     for a in req.answers}
    q_by_id = {q["id"]: q for q in questions}
    for r in results:
        q = q_by_id.get(r.get("question_id")) or {}
        chosen = chosen_by_qid.get(r.get("question_id"), "")
        verdict = grade_verdict(
            answer_correct=r["is_correct"] is True,
            chosen_evidence=chosen,
            correct_evidence=q.get("evidence") or "",
        )
        r["verdict"] = verdict
        r["evidence_ok"] = None if verdict == "unknown" else (verdict in ("confirmed", "expression_weak"))
```

在后续 `record_answer(...)` 调用里补两个参数（找到 `module="quiz",` 那一段，在 `duration_ms=...` 之后插入）：

```python
                evidence_text=chosen_by_qid.get(q["id"], ""),
                evidence_ok=r["evidence_ok"],
```

最后把返回体改为同时带 score：

```python
    score = sum(1 for r in results if r["is_correct"])
    quiz.score = score
    db.commit()
    return {"answers": results, "score": score, "total": len(questions)}
```

（这段本来就有，确认 `answers` 里已包含 `verdict` / `evidence_ok` 即可。）

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_quiz_submit_evidence.py -v`

Expected: 全部 PASS

再确认没破坏原有用例：

Run: `cd backend && python -m pytest tests/test_quiz.py tests/test_ask_questions.py -v`

Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/quiz.py backend/tests/test_quiz_submit_evidence.py
git commit -m "feat(quiz): submit 接收 evidence_sentence 并返回四态 verdict"
```

---

## Task 4: Flutter——模型与仓储支持出处

**Files:**
- Modify: `student-app/lib/features/ask/data/read_ask_cards_models.dart:22-46`（`ReaderQuizGradeRow`）
- Modify: `student-app/lib/features/ask/data/read_ask_cards_repository.dart:33-52`（`submitQuiz`）

- [ ] **Step 1: 加 `verdict` 到判分行**

把 `read_ask_cards_models.dart` 的 `ReaderQuizGradeRow` 换成：

```dart
class ReaderQuizGradeRow {
  const ReaderQuizGradeRow({
    required this.questionId,
    required this.isCorrect,
    this.correctIndex,
    this.selectedIndex,
    this.verdict = 'unknown',
    this.evidenceOk,
  });

  final String questionId;
  final bool isCorrect;
  final int? correctIndex;
  final int? selectedIndex;

  /// 答 + 指四态：confirmed | lucky | expression_weak | not_understood | unknown
  final String verdict;

  /// 出处是否正确；null 表示本次未指出处（旧客户端）或题目无 evidence
  final bool? evidenceOk;

  static ReaderQuizGradeRow? tryParse(Object? raw) {
    if (raw is! Map) return null;
    final qid = '${raw['question_id'] ?? ''}';
    return ReaderQuizGradeRow(
      questionId: qid,
      isCorrect: raw['is_correct'] == true,
      correctIndex: raw['correct_index'] is num ? (raw['correct_index'] as num).toInt() : null,
      selectedIndex: raw['selected_index'] is num ? (raw['selected_index'] as num).toInt() : null,
      verdict: '${raw['verdict'] ?? 'unknown'}',
      evidenceOk: raw['evidence_ok'] is bool ? raw['evidence_ok'] as bool : null,
    );
  }
}
```

- [ ] **Step 2: 改 `submitQuiz` 传句子**

把 `read_ask_cards_repository.dart` 的 `submitQuiz` 换成（新增 `evidenceSentences` 参数：题目 id → 孩子选中的句子）：

```dart
  Future<List<ReaderQuizGradeRow>> submitQuiz({
    required int quizId,
    required List<ReaderQuizQuestion> questions,
    required Map<String, int> answers,
    required int durationMs,
    Map<String, String> evidenceSentences = const {},
  }) async {
    final payload = [
      for (final q in questions)
        {
          'question_id': q.id,
          'selected_index': answers[q.id],
          'duration_ms': durationMs,
          if (evidenceSentences[q.id] != null &&
              evidenceSentences[q.id]!.isNotEmpty)
            'evidence_sentence': evidenceSentences[q.id],
        },
    ];
    final raw = await _api.post('/api/quiz/submit', body: {'quiz_id': quizId, 'answers': payload});
    final m = asMap(raw);
    final rows = m['answers'];
    if (rows is! List) return const [];
    return [for (final r in rows) ReaderQuizGradeRow.tryParse(r)].whereType<ReaderQuizGradeRow>().toList();
  }
```

- [ ] **Step 3: 确认编译**

Run: `cd student-app && flutter analyze`

Expected: 无 error（可能有既存 info/warning，不算失败）

- [ ] **Step 4: 提交**

```bash
git add student-app/lib/features/ask/data/read_ask_cards_models.dart student-app/lib/features/ask/data/read_ask_cards_repository.dart
git commit -m "feat(student-app): quiz 判分模型支持 verdict 与出处回传"
```

---

## Task 5: Flutter——控制器记录孩子指的句子

**Files:**
- Modify: `student-app/lib/features/ask/immersive_quiz_controller.dart:6-110`（`ImmersiveQuizState` + submit）

- [ ] **Step 1: state 加字段**

把 `ImmersiveQuizState` 的字段区（`final Map<String, int> answers;` 之后）加一行：

```dart
  final Map<String, int> answers;

  /// 答 + 指：题目 id → 孩子选中的句子原文（空 = 未指）
  final Map<String, String> evidencePicks;
```

构造函数参数里加（`this.answers = const {},` 之后）：

```dart
    this.evidencePicks = const {},
```

`copyWith` 参数里加 `Map<String, String>? evidencePicks,`，并在返回体里加 `evidencePicks: evidencePicks ?? this.evidencePicks,`。

- [ ] **Step 2: 加选择方法**

在 `pickAnswer` 之后追加：

```dart
  void pickEvidence(String questionId, String sentence) {
    if (state.submitted) return;
    state = state.copyWith(evidencePicks: {...state.evidencePicks, questionId: sentence});
  }
```

- [ ] **Step 3: submit 传出处**

在 `submit()` 里，把 `submitQuiz(...)` 调用改为：

```dart
      final results = await ref.read(readAskCardsRepositoryProvider).submitQuiz(
            quizId: quizId,
            questions: state.questions,
            answers: state.answers,
            durationMs: durationMs,
            evidenceSentences: state.evidencePicks,
          );
```

- [ ] **Step 4: 确认编译**

Run: `cd student-app && flutter analyze`

Expected: 无 error

- [ ] **Step 5: 提交**

```bash
git add student-app/lib/features/ask/immersive_quiz_controller.dart
git commit -m "feat(student-app): quiz 控制器记录孩子指出的句子"
```

---

## Task 6: Flutter——句子选择区与四态文案

**Files:**
- Modify: `student-app/lib/features/ask/ui/immersive_quiz_cards.dart`
- Test: `student-app/test/features/ask/quiz_evidence_test.dart`（新建）

- [ ] **Step 1: 写失败测试**

创建 `student-app/test/features/ask/quiz_evidence_test.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/ask/ui/quiz_verdict_text.dart';

void main() {
  group('quizVerdictText', () {
    test('confirmed 是正向反馈', () {
      final t = quizVerdictText('confirmed');
      expect(t, contains('关键'));
    });

    test('lucky 指出「答案对但依据不对」，不否定孩子', () {
      final t = quizVerdictText('lucky');
      expect(t, contains('依据'));
      // 不能出现「错」这种否定词
      expect(t.contains('错'), isFalse);
    });

    test('expression_weak 肯定理解，指向表达', () {
      final t = quizVerdictText('expression_weak');
      expect(t, contains('这句'));
      // 关键：不能打红叉式的否定
      expect(t.contains('错'), isFalse);
    });

    test('not_understood 引导回去看', () {
      final t = quizVerdictText('not_understood');
      expect(t, contains('再看'));
    });

    test('unknown 不显示任何出处评价', () {
      expect(quizVerdictText('unknown'), isEmpty);
    });
  });

  group('quizVerdictColor', () {
    test('expression_weak 不用错误色', () {
      expect(quizVerdictColor('expression_weak'), isNot(const Color(0xFFC05B4A)));
    });

    test('confirmed 用绿色', () {
      expect(quizVerdictColor('confirmed'), const Color(0xFF2E8B5A));
    });
  });
}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd student-app && flutter test test/features/ask/quiz_evidence_test.dart`

Expected: FAIL，找不到 `quiz_verdict_text.dart`

- [ ] **Step 3: 新建文案模块**

创建 `student-app/lib/features/ask/ui/quiz_verdict_text.dart`：

```dart
import 'package:flutter/material.dart';

/// 答 + 指四态的文案与配色。
///
/// 设计约束（见 spec 5.1 与附.1）：
/// - `expression_weak`（答案错、出处对）**不得使用错误色**，也不得说「错」。
///   这类孩子理解到位、只是表达没到，正确的响应是帮他表述，不是否定。
/// - `lucky` 同理：只指出依据不对，不说答案错（答案确实是对的）。
const _green = Color(0xFF2E8B5A);
const _amber = Color(0xFFDC872D);
const _gray = Color(0xFF78817B);

String quizVerdictText(String verdict) {
  switch (verdict) {
    case 'confirmed':
      return '对了，你找的这句正是关键。';
    case 'lucky':
      return '答案对了，但你说的这句不是依据。再看看哪句能支持它？';
    case 'expression_weak':
      return '你找的这句是对的，只是话没说明白。你想说的是什么？';
    case 'not_understood':
      return '我们回去再看看这一句。';
    default:
      return '';
  }
}

Color quizVerdictColor(String verdict) {
  switch (verdict) {
    case 'confirmed':
      return _green;
    case 'lucky':
    case 'not_understood':
      return _amber;
    case 'expression_weak':
      // 中性灰：理解是对的，不需要红叉
      return _gray;
    default:
      return _gray;
  }
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd student-app && flutter test test/features/ask/quiz_evidence_test.dart`

Expected: 全部 PASS

- [ ] **Step 5: 加句子选择 UI**

在 `immersive_quiz_cards.dart` 顶部 import 加：

```dart
import 'quiz_verdict_text.dart';
```

把 `ImmersiveQuizCard` 的 `build` 里 `_QuizQuestionBlock(...)` 的调用改为（多传三个参数）：

```dart
                _QuizQuestionBlock(
                  index: qi,
                  question: s.questions[qi],
                  chosen: s.answers[s.questions[qi].id],
                  submitted: s.submitted,
                  result: s.submitted ? _resultFor(s, qi) : null,
                  onPick: (i) => ctl.pickAnswer(s.questions[qi].id, i),
                  sentences: sentences,
                  pickedEvidence: s.evidencePicks[s.questions[qi].id],
                  onPickEvidence: (sent) => ctl.pickEvidence(s.questions[qi].id, sent),
                ),
```

在 `build` 开头、`final ctl = ...` 之后加一行取句子列表（课文全文来自 `askController` 的 context）：

```dart
    final sentences = splitSentences(ref.watch(askControllerProvider).context);
```

并加 import：

```dart
import '../../../core/text_utils.dart';
import 'ask_controller.dart';
```

把 `_QuizQuestionBlock` 换成：

```dart
class _QuizQuestionBlock extends StatelessWidget {
  const _QuizQuestionBlock({
    required this.index,
    required this.question,
    required this.chosen,
    required this.submitted,
    required this.result,
    required this.onPick,
    required this.sentences,
    required this.pickedEvidence,
    required this.onPickEvidence,
  });

  final int index;
  final ReaderQuizQuestion question;
  final int? chosen;
  final bool submitted;
  final ReaderQuizGradeRow? result;
  final ValueChanged<int> onPick;
  final List<String> sentences;
  final String? pickedEvidence;
  final ValueChanged<String> onPickEvidence;

  @override
  Widget build(BuildContext context) {
    final verdict = result?.verdict ?? 'unknown';
    final showEvidencePicker = sentences.isNotEmpty && !submitted;
    final verdictText = submitted ? quizVerdictText(verdict) : '';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(question.prompt, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600, height: 1.45)),
          for (var i = 0; i < question.choices.length; i++)
            _ChoiceTile(
              label: '${String.fromCharCode(65 + i)}. ${question.choices[i]}',
              state: _choiceVisual(i, chosen, submitted, result, question.choices.length),
              onTap: submitted ? null : () => onPick(i),
            ),
          if (showEvidencePicker && chosen != null) ...[
            const SizedBox(height: 8),
            const Text('👆 你是从课文哪一句看出来的？点亮那一句',
                style: TextStyle(fontSize: 12, color: AppColors.gray, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            for (var si = 0; si < sentences.length; si++)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: _EvidenceTile(
                  label: sentences[si],
                  selected: pickedEvidence == sentences[si],
                  onTap: () => onPickEvidence(sentences[si]),
                ),
              ),
          ],
          if (verdictText.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(verdictText,
                  style: TextStyle(fontSize: 12, color: quizVerdictColor(verdict), height: 1.5)),
            ),
        ],
      ),
    );
  }

  _ChoiceVisual _choiceVisual(int i, int? chosen, bool submitted, ReaderQuizGradeRow? r, int nChoices) {
    if (!submitted) {
      return chosen == i ? _ChoiceVisual.selected : _ChoiceVisual.normal;
    }
    final ci = r?.correctIndex;
    final sel = r?.selectedIndex ?? chosen;
    final hasKey = ci != null && ci >= 0 && ci < nChoices;
    if (hasKey && i == ci) return _ChoiceVisual.correct;
    if (hasKey && i == sel && sel != ci) return _ChoiceVisual.wrong;
    if (!hasKey && r != null && r.isCorrect && i == sel) return _ChoiceVisual.correct;
    if (!hasKey && r != null && !r.isCorrect && i == sel) return _ChoiceVisual.wrong;
    return _ChoiceVisual.normal;
  }
}

class _EvidenceTile extends StatelessWidget {
  const _EvidenceTile({required this.label, required this.selected, required this.onTap});

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: selected ? AppColors.blueSoft : Colors.white,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: selected ? AppColors.blue : const Color(0xFFE3E6E2)),
          ),
          child: Text(label,
              style: TextStyle(fontSize: 12, color: selected ? AppColors.blue : const Color(0xFF2B332E))),
        ),
      ),
    );
  }
}
```

- [ ] **Step 6: 确认编译与测试**

Run: `cd student-app && flutter analyze && flutter test test/features/ask/quiz_evidence_test.dart`

Expected: analyze 无 error；测试全部 PASS

- [ ] **Step 7: 提交**

```bash
git add student-app/lib/features/ask/ui/immersive_quiz_cards.dart student-app/lib/features/ask/ui/quiz_verdict_text.dart student-app/test/features/ask/quiz_evidence_test.dart
git commit -m "feat(student-app): quiz 加「指出处」与四态反馈文案"
```

---

## Task 7: 端到端手动验证

**Files:** 无（手动验证）

- [ ] **Step 1: 启动后端（必须在 backend 目录，否则读空库）**

```bash
cd backend && python -m uvicorn app.main:app --port 8010
```

- [ ] **Step 2: 启动学生端**

```bash
cd student-app && flutter run -d chrome
```

- [ ] **Step 3: 逐个走四种情况**

在阅读器里进入「边读边问」→ 出测验，然后：

| 情况 | 操作 | 期望 |
| --- | --- | --- |
| `confirmed` | 选对答案 + 点亮正确句 | 绿色「你找的这句正是关键」 |
| `lucky` | 选对答案 + 点亮无关句 | 琥珀色「答案对了，但你说的这句不是依据」 |
| `expression_weak` | 选错答案 + 点亮正确句 | **灰色**「你找的这句是对的，只是话没说明白」，**不得出现红叉** |
| `not_understood` | 选错答案 + 点亮无关句 | 琥珀色「我们回去再看看这一句」 |

- [ ] **Step 4: 验证不填出处不阻塞**

不点亮任何句子，直接提交 → 与改造前行为一致（能提交、能判分、无四态文案）。

- [ ] **Step 5: 验证落库**

```bash
cd backend && python -c "
import sqlite3
c = sqlite3.connect('zhixueban.db')
for r in c.execute('select question, student_answer, is_correct, evidence_text, evidence_ok from answer_records where module=\"quiz\" order by id desc limit 5'):
    print(r)
"
```

Expected: `evidence_text` 有值、`evidence_ok` 为 0/1（未指出处时为 NULL）

---

## 自检记录

**Spec 覆盖**：本计划只覆盖 spec 待整改 #1（答 + 指）。spec 其余 22 项属其他子系统，各自单独写计划。

**Placeholder 扫描**：无 TBD / TODO；每个代码步骤都给了完整代码。

**类型一致性**：
- `grade_verdict(answer_correct, chosen_evidence, correct_evidence)` → `str`，Task 1 定义、Task 3 调用一致。
- `evidence_ok` 类型：模型 `bool | None`、API `None | bool`、Dart `bool?`，一致。
- `verdict` 字符串常量 `confirmed|lucky|expression_weak|not_understood|unknown`，后端常量与 Dart switch 分支一致。
- `record_answer` 新参数名 `evidence_text` / `evidence_ok`，Task 2 定义、Task 3 调用一致。

**已知偏差**：spec 第 5.5 节称 `KnowledgePoint` 有 `original_sentence` 字段，实际**不存在**（全库搜索仅出现在文档中）。迁移缺口那条待整改需改成基于 `KnowledgePointPool.extra` 的 `example` 字段。这不影响本计划，但要在 spec 里更正。
