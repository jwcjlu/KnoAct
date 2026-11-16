# 学习材料管理中心（知识点库 + 训练方案）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在既有专项训练上游补「知识点库 + 训练方案」两层：讲义 PDF 解析成可复用知识点，家长勾选组合成可保存方案，发布时物化成专项训练。

**Architecture:** 两张新表 `KnowledgePointPool`（知识点库，按家长隔离）与 `TrainingPlan`（训练方案，`point_ids` 存 JSON 数组），`TrainingItem` 加 `point_pool_id` 溯源字段；新增 `routers/knowledge_pool.py` 提供 pool/plan 的 CRUD + `from-pdf` + `publish`（发布时把知识点物化成 `TrainingItem`，按 `point_pool_id` 幂等更新同一组、保留未变条目的掌握度）；前端 `parent-web` 专项训练 Tab 内扩「知识点库」「训练方案」两个子视图。闯关/SRS 掌握度零改动。

**Tech Stack:** FastAPI + SQLAlchemy（`Base.metadata.create_all` 自动建新表，无 alembic）；pytest + TestClient；原生 JS 单文件前端 `parent-web/app.js`。

**Spec:** `docs/superpowers/specs/2026-11-15-knowledge-point-pool-design.md`

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/models.py` | 新增 `KnowledgePointPool`、`TrainingPlan` 两表；`TrainingItem` 加 `point_pool_id` 列 |
| `backend/app/routers/knowledge_pool.py` | 新 router：pool CRUD + `from-pdf` + plans CRUD + `publish` |
| `backend/app/services/plan_publish.py` | 发布核心逻辑（物化 + 幂等更新 + 保留未变条目掌握度），供 router 调用 |
| `backend/app/main.py` | `include_router(knowledge_pool.router)` |
| `backend/tests/test_knowledge_pool.py` | 全部测试 |
| `parent-web/app.js` | 知识点库子视图 + 训练方案子视图 + 发布接线 |

---

## Task 1: 数据模型（`KnowledgePointPool` / `TrainingPlan` / `TrainingItem.point_pool_id`）

**Files:**
- Modify: `backend/app/models.py`（在 `TrainingItem` 类附近追加两表 + 改 `TrainingItem`）

- [ ] **Step 1: 写模型 + 建表（`create_all` 自动建，无需迁移脚本）**

在 `models.py` 中，`TrainingItem` 类里加一个字段，并在文件末尾（`ReadingPassage` 之后）追加两张新表。

`TrainingItem` 加字段（在 `source_page` 字段之后插入）：

```python
    point_pool_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_point_pool.id"), nullable=True)
```

> 注意：`point_pool_id` 的 FK 指向 `knowledge_point_pool` 表，该表定义在文件更靠后的位置。SQLAlchemy 的 `Base.metadata` 会在 `create_all` 时按依赖排序建表，FK 字符串引用即可，无需表先于引用定义。

追加两张新表（放在 `ReadingPassage` 类定义之后）：

```python
class KnowledgePointPool(Base):
    """知识点库：讲义 PDF 解析出的可复用知识点，按家长隔离。"""
    __tablename__ = "knowledge_point_pool"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(16))            # 语文/英语/数学
    category: Mapped[str] = mapped_column(String(32), default="")  # 短语/句型/语法/生字/古诗…
    content: Mapped[str] = mapped_column(LongText)              # 知识点主体（如 look after）
    extra: Mapped[str] = mapped_column(LongText, default="{}")  # JSON：释义/例句/音标/作者
    source: Mapped[str] = mapped_column(String(16), default="manual")  # pdf | manual
    document_id: Mapped[int | None] = mapped_column(ForeignKey("pdf_documents.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TrainingPlan(Base):
    """训练方案：家长勾选知识点组合，可保存/编辑/发布成专项训练。"""
    __tablename__ = "training_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    point_ids: Mapped[str] = mapped_column(LongText, default="[]")   # JSON 数组，如 [3,7,12]
    group_id: Mapped[int | None] = mapped_column(ForeignKey("training_groups.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")  # draft | published
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: 验证建表成功**

Run: `cd backend && python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine); print([t for t in Base.metadata.tables if t in ('knowledge_point_pool','training_plans')])"`
Expected: 打印 `['knowledge_point_pool', 'training_plans']`

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/models.py && git commit -m "feat(models): 新增 KnowledgePointPool / TrainingPlan + TrainingItem.point_pool_id 溯源列"
```

---

## Task 2: 发布核心服务 `services/plan_publish.py`

**Files:**
- Create: `backend/app/services/plan_publish.py`
- Test: `backend/tests/test_knowledge_pool.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_knowledge_pool.py`（新建）：

```python
import json
from conftest import parent_child


def _mk_point(db, owner, subject="英语", content="look after", extra=None):
    from app.models import KnowledgePointPool
    p = KnowledgePointPool(owner_id=owner.id, subject=subject, content=content,
                           category="短语", source="manual",
                           extra=json.dumps(extra or {"释义": "照顾"}, ensure_ascii=False))
    db.add(p); db.flush()
    return p


def test_publish_creates_group_and_items(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p1 = _mk_point(db, parent, content="look after")
    p2 = _mk_point(db, parent, content="look for")
    r = client.post("/api/plans", json={"subject": "英语", "title": "look 短语",
                                        "point_ids": [p1.id, p2.id]}, headers=parent_h)
    plan_id = r.json()["id"]
    r2 = client.post(f"/api/plans/{plan_id}/publish", headers=parent_h)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["group_id"] and body["item_count"] == 2
    # 物化：TrainingItem 内容来自知识点，且带 point_pool_id 溯源
    from app.models import TrainingItem
    items = db.query(TrainingItem).filter_by(group_id=body["group_id"]).order_by(TrainingItem.id).all()
    assert {it.primary for it in items} == {"look after", "look for"}
    assert all(it.point_pool_id in (p1.id, p2.id) for it in items)


def test_publish_idempotent_same_group(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent)
    plan_id = client.post("/api/plans", json={"subject": "英语", "title": "t",
                                              "point_ids": [p.id]}, headers=parent_h).json()["id"]
    g1 = client.post(f"/api/plans/{plan_id}/publish", headers=parent_h).json()["group_id"]
    g2 = client.post(f"/api/plans/{plan_id}/publish", headers=parent_h).json()["group_id"]
    assert g1 == g2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_knowledge_pool.py -v`
Expected: FAIL（`/api/plans` 404，router 未注册）

- [ ] **Step 3: 写 `plan_publish.py`**

```python
"""训练方案发布：把勾选知识点物化成 TrainingItem，幂等更新同一组。"""
import json

from sqlalchemy.orm import Session

from ..models import KnowledgePointPool, TrainingGroup, TrainingItem, TrainingPlan
from .drill_rule import infer_kind, generate_group_content, review_group_items


def publish_plan(db: Session, plan: TrainingPlan) -> tuple[TrainingGroup, int]:
    """按 plan.point_ids 物化知识点，新建或更新 group，返回 (group, item_count)。

    - 幂等：plan.group_id 已存在则更新该组（不新建重复组）。
    - 保留掌握度：更新时按 point_pool_id 匹配，未变知识点保留原 TrainingItem（及 mastery），
      只增删变化的条目。
    """
    point_ids = json.loads(plan.point_ids or "[]")
    if not point_ids:
        raise ValueError("方案未勾选任何知识点")
    points = (db.query(KnowledgePointPool)
              .filter(KnowledgePointPool.id.in_(point_ids),
                      KnowledgePointPool.owner_id == plan.owner_id)
              .order_by(KnowledgePointPool.id).all())
    if not points:
        raise ValueError("未找到有效知识点")

    group = db.get(TrainingGroup, plan.group_id) if plan.group_id else None
    if group is None:
        group = TrainingGroup(owner_id=plan.owner_id, subject=plan.subject,
                              title=plan.title, source="custom",
                              kind=infer_kind(plan.subject, ""))
        db.add(group); db.flush()
    else:
        # 删除不再勾选的条目（保留命中 point_pool_id 的条目及其 mastery）
        wanted = {p.id for p in points}
        for it in db.query(TrainingItem).filter_by(group_id=group.id).all():
            if it.point_pool_id not in wanted:
                db.delete(it)
        db.flush()

    existing_by_pool = {it.point_pool_id: it for it in
                        db.query(TrainingItem).filter_by(group_id=group.id).all()}

    items_payload = []
    for p in points:
        if p.id in existing_by_pool:
            continue
        extra = _load_json(p.extra)
        item = TrainingItem(
            group_id=group.id, kind="drill_item",
            primary=p.content,
            secondary=extra.get("释义") or extra.get("作者") or "",
            example=extra.get("例句") or "",
            point_pool_id=p.id,
        )
        db.add(item); db.flush()
        items_payload.append({"primary": p.content,
                              "secondary": extra.get("释义") or extra.get("作者") or ""})

    all_items = db.query(TrainingItem).filter_by(group_id=group.id).order_by(TrainingItem.id).all()
    if items_payload:
        content = generate_group_content(db, plan.subject, group.kind, items_payload)
        group.intro = json.dumps(content["intro"], ensure_ascii=False)
        group.group_rule = json.dumps(content["group_rule"], ensure_ascii=False)
        group.ai_review = json.dumps(
            review_group_items(db, plan.subject, group.kind, items_payload), ensure_ascii=False)

    plan.group_id = group.id
    plan.status = "published"
    plan.updated_at = __import__("datetime").datetime.utcnow()
    db.commit()
    return group, len(all_items)


def _load_json(s: str) -> dict:
    try:
        v = json.loads(s or "{}")
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_knowledge_pool.py -v`
Expected: 仍需 Task 3 的 router 才通过（此 Task 只让 service 就绪，测试在 Task 3 完成后一起绿）

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/services/plan_publish.py && git commit -m "feat(services): plan_publish 物化知识点 + 幂等更新同组"
```

---

## Task 3: 路由 `routers/knowledge_pool.py` + 注册

**Files:**
- Create: `backend/app/routers/knowledge_pool.py`
- Modify: `backend/app/main.py`（include_router）
- Test: `backend/tests/test_knowledge_pool.py`（补充）

- [ ] **Step 1: 写 router**

`backend/app/routers/knowledge_pool.py`：

```python
import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.deps import require_role
from ..database import get_db
from ..models import KnowledgePointPool, TrainingPlan, User

router = APIRouter(prefix="/api", tags=["knowledge-pool"])


def _own(db: Session, user: User, model, obj_id: int):
    obj = db.get(model, obj_id)
    if obj is None:
        return None
    if user.role != "admin" and obj.owner_id != user.id:
        return False
    return obj


def _point_dict(p: KnowledgePointPool) -> dict:
    return {"id": p.id, "subject": p.subject, "category": p.category,
            "content": p.content, "extra": p.extra, "source": p.source,
            "document_id": p.document_id}


class PointIn(BaseModel):
    subject: str = ""
    category: str = ""
    content: str = ""
    extra: str = "{}"


@router.get("/knowledge-pool")
def list_points(subject: str = "", category: str = "",
                user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    q = db.query(KnowledgePointPool)
    if user.role != "admin":
        q = q.filter(KnowledgePointPool.owner_id == user.id)
    if subject:
        q = q.filter(KnowledgePointPool.subject == subject)
    if category:
        q = q.filter(KnowledgePointPool.category == category)
    return [_point_dict(p) for p in q.order_by(KnowledgePointPool.id.desc()).all()]


@router.post("/knowledge-pool")
def create_point(req: PointIn, user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    p = KnowledgePointPool(owner_id=user.id, subject=req.subject, category=req.category,
                           content=req.content, extra=req.extra, source="manual")
    db.add(p); db.commit(); db.refresh(p)
    return _point_dict(p)


@router.put("/knowledge-pool/{point_id}")
def update_point(point_id: int, req: PointIn,
                 user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    p.subject = req.subject or p.subject
    p.category = req.category or p.category
    p.content = req.content or p.content
    p.extra = req.extra if req.extra != "{}" else p.extra
    db.commit()
    return _point_dict(p)


@router.delete("/knowledge-pool/{point_id}")
def delete_point(point_id: int, user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    db.delete(p); db.commit()
    return {"ok": True}


@router.post("/knowledge-pool/from-pdf")
async def from_pdf(subject: str = Form(...), handout_kind: str = Form("outline"),
                   file: UploadFile = File(...),
                   user: User = Depends(require_role("parent", "admin")),
                   db: Session = Depends(get_db)):
    """上传讲义 PDF → OCR → 提取知识点 → 写知识点库（不建训练）。"""
    import os
    from ..models import PdfDocument
    from ..services.pdf_split import render_pages, _ocr_page
    from ..services.drill_rule import extract_items_from_pages

    data = await file.read()
    if not data:
        return {"error": "请上传 PDF"}
    os.makedirs("uploads", exist_ok=True)
    doc = PdfDocument(filename=file.filename, subject=subject, storage_path="",
                      content_kind="handout", handout_kind=handout_kind)
    db.add(doc); db.commit(); db.refresh(doc)
    safe_name = os.path.basename(file.filename or "upload.pdf")
    path = f"uploads/{doc.id}_{safe_name}"
    with open(path, "wb") as f:
        f.write(data)
    doc.storage_path = path
    db.commit()

    pages = render_pages(doc.id, path, f"uploads/{doc.id}_pages")
    ocr_pages = []
    for p in pages:
        text = _ocr_page(path, p["page_number"] - 1, db, "识别这张讲义页面中的全部文字，原样输出。")
        ocr_pages.append({"page_number": p["page_number"], "text": text})

    items = extract_items_from_pages(db, handout_kind, ocr_pages)
    created = 0
    for it in items:
        extra = {"释义": it.get("secondary") or ""}
        db.add(KnowledgePointPool(
            owner_id=user.id, subject=subject, category=handout_kind,
            content=it.get("primary") or "", source="pdf",
            document_id=doc.id,
            extra=json.dumps(extra, ensure_ascii=False)))
        created += 1
    db.commit()
    return {"document_id": doc.id, "count": created}


class PlanIn(BaseModel):
    subject: str = ""
    title: str = ""
    point_ids: list[int] = []


@router.get("/plans")
def list_plans(user: User = Depends(require_role("parent", "admin")),
               db: Session = Depends(get_db)):
    q = db.query(TrainingPlan)
    if user.role != "admin":
        q = q.filter(TrainingPlan.owner_id == user.id)
    return [{"id": p.id, "subject": p.subject, "title": p.title,
             "point_ids": json.loads(p.point_ids or "[]"),
             "group_id": p.group_id, "status": p.status} for p in q.order_by(TrainingPlan.id.desc()).all()]


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, user: User = Depends(require_role("parent", "admin")),
             db: Session = Depends(get_db)):
    p = _own(db, user, TrainingPlan, plan_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    ids = json.loads(p.point_ids or "[]")
    points = db.query(KnowledgePointPool).filter(KnowledgePointPool.id.in_(ids)).all() if ids else []
    return {"id": p.id, "subject": p.subject, "title": p.title,
            "point_ids": ids, "group_id": p.group_id, "status": p.status,
            "points": [_point_dict(x) for x in points]}


@router.post("/plans")
def create_plan(req: PlanIn, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    p = TrainingPlan(owner_id=user.id, subject=req.subject, title=req.title,
                     point_ids=json.dumps(req.point_ids))
    db.add(p); db.commit(); db.refresh(p)
    return {"id": p.id}


@router.put("/plans/{plan_id}")
def update_plan(plan_id: int, req: PlanIn,
                user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    p = _own(db, user, TrainingPlan, plan_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    p.subject = req.subject or p.subject
    p.title = req.title or p.title
    p.point_ids = json.dumps(req.point_ids)
    db.commit()
    return {"id": p.id, "point_ids": req.point_ids}


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, user: User = Depends(require_role("parent", "admin")),
                db: Session = Depends(get_db)):
    p = _own(db, user, TrainingPlan, plan_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    db.delete(p); db.commit()
    return {"ok": True}


@router.post("/plans/{plan_id}/publish")
def publish_plan(plan_id: int, user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    from ..services.plan_publish import publish_plan as _publish
    p = _own(db, user, TrainingPlan, plan_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    try:
        group, count = _publish(db, p)
    except ValueError as e:
        return {"error": str(e)}
    return {"group_id": group.id, "item_count": count}
```

- [ ] **Step 2: 注册 router**

在 `backend/app/main.py` 的 `include_router(...)` 区块（`from ..routers import ...` 附近）加导入与注册：

```python
from app.routers import knowledge_pool
...
app.include_router(knowledge_pool.router)
```

> 具体 import 位置遵循现有 `main.py` 的 router 导入风格（逐行 `from app.routers import xxx`），在其后追加一行 `from app.routers import knowledge_pool`，并在 `include_router` 列表后追加 `app.include_router(knowledge_pool.router)`。

- [ ] **Step 3: 补隔离与编辑测试**

`backend/tests/test_knowledge_pool.py` 追加：

```python
def test_pool_isolated_by_parent(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p2, _, p2_h, _ = parent_child(db, prefix="other")
    _mk_point(db, parent, content="look after")
    # 另一个家长看不到
    r = client.get("/api/knowledge-pool", headers=p2_h)
    assert all(x["owner_id"] != parent.id for x in r.json()) or r.json() == []


def test_crud_and_edit(client, db):
    parent, child, parent_h, _ = parent_child(db)
    r = client.post("/api/knowledge-pool", json={"subject": "英语", "category": "短语",
                                                 "content": "give up", "extra": '{"释义":"放弃"}'},
                    headers=parent_h)
    pid = r.json()["id"]
    r2 = client.put(f"/api/knowledge-pool/{pid}", json={"content": "give in",
                                                        "extra": '{"释义":"让步"}'}, headers=parent_h)
    assert r2.json()["content"] == "give in"
    r3 = client.delete(f"/api/knowledge-pool/{pid}", headers=parent_h)
    assert r3.json()["ok"] is True
```

- [ ] **Step 4: 跑全部测试**

Run: `cd backend && python -m pytest tests/test_knowledge_pool.py -v`
Expected: PASS（Task 2 的两个测试 + 本 Task 的两个测试全绿）

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/routers/knowledge_pool.py app/main.py tests/test_knowledge_pool.py && git commit -m "feat(routers): 知识点库 + 训练方案 CRUD + from-pdf + publish"
```

---

## Task 4: 家长端 UI（`parent-web/app.js`）

**Files:**
- Modify: `parent-web/app.js`（专项训练 Tab 内扩两个子视图）

- [ ] **Step 1: 加状态与渲染分支**

在 `drillGroups` 附近（约 `app.js:103`）加状态：

```js
let poolPoints = [];       // [{id, subject, category, content, extra, source}]
let plans = [];            // [{id, subject, title, point_ids, group_id, status}]
let poolTab = null;        // null | 'pool' | 'plans'
let poolSelected = new Set();  // 知识点库勾选（组合用）
```

在 `renderDrillTab`（约 `app.js:3045`）顶部，按 `poolTab` 分流：

```js
function renderDrillTab(){
  if(poolTab==='pool') return renderPoolTab();
  if(poolTab==='plans') return renderPlansTab();
  // ...现有列表渲染...
}
```

- [ ] **Step 2: 知识点库子视图 `renderPoolTab`**

```js
async function loadPool(){ poolPoints = await api('/api/knowledge-pool'); if(!Array.isArray(poolPoints)) poolPoints=[]; }

function renderPoolTab(){
  const rows = poolPoints.map(p=>{
    let extra = {}; try{ extra = JSON.parse(p.extra||'{}'); }catch(e){}
    return `<div class="row">
      <input type="checkbox" ${poolSelected.has(p.id)?'checked':''} onchange="togglePoolSel(${p.id})">
      <div style="font-weight:600">${escapeHtml(p.content||'')}</div>
      <div class="sub">${escapeHtml(p.subject)} · ${escapeHtml(p.category)} · ${escapeHtml(extra['释义']||extra['例句']||'')}</div>
      <button class="btn-ghost" onclick="editPoolPoint(${p.id})">编辑</button>
      <button class="btn-ghost" onclick="delPoolPoint(${p.id})">删除</button>
    </div>`;
  }).join('');
  return `<div class="head"><h3>知识点库</h3>
      <button class="btn-primary" onclick="uploadPoolPdf()">上传讲义 PDF</button>
      <button class="btn-ghost" onclick="addPoolPoint()">手动新增</button>
      <button class="btn-primary" onclick="createPlanFromSel()">组合成方案(${poolSelected.size})</button>
    </div>
    ${rows || '<div style="text-align:center;padding:32px 0;color:#8e9691">暂无知识点</div>'}
    <button class="btn-ghost" onclick="poolTab=null;render()">返回</button>`;
}

function togglePoolSel(id){ poolSelected.has(id)?poolSelected.delete(id):poolSelected.add(id); render(); }
```

- [ ] **Step 3: 知识点库动作（上传/增/编辑/删）**

```js
function uploadPoolPdf(){
  const subject = prompt('学科（语文/英语/数学）','英语');
  const kind = prompt('讲义类型（phrase/outline）','phrase');
  const inp = document.createElement('input'); inp.type='file'; inp.accept='application/pdf';
  inp.onchange = async ()=>{
    const fd = new FormData(); fd.append('subject', subject); fd.append('handout_kind', kind); fd.append('file', inp.files[0]);
    toast('正在识别讲义…（OCR 逐页提取）');
    const r = await apiForm('/api/knowledge-pool/from-pdf', fd);
    toast(`已提取 ${r.count||0} 条知识点`);
    await loadPool(); render();
  };
  inp.click();
}

function addPoolPoint(){
  const content = prompt('知识点内容（如 look after）');
  if(!content) return;
  const subject = prompt('学科','英语');
  const category = prompt('分类','短语');
  const extra = prompt('释义（JSON，可留空）','{"释义":""}');
  await api('/api/knowledge-pool', {method:'POST', body:{subject, category, content, extra: extra||'{}'}});
  await loadPool(); render();
}

function editPoolPoint(id){
  const p = poolPoints.find(x=>x.id===id); if(!p) return;
  const content = prompt('内容', p.content); if(!content) return;
  await api(`/api/knowledge-pool/${id}`, {method:'PUT', body:{content, extra:p.extra, subject:p.subject, category:p.category}});
  await loadPool(); render();
}

async function delPoolPoint(id){
  if(!confirm('删除该知识点？')) return;
  await api(`/api/knowledge-pool/${id}`, {method:'DELETE'});
  poolSelected.delete(id); await loadPool(); render();
}
```

- [ ] **Step 4: 训练方案子视图 `renderPlansTab` + 发布**

```js
async function loadPlans(){ plans = await api('/api/plans'); if(!Array.isArray(plans)) plans=[]; }

function renderPlansTab(){
  const rows = plans.map(p=>`<div class="row">
    <div style="font-weight:600">${escapeHtml(p.title||'未命名')}</div>
    <div class="sub">${escapeHtml(p.subject)} · ${p.point_ids.length} 个知识点 · ${p.status==='published'?'已发布':'草稿'}</div>
    ${p.status==='published'
      ? `<button class="btn-ghost" onclick="publishPlan(${p.id})">重新发布</button>`
      : `<button class="btn-primary" onclick="publishPlan(${p.id})">发布</button>`}
  </div>`).join('');
  return `<div class="head"><h3>训练方案</h3>
      <button class="btn-ghost" onclick="poolTab='pool';render()">去勾选知识点</button></div>
    ${rows || '<div style="text-align:center;padding:32px 0;color:#8e9691">暂无方案，先在知识点库勾选组合</div>'}
    <button class="btn-ghost" onclick="poolTab=null;render()">返回</button>`;
}

async function createPlanFromSel(){
  if(poolSelected.size===0){ toast('请先勾选知识点'); return; }
  const title = prompt('方案名称'); if(!title) return;
  const subject = prompt('学科','英语');
  await api('/api/plans', {method:'POST', body:{subject, title, point_ids:[...poolSelected]}});
  poolSelected.clear(); poolTab='plans'; await loadPlans(); render();
}

async function publishPlan(id){
  const r = await api(`/api/plans/${id}/publish`, {method:'POST'});
  if(r.error){ toast(r.error); return; }
  toast(`已生成专项训练（组 ${r.group_id}），请到专项训练列表审核`);
  poolTab=null; await loadDrillGroups(); render();
}
```

- [ ] **Step 5: 专项训练 Tab 顶部加入口**

在现有「专项训练」列表头（`renderDrillTab` 的 head 区，约 `app.js:3073` 的「新建专项」按钮旁）加两个入口按钮：

```html
<button class="btn-ghost" onclick="poolTab='pool';loadPool().then(()=>render())">知识点库</button>
<button class="btn-ghost" onclick="poolTab='plans';loadPlans().then(()=>render())">训练方案</button>
```

- [ ] **Step 6: 手工验证**

Run: 后端 `cd backend && python -m uvicorn app.main:app --port 8010`；家长端 `python -m http.server 8767 --directory parent-web`
Expected: 专项训练 Tab 出现「知识点库」「训练方案」入口；上传两本 PDF → 库里见知识点 → 勾选组合 → 方案 → 发布 → 专项训练列表见 pending 组 → 审组。

- [ ] **Step 7: Commit**

```bash
cd backend && git add ../parent-web/app.js && git commit -m "feat(parent-web): 专项训练 Tab 扩知识点库 + 训练方案子视图"
```

---

## 自检（对照 spec）

1. **Spec 覆盖**：§1 三处模型 → Task 1；§2 接口 → Task 3；§2.1 publish 幂等+保留掌握度 → Task 2；§3 前端 → Task 4；§6 顺序 → 各 Task 顺序一致。✅
2. **占位符**：无 TBD/TODO；每步含实际代码。✅
3. **类型一致性**：`point_pool_id`、`publish_plan` 签名、`_own` 返回（`None`/`False`/obj）在 Task 2/3 中一致；前端 `poolTab`/`poolSelected` 命名一致。✅

## 已知取舍

- `from-pdf` 里 `extra` 只存 `释义`（`it["secondary"]`），例句暂不解析（`extract_items_from_pages` 只返回 primary/secondary，无 example 字段）；后续可扩展。
- `update_point` 的 `extra` 仅在非 `"{}"` 时覆盖——避免前端回传空对象误清内容；前端 `editPoolPoint` 恒回传原 `extra`，安全。
- 发布更新时 `generate_group_content` 仅对**新增条目**重算 `intro`/`group_rule`（`items_payload` 非空才触发），避免仅删条目时无谓 AI 调用。
