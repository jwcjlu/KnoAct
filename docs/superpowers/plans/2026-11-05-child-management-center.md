# 孩子管理中心 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 家长端新增完整「孩子管理」中心：孩子的新建/编辑/归档（软删）/恢复，以及从孩子侧查看与修改其绑定的教材。

**Architecture:** `User.status`（active/archived）软删；后端新增编辑/归档/恢复/查绑定教材接口 + 登录拒绝归档 + 定时任务排除归档 + `/users` include_archived；家长端新增「孩子管理」Tab。

**Tech Stack:** FastAPI + SQLAlchemy（后端）；原生 JS `parent-web`（家长端）；学生端基本不动。

**Spec:** `docs/superpowers/specs/2026-11-05-child-management-center-design.md`

---

## 文件结构

**后端：**
- `backend/app/models.py`（修改）— `User.status` 字段
- `backend/app/seed.py`（修改）— `_migrate_user_status` 迁移
- `backend/app/routers/users.py`（修改）— 编辑/归档/恢复/查教材 + `/users` include_archived
- `backend/app/routers/auth.py`（修改）— 登录拒绝归档孩子（403）
- `backend/app/services/task_gen.py`（修改）— `generate_daily_tasks` 排除归档
- `backend/tests/test_children_api.py`（修改）— 测试

**家长端：**
- `parent-web/app.js`（修改）— 孩子管理 Tab

---

## Task 1: `User.status` 字段 + 迁移 + 登录拒绝 + 定时任务排除

**Files:**
- Modify: `backend/app/models.py`, `backend/app/seed.py`, `backend/app/routers/auth.py`, `backend/app/services/task_gen.py`
- Test: `backend/tests/test_children_api.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_children_api.py 追加
def test_archived_child_login_rejected(setup_db, client, db):
    from app.models import User
    c = User(name="晨晨", role="child", status="archived")
    db.add(c); db.commit()
    r = client.post("/api/auth/login", json={"name": "晨晨"})
    assert r.status_code == 403
    assert r.json()["error"] == "archived"


def test_archived_child_excluded_from_daily_tasks(setup_db, db):
    from app.models import User, PdfDocument, Lesson, UserDocument, WordBank, KnowledgePoint, Text
    from app.services.task_gen import generate_daily_tasks
    from datetime import date
    c = User(name="归档孩子", role="child", status="archived")
    db.add(c); db.flush()
    doc = PdfDocument(filename="语文.pdf", subject="语文", storage_path="")
    db.add(doc); db.flush()
    l = Lesson(document_id=doc.id, subject="语文", title="第1课", start_page=1, end_page=1, extract_status="done", audit_status="approved")
    db.add(l); db.flush()
    db.add(WordBank(lesson_id=l.id, subject="语文", word="白鹭", extra="x"))
    db.add(KnowledgePoint(subject="语文", category="字词", content="形近字", lesson_id=l.id))
    db.add(Text(lesson_id=l.id, content="白鹭是一首精巧的诗。"))
    db.add(UserDocument(user_id=c.id, document_id=doc.id))
    db.commit()
    generate_daily_tasks(db, date.today())
    assert db.query(Task).filter_by(user_id=c.id, date=date.today()).count() == 0
```

- [ ] **Step 2: 实现**

`models.py` User 加：
```python
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | archived
```

`seed.py` 加迁移（放 `_migrate_bucket_columns` 后）：
```python
def _migrate_user_status():
    from sqlalchemy import inspect, text
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("users")}
    if "status" in cols:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(16) DEFAULT 'active'"))
```
并在 `seed()` 里调用。

`auth.py` login：
```python
@router.post("/login")
def login(req: LoginReq, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(name=req.name).first()
    if user and user.status == "archived":
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail={"error": "archived"})
    if not user:
        user = User(name=req.name, role=req.role)
        db.add(user); db.commit(); db.refresh(user)
    return {"id": user.id, "name": user.name, "role": user.role}
```

`task_gen.py` generate_daily_tasks：
```python
    for (uid,) in db.query(User.id).filter_by(role="child", status="active").all():
```

- [ ] **Step 3: 跑测试**

Run: `cd backend && python -m pytest tests/test_children_api.py -q`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/models.py backend/app/seed.py backend/app/routers/auth.py backend/app/services/task_gen.py backend/tests/test_children_api.py
git commit -m "feat(child-mgmt): User.status 归档 + 登录拒绝归档 + 定时任务排除归档"
```

---

## Task 2: 编辑/归档/恢复/查绑定教材接口 + include_archived

**Files:**
- Modify: `backend/app/routers/users.py`
- Test: `backend/tests/test_children_api.py`

- [ ] **Step 1: 写失败测试**

```python
def test_edit_child_updates_fields(setup_db, client, db):
    from app.models import User
    c = User(name="晨晨", role="child", grade=3, edition="人教")
    db.add(c); db.commit()
    r = client.put(f"/api/children/{c.id}", json={"name": "晨晨2", "grade": 5, "edition": "北师大"})
    assert r.status_code == 200
    assert r.json()["grade"] == 5
    assert r.json()["edition"] == "北师大"
    assert r.json()["name"] == "晨晨2"


def test_archive_unarchive_idempotent(setup_db, client, db):
    from app.models import User
    c = User(name="晨晨", role="child", grade=3)
    db.add(c); db.commit()
    assert client.post(f"/api/children/{c.id}/archive").json() == {"ok": True}
    assert client.post(f"/api/children/{c.id}/archive").json() == {"ok": True}  # 幂等
    db.expire_all()
    assert db.get(User, c.id).status == "archived"
    assert client.post(f"/api/children/{c.id}/unarchive").json() == {"ok": True}
    db.expire_all()
    assert db.get(User, c.id).status == "active"


def test_child_documents_listing(setup_db, client, db):
    from app.models import User, PdfDocument, UserDocument
    c = User(name="晨晨", role="child", grade=3)
    d = PdfDocument(filename="语文.pdf", subject="语文", storage_path="", grade=3, edition="人教")
    db.add_all([c, d]); db.flush()
    db.add(UserDocument(user_id=c.id, document_id=d.id))
    db.commit()
    r = client.get(f"/api/children/{c.id}/documents").json()
    assert len(r["documents"]) == 1
    assert r["documents"][0]["filename"] == "语文.pdf"


def test_users_include_archived(setup_db, client, db):
    from app.models import User
    db.add(User(name="活跃", role="child", status="active"))
    db.add(User(name="归档", role="child", status="archived"))
    db.commit()
    active = client.get("/api/users?role=child").json()
    assert all(u["name"] != "归档" for u in active)
    allu = client.get("/api/users?role=child&include_archived=1").json()
    assert any(u["name"] == "归档" for u in allu)
```

- [ ] **Step 2: 实现接口**

`users.py`：

```python
class UpdateChildReq(BaseModel):
    name: str | None = None
    grade: int | None = None
    edition: str | None = None


@children_router.put("/{child_id}")
def update_child(child_id: int, req: UpdateChildReq, db: Session = Depends(get_db)):
    child = db.get(User, child_id)
    if not child:
        return {"error": "not found"}
    if req.name is not None:
        child.name = req.name
    if req.edition is not None:
        child.edition = req.edition
    if req.grade is not None:
        child.grade = req.grade
        from ..services.bucket_service import ensure_bucket
        db.commit()
        ensure_bucket(db, child_id)
    db.commit()
    db.refresh(child)
    return {"id": child.id, "name": child.name, "grade": child.grade, "edition": child.edition}


@children_router.post("/{child_id}/archive")
def archive_child(child_id: int, db: Session = Depends(get_db)):
    child = db.get(User, child_id)
    if not child:
        return {"error": "not found"}
    child.status = "archived"
    db.commit()
    return {"ok": True}


@children_router.post("/{child_id}/unarchive")
def unarchive_child(child_id: int, db: Session = Depends(get_db)):
    child = db.get(User, child_id)
    if not child:
        return {"error": "not found"}
    child.status = "active"
    db.commit()
    return {"ok": True}


@children_router.get("/{child_id}/documents")
def child_documents(child_id: int, db: Session = Depends(get_db)):
    from ..models import UserDocument, PdfDocument
    bound = db.query(UserDocument.document_id).filter_by(user_id=child_id)
    docs = db.query(PdfDocument).filter(PdfDocument.id.in_(bound)).all()
    return {"documents": [
        {"id": d.id, "filename": d.filename, "subject": d.subject, "grade": d.grade, "edition": d.edition}
        for d in docs
    ]}
```

`list_users` 加 `include_archived: int = 0` 参数：
```python
def list_users(role: str | None = None, parent_id: int | None = None,
               include_archived: int = 0, db: Session = Depends(get_db)):
    q = db.query(User)
    if role:
        q = q.filter_by(role=role)
    if parent_id is not None:
        q = q.filter_by(parent_id=parent_id)
    if not include_archived:
        q = q.filter(User.status != "archived")
    return [...]
```

- [ ] **Step 3: 跑测试**

Run: `cd backend && python -m pytest tests/test_children_api.py -q`
Expected: PASS

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/users.py backend/tests/test_children_api.py
git commit -m "feat(child-mgmt): 编辑/归档/恢复/查绑定教材接口 + include_archived"
```

---

## Task 3: 家长端「孩子管理」Tab

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1: 加 Tab + 渲染**

在 `PARENT_TABS` 加 `['孩子管理','users']`（或复用现有 icon key，见 `icon()`）。加状态 `archivedChildren = []`、`showArchived = false`。新增：

```javascript
async function loadArchivedChildren(){
  const list = await api('/api/users?role=child&include_archived=1');
  archivedChildren = Array.isArray(list) ? list.filter(c=>c.status==='archived') : [];
}
function renderChildMgmt(){
  const visible = showArchived ? [...children, ...archivedChildren] : children;
  const rows = visible.map(c=>`
    <div class="pdf-row">
      <div><div class="nm">${escapeAttr(c.name)}${c.status==='archived'?'（已归档）':''}</div>
        <div class="meta">${c.grade?c.grade+'年级':''}${c.edition?' · '+c.edition:''}</div></div>
      <div style="display:flex;gap:6px;margin-left:auto">
        <button class="btn-ghost" onclick="editChild(${c.id})">编辑</button>
        <button class="btn-ghost" onclick="openChildDocs(${c.id})">看教材</button>
        ${c.status==='archived'
          ? `<button class="btn-ghost" onclick="unarchiveChild(${c.id})">恢复</button>`
          : `<button class="btn-ghost" style="color:#c05b4a" onclick="archiveChild(${c.id})">归档</button>`}
      </div>
    </div>`).join('');
  return `<div class="parent-grid">
    <div class="parent-panel" style="grid-column:1/-1">
      <div class="head"><div class="ic blue">${icon('users',20)}</div><div><h3>孩子管理</h3><div class="sub">新建、编辑、归档孩子；查看孩子绑定的教材</div></div>
        <button class="btn-ghost" style="margin-left:auto" onclick="showArchived=!showArchived;render()">${showArchived?'只看活跃':'显示已归档'}</button></div>
      <div class="bd">${rows || '<div style="color:#8e9691;padding:8px 0">暂无孩子</div>'}
        <button class="next-lesson-btn" style="margin-top:16px" onclick="showAddChildForm()">新建孩子</button>
      </div>
    </div>
    ${renderChildDocs()}
  </div>`;
}
```

- [ ] **Step 2: 新建/编辑/归档/恢复/看教材 函数**

新建：`showAddChildForm()` 渲染内联表单（姓名 input + 年级 select + 版本 input + 提交），提交调 `api('/api/children', {method:'POST', body:{parent_id:parentId, name, grade:Number(grade), edition}})`。

编辑：`editChild(id)` 用 `prompt` 三步（或内联表单，与新建一致），提交 `api('/api/children/${id}', {method:'PUT', body:{name, grade:Number(grade), edition}})`。

归档：`archiveChild(id)` → `confirm` → `api('/api/children/${id}/archive', {method:'POST'})` → `loadChildren()` + `loadArchivedChildren()` + render。
恢复：`unarchiveChild(id)` 同理 `unarchive`。

看教材：`openChildDocs(id)` → `api('/api/children/${id}/documents')` → 存 `childDocs`/`childDocsId` → render 展开列表（当前所有教材 + 勾选状态，勾/取消调 bind/unbind，复用 `toggleDocBind`）。

- [ ] **Step 3: 挂到 renderParent / reloadChildData**

`renderParent()` 加 `if(parentTab==='孩子管理') body = renderChildMgmt();`；`setParentTab` 切到孩子管理时 `loadChildren().then(()=>loadArchivedChildren()).then(()=>render())`。

- [ ] **Step 4: 校验**

Run: `node --check parent-web/app.js` → SYNTAX OK。人工检查：所有 `onclick=` 引用已定义顶层函数、`escapeAttr` 用于孩子名。

- [ ] **Step 5: 提交**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): 孩子管理 Tab（新建/编辑/归档/恢复/看绑定教材）"
```

---

## Self-Review

**1. Spec 覆盖**：第 1 节（status 字段+迁移）→ Task 1；第 2 节（编辑/归档/恢复/查教材/include_archived/login）→ Task 1+2；第 3 节（家长端）→ Task 3；第 4 节（学生端不动）→ 无任务（符合）。✅

**2. 占位符**：无 TBD；Task 3 前端函数给的是骨架，实现时需对齐 `parent-web` 现有 `icon()`/`escapeAttr()`/`api()` 的真实签名（已在 Context 注明）。✅

**3. 类型一致**：`User.status`（String default "active"）在 Task 1/2 一致；`archive`/`unarchive` 返回 `{"ok": True}` 一致；`include_archived` 参数名在 Task 2 前后端一致。✅
