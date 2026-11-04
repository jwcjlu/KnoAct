# 多学生管理 + 年级/学年桶 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 KnoAct 支持多学生（家长名下多孩子）、孩子有年级并按学年「分桶」封存历史数据（错题本/练习题/掌握度/积分/目标），升年级后仍可回看低年级数据。

**Architecture:** 后端新增 `SchoolYearBucket`（学年桶）与 `ChildConfig`（孩子配置覆盖）两张表；`User` 加 `grade`/`edition`/`parent_id`；学习痕迹表加 `bucket_id` 外键。年级推进用「自然学年（9 月）+ 家长手动」双触发，幂等。所有查询端点加可选 `bucket_id`，默认取当前 active 桶。前端按桶渲染「学年切换」。

**Tech Stack:** FastAPI + SQLAlchemy（backend）；pytest + TestClient（测试）；Flutter（学生端）；原生 JS（parent-web 家长端）。

**约定：** 后端测试目录 `backend/tests/`，运行环境用 Bash 的 `python`（见 AGENTS.md「两个 Python」）。所有测试先写再实现（TDD），每任务结束时 `git commit`。

---

## 阶段一：后端数据模型（Task 1–3）

### Task 1: `User` 扩展（grade / edition / parent_id）+ `SchoolYearBucket` / `ChildConfig` 模型

**Files:**
- Modify: `backend/app/models.py`（`User` 类 ~line 10–14；文末追加两张新表）
- Test: `backend/tests/test_grade_bucket_models.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_grade_bucket_models.py`：

```python
"""学年桶与孩子档案字段的模型层测试。"""
from app.models import User, SchoolYearBucket, ChildConfig


def test_user_has_grade_edition_parent_fields(setup_db, db):
    parent = User(name="金爸爸", role="parent")
    db.add(parent); db.flush()
    child = User(name="晨晨", role="child", grade=3, edition="人教版", parent_id=parent.id)
    db.add(child); db.commit()
    got = db.get(User, child.id)
    assert got.grade == 3
    assert got.edition == "人教版"
    assert got.parent_id == parent.id


def test_user_grade_defaults_to_none(setup_db, db):
    u = User(name="老用户", role="child")
    db.add(u); db.commit()
    assert db.get(User, u.id).grade is None


def test_school_year_bucket_fields(setup_db, db):
    child = User(name="晨晨", role="child", grade=3)
    db.add(child); db.flush()
    b = SchoolYearBucket(user_id=child.id, grade=3, school_year="2025-2026", status="active")
    db.add(b); db.commit()
    got = db.get(SchoolYearBucket, b.id)
    assert got.user_id == child.id
    assert got.grade == 3
    assert got.school_year == "2025-2026"
    assert got.status == "active"


def test_child_config_override(setup_db, db):
    child = User(name="晨晨", role="child", grade=3)
    db.add(child); db.flush()
    c = ChildConfig(user_id=child.id, key="difficulty_语文", value="困难")
    db.add(c); db.commit()
    got = db.get(ChildConfig, c.id)
    assert got.key == "difficulty_语文"
    assert got.value == "困难"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_grade_bucket_models.py -v`
Expected: FAIL，报 `ImportError: cannot import name 'SchoolYearBucket'`（因为模型还没定义）。

- [ ] **Step 3: 实现模型**

在 `backend/app/models.py` 的 `User` 类（~line 10–14）加字段：

```python
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))  # 'parent' | 'child'
    grade: Mapped[int] = mapped_column(Integer, nullable=True)          # 当前年级 1~6（一年级~六年级）
    edition: Mapped[str] = mapped_column(String(64), default="")        # 教材版本（人教版/苏教版…）
    parent_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)  # 归属家长
```

在文件末尾（`RenderTask` 类之后）追加两张新表：

```python
class SchoolYearBucket(Base):
    """一个孩子的一个学年「桶」：升年级即封存旧桶、开新桶，历史数据按桶归档。"""
    __tablename__ = "school_year_buckets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    grade: Mapped[int] = mapped_column(Integer)
    school_year: Mapped[str] = mapped_column(String(16))          # 如 "2025-2026"
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | archived


class ChildConfig(Base):
    """孩子对全局配置的覆盖项；未配则回落全局 ModelConfig。跨学年沿用，不分桶。"""
    __tablename__ = "child_config"
    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_child_config_user_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[str] = mapped_column(LongText, default="")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_grade_bucket_models.py -v`
Expected: PASS（4 个测试全过）。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/models.py backend/tests/test_grade_bucket_models.py && git commit -m "feat(models): User 加 grade/edition/parent_id，新增学年桶与孩子配置表"
```

---

### Task 2: 学习痕迹表加 `bucket_id` 外键

**Files:**
- Modify: `backend/app/models.py`（`Mistake`/`Task`/`Question`/`Quiz`/`WordMastery`/`KnowledgeMastery`/`Point`/`Goal` 加 `bucket_id`）
- Test: `backend/tests/test_grade_bucket_models.py`（追加测试）

- [ ] **Step 1: 写失败测试**

在 `test_grade_bucket_models.py` 追加：

```python
def test_mistake_belongs_to_bucket(setup_db, db):
    from app.models import Mistake
    child = User(name="晨晨", role="child", grade=3)
    db.add(child); db.flush()
    b = SchoolYearBucket(user_id=child.id, grade=3, school_year="2025-2026")
    db.add(b); db.flush()
    m = Mistake(user_id=child.id, bucket_id=b.id, source_type="dictation",
                question="听写：苹果", your_answer="苹菓", correct_answer="苹果")
    db.add(m); db.commit()
    got = db.get(Mistake, m.id)
    assert got.bucket_id == b.id


def test_point_belongs_to_bucket(setup_db, db):
    from app.models import Point
    child = User(name="晨晨", role="child", grade=3)
    db.add(child); db.flush()
    b = SchoolYearBucket(user_id=child.id, grade=3, school_year="2025-2026")
    db.add(b); db.flush()
    p = Point(user_id=child.id, bucket_id=b.id, delta=20, reason="完成听写")
    db.add(p); db.commit()
    assert db.get(Point, p.id).bucket_id == b.id
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_grade_bucket_models.py -v`
Expected: FAIL，报 `TypeError`/`InvalidRequestError`（`Mistake` 无 `bucket_id` 属性）。

- [ ] **Step 3: 实现（给 8 张表加 `bucket_id`）**

在 `models.py` 对应类的字段末尾加一行 `bucket_id`（`nullable=True`，迁移回填前可为空）：

- `Mistake`（~line 132）：`bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)`
- `Task`（~line 185）：同上
- `Question`（~line 80）：同上；并加 `user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)`（题目改按孩子生成）
- `Quiz`（~line 239）：`bucket_id`（已有 `user_id`）
- `WordMastery`（~line 120）：`bucket_id`
- `KnowledgeMastery`（~line 250）：`bucket_id`
- `Point`（~line 154）：`bucket_id`
- `Goal`（~line 162）：`bucket_id`

每处加在类内字段列表末尾即可。示例（`Mistake`）：

```python
class Mistake(Base):
    __tablename__ = "mistakes"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    bucket_id: Mapped[int] = mapped_column(ForeignKey("school_year_buckets.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String(32))
    # …其余字段不变
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_grade_bucket_models.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/models.py backend/tests/test_grade_bucket_models.py && git commit -m "feat(models): 学习痕迹表（错题/任务/题/测验/掌握度/积分/目标）加 bucket_id"
```

---

### Task 3: 桶服务 `bucket_service.py`（当前桶解析 / 建桶 / 升年级）

**Files:**
- Create: `backend/app/services/bucket_service.py`
- Test: `backend/tests/test_bucket_service.py`（新建）

这是整个功能的骨架：`get_active_bucket`、`ensure_bucket`、`promote_grade`（升年级，幂等）。

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_bucket_service.py`：

```python
"""学年桶服务：当前桶解析、兜底建桶、升年级幂等。"""
from datetime import datetime

from app.services.bucket_service import (
    get_active_bucket, ensure_bucket, promote_grade, current_school_year,
)
from app.models import User, SchoolYearBucket


def _child(db, grade=3):
    u = User(name="晨晨", role="child", grade=grade)
    db.add(u); db.flush()
    return u


def test_get_active_bucket_returns_active(setup_db, db):
    child = _child(db, 3)
    b = SchoolYearBucket(user_id=child.id, grade=3, school_year="2025-2026", status="active")
    db.add(b); db.commit()
    assert get_active_bucket(db, child.id).id == b.id


def test_get_active_bucket_none_when_no_bucket(setup_db, db):
    child = _child(db, 3)
    db.commit()
    assert get_active_bucket(db, child.id) is None


def test_ensure_bucket_creates_when_missing(setup_db, db):
    child = _child(db, 3)
    db.commit()
    b = ensure_bucket(db, child.id)
    assert b is not None
    assert b.grade == 3
    assert b.status == "active"
    assert b.school_year == current_school_year()


def test_ensure_bucket_idempotent(setup_db, db):
    child = _child(db, 3)
    db.commit()
    b1 = ensure_bucket(db, child.id)
    b2 = ensure_bucket(db, child.id)
    assert b1.id == b2.id


def test_promote_grade_archives_old_and_creates_new(setup_db, db):
    child = _child(db, 3)
    db.commit()
    ensure_bucket(db, child.id)
    promote_grade(db, child.id)
    db.refresh(child)
    assert child.grade == 4
    buckets = db.query(SchoolYearBucket).filter_by(user_id=child.id).all()
    assert len(buckets) == 2
    assert sum(1 for b in buckets if b.status == "active") == 1
    active = get_active_bucket(db, child.id)
    assert active.grade == 4


def test_promote_grade_idempotent(setup_db, db):
    child = _child(db, 3)
    db.commit()
    ensure_bucket(db, child.id)
    promote_grade(db, child.id)
    promote_grade(db, child.id)  # 第二次应无效果
    db.refresh(child)
    assert child.grade == 4
    assert len(db.query(SchoolYearBucket).filter_by(user_id=child.id).all()) == 2


def test_current_school_year_september_boundary():
    # 学年：9/1 ~ 次年 8/31；直接断言格式正确、长度 9
    sy = current_school_year()
    assert len(sy) == 9 and sy[4] == "-"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_bucket_service.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.bucket_service'`。

- [ ] **Step 3: 实现 `bucket_service.py`**

新建 `backend/app/services/bucket_service.py`：

```python
"""学年桶服务：当前桶解析、兜底建桶、升年级（幂等）。

学年定义：9 月 1 日 ~ 次年 8 月 31 日。school_year 形如 "2025-2026"。
升年级 = 封存当前 active 桶 + 新建 grade+1 的 active 桶 + 更新 User.grade。
"""
from datetime import datetime, date

from sqlalchemy.orm import Session

from ..models import User, SchoolYearBucket


def current_school_year(today: date | None = None) -> str:
    """返回当前日期的学年字符串（如 "2025-2026"）。"""
    today = today or date.today()
    if today.month >= 9:
        return f"{today.year}-{today.year + 1}"
    return f"{today.year - 1}-{today.year}"


def get_active_bucket(db: Session, user_id: int) -> SchoolYearBucket | None:
    return (db.query(SchoolYearBucket)
            .filter_by(user_id=user_id, status="active")
            .order_by(SchoolYearBucket.id.desc())
            .first())


def ensure_bucket(db: Session, user_id: int) -> SchoolYearBucket:
    """取孩子当前 active 桶；没有则按 User.grade 兜底建一个。"""
    active = get_active_bucket(db, user_id)
    if active:
        return active
    user = db.get(User, user_id)
    grade = user.grade if user and user.grade else 3  # 缺省三年级
    bucket = SchoolYearBucket(
        user_id=user_id, grade=grade,
        school_year=current_school_year(), status="active",
        started_at=datetime.utcnow(),
    )
    db.add(bucket)
    db.commit()
    db.refresh(bucket)
    return bucket


def promote_grade(db: Session, user_id: int, target_grade: int | None = None) -> SchoolYearBucket:
    """升年级（幂等）：封存当前桶、开新桶、更新 User.grade。

    target_grade 缺省 = 当前 grade + 1；可传具体值以支持跳级/留级（家长手动改）。
    幂等保证：目标 grade 已等于当前 User.grade 且已存在对应 active 桶时，直接返回。
    """
    user = db.get(User, user_id)
    if not user:
        raise ValueError(f"user {user_id} not found")
    new_grade = target_grade if target_grade is not None else (user.grade or 0) + 1
    if new_grade == user.grade:
        # 已是目标年级，确保有 active 桶即可（留级到同级视为 no-op）
        return ensure_bucket(db, user_id)
    now = datetime.utcnow()
    active = get_active_bucket(db, user_id)
    if active:
        active.status = "archived"
        active.ended_at = now
    bucket = SchoolYearBucket(
        user_id=user_id, grade=new_grade,
        school_year=current_school_year(), status="active",
        started_at=now,
    )
    user.grade = new_grade
    db.add(bucket)
    db.commit()
    db.refresh(bucket)
    return bucket
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_bucket_service.py -v`
Expected: PASS（7 个测试全过）。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/services/bucket_service.py backend/tests/test_bucket_service.py && git commit -m "feat(bucket): 学年桶服务（当前桶/兜底建桶/升年级幂等）"
```

---

### Task 3b: 教材加 `edition`/`grade` 字段（教材库分版本）

**Files:**
- Modify: `backend/app/models.py`（`PdfDocument` 加 `edition`/`grade`）
- Test: `backend/tests/test_grade_bucket_models.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `test_grade_bucket_models.py` 追加：

```python
def test_pdf_document_has_edition_grade(setup_db, db):
    from app.models import PdfDocument
    d = PdfDocument(filename="语文.pdf", subject="语文", storage_path="",
                    edition="人教版", grade=3)
    db.add(d); db.commit()
    got = db.get(PdfDocument, d.id)
    assert got.edition == "人教版"
    assert got.grade == 3
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_grade_bucket_models.py -v`
Expected: FAIL（`PdfDocument` 无 `edition`/`grade`）。

- [ ] **Step 3: 实现**

`backend/app/models.py` 的 `PdfDocument`（~line 16–21）加两字段：

```python
class PdfDocument(Base):
    __tablename__ = "pdf_documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(16))  # '语文' | '英语' | '数学'
    storage_path: Mapped[str] = mapped_column(String(512))
    edition: Mapped[str] = mapped_column(String(64), default="")   # 教材版本（人教版/苏教版…）
    grade: Mapped[int] = mapped_column(Integer, nullable=True)     # 年级 1~6
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_grade_bucket_models.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/models.py backend/tests/test_grade_bucket_models.py && git commit -m "feat(models): PdfDocument 加 edition/grade 支持教材分版本"
```

---

## 阶段二：升级流程接入 + 配置（Task 4–6）

### Task 4: 孩子档案 API（家长建孩子/升年级/改年级/列名下孩子）

**Files:**
- Modify: `backend/app/routers/users.py`
- Create: `backend/app/routers/buckets.py`（`GET /api/buckets?user_id=` 列桶）
- Modify: `backend/app/main.py`（include buckets router）
- Test: `backend/tests/test_children_api.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_children_api.py`：

```python
"""孩子档案与学年桶 API 测试。"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User


def _client():
    return TestClient(app)


def _add_user(name, role, **kw):
    s = SessionLocal()
    u = User(name=name, role=role, **kw)
    s.add(u); s.commit(); s.flush()
    uid = u.id
    s.close()
    return uid


def test_list_children_filters_by_parent(setup_db):
    parent = _add_user("金爸爸", "parent")
    c1 = _add_user("晨晨", "child", parent_id=parent, grade=3)
    _add_user("林晨", "child", grade=4)  # 别的家长的孩子
    resp = _client().get(f"/api/users?role=child&parent_id={parent}")
    data = resp.json()
    assert [u["id"] for u in data] == [c1]


def test_create_child_builds_bucket(setup_db):
    parent = _add_user("金爸爸", "parent")
    resp = _client().post("/api/children", json={
        "parent_id": parent, "name": "新孩子", "grade": 2, "edition": "苏教版",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["grade"] == 2
    # 建档即建第一个 active 桶
    buckets = _client().get(f"/api/buckets?user_id={data['id']}").json()
    assert any(b["status"] == "active" and b["grade"] == 2 for b in buckets)


def test_promote_grade_endpoint(setup_db):
    child = _add_user("晨晨", "child", grade=3)
    resp = _client().post(f"/api/children/{child}/promote")
    assert resp.status_code == 200
    assert resp.json()["grade"] == 4
    buckets = _client().get(f"/api/buckets?user_id={child}").json()
    assert any(b["status"] == "archived" and b["grade"] == 3 for b in buckets)
    assert any(b["status"] == "active" and b["grade"] == 4 for b in buckets)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_children_api.py -v`
Expected: FAIL（`POST /api/children` 与 `/api/buckets` 路由不存在，404）。

- [ ] **Step 3: 实现 `buckets.py` 路由**

新建 `backend/app/routers/buckets.py`：

```python
"""学年桶列表：前端切换学年用。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import SchoolYearBucket

router = APIRouter(prefix="/api/buckets", tags=["buckets"])


@router.get("")
def list_buckets(user_id: int, db: Session = Depends(get_db)):
    buckets = (db.query(SchoolYearBucket)
               .filter_by(user_id=user_id)
               .order_by(SchoolYearBucket.grade.desc(), SchoolYearBucket.id.desc())
               .all())
    return [
        {"id": b.id, "grade": b.grade, "school_year": b.school_year, "status": b.status}
        for b in buckets
    ]
```

- [ ] **Step 4: 实现 `users.py` 扩展（children CRUD + 家长过滤）**

在 `backend/app/routers/users.py` 中：

(a) 改 `list_users`，支持 `parent_id` 过滤：

```python
@router.get("")
def list_users(role: str | None = None, parent_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(User)
    if role:
        q = q.filter_by(role=role)
    if parent_id is not None:
        q = q.filter_by(parent_id=parent_id)
    return [{"id": u.id, "name": u.name, "role": u.role, "grade": u.grade, "edition": u.edition}
            for u in q.order_by(User.id).all()]
```

(b) 追加孩子档案端点（同文件末尾）：

```python
class CreateChildReq(BaseModel):
    parent_id: int
    name: str
    grade: int
    edition: str = ""


@router.post("/children")
def create_child(req: CreateChildReq, db: Session = Depends(get_db)):
    from ..services.bucket_service import ensure_bucket
    child = User(name=req.name, role="child", grade=req.grade,
                 edition=req.edition, parent_id=req.parent_id)
    db.add(child); db.commit(); db.refresh(child)
    ensure_bucket(db, child.id)
    return {"id": child.id, "name": child.name, "role": child.role,
            "grade": child.grade, "edition": child.edition}


@router.post("/children/{child_id}/promote")
def promote_child(child_id: int, db: Session = Depends(get_db)):
    from ..services.bucket_service import promote_grade
    promote_grade(db, child_id)
    child = db.get(User, child_id)
    return {"id": child.id, "grade": child.grade}
```

并在文件顶部加 `from pydantic import BaseModel`（如尚未引入）。

- [ ] **Step 5: 在 `main.py` 注册 buckets 路由**

`backend/app/main.py`：
- import 行（~line 4）末尾加 `buckets`
- `app.include_router(...)` 区（~line 24–43）加一行 `app.include_router(buckets.router)`

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_children_api.py tests/test_users.py -v`
Expected: 全 PASS（注意 `test_users.py` 里 `test_list_children_filters_by_role_and_sorts_by_id` 断言 `set(u) == {"id","name","role"}` 会因新增 `grade`/`edition` 字段而失败——需同步更新该断言为 `{"id","name","role","grade","edition"}`）。

- [ ] **Step 7: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/routers/users.py backend/app/routers/buckets.py backend/app/main.py backend/tests/test_children_api.py backend/tests/test_users.py && git commit -m "feat(api): 孩子档案端点（建孩子/升年级/列名下孩子）+ 学年桶列表"
```

---

### Task 5: 配置三级降级（孩子覆盖 > 全局 > 默认）

**Files:**
- Create: `backend/app/services/child_config.py`
- Modify: `backend/app/routers/learning.py`（`_cfg_int`/`_cfg_str` 加 child_id 参数）
- Modify: `backend/app/services/task_gen.py`（`_default_count` 加 child_id 参数）
- Test: `backend/tests/test_child_config.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_child_config.py`：

```python
"""孩子配置覆盖：孩子 > 全局 > 默认 三级降级。"""
from app.services.child_config import get_child_config_int, get_child_config_str
from app.models import User, ModelConfig, ChildConfig


def _child(db, grade=3):
    u = User(name="晨晨", role="child", grade=grade)
    db.add(u); db.flush()
    return u


def test_child_override_wins(setup_db, db):
    child = _child(db)
    db.add(ModelConfig(key="difficulty_语文", value="中等"))
    db.add(ChildConfig(user_id=child.id, key="difficulty_语文", value="困难"))
    db.commit()
    assert get_child_config_str(db, child.id, "difficulty_语文", "默认") == "困难"


def test_falls_back_to_global(setup_db, db):
    child = _child(db)
    db.add(ModelConfig(key="task_dictation_count_语文", value="10"))
    db.commit()
    assert get_child_config_int(db, child.id, "task_dictation_count_语文", 7) == 10


def test_falls_back_to_default(setup_db, db):
    child = _child(db)
    db.commit()
    assert get_child_config_int(db, child.id, "nope", 7) == 7
    assert get_child_config_str(db, child.id, "nope", "默认") == "默认"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_child_config.py -v`
Expected: FAIL，`ModuleNotFoundError`。

- [ ] **Step 3: 实现 `child_config.py`**

新建 `backend/app/services/child_config.py`：

```python
"""孩子配置覆盖：读配置时按 孩子覆盖 > 全局 ModelConfig > 默认 三级降级。"""
from sqlalchemy.orm import Session
from ..models import ModelConfig, ChildConfig


def get_child_config_str(db: Session, child_id: int, key: str, fallback: str) -> str:
    row = db.query(ChildConfig).filter_by(user_id=child_id, key=key).first()
    if row and row.value:
        return row.value
    g = db.query(ModelConfig).filter_by(key=key).first()
    return g.value if g and g.value else fallback


def get_child_config_int(db: Session, child_id: int, key: str, fallback: int) -> int:
    val = get_child_config_str(db, child_id, key, "")
    try:
        return int(val) if val else fallback
    except ValueError:
        return fallback
```

- [ ] **Step 4: 让现有配置读取函数加 child_id 参数**

`backend/app/routers/learning.py`（~line 18–30）：`_cfg_int` / `_cfg_str` 增加 `child_id` 参数并委托给 `child_config`：

```python
def _cfg_int(db, key, fallback, child_id=None):
    from ..services.child_config import get_child_config_int
    if child_id is None:
        # 无 child 时退回全局读法（兼容旧调用）
        from ..models import ModelConfig
        row = db.query(ModelConfig).filter_by(key=key).first()
        try:
            return int(row.value) if row and row.value else fallback
        except ValueError:
            return fallback
    return get_child_config_int(db, child_id, key, fallback)


def _cfg_str(db, key, fallback, child_id=None):
    from ..services.child_config import get_child_config_str
    if child_id is None:
        from ..models import ModelConfig
        row = db.query(ModelConfig).filter_by(key=key).first()
        return row.value if row and row.value else fallback
    return get_child_config_str(db, child_id, key, fallback)
```

`backend/app/services/task_gen.py`（~line 23）：`_default_count` 加 `child_id=None` 参数并委托：

```python
def _default_count(db: Session, key: str, fallback: int, child_id=None) -> int:
    from .child_config import get_child_config_int
    return get_child_config_int(db, child_id, key, fallback)
```

（`child_id=None` 时 `get_child_config_int` 里 `filter_by(user_id=None, …)` 查不到孩子行，会正确回落全局，行为与原来一致。）

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_child_config.py -v`
Expected: PASS。

- [ ] **Step 6: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/services/child_config.py backend/app/routers/learning.py backend/app/services/task_gen.py backend/tests/test_child_config.py && git commit -m "feat(config): 学习规则按孩子覆盖（孩子>全局>默认三级降级）"
```

---

### Task 6: 每日任务按孩子（active 桶）生成 + 挂桶

**Files:**
- Modify: `backend/app/services/task_gen.py`（`generate_tasks_for_user` 里给 Task/Question 挂 bucket，`generate_daily_tasks` 遍历 active 桶孩子）
- Test: `backend/tests/test_task_gen.py`（追加或修改）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_task_gen.py` 追加：

```python
def test_generate_daily_tasks_attaches_bucket(setup_db, db):
    from app.services.task_gen import generate_tasks_for_user
    from app.services.bucket_service import ensure_bucket
    from app.models import Task, User
    from datetime import date
    u = User(name="晨晨", role="child", grade=3)
    db.add(u); db.commit()
    bucket = ensure_bucket(db, u.id)
    # 需要至少一课才有任务可生成；无课则任务为空，桶仍应已建
    generate_tasks_for_user(db, u.id, date.today())
    # 若生成了任务，应挂在 active 桶上
    for t in db.query(Task).filter_by(user_id=u.id).all():
        assert t.bucket_id == bucket.id
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_task_gen.py -v`
Expected: 若生成了任务则断言 `t.bucket_id == bucket.id` 失败（目前未设 bucket_id）；若无课生成空任务则测试空转通过——需在实现后确认有课场景。

- [ ] **Step 3: 实现**

`backend/app/services/task_gen.py` 中：

(a) `generate_tasks_for_user`（~line 171）开头解析 bucket，末尾给 Task 挂 bucket：

```python
def generate_tasks_for_user(db: Session, user_id: int, day: date, force: bool = False):
    from .bucket_service import ensure_bucket
    bucket = ensure_bucket(db, user_id)
    if force:
        db.query(Task).filter_by(user_id=user_id, date=day).delete(synchronize_session=False)
        db.query(Question).filter_by(date=day, user_id=user_id).delete(synchronize_session=False)
    # …中间逻辑不变…
    for gen in gens:
        if gen is not None:
            gen.user_id = user_id
            gen.date = day
            gen.bucket_id = bucket.id
            db.add(gen)
    db.commit()
```

同时 `_gen_knowledge` / `_gen_listening` / `_gen_math_practice` 里 `db.add(Question(...))` 处补 `user_id=user_id` 与 `bucket_id=bucket.id`——最简单做法是给这三个生成函数传 `bucket`（或 user_id），在 `Question` 构造里加 `user_id=user_id`，并在这三个函数返回前不设 bucket，改由 `generate_tasks_for_user` 收集后统一设。为最小改动，**改为在 `generate_tasks_for_user` 内、`db.add(gen)` 之前，把生成的 `Question` 也补 user_id/bucket**：具体做法是给三个 `_gen_*` 函数签名加 `user_id` 参数并在构造 `Question` 时带上 `user_id=user_id`；`bucket_id` 在 `db.add(gen)` 后统一 `db.flush()` 再对当天该孩子的 `Question` 回填。

**简化方案（推荐）**：给三个 `_gen_*` 函数加 `bucket_id` 参数，构造 `Question` 时直接带 `user_id=user_id, bucket_id=bucket_id`。调整函数签名：

```python
def _gen_knowledge(db, lesson, user_id, count, new_ratio, bucket_id): ...
def _gen_listening(db, lesson, bucket_id): ...   # 内部 Question 加 user_id/bucket_id
def _gen_math_practice(db, lesson, bucket_id): ...
```

调用处（~line 190–196）相应传参。所有 `Question(...)` 构造补 `user_id=user_id` 与 `bucket_id=bucket_id`。

(b) `generate_daily_tasks`（~line 205）改为遍历「有 active 桶的孩子」：

```python
def generate_daily_tasks(db: Session, day: date, force: bool = False):
    from .bucket_service import ensure_bucket
    for (uid,) in db.query(User.id).filter_by(role="child").all():
        ensure_bucket(db, uid)  # 兜底：无桶先建
        generate_tasks_for_user(db, uid, day, force=force)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_task_gen.py tests/test_tasks_router.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/services/task_gen.py backend/tests/test_task_gen.py && git commit -m "feat(tasks): 每日任务与题目按孩子挂学年桶，调度遍历 active 桶孩子"
```

---

## 阶段三：回看/切换（Task 7–8）

### Task 7: 查询端点加 `bucket_id` 过滤（默认当前 active 桶）+ 历史桶只读

**Files:**
- Modify: `backend/app/routers/mistakes.py`、`points.py`、`goals.py`、`mastery.py`、`quiz.py`、`learning.py`（读端点加 bucket_id；写端点对历史桶拒绝）
- Create: `backend/app/services/bucket_guard.py`（只读守卫）
- Test: `backend/tests/test_bucket_readonly.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_bucket_readonly.py`：

```python
"""回看切换：查询按桶过滤；历史桶只读。"""
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import User, SchoolYearBucket, Point
from app.services.bucket_service import ensure_bucket, promote_grade


def _client():
    return TestClient(app)


def _child_with_two_buckets():
    s = SessionLocal()
    u = User(name="晨晨", role="child", grade=3)
    s.add(u); s.commit()
    ensure_bucket(s, u.id)
    # 三年级桶加积分
    b3 = ensure_bucket(s, u.id)
    s.add(Point(user_id=u.id, bucket_id=b3.id, delta=30, reason="三年级"))
    s.commit()
    promote_grade(s, u.id)  # 升到四年级
    b4 = ensure_bucket(s, u.id)
    s.add(Point(user_id=u.id, bucket_id=b4.id, delta=10, reason="四年级"))
    s.commit()
    uid = u.id
    s.close()
    return uid


def test_points_balance_defaults_to_active_bucket(setup_db):
    uid = _child_with_two_buckets()
    resp = _client().get(f"/api/points/balance?user_id={uid}")
    assert resp.json()["balance"] == 10  # 只算四年级（当前 active）桶


def test_points_balance_can_view_old_bucket(setup_db):
    uid = _child_with_two_buckets()
    s = SessionLocal()
    b3 = s.query(SchoolYearBucket).filter_by(user_id=uid, grade=3).first()
    s.close()
    resp = _client().get(f"/api/points/balance?user_id={uid}&bucket_id={b3.id}")
    assert resp.json()["balance"] == 30  # 回看三年级桶
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_bucket_readonly.py -v`
Expected: FAIL（当前 `balance` 不过滤 bucket，返回 40）。

- [ ] **Step 3: 实现 `bucket_guard.py`**

新建 `backend/app/services/bucket_guard.py`：

```python
"""桶只读守卫：写操作前校验目标桶是否为当前 active 桶。"""
from sqlalchemy.orm import Session
from ..models import SchoolYearBucket
from .bucket_service import get_active_bucket


def resolve_bucket_id(db: Session, user_id: int, bucket_id: int | None) -> int | None:
    """解析查询用的桶：显式 bucket_id 优先，否则当前 active 桶；都没有返回 None。"""
    if bucket_id is not None:
        return bucket_id
    active = get_active_bucket(db, user_id)
    return active.id if active else None


def assert_writable(db: Session, user_id: int, bucket_id: int | None = None) -> None:
    """写操作守卫：bucket_id 未指定时默认写 active 桶（允许）；指定了历史桶则拒绝。"""
    if bucket_id is None:
        return
    active = get_active_bucket(db, user_id)
    if active is None or active.id != bucket_id:
        raise PermissionError("历史学年只读，不能修改")
```

- [ ] **Step 4: 改查询/写端点**

以 `points.py` 为例（`balance` 读 + `redeem` 写）：

```python
@router.get("/balance")
def balance(user_id: int, bucket_id: int | None = None, db: Session = Depends(get_db)):
    from ..services.bucket_guard import resolve_bucket_id
    bid = resolve_bucket_id(db, user_id, bucket_id)
    q = db.query(Point).filter_by(user_id=user_id)
    if bid is not None:
        q = q.filter_by(bucket_id=bid)
    return {"balance": sum(p.delta for p in q.all())}


@router.post("/redeem")
def redeem(req: RedeemReq, bucket_id: int | None = None, db: Session = Depends(get_db)):
    from ..services.bucket_guard import resolve_bucket_id, assert_writable
    bid = resolve_bucket_id(db, req.user_id, bucket_id)
    assert_writable(db, req.user_id, bucket_id)
    # …其余逻辑，Point 构造带 bucket_id=bid …
```

同样的模式应用到：
- `mistakes.py` `list_mistakes` / `weakness_report`：查询加 `bucket_id` 过滤；`mark_correct`/`mark_wrong` 写守卫。
- `goals.py` `list_goals` 读过滤；`create_goal`/`assess` 写守卫。
- `mastery.py` `overview`/`report` 读过滤；`record` 写守卫（`record_attempt` 内部 `KnowledgeMastery`/`WordMastery` 需带 bucket——见 Task 8）。
- `quiz.py` `quiz_generate`/`quiz_submit` 挂 bucket（写 active 桶）。
- `learning.py` 各读端点按需加 bucket 过滤（错题/掌握度相关的）。

> 注：为控制篇幅与风险，本任务先落 `points`、`mistakes`、`goals` 三个最典型的「读+写」端点（覆盖测试），`mastery`/`quiz`/`learning` 的桶过滤在 Task 8 随掌握度挂桶一并处理。

- [ ] **Step 5: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_bucket_readonly.py tests/test_points.py tests/test_mistakes.py tests/test_goals.py -v`
Expected: 全 PASS（需同步修 `test_points.py` 等旧测试，若它们断言了旧的返回结构——主要是加了可选 `bucket_id` 参数不影响旧调用）。

- [ ] **Step 6: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/services/bucket_guard.py backend/app/routers/points.py backend/app/routers/mistakes.py backend/app/routers/goals.py backend/tests/test_bucket_readonly.py && git commit -m "feat(bucket): 查询端点按桶过滤 + 历史桶只读守卫"
```

---

### Task 8: 掌握度/测验挂桶 + 全链路默认取 active 桶

**Files:**
- Modify: `backend/app/services/mastery.py`（`record_attempt` 加 bucket 维度）
- Modify: `backend/app/routers/mastery.py`、`quiz.py`、`learning.py`
- Test: `backend/tests/test_mastery_api.py`、`backend/tests/test_quiz.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_mastery_api.py` 追加：

```python
def test_mastery_record_scoped_to_bucket(setup_db, db):
    from app.services.bucket_service import ensure_bucket
    from app.models import User, KnowledgeMastery, KnowledgePoint, Lesson
    u = User(name="晨晨", role="child", grade=3)
    db.add(u); db.commit()
    b = ensure_bucket(db, u.id)
    lesson = Lesson(document_id=1, subject="语文", title="课", start_page=1, end_page=1)
    db.add(lesson); db.flush()
    kp = KnowledgePoint(lesson_id=lesson.id, subject="语文", category="字词", content="苹果")
    db.add(kp); db.commit()
    from app.services.mastery import record_attempt
    record_attempt(db, u.id, "knowledge", kp.id, True, bucket_id=b.id)
    row = db.query(KnowledgeMastery).filter_by(user_id=u.id, knowledge_point_id=kp.id).first()
    assert row.bucket_id == b.id
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_mastery_api.py -v`
Expected: FAIL（`record_attempt` 不接受 `bucket_id` 关键字）。

- [ ] **Step 3: 实现**

`backend/app/services/mastery.py` 的 `record_attempt` 加 `bucket_id: int | None = None` 参数，构造 `KnowledgeMastery`/`WordMastery` 时带 `bucket_id=bucket_id`（`nullable`，None 时兼容旧调用）：

```python
def record_attempt(db, user_id, target_type, target_id, is_correct, bucket_id=None):
    if target_type == "knowledge":
        row = db.query(KnowledgeMastery).filter_by(user_id=user_id, knowledge_point_id=target_id, bucket_id=bucket_id).first()
        if not row:
            row = KnowledgeMastery(user_id=user_id, knowledge_point_id=target_id, bucket_id=bucket_id)
            db.add(row)
    else:
        row = db.query(WordMastery).filter_by(user_id=user_id, word_bank_id=target_id, bucket_id=bucket_id).first()
        if not row:
            row = WordMastery(user_id=user_id, word_bank_id=target_id, bucket_id=bucket_id,
                              correct_count=0, mistake_count=0, is_weak=False)
            db.add(row)
    # …其余逻辑不变…
```

`routers/mastery.py` 的 `record` 端点解析 active 桶并传 `bucket_id`；`overview`/`report` 读时按桶过滤。

`routers/quiz.py` 的 `quiz_generate`/`quiz_submit`：构造 `Quiz` 与记录错题/掌握度时带上 active 桶的 `bucket_id`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_mastery_api.py tests/test_quiz.py tests/test_mastery.py -v`
Expected: PASS（注意 `test_mastery.py` 里若直接调 `record_attempt` 旧签名，仍兼容，因为 `bucket_id` 有默认值 None）。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/services/mastery.py backend/app/routers/mastery.py backend/app/routers/quiz.py backend/tests/test_mastery_api.py && git commit -m "feat(bucket): 掌握度与测验记录按学年桶隔离"
```

---

## 阶段四：数据迁移（Task 9）

### Task 9: 迁移脚本（存量孩子补年级/建桶/回填 bucket_id/丢弃全局题）

**Files:**
- Create: `backend/app/migrate_grade_buckets.py`（一次性迁移脚本）
- Test: `backend/tests/test_migrate_grade_buckets.py`（新建）

- [ ] **Step 1: 写失败测试**

新建 `backend/tests/test_migrate_grade_buckets.py`：

```python
"""迁移脚本：存量孩子补年级、建桶、回填 bucket_id。"""
from app.migrate_grade_buckets import migrate
from app.models import User, SchoolYearBucket, Mistake, Point


def test_migrate_backfills_existing_children(setup_db, db):
    # 造存量数据：无年级、无桶、已有错题/积分
    child = User(name="晨晨", role="child")
    db.add(child); db.commit()
    db.add(Mistake(user_id=child.id, source_type="dictation",
                   question="听写：苹果", your_answer="苹菓", correct_answer="苹果"))
    db.add(Point(user_id=child.id, delta=20, reason="旧积分"))
    db.commit()

    migrate(db)

    got = db.get(User, child.id)
    assert got.grade == 3  # 缺省三年级
    bucket = db.query(SchoolYearBucket).filter_by(user_id=child.id).first()
    assert bucket is not None
    assert bucket.status == "active"
    m = db.query(Mistake).filter_by(user_id=child.id).first()
    assert m.bucket_id == bucket.id
    p = db.query(Point).filter_by(user_id=child.id).first()
    assert p.bucket_id == bucket.id


def test_migrate_idempotent(setup_db, db):
    child = User(name="晨晨", role="child")
    db.add(child); db.commit()
    migrate(db)
    migrate(db)  # 二次运行不应重复建桶
    buckets = db.query(SchoolYearBucket).filter_by(user_id=child.id).all()
    assert len(buckets) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_migrate_grade_buckets.py -v`
Expected: FAIL，`ModuleNotFoundError`。

- [ ] **Step 3: 实现迁移脚本**

新建 `backend/app/migrate_grade_buckets.py`：

```python
"""一次性迁移：给存量 child 补 grade、建默认 active 桶、回填学习痕迹 bucket_id。

幂等：已建桶的孩子跳过；已有 grade 的不覆盖。
运行方式：cd backend && python -m app.migrate_grade_buckets
"""
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import (User, SchoolYearBucket, Mistake, Task, Point, Goal,
                     WordMastery, KnowledgeMastery, Quiz, Question)
from .services.bucket_service import current_school_year


# 需要回填 bucket_id 的 (模型, 是否含 user_id 列)
_TRACE_MODELS = [Mistake, Task, Point, Goal, WordMastery, KnowledgeMastery, Quiz]


def migrate(db: Session) -> None:
    children = db.query(User).filter_by(role="child").all()
    for child in children:
        if child.grade is None:
            child.grade = 3  # 缺省三年级
        # 已有 active 桶则跳过
        existing = db.query(SchoolYearBucket).filter_by(user_id=child.id, status="active").first()
        if existing:
            db.commit()
            continue
        bucket = SchoolYearBucket(user_id=child.id, grade=child.grade,
                                  school_year=current_school_year(), status="active")
        db.add(bucket)
        db.flush()
        for model in _TRACE_MODELS:
            rows = db.query(model).filter_by(user_id=child.id, bucket_id=None).all()
            for r in rows:
                r.bucket_id = bucket.id
        db.commit()
    # 丢弃无归属的存量全局题目
    db.query(Question).filter(Question.user_id.is_(None)).delete(synchronize_session=False)
    db.commit()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        migrate(db)
        print("迁移完成")
    finally:
        db.close()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_migrate_grade_buckets.py -v`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add backend/app/migrate_grade_buckets.py backend/tests/test_migrate_grade_buckets.py && git commit -m "feat(migrate): 存量孩子补年级/建桶/回填 bucket_id 的一次性迁移脚本"
```

---

## 阶段五：前端「学年切换」UI（Task 10–12）

> 前端任务依赖后端阶段一~四完成。Flutter 学生端与 parent-web 家长端是两个独立前端，可并行。

### Task 10: Flutter 学生端「学年切换」（错题本/积分等页面顶部）

**Files:**
- Modify: `student-app/lib/features/center/center_page.dart` 等（加学年切换下拉）
- Create: `student-app/lib/features/center/bucket_selector.dart`（或作为 widget 复用）
- Test: `student-app/test/features/center/center_page_test.dart`（追加）

- [ ] **Step 1: 写失败测试**（Flutter widget 测试，验证切换后请求带 bucket_id）

在 `center_page_test.dart` 追加一个测试：mock 仓库，点学年下拉选「三年级」，断言仓库收到 `bucket_id` 参数。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd student-app && E:/dev/flutter/bin/flutter test test/features/center/center_page_test.dart`
Expected: FAIL。

- [ ] **Step 3: 实现**：新增 `bucket_selector` widget（调 `GET /api/buckets?user_id=` 拉桶列表），页面顶部渲染下拉；选中历史桶时查询带 `bucket_id`，并标注「历史学年只读」。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd student-app && E:/dev/flutter/bin/flutter test && E:/dev/flutter/bin/flutter analyze`
Expected: PASS / 无 error。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add student-app/ && git commit -m "feat(student-app): 学年切换（按桶回看历史数据）"
```

### Task 11: parent-web 家长端「孩子列表按家长过滤 + 学年视图」

**Files:**
- Modify: `parent-web/app.js`、`parent-web/index.html`

- [ ] **Step 1–4:** 家长登录后拉自己名下孩子（`GET /api/users?role=child&parent_id=<家长>`）；孩子条目可展开「学年」下拉切桶回看错题/积分等。手动测试（`python -m http.server 8767 --directory parent-web`）。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add parent-web/ && git commit -m "feat(parent-web): 孩子列表按家长过滤 + 学年视图"
```

### Task 12: parent-web 家长端「建孩子/升年级/改年级」操作

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1–4:** 家长端加「新建孩子」（设年级/版本）、「升年级」按钮（调 `POST /api/children/{id}/promote`）、改年级/改版本。手动测试。

- [ ] **Step 5: Commit**

```bash
cd D:/workspace/github/KnoAct && git add parent-web/ && git commit -m "feat(parent-web): 建孩子/升年级/改年级操作"
```

---

## 验证清单（全部完成后）

- [ ] `cd backend && python -m pytest -v` 全绿（含新增桶/配置/迁移测试，且旧测试不回归）。
- [ ] 手动验证：起后端（`cd backend && python -m uvicorn app.main:app --port 8010`），家长建两个孩子（不同年级/版本），各自登录，升年级后回看三年级错题本/积分。
- [ ] `cd student-app && E:/dev/flutter/bin/flutter analyze && flutter test` 通过。

## 风险与备注

- `test_users.py` 的字段断言（`set(u) == {"id","name","role"}`）需随 `list_users` 返回新增 `grade`/`edition` 字段而更新（Task 4 Step 6 已注明）。
- `record_attempt` 加 `bucket_id` 默认值 None，兼容旧调用与旧测试。
- 模型加 `bucket_id` 均为 `nullable=True`，迁移脚本负责回填；新数据由 `ensure_bucket`/`bucket_guard` 兜底填充。
