# 孩子讲一遍（表达练习）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让孩子对一个知识点写一段自己的解释，家长端能看到这段原话。

**Architecture:** 一张表 `ExpressionNote`（刻意不含 verdict/score）、四个 CRUD 端点、Flutter 一个输入页、家长端一个展示区块。**无 AI、无判定、不写掌握度。**

**Tech Stack:** FastAPI + SQLAlchemy (SQLite/MySQL)、pytest、Flutter + Riverpod、parent-web 原生 JS

**依据 spec:** `docs/superpowers/specs/2026-11-25-feynman-teach-ai-design.md`（v6 最小版）

---

## 设计约束（实现时不可违反）

| 约束 | 原因 |
| --- | --- |
| **表里不能有 `verdict` / `score` / `ai_*` 字段** | spec 五轮失败证明判不出「讲得好不好」，不留位置就不会有人偷偷加 |
| **不进每日任务、不计积分、不写掌握度** | 它不是学习功能，是「家长了解孩子怎么想」的窗口 |
| **结束页不评价** | 不判定就不该假装评价（连「讲得好」都不说） |
| **只有孩子本人能写** | 家长代写会让记录失去意义 |
| **年级 < 3 服务端拦截** | 低年级语言产出弱，会退化成复述 |

---

## File Structure

| 文件 | 职责 | 动作 |
| --- | --- | --- |
| `backend/app/models.py` | 新增 `ExpressionNote` | Modify |
| `backend/app/routers/expression.py` | 4 个端点：topics / notes CRUD | Create |
| `backend/app/main.py` | include_router | Modify |
| `backend/app/services/cleanup.py` | 删课时 detach `expression_notes` | Modify |
| `backend/tests/test_expression.py` | 后端测试 | Create |
| `student-app/lib/features/expression/data/expression_repository.dart` | API 调用 | Create |
| `student-app/lib/features/expression/expression_controller.dart` | 状态 | Create |
| `student-app/lib/features/expression/ui/expression_page.dart` | 输入页 + 结束态 | Create |
| `student-app/lib/core/router.dart` | 路由 + redirect 白名单 | Modify |
| `student-app/test/features/expression/expression_test.dart` | Flutter 测试 | Create |
| `parent-web/app.js` | 报告 Tab 加「孩子讲的」 | Modify |

---

## Task 1: 数据模型

**Files:**
- Modify: `backend/app/models.py`（在 `AnswerRecord` 之后追加）
- Test: `backend/tests/test_expression.py`（新建）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_expression.py`：

```python
"""表达练习（孩子讲一遍）的模型层测试。

本表刻意不含 verdict / score / ai_* —— 见 spec 的「五轮失败记录」。
"""
import inspect

from app.models import ExpressionNote


def test_expression_note_has_no_judgement_columns():
    """表里不能有判定类字段：判不出「讲得好不好」，就不给位置。"""
    cols = set(inspect.get_column_names(ExpressionNote.__table__))
    forbidden = {"verdict", "score", "passed", "grade", "ai_verdict", "ai_score"}
    assert not (cols & forbidden), f"不该有判定字段：{cols & forbidden}"
    assert not any(c.startswith("ai_") for c in cols), f"不该有 AI 字段：{cols}"


def test_expression_note_required_columns_exist():
    cols = set(inspect.get_column_names(ExpressionNote.__table__))
    for name in ("id", "user_id", "bucket_id", "knowledge_point_id", "item_id",
                 "title", "text", "created_at"):
        assert name in cols, f"缺列 {name}"


def test_expression_note_fk_ondelete_set_null():
    """知识点被删除时必须 SET NULL，否则 cleanup 删课会撞外键。"""
    for fk_col in (ExpressionNote.__table__.c.knowledge_point_id,
                   ExpressionNote.__table__.c.item_id):
        fks = list(fk_col.foreign_keys)
        assert len(fks) == 1
        assert fks[0].ondelete == "SET NULL", f"{fk_col.name} 应为 SET NULL"
```

注意：`inspect.get_column_names` 需要 `sqlalchemy.inspect`。若该辅助不存在，改用：

```python
cols = {c.name for c in ExpressionNote.__table__.columns}
```

按实际可用的写法调整，但**三条断言的含义不变**。

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_expression.py -v`

Expected: FAIL，`ImportError: cannot import name 'ExpressionNote'`

- [ ] **Step 3: 加模型**

在 `backend/app/models.py` 的 `class AnswerRecord` 之后（`class BrainGameResult` 之前）插入：

```python
class ExpressionNote(Base):
    """孩子用自己的话讲一个知识点的记录。

    刻意不含 verdict / score / ai_* 字段：本功能不做判定，也不做 AI 交互。
    详见 docs/superpowers/specs/2026-11-25-feynman-teach-ai-design.md 的「五轮失败记录」。
    """
    __tablename__ = "expression_notes"
    __table_args__ = (
        Index("ix_expression_notes_user_created", "user_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int | None] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    # 讲的是哪个：两个来源二选一（服务层校验至少一个非空）
    knowledge_point_id: Mapped[int | None] = mapped_column(
        ForeignKey("knowledge_points.id", ondelete="SET NULL"), nullable=True)
    item_id: Mapped[int | None] = mapped_column(
        ForeignKey("training_items.id", ondelete="SET NULL"), nullable=True)
    # 冗余存标题：知识点被删后家长端仍可读
    title: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(LongText)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_expression.py -v`
Expected: 3 passed

再确认表能被建出来：
Run: `cd backend && python -m pytest tests/test_schema_sync.py tests/test_models.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/tests/test_expression.py
git commit -m "feat(expression): 加 ExpressionNote 表（无判定字段）"
```

---

## Task 2: topics 端点

**Files:**
- Create: `backend/app/routers/expression.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_expression.py`（追加）

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_expression.py`：

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from conftest import bound_child_headers, make_account


def _client():
    from app.routers.expression import router as expression_router
    app = FastAPI()
    app.include_router(expression_router)
    return TestClient(app)


def _seed_child(grade=4, prefix="expr"):
    """建家长 + 孩子，返回 (child_id, headers)。"""
    from app.database import SessionLocal
    s = SessionLocal()
    p = make_account(s, f"p_{prefix}", "parent")
    u = make_account(s, f"k_{prefix}", "child", parent=p)
    u.grade = grade
    s.commit()
    uid = u.id
    s.close()
    return uid, bound_child_headers(uid)


def _seed_kp_with_mastery(user_id, content="比喻", prefix="kp"):
    """建一课 + 一个知识点 + 该孩子的 KnowledgeMastery，返回 knowledge_point_id。"""
    from app.database import SessionLocal
    from app.models import KnowledgeMastery, KnowledgePoint, Lesson, PdfDocument
    s = SessionLocal()
    doc = PdfDocument(filename=f"{prefix}.pdf", subject="语文", storage_path="")
    s.add(doc); s.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title=f"{prefix}课",
                    start_page=1, end_page=1, audit_status="approved")
    s.add(lesson); s.flush()
    kp = KnowledgePoint(lesson_id=lesson.id, subject="语文", category="修辞", content=content)
    s.add(kp); s.flush()
    s.add(KnowledgeMastery(user_id=user_id, knowledge_point_id=kp.id, attempts="[]"))
    s.commit()
    kp_id = kp.id
    s.close()
    return kp_id


def test_topics_returns_knowledge_points_with_mastery():
    uid, h = _seed_child()
    kp_id = _seed_kp_with_mastery(uid, "比喻")
    r = _client().get(f"/api/expression/topics?user_id={uid}", headers=h)
    assert r.status_code == 200
    topics = r.json()["topics"]
    assert any(t["kind"] == "knowledge_point" and t["id"] == kp_id for t in topics)
    assert any(t["title"] == "比喻" for t in topics)


def test_topics_excludes_kp_without_mastery():
    uid, h = _seed_child(prefix="expr2")
    # 建一个知识点但不建 mastery
    from app.database import SessionLocal
    from app.models import KnowledgePoint, Lesson, PdfDocument
    s = SessionLocal()
    doc = PdfDocument(filename="x.pdf", subject="语文", storage_path="")
    s.add(doc); s.flush()
    lesson = Lesson(document_id=doc.id, subject="语文", title="x课",
                    start_page=1, end_page=1, audit_status="approved")
    s.add(lesson); s.flush()
    kp = KnowledgePoint(lesson_id=lesson.id, subject="语文", category="修辞", content="没用过的")
    s.add(kp); s.commit()
    kp_id = kp.id
    s.close()

    r = _client().get(f"/api/expression/topics?user_id={uid}", headers=h)
    assert r.status_code == 200
    assert not any(t["id"] == kp_id and t["kind"] == "knowledge_point"
                   for t in r.json()["topics"])


def test_topics_returns_explore_items_only():
    """只有 kind='explore' 的条目能讲；phrase/drill_item 不返回。"""
    from app.database import SessionLocal
    from app.models import TrainingGroup, TrainingItem, User
    uid, h = _seed_child(prefix="expr3")
    s = SessionLocal()
    parent_id = s.get(User, uid).parent_id
    g = TrainingGroup(owner_id=parent_id, subject="语文", title="组", source="custom", kind="explore")
    s.add(g); s.flush()
    ex = TrainingItem(group_id=g.id, kind="explore", primary="比喻的规律")
    ph = TrainingItem(group_id=g.id, kind="drill_item", primary="不该出现")
    s.add_all([ex, ph]); s.commit()
    ex_id, ph_id = ex.id, ph.id
    s.close()

    topics = _client().get(f"/api/expression/topics?user_id={uid}", headers=h).json()["topics"]
    ids = {t["id"] for t in topics if t["kind"] == "training_item"}
    assert ex_id in ids
    assert ph_id not in ids


def test_topics_rejects_grade_below_3():
    uid, h = _seed_child(grade=2, prefix="expr4")
    r = _client().get(f"/api/expression/topics?user_id={uid}", headers=h)
    assert r.status_code == 403


def test_topics_allows_grade_none():
    """grade is None 视为 3，放行（与 bucket_service 的 grade or 3 一致）。"""
    uid, h = _seed_child(grade=None, prefix="expr5")
    r = _client().get(f"/api/expression/topics?user_id={uid}", headers=h)
    assert r.status_code == 200
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_expression.py -k topics -v`

Expected: FAIL，`ModuleNotFoundError: No module named 'app.routers.expression'`

- [ ] **Step 3: 建 router 与 topics**

创建 `backend/app/routers/expression.py`：

```python
"""孩子讲一遍（表达练习）：家长能看到孩子自己的解释。

刻意不做判定、不写掌握度——见 docs/superpowers/specs/2026-11-25-feynman-teach-ai-design.md。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.access import ensure_user_access, require_learning_user, resolve_target_user_id
from ..database import get_db
from ..models import (
    KnowledgeMastery, KnowledgePoint, TrainingGroup, TrainingItem, User,
)
from ..services.bucket_guard import resolve_bucket_id

router = APIRouter(prefix="/api/expression", tags=["expression"])

MIN_GRADE = 3


def _require_grade(user_id: int, db: Session) -> User:
    """目标孩子须 ≥3 年级；grade 为 None 视为 3（与 bucket_service 一致）。"""
    child = db.get(User, user_id)
    if child is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if (child.grade or MIN_GRADE) < MIN_GRADE:
        raise HTTPException(status_code=403, detail={"error": "grade_too_low"})
    return child


@router.get("/topics")
def list_topics(user_id: int = Depends(resolve_target_user_id),
                _auth: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    """可讲的主题：孩子有掌握度记录的知识点 + 家庭 group 下的 explore 条目。"""
    _require_grade(user_id, db)
    topics: list[dict] = []

    bid = resolve_bucket_id(db, user_id, None)
    q = (db.query(KnowledgeMastery, KnowledgePoint)
         .join(KnowledgePoint, KnowledgeMastery.knowledge_point_id == KnowledgePoint.id)
         .filter(KnowledgeMastery.user_id == user_id))
    if bid is not None:
        q = q.filter(KnowledgeMastery.bucket_id == bid)
    for _m, kp in q.order_by(KnowledgePoint.id).all():
        topics.append({"kind": "knowledge_point", "id": kp.id,
                       "title": (kp.content or "")[:255]})

    child = db.get(User, user_id)
    parent_id = child.parent_id if child else None
    if parent_id:
        group_ids = [r[0] for r in db.query(TrainingGroup.id).filter_by(owner_id=parent_id).all()]
        if group_ids:
            items = (db.query(TrainingItem)
                     .filter(TrainingItem.group_id.in_(group_ids),
                             TrainingItem.kind == "explore")
                     .order_by(TrainingItem.id).all())
            for it in items:
                topics.append({"kind": "training_item", "id": it.id,
                               "title": (it.primary or it.block_title or "")[:255]})

    return {"topics": topics}
```

- [ ] **Step 4: 注册 router**

在 `backend/app/main.py` 的 `include_router` 区加入（跟着现有格式）：

```python
from .routers import expression as expression_router
app.include_router(expression_router.router)
```

（按 main.py 现有的 import 风格调整；若那里是逐个 `from .routers import xxx` 再 `include_router(xxx.router)`，照同样写法。）

- [ ] **Step 5: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_expression.py -v`
Expected: 模型 3 条 + topics 5 条全部 PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/expression.py backend/app/main.py backend/tests/test_expression.py
git commit -m "feat(expression): topics 端点（知识点 + explore 条目）"
```

---

## Task 3: notes 的写 / 读 / 删

**Files:**
- Modify: `backend/app/routers/expression.py`
- Test: `backend/tests/test_expression.py`（追加）

- [ ] **Step 1: 写失败测试**

追加：

```python
def test_create_note_with_knowledge_point():
    uid, h = _seed_child(prefix="n1")
    kp_id = _seed_kp_with_mastery(uid, "比喻", prefix="n1")
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id,
        "text": "比喻就是把一个东西说成另一个东西，但要有相似点",
    }, headers=h)
    assert r.status_code == 200
    assert r.json()["id"] > 0


def test_create_note_snapshots_title():
    uid, h = _seed_child(prefix="n2")
    kp_id = _seed_kp_with_mastery(uid, "拟人", prefix="n2")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "拟人是把东西写成人"
    }, headers=h)
    notes = _client().get(f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"]
    assert notes[0]["title"] == "拟人"


def test_create_note_rejects_empty_text():
    uid, h = _seed_child(prefix="n3")
    kp_id = _seed_kp_with_mastery(uid, "排比", prefix="n3")
    for bad in ("", "   ", "\n\n"):
        r = _client().post("/api/expression/notes", json={
            "user_id": uid, "knowledge_point_id": kp_id, "text": bad
        }, headers=h)
        assert r.status_code == 400, f"{bad!r} 应被拒"


def test_create_note_rejects_too_long():
    uid, h = _seed_child(prefix="n4")
    kp_id = _seed_kp_with_mastery(uid, "夸张", prefix="n4")
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "字" * 5001
    }, headers=h)
    assert r.status_code == 400


def test_create_note_requires_exactly_one_target():
    uid, h = _seed_child(prefix="n5")
    kp_id = _seed_kp_with_mastery(uid, "反问", prefix="n5")
    # 两个都不给
    r = _client().post("/api/expression/notes",
                       json={"user_id": uid, "text": "讲讲"}, headers=h)
    assert r.status_code == 400
    # 两个都给
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "item_id": 1, "text": "讲讲"
    }, headers=h)
    assert r.status_code == 400


def test_create_note_rejects_unowned_knowledge_point():
    """不能讲一个自己没有掌握度记录的知识点。"""
    uid, h = _seed_child(prefix="n6")
    other_uid, _oh = _seed_child(prefix="n6b")
    kp_id = _seed_kp_with_mastery(other_uid, "别人的知识点", prefix="n6b")
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "我讲讲"
    }, headers=h)
    assert r.status_code == 403


def test_parent_cannot_create_note():
    """只有孩子本人能写；家长代写会让记录失去意义。"""
    from app.database import SessionLocal
    from app.models import User
    uid, _h = _seed_child(prefix="n7")
    kp_id = _seed_kp_with_mastery(uid, "借代", prefix="n7")
    s = SessionLocal()
    parent_id = s.get(User, uid).parent_id
    s.close()
    from conftest import auth_headers
    s = SessionLocal()
    parent_h = auth_headers(s.get(User, parent_id))
    s.close()
    r = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "家长代写"
    }, headers=parent_h)
    assert r.status_code == 403


def test_parent_can_read_child_notes():
    uid, h = _seed_child(prefix="n8")
    kp_id = _seed_kp_with_mastery(uid, "设问", prefix="n8")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "孩子写的"
    }, headers=h)

    from app.database import SessionLocal
    from app.models import User
    from conftest import auth_headers
    s = SessionLocal()
    parent_h = auth_headers(s.get(User, s.get(User, uid).parent_id))
    s.close()
    r = _client().get(f"/api/expression/notes?user_id={uid}", headers=parent_h)
    assert r.status_code == 200
    assert r.json()["notes"][0]["text"] == "孩子写的"


def test_cannot_read_other_child_notes():
    uid, h = _seed_child(prefix="n9")
    other_uid, _oh = _seed_child(prefix="n9b")
    r = _client().get(f"/api/expression/notes?user_id={other_uid}", headers=h)
    assert r.status_code == 403


def test_delete_note():
    uid, h = _seed_child(prefix="n10")
    kp_id = _seed_kp_with_mastery(uid, "对偶", prefix="n10")
    note_id = _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "删掉我"
    }, headers=h).json()["id"]
    r = _client().delete(f"/api/expression/notes/{note_id}", headers=h)
    assert r.status_code == 200
    assert _client().get(f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"] == []


def test_cannot_delete_other_child_note():
    uid, h = _seed_child(prefix="n11")
    other_uid, other_h = _seed_child(prefix="n11b")
    kp_id = _seed_kp_with_mastery(other_uid, "对比", prefix="n11b")
    note_id = _client().post("/api/expression/notes", json={
        "user_id": other_uid, "knowledge_point_id": kp_id, "text": "别人的"
    }, headers=other_h).json()["id"]
    r = _client().delete(f"/api/expression/notes/{note_id}", headers=h)
    assert r.status_code == 403


def test_note_survives_knowledge_point_deletion():
    """知识点被删后，记录仍可读（title 快照 + FK SET NULL）。"""
    from app.database import SessionLocal
    from app.models import KnowledgePoint
    uid, h = _seed_child(prefix="n12")
    kp_id = _seed_kp_with_mastery(uid, "被删掉的知识点", prefix="n12")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "我讲过了"
    }, headers=h)

    s = SessionLocal()
    s.query(KnowledgePoint).filter_by(id=kp_id).delete(synchronize_session=False)
    s.commit()
    s.close()

    notes = _client().get(f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"]
    assert len(notes) == 1
    assert notes[0]["title"] == "被删掉的知识点"
    assert notes[0]["text"] == "我讲过了"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_expression.py -k "note" -v`

Expected: FAIL，`404 Not Found`（端点还没实现）

- [ ] **Step 3: 实现三个端点**

追加到 `backend/app/routers/expression.py`：

```python
from datetime import datetime

from fastapi import Body
from pydantic import BaseModel

from ..models import ExpressionNote
from ..services.bucket_guard import assert_writable

MAX_TEXT_LEN = 5000


class NoteReq(BaseModel):
    user_id: int
    knowledge_point_id: int | None = None
    item_id: int | None = None
    text: str


def _validate_target(child: User, req: NoteReq, db: Session) -> str:
    """校验主题归属并返回 title 快照。"""
    if (req.knowledge_point_id is None) == (req.item_id is None):
        raise HTTPException(status_code=400, detail="必须且只能指定一个主题")

    if req.knowledge_point_id is not None:
        bid = resolve_bucket_id(db, child.id, None)
        q = db.query(KnowledgeMastery).filter_by(
            user_id=child.id, knowledge_point_id=req.knowledge_point_id)
        if bid is not None:
            q = q.filter(KnowledgeMastery.bucket_id == bid)
        if q.first() is None:
            raise HTTPException(status_code=403, detail={"error": "forbidden"})
        kp = db.query(KnowledgePoint).filter_by(id=req.knowledge_point_id).first()
        if kp is None:
            raise HTTPException(status_code=404, detail="知识点不存在")
        return (kp.content or "")[:255]

    parent_id = child.parent_id
    item = (db.query(TrainingItem)
            .join(TrainingGroup, TrainingItem.group_id == TrainingGroup.id)
            .filter(TrainingItem.id == req.item_id,
                    TrainingGroup.owner_id == parent_id,
                    TrainingItem.kind == "explore")
            .first())
    if item is None:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})
    return (item.primary or item.block_title or "")[:255]


@router.post("/notes")
def create_note(req: NoteReq, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    ensure_user_access(user, req.user_id, db)
    # 只有孩子本人能写
    if user.id != req.user_id:
        raise HTTPException(status_code=403, detail={"error": "forbidden"})

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="内容不能为空")
    if len(text) > MAX_TEXT_LEN:
        raise HTTPException(status_code=400, detail=f"内容不能超过 {MAX_TEXT_LEN} 字")

    child = _require_grade(req.user_id, db)
    title = _validate_target(child, req, db)

    bid = resolve_bucket_id(db, req.user_id, None)
    note = ExpressionNote(
        user_id=req.user_id, bucket_id=bid,
        knowledge_point_id=req.knowledge_point_id, item_id=req.item_id,
        title=title, text=text,
    )
    db.add(note); db.commit(); db.refresh(note)
    return {"id": note.id, "created_at": note.created_at.isoformat()}


@router.get("/notes")
def list_notes(user_id: int = Depends(resolve_target_user_id),
               _auth: User = Depends(require_learning_user),
               limit: int = 50, db: Session = Depends(get_db)):
    """不按桶过滤：家长要能看孩子以前怎么讲的，这些内容无调度含义。"""
    _require_grade(user_id, db)
    rows = (db.query(ExpressionNote).filter_by(user_id=user_id)
            .order_by(ExpressionNote.created_at.desc())
            .limit(max(1, min(limit, 200))).all())
    return {"notes": [
        {"id": n.id, "title": n.title, "text": n.text,
         "created_at": n.created_at.isoformat()}
        for n in rows
    ]}


@router.delete("/notes/{note_id}")
def delete_note(note_id: int, user: User = Depends(require_learning_user),
                db: Session = Depends(get_db)):
    note = db.get(ExpressionNote, note_id)
    if note is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    ensure_user_access(user, note.user_id, db)
    try:
        assert_writable(db, note.user_id, note.bucket_id)
    except PermissionError:
        raise HTTPException(status_code=400, detail="历史学年只读")
    db.delete(note); db.commit()
    return {"ok": True}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_expression.py -v`
Expected: 全部 PASS（模型 3 + topics 5 + notes 12）

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/expression.py backend/tests/test_expression.py
git commit -m "feat(expression): notes 写/读/删（孩子可写，家长可读）"
```

---

## Task 4: 删课时不撞外键

**Files:**
- Modify: `backend/app/services/cleanup.py:22-29`（`detach_points`）
- Test: `backend/tests/test_expression.py`（追加）

- [ ] **Step 1: 写失败测试**

追加：

```python
def test_purge_lesson_does_not_break_on_expression_notes():
    """删课（含知识点）时，expression_notes 不能撞外键。"""
    from app.database import SessionLocal
    from app.models import KnowledgePoint, Lesson
    from app.services.cleanup import purge_lessons

    uid, h = _seed_child(prefix="pg1")
    kp_id = _seed_kp_with_mastery(uid, "要被删的", prefix="pg1")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "我讲过了"
    }, headers=h)

    s = SessionLocal()
    lesson_id = s.get(KnowledgePoint, kp_id).lesson_id
    purge_lessons(s, [lesson_id])   # 不应抛外键异常
    s.close()

    notes = _client().get(f"/api/expression/notes?user_id={uid}", headers=h).json()["notes"]
    assert len(notes) == 1
    assert notes[0]["title"] == "要被删的"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_expression.py -k purge -v`

Expected: 在 SQLite 上可能因 FK 未强制而“假通过”。**先确认测试真的能暴露问题**：在 `conftest.py` 已对 SQLite 开启 `PRAGMA foreign_keys=ON`，所以预期 FAIL（`FOREIGN KEY constraint failed` 或 `Note` 相关）。若通过，说明 SET NULL 已生效，本任务可只做 Step 3 的显式 detach 以保证 MySQL 上同样安全。

- [ ] **Step 3: 在 cleanup 里 detach**

在 `backend/app/services/cleanup.py` 的 `detach_points` 里，`Note` 那段之后追加：

```python
    db.query(ExpressionNote).filter(ExpressionNote.knowledge_point_id.in_(point_ids)).update(
        {ExpressionNote.knowledge_point_id: None}, synchronize_session=False)
```

并把 import 改成包含 `ExpressionNote`（看文件顶部现有 import 的写法，通常是 `from ..models import KnowledgePoint, KnowledgeMastery, Mistake, Note` 这种）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_expression.py tests/test_fk_cleanup.py -v`
Expected: 全部 PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/services/cleanup.py backend/tests/test_expression.py
git commit -m "fix(cleanup): 删课时 detach expression_notes"
```

---

## Task 5: Flutter 输入页

**Files:**
- Create: `student-app/lib/features/expression/data/expression_repository.dart`
- Create: `student-app/lib/features/expression/expression_controller.dart`
- Create: `student-app/lib/features/expression/ui/expression_page.dart`
- Modify: `student-app/lib/core/router.dart`
- Test: `student-app/test/features/expression/expression_test.dart`

- [ ] **Step 1: 写失败测试**

创建 `student-app/test/features/expression/expression_test.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:student_app/features/expression/ui/expression_done_view.dart';

/// 结束页不能有任何评价性语言：本功能不做判定，评价就是撒谎。
void main() {
  testWidgets('结束页只说记下来了，不评价', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ExpressionDoneView())),
    );

    expect(find.textContaining('记下来了'), findsOneWidget);

    // 不得出现评价词
    const banned = ['好', '棒', '正确', '完整', '不错', '优秀', '错'];
    for (final word in banned) {
      expect(find.textContaining(word), findsNothing,
          reason: '结束页不该出现「$word」——本功能不判定');
    }
  });

  testWidgets('结束页有「再讲一个」和「返回」', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: Scaffold(body: ExpressionDoneView())),
    );
    expect(find.text('再讲一个'), findsOneWidget);
    expect(find.text('返回'), findsOneWidget);
  });
}
```

- [ ] **Step 2: 运行确认失败**

Run: `cd student-app && flutter test test/features/expression/expression_test.dart`

Expected: FAIL，找不到 `expression_done_view.dart`

- [ ] **Step 3: 写结束页**

Create `student-app/lib/features/expression/ui/expression_done_view.dart`：

```dart
import 'package:flutter/material.dart';

import '../../../core/theme.dart';

/// 写完后的结束页。
///
/// 刻意不评价：本功能不做判定（见 spec 的「五轮失败记录」）。
/// 说「讲得好」等于撒谎——系统并不知道他讲得对不对。
class ExpressionDoneView extends StatelessWidget {
  const ExpressionDoneView({super.key, this.onAgain, this.onBack});

  final VoidCallback? onAgain;
  final VoidCallback? onBack;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.check_circle_outline, size: 48, color: AppColors.green),
            const SizedBox(height: 16),
            const Text('记下来了',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            Text('你讲的这段话，爸爸/妈妈能看到。',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: AppColors.gray, height: 1.6)),
            const SizedBox(height: 24),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                OutlinedButton(onPressed: onAgain, child: const Text('再讲一个')),
                const SizedBox(width: 12),
                FilledButton(onPressed: onBack, child: const Text('返回')),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: 运行确认通过**

Run: `cd student-app && flutter test test/features/expression/expression_test.dart`
Expected: 2 passed

- [ ] **Step 5: 写 repository 与 controller**

Create `student-app/lib/features/expression/data/expression_repository.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api_client.dart';
import '../../../core/providers.dart';

class ExpressionTopic {
  const ExpressionTopic({required this.kind, required this.id, required this.title});
  final String kind;   // knowledge_point | training_item
  final int id;
  final String title;

  static ExpressionTopic? tryParse(Object? raw) {
    if (raw is! Map) return null;
    final id = (raw['id'] as num?)?.toInt();
    if (id == null) return null;
    return ExpressionTopic(
      kind: '${raw['kind'] ?? ''}',
      id: id,
      title: '${raw['title'] ?? ''}',
    );
  }
}

class ExpressionRepository {
  ExpressionRepository(this._api);

  final ApiClient _api;

  Future<List<ExpressionTopic>> topics({required int userId}) async {
    final raw = await _api.get('/api/expression/topics?user_id=$userId');
    final m = asMap(raw);
    final list = m['topics'];
    if (list is! List) return const [];
    return [for (final t in list) ExpressionTopic.tryParse(t)]
        .whereType<ExpressionTopic>()
        .toList();
  }

  Future<void> createNote({
    required int userId,
    int? knowledgePointId,
    int? itemId,
    required String text,
  }) async {
    await _api.post('/api/expression/notes', body: {
      'user_id': userId,
      if (knowledgePointId != null) 'knowledge_point_id': knowledgePointId,
      if (itemId != null) 'item_id': itemId,
      'text': text,
    });
  }
}

final expressionRepositoryProvider =
    Provider<ExpressionRepository>((ref) => ExpressionRepository(ref.watch(apiClientProvider)));
```

Create `student-app/lib/features/expression/expression_controller.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../auth/session.dart';
import 'data/expression_repository.dart';

class ExpressionState {
  const ExpressionState({
    this.topics = const [],
    this.selected,
    this.text = '',
    this.busy = false,
    this.done = false,
  });

  final List<ExpressionTopic> topics;
  final ExpressionTopic? selected;
  final String text;
  final bool busy;
  final bool done;

  ExpressionState copyWith({
    List<ExpressionTopic>? topics,
    ExpressionTopic? Function()? selected,
    String? text,
    bool? busy,
    bool? done,
  }) =>
      ExpressionState(
        topics: topics ?? this.topics,
        selected: selected != null ? selected() : this.selected,
        text: text ?? this.text,
        busy: busy ?? this.busy,
        done: done ?? this.done,
      );
}

class ExpressionController extends Notifier<ExpressionState> {
  int? get _uid => ref.read(currentChildIdProvider);

  @override
  ExpressionState build() {
    ref.watch(currentChildIdProvider);
    return const ExpressionState();
  }

  Future<void> loadTopics() async {
    final uid = _uid;
    if (uid == null) return;
    try {
      final topics = await ref.read(expressionRepositoryProvider).topics(userId: uid);
      state = state.copyWith(topics: topics);
    } catch (_) {
      state = state.copyWith(topics: const []);
    }
  }

  void select(ExpressionTopic t) => state = state.copyWith(selected: () => t);

  void setText(String v) => state = state.copyWith(text: v);

  Future<void> submit() async {
    final uid = _uid;
    final sel = state.selected;
    if (uid == null || sel == null || state.busy) return;
    if (state.text.trim().isEmpty) return;

    state = state.copyWith(busy: true);
    try {
      await ref.read(expressionRepositoryProvider).createNote(
            userId: uid,
            knowledgePointId: sel.kind == 'knowledge_point' ? sel.id : null,
            itemId: sel.kind == 'training_item' ? sel.id : null,
            text: state.text.trim(),
          );
      state = state.copyWith(busy: false, done: true);
    } catch (_) {
      state = state.copyWith(busy: false);
    }
  }

  void again() => state = const ExpressionState();
}

final expressionControllerProvider =
    NotifierProvider<ExpressionController, ExpressionState>(ExpressionController.new);
```

- [ ] **Step 6: 确认编译**

Run: `cd student-app && flutter analyze`
Expected: 无新增 error（基线 15 条 info）

- [ ] **Step 7: 提交**

```bash
git add student-app/lib/features/expression/ student-app/test/features/expression/
git commit -m "feat(student-app): 表达练习的仓储/控制器/结束页"
```

---

## Task 6: Flutter 输入页与路由

**Files:**
- Create: `student-app/lib/features/expression/ui/expression_page.dart`
- Modify: `student-app/lib/core/router.dart`

- [ ] **Step 1: 写输入页**

Create `student-app/lib/features/expression/ui/expression_page.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/theme.dart';
import '../../../core/widgets.dart';
import '../../shell/task_page_app_bar.dart';
import '../expression_controller.dart';
import 'expression_done_view.dart';

class ExpressionPage extends ConsumerWidget {
  const ExpressionPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final s = ref.watch(expressionControllerProvider);
    final ctl = ref.read(expressionControllerProvider.notifier);

    if (s.done) {
      return Scaffold(
        appBar: const TaskPageAppBar(title: '讲一遍'),
        body: ExpressionDoneView(
          onAgain: ctl.again,
          onBack: () => Navigator.of(context).maybePop(),
        ),
      );
    }

    if (s.selected == null) {
      return Scaffold(
        appBar: const TaskPageAppBar(title: '讲一遍'),
        body: s.topics.isEmpty
            ? const Center(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Text('还没有可以讲的知识点，先去学一课吧。',
                      textAlign: TextAlign.center,
                      style: TextStyle(color: AppColors.gray, height: 1.6)),
                ),
              )
            : ListView(
                padding: const EdgeInsets.all(20),
                children: [
                  const Text('挑一个来讲',
                      style: TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                  const SizedBox(height: 12),
                  for (final t in s.topics)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: OutlinedButton(
                        onPressed: () => ctl.select(t),
                        child: Align(
                          alignment: Alignment.centerLeft,
                          child: Text(t.title.isEmpty ? '（未命名）' : t.title),
                        ),
                      ),
                    ),
                ],
              ),
      );
    }

    final canSubmit = s.text.trim().isNotEmpty && !s.busy;
    return Scaffold(
      appBar: const TaskPageAppBar(title: '讲一遍'),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          SectionCard(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(s.selected!.title,
                  style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700)),
              const SizedBox(height: 12),
              const Text('用你自己的话讲讲这个知识点，就当讲给一个完全不懂的人听。',
                  style: TextStyle(fontSize: 13, color: AppColors.gray, height: 1.6)),
              const SizedBox(height: 12),
              TextField(
                key: const ValueKey('expression-input'),
                maxLines: 8,
                maxLength: 5000,
                decoration: const InputDecoration(
                  hintText: '随便说，说多少都行…',
                  border: OutlineInputBorder(),
                ),
                onChanged: ctl.setText,
              ),
            ]),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: canSubmit ? ctl.submit : null,
            child: Text(s.busy ? '正在保存…' : '讲完了'),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 2: 加路由**

在 `student-app/lib/core/router.dart` 里：

1. 加 import：`import '../features/expression/ui/expression_page.dart';`
2. 在路由表加一条 `GoRoute(path: '/expression', builder: (_, __) => const ExpressionPage())`
3. **把 `/expression` 加进 redirect 白名单**（该处是精确路径集合匹配，漏一条会被弹回 `/home`）

按文件现有写法调整；三项缺一不可。

- [ ] **Step 3: 确认编译与测试**

Run: `cd student-app && flutter analyze && flutter test`
Expected: analyze 无新增 error；全部测试通过

- [ ] **Step 4: 提交**

```bash
git add student-app/lib/features/expression/ui/expression_page.dart student-app/lib/core/router.dart
git commit -m "feat(student-app): 表达练习输入页与路由"
```

---

## Task 7: 家长端展示

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1: 加载函数**

在 `parent-web/app.js` 里，跟着 `loadMasteryReport` 的写法加：

```javascript
let expressionNotes = [];
async function loadExpressionNotes(){
  if(!uid){ expressionNotes = []; return []; }
  try{
    const r = await api(`/api/expression/notes?user_id=${uid}&limit=20`);
    expressionNotes = r.notes || [];
  }catch(_){ expressionNotes = []; }
  return expressionNotes;
}
```

并在切换孩子时清空（找到 `masteryReport = null;` 那几处，一起加 `expressionNotes = [];`）。

- [ ] **Step 2: 渲染区块**

在 `renderReportTab()` 里，掌握度 panel 之后、`当天做题明细` panel 之前插入：

```javascript
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic purple">${icon('edit',20)}</div>
        <div><h3>孩子讲的</h3><div class="sub">孩子用自己的话讲知识点（原话，未做对错判断）</div></div></div>
      <div class="bd">
        ${expressionNotes.length ? expressionNotes.map(n=>`
          <div class="goal-item" style="display:block">
            <div class="g-top"><span class="g-name">${escapeAttr(n.title||'（未命名）')}</span></div>
            <div class="g-meta" style="white-space:pre-wrap;line-height:1.7">${escapeAttr(n.text)}</div>
            <div class="g-meta">${escapeAttr((n.created_at||'').slice(0,16).replace('T',' '))}</div>
          </div>`).join('')
          : '<p style="font-size:13px;color:var(--gray2)">还没有讲过</p>'}
      </div>
    </div>
```

**必须用 `escapeAttr` 转义**（`text` 是孩子自由输入）。

- [ ] **Step 3: 加进报告 Tab 的加载**

找到 `Promise.all([loadReport(), loadMasteryReport(), loadAnswerRecords()])`（约第 279 行），加上 `loadExpressionNotes()`。

- [ ] **Step 4: 手动验证**

```bash
cd backend && python -m uvicorn app.main:app --port 8010
python -m http.server 8767 --directory parent-web
```

浏览器打开 `http://127.0.0.1:8767` → 报告 Tab → 应看到「孩子讲的」区块。

- [ ] **Step 5: 提交**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): 报告页加「孩子讲的」"
```

---

## Task 8: 端到端验证

**Files:** 无

- [ ] **Step 1: 后端（必须在 backend 目录，否则读空库）**

```bash
cd backend && python -m uvicorn app.main:app --port 8010
```

- [ ] **Step 2: 学生端**

```bash
cd student-app && flutter run -d chrome
```

- [ ] **Step 3: 走一遍**

| 步骤 | 期望 |
| --- | --- |
| 进 `/expression` | 看到可讲的主题列表（或「还没有可以讲的知识点」） |
| 选一个 | 出现题干 + 输入框 |
| 不输入 | 「讲完了」置灰 |
| 输入一段后提交 | 进入结束页「记下来了」 |
| **看结束页** | **没有任何评价词**（好/棒/正确/不完整） |
| 家长端报告 Tab | 看到刚才那段原话 |

- [ ] **Step 4: 验证年级门槛**

把某个孩子的 `grade` 改成 2：

```bash
cd backend && python -c "
import sqlite3
c = sqlite3.connect('zhixueban.db')
c.execute('update users set grade=2 where role=\"child\" limit 1')
c.commit()
print('ok')
"
```

重新打开 `/expression` → 应提示不可用（或列表为空）。改回 3 以上再验证。

---

## 自检记录

**Spec 覆盖**

| spec 要求 | 对应任务 |
| --- | --- |
| `ExpressionNote` 无判定字段 | Task 1（测试断言字段不存在） |
| `title` 快照规则 | Task 3（`_validate_target` 返回快照） |
| FK `ondelete='SET NULL'` | Task 1（模型）+ Task 4（cleanup detach） |
| `bucket_id` 写入、读取不按桶过滤 | Task 3（`resolve_bucket_id` / `list_notes` 不过滤） |
| topics 两个数据源 | Task 2 |
| 年级门槛服务端强制 | Task 2（`_require_grade`，四个端点都调） |
| 只有孩子本人能写 | Task 3（`user.id != req.user_id` → 403） |
| `assert_writable` + PermissionError | Task 3（`delete_note`） |
| 结束页不评价 | Task 5（测试断言无评价词） |
| 家长端展示（`renderReportTab` + `Promise.all`） | Task 7 |
| 不进每日任务 / 不计积分 / 不写掌握度 | 全计划无相关改动（未调用 `record_attempt`，未改 `task_gen`） |

**Placeholder 扫描**：无 TBD；每个代码步骤都给了完整代码。

**类型一致性**：
- `ExpressionNote.title` 是 `str`（255），`_validate_target` 返回 `str`，一致。
- topics 返回的 `kind` 只有 `knowledge_point` / `training_item` 两种，Dart 侧 `select()` 用同一字符串判断，一致。
- `NoteReq.text` 在服务层 `strip()` 后校验，与 Flutter 侧 `state.text.trim().isEmpty` 对应。

**已知偏差**：
- Task 4 Step 2 提到「SQLite 上可能假通过」——因为 `ondelete="SET NULL"` 已在 Task 1 生效，显式 detach 仍要做，保证 MySQL 与清理顺序无关。
