"""数学出题 + 数值归一判分 + 进度按学科隔离。"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from conftest import make_account, make_lesson, bound_child_headers


def test_grade_math_answer_normalization():
    from app.services.math_gen import grade_math_answer
    assert grade_math_answer("8", "8.0") is True
    assert grade_math_answer("8", "八") is True
    assert grade_math_answer("8", "8 个") is True
    assert grade_math_answer("8", "9") is False
    assert grade_math_answer("3/4", "0.75") is True
    assert grade_math_answer("十二", "12") is True
    assert grade_math_answer("二十五", "25") is True


def test_generate_math_questions_fallback(setup_db):
    from app.services.math_gen import generate_math_questions, FALLBACK_MATH_QUESTIONS
    from app.database import SessionLocal
    s = SessionLocal()
    # 无真实 provider（fake）时返回兜底题，绝不抛异常
    qs = generate_math_questions(s, "认识加法", n=3)
    assert len(qs) == len(FALLBACK_MATH_QUESTIONS)
    for q in qs:
        assert q["question"] and q["answer"]
    s.close()


def test_generate_math_questions_split_respects_counts(setup_db):
    from app.services.math_gen import generate_math_questions_split
    from app.database import SessionLocal
    s = SessionLocal()
    split = generate_math_questions_split(s, "认识加法", n_calc=2, n_word=1)
    assert set(split.keys()) == {"calc", "word"}
    assert len(split["calc"]) == 2
    assert len(split["word"]) == 1
    for q in split["calc"] + split["word"]:
        assert q["question"] and str(q["answer"]).strip()
    s.close()


def test_math_material_endpoint(setup_db):
    from app.models import User, Lesson, Text, UserDocument
    from app.database import SessionLocal
    from app.routers.math import router as math_router
    s = SessionLocal()
    make_lesson(s, subject="数学", title="第 1 单元 · 加法", extract_status="done")
    s.commit()
    lesson = s.query(Lesson).filter_by(subject="数学").first()
    s.add(Text(lesson_id=lesson.id, content="认识加法：3+5=8"))
    p = make_account(s, "p_mm", "parent")
    uid = make_account(s, "晨晨", "child", parent=p).id
    s.add(UserDocument(user_id=uid, document_id=lesson.document_id))
    s.commit()
    lid = lesson.id
    s.close()

    app = FastAPI()
    app.include_router(math_router)
    c = TestClient(app)
    h = bound_child_headers(uid)
    r = c.get(f"/api/math/material?lesson_id={lid}", headers=h)
    assert r.status_code == 200
    d = r.json()
    assert d["title"] == "第 1 单元 · 加法"
    assert len(d["questions"]) == 3
    for q in d["questions"]:
        assert q["id"] and q["question"] and q["answer"]


def test_grade_math_work_photo_fake_branches(setup_db):
    from app.services.math_gen import grade_math_work_photo, CONFIDENCE_THRESHOLD
    from app.database import SessionLocal
    s = SessionLocal()
    ok = grade_math_work_photo(s, b"\x89PNG", "小明有几个？", "5")
    for key in ("final_answer", "steps_plausible", "confidence", "reason", "ai_status", "ai_correct"):
        assert key in ok
    assert ok["ai_status"] == "ok"
    assert ok["confidence"] >= CONFIDENCE_THRESHOLD
    pending = grade_math_work_photo(s, b"__FORCE_PENDING__", "题", "5")
    assert pending["ai_status"] == "pending_review"
    failed = grade_math_work_photo(s, b"__FORCE_FAIL__", "题", "5")
    assert failed["ai_status"] == "failed"
    s.close()


def test_parse_math_task_content_legacy_list():
    from app.services.math_gen import parse_math_task_content
    import json
    raw = json.dumps([{"question": "1+1", "answer": "2"}], ensure_ascii=False)
    parsed = parse_math_task_content(raw)
    assert len(parsed["calc"]) == 1 and parsed["word"] == []


def test_math_task_material_hides_word_answer(setup_db):
    import json
    from datetime import date
    from app.models import User, Task
    from app.database import SessionLocal
    from app.routers.math import router as math_router
    s = SessionLocal()
    p = make_account(s, "p_mtm", "parent")
    make_account(s, "晨晨", "child", parent=p)
    s.commit()
    uid = s.query(User).filter_by(name="晨晨").first().id
    content = {
        "calc": [{"question": "3+5=？", "answer": "8"}],
        "word": [{"id": "w1", "question": "还剩几个？", "answer": "5"}],
    }
    t = Task(user_id=uid, date=date.today(), subject="数学", task_type="math", title="数学",
             content=json.dumps(content, ensure_ascii=False), points=20, content_status="published")
    s.add(t); s.commit()
    tid = t.id
    s.close()

    app = FastAPI()
    app.include_router(math_router)
    c = TestClient(app)
    r = c.get(f"/api/math/task/{tid}/material", headers=bound_child_headers(uid))
    d = r.json()
    assert d["ok"] is True
    assert "answer" not in d["calc"][0]
    assert "answer" not in d["word"][0]
    assert d["word"][0]["question"] == "还剩几个？"


def test_math_task_grade_split_calc_only(setup_db):
    import json
    from datetime import date
    from app.models import User, Task
    from app.database import SessionLocal
    from app.routers.math import router as math_router
    s = SessionLocal()
    p = make_account(s, "p_mtg2", "parent")
    make_account(s, "晨晨", "child", parent=p)
    s.commit()
    uid = s.query(User).filter_by(name="晨晨").first().id
    content = {
        "calc": [{"question": "3+5=？", "answer": "8"}],
        "word": [{"question": "应用", "answer": "5"}],
    }
    t = Task(user_id=uid, date=date.today(), subject="数学", task_type="math", title="数学",
             content=json.dumps(content, ensure_ascii=False), points=20, content_status="published")
    s.add(t); s.commit()
    tid = t.id
    s.close()

    app = FastAPI()
    app.include_router(math_router)
    c = TestClient(app)
    h = bound_child_headers(uid)
    r = c.post(f"/api/math/task/{tid}/grade", json={"user_id": uid, "answers": ["8"]}, headers=h)
    d = r.json()
    assert d["ok"] is True and d["total"] == 1
    s2 = SessionLocal()
    saved = json.loads(s2.get(Task, tid).content)
    assert saved["calc"][0]["is_correct"] is True
    assert "is_correct" not in saved["word"][0]
    s2.close()


def test_math_task_grade_endpoint(setup_db):
    import json
    from datetime import date
    from app.models import User, Task, Mistake
    from app.database import SessionLocal
    from app.routers.math import router as math_router
    s = SessionLocal()
    p = make_account(s, "p_mtg", "parent")
    make_account(s, "晨晨", "child", parent=p)
    s.commit()
    uid = s.query(User).filter_by(name="晨晨").first().id
    qs = [{"question": "3 + 5 = ？", "answer": "8"}, {"question": "12 - 7 = ？", "answer": "5"}]
    t = Task(user_id=uid, date=date.today(), subject="数学", task_type="math", title="数学练习",
             content=json.dumps(qs, ensure_ascii=False), points=20, content_status="published")
    s.add(t); s.commit()
    tid = t.id
    s.close()

    app = FastAPI()
    app.include_router(math_router)
    c = TestClient(app)
    h = bound_child_headers(uid)
    r = c.post(f"/api/math/task/{tid}/grade", json={"user_id": uid, "answers": ["八", "6"]}, headers=h)
    d = r.json()
    assert d["ok"] is True
    assert d["correct"] == 1 and d["total"] == 2
    assert d["results"][1] == {"is_correct": False, "correct_answer": "5"}

    s2 = SessionLocal()
    m = s2.query(Mistake).filter_by(user_id=uid, question="12 - 7 = ？").first()
    assert m is not None and m.source_type == "math" and m.your_answer == "6"
    saved = json.loads(s2.get(Task, tid).content)
    assert [q["your_answer"] for q in saved] == ["八", "6"]
    assert [q["is_correct"] for q in saved] == [True, False]
    s2.get(Task, tid).submit_status = "approved"
    s2.commit()
    s2.close()

    r2 = c.post(f"/api/math/task/{tid}/grade", json={"user_id": uid, "answers": ["8", "5"]}, headers=h)
    assert r2.json()["ok"] is False


def test_math_task_grade_scoped_to_bucket(setup_db):
    import json
    from datetime import date
    from app.models import User, Task, Mistake
    from app.database import SessionLocal
    from app.services.bucket_service import ensure_bucket
    from app.routers.math import router as math_router
    s = SessionLocal()
    p = make_account(s, "p_mts", "parent")
    make_account(s, "晨晨", "child", parent=p)
    s.commit()
    uid = s.query(User).filter_by(name="晨晨").first().id
    b = ensure_bucket(s, uid)
    b_id = b.id
    qs = [{"question": "3 + 5 = ？", "answer": "8"}, {"question": "12 - 7 = ？", "answer": "5"}]
    t = Task(user_id=uid, date=date.today(), subject="数学", task_type="math", title="数学练习",
             content=json.dumps(qs, ensure_ascii=False), points=20, content_status="published",
             bucket_id=b_id)
    s.add(t); s.commit()
    tid = t.id
    s.close()

    app = FastAPI()
    app.include_router(math_router)
    c = TestClient(app)
    h = bound_child_headers(uid)
    r = c.post(f"/api/math/task/{tid}/grade", json={"user_id": uid, "answers": ["八", "6"]}, headers=h)
    assert r.json()["ok"] is True

    s2 = SessionLocal()
    m = s2.query(Mistake).filter_by(user_id=uid, question="12 - 7 = ？").first()
    assert m is not None
    assert m.bucket_id == b_id  # 错题挂在 active 桶，而非 NULL 命名空间
    s2.close()


def test_progress_advance_subject_isolation(setup_db):
    from app.models import User, Lesson, LearningProgress
    from app.database import SessionLocal
    from app.routers.progress import router as progress_router
    s = SessionLocal()
    p = make_account(s, "p_pais", "parent")
    make_account(s, "晨晨", "child", parent=p)
    s.commit()
    uid = s.query(User).filter_by(name="晨晨").first().id
    make_lesson(s, subject="语文", title="语文第1课")
    make_lesson(s, subject="数学", title="数学第1课")
    s.commit()
    math_lesson_id = s.query(Lesson).filter_by(subject="数学").first().id
    s.close()

    app = FastAPI()
    app.include_router(progress_router)
    c = TestClient(app)
    h = bound_child_headers(uid)
    r = c.post("/api/progress/advance", json={"user_id": uid, "correct": 3, "total": 3, "subject": "数学"},
               headers=h)
    assert r.json()["passed"] is True

    s2 = SessionLocal()
    prog = s2.query(LearningProgress).filter_by(user_id=uid, subject="数学").first()
    assert prog is not None
    assert prog.current_lesson_id == math_lesson_id
    # 语文进度行未创建，说明数学推进不影响语文
    chinese_prog = s2.query(LearningProgress).filter_by(user_id=uid, subject="语文").first()
    assert chinese_prog is None
    s2.close()
