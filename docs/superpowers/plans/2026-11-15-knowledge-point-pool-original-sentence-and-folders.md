# 知识点库：原句提取 + 多级目录 + 标签 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在已落地的知识点库之上，补「解析提取原句 + 多级目录 + 标签」三件事。

**Architecture:** 新增 `KnowledgeFolder` 目录表（`parent_id` 多级），`KnowledgePointPool` 加 `folder_id`（归属目录）与 `tags`（JSON 数组）字段，原句存 `extra["原句"]`；`_extract_one_batch` prompt 加 `example`（原句）返回；`from-pdf` 上传后自动建目录（名=文件名）并归类；新增目录 CRUD + 知识点 move/tags 接口；前端目录树 + 标签筛选 + 表单扩展。

**Tech Stack:** FastAPI + SQLAlchemy（`create_all` 自动建表）；pytest + TestClient；原生 JS 单文件 `parent-web/app.js`。

**Spec:** `docs/superpowers/specs/2026-11-15-knowledge-point-pool-original-sentence-and-folders-design.md`

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/models.py` | 新增 `KnowledgeFolder`；`KnowledgePointPool` 加 `folder_id`/`tags` |
| `backend/app/services/drill_rule.py` | `_extract_one_batch` 加 `example` 原句提取 |
| `backend/app/routers/knowledge_pool.py` | `from-pdf` 建目录+写原句；目录 CRUD；知识点 move/tags |
| `backend/tests/test_knowledge_pool.py` | 目录/原句/标签测试 |
| `parent-web/app.js` | 目录树 + 标签筛选 + 表单扩展 |

---

## Task 1: 数据模型（`KnowledgeFolder` + `KnowledgePointPool.folder_id/tags`）

**Files:**
- Modify: `backend/app/models.py`

- [ ] **Step 1: 加字段与新表**

在 `KnowledgePointPool` 类里（`created_at` 字段之后）加两个字段：

```python
    folder_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_folders.id"), nullable=True)
    tags: Mapped[str] = mapped_column(LongText, default="[]")  # JSON 数组，如 ["易错","重点"]
```

在 `KnowledgePointPool` 类定义**之前**（或 `TrainingPlan` 之后均可，FK 字符串引用不要求顺序）追加新表：

```python
class KnowledgeFolder(Base):
    """知识点库目录：parent_id 多级，按家长隔离。"""
    __tablename__ = "knowledge_folders"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(128))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_folders.id"), nullable=True)
    subject: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: 验证建表**

Run: `cd backend && python -c "from app.database import Base, engine; import app.models; Base.metadata.create_all(bind=engine); print('knowledge_folders' in Base.metadata.tables)"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
cd backend && git add app/models.py && git commit -m "feat(models): 新增 KnowledgeFolder 目录表 + KnowledgePointPool.folder_id/tags"
```

---

## Task 2: 解析提取原句（`drill_rule._extract_one_batch`）

**Files:**
- Modify: `backend/app/services/drill_rule.py`

- [ ] **Step 1: prompt 加 example**

`_extract_one_batch` 的 prompt 里，返回格式字符串从：

```python
        '只返回 JSON：{"items":[{"primary":"原文","secondary":"释义/作者/解释","source_page":页码}]}。'
```

改为：

```python
        '只返回 JSON：{"items":[{"primary":"原文","secondary":"释义/作者/解释","example":"该知识点在讲义中的原句原文","source_page":页码}]}。'
```

并在 prompt 的说明里加一句约束（在 `source_page 用该条目所在页码…` 那句附近补）：

```python
        "example 是知识点在讲义里的原句原文（照抄，不要自己编例句）。"
```

- [ ] **Step 2: out.append 补 example**

`out.append(...)` 那行，从：

```python
        out.append({"primary": primary, "secondary": (it.get("secondary") or "").strip(), "source_page": sp})
```

改为：

```python
        out.append({"primary": primary, "secondary": (it.get("secondary") or "").strip(),
                    "example": (it.get("example") or "").strip(), "source_page": sp})
```

- [ ] **Step 3: 验证 import 干净**

Run: `cd backend && python -c "from app.services.drill_rule import extract_items_from_pages; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
cd backend && git add app/services/drill_rule.py && git commit -m "feat(services): 讲义解析提取 example 原句"
```

---

## Task 3: 目录/标签路由 + from-pdf 建目录

**Files:**
- Modify: `backend/app/routers/knowledge_pool.py`
- Test: `backend/tests/test_knowledge_pool.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_knowledge_pool.py` 追加：

```python
def test_folder_tree_and_move(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent, content="look after")
    # 建目录
    r = client.post("/api/knowledge-folders", json={"name": "look 短语", "subject": "英语", "parent_id": None}, headers=parent_h)
    fid = r.json()["id"]
    # 移动知识点进目录
    r2 = client.put(f"/api/knowledge-pool/{p.id}/move", json={"folder_id": fid}, headers=parent_h)
    assert r2.json()["folder_id"] == fid
    # 目录树含该知识点
    tree = client.get("/api/knowledge-folders", headers=parent_h).json()
    root = [f for f in tree if f["id"] == fid][0]
    assert root["point_count"] == 1


def test_point_tags(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent, content="give up")
    r = client.put(f"/api/knowledge-pool/{p.id}/tags", json={"tags": ["易错", "重点"]}, headers=parent_h)
    import json as _json
    assert _json.loads(r.json()["tags"]) == ["易错", "重点"]


def test_delete_folder_nonempty_refused(client, db):
    parent, child, parent_h, _ = parent_child(db)
    p = _mk_point(db, parent, content="look after")
    fid = client.post("/api/knowledge-folders", json={"name": "f", "subject": "英语", "parent_id": None}, headers=parent_h).json()["id"]
    client.put(f"/api/knowledge-pool/{p.id}/move", json={"folder_id": fid}, headers=parent_h)
    r = client.delete(f"/api/knowledge-folders/{fid}", headers=parent_h)
    assert r.json().get("error")
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_knowledge_pool.py -v`
Expected: 新增的 3 个测试 FAIL（`/api/knowledge-folders` 404）

- [ ] **Step 3: 写目录/标签接口 + 改 from-pdf**

在 `routers/knowledge_pool.py` 顶部 import 加 `KnowledgeFolder`（`from ..models import KnowledgePointPool, TrainingPlan, KnowledgeFolder, User`）。

新增（放在 pool CRUD 之后、plans 之前均可）：

```python
class FolderIn(BaseModel):
    name: str = ""
    subject: str = ""
    parent_id: int | None = None


def _folder_tree(db: Session, owner_id: int, subject: str = "") -> list[dict]:
    folders = db.query(KnowledgeFolder)
    if subject:
        folders = folders.filter(KnowledgeFolder.subject == subject)
    folders = folders.filter(KnowledgeFolder.owner_id == owner_id).order_by(KnowledgeFolder.id).all()
    count_map = dict(db.query(KnowledgePointPool.folder_id, func.count(KnowledgePointPool.id))
                     .filter(KnowledgePointPool.folder_id.isnot(None))
                     .group_by(KnowledgePointPool.folder_id).all())
    nodes = {f.id: {"id": f.id, "name": f.name, "subject": f.subject,
                    "parent_id": f.parent_id, "point_count": int(count_map.get(f.id, 0)),
                    "children": []} for f in folders}
    roots = []
    for f in folders:
        if f.parent_id and f.parent_id in nodes:
            nodes[f.parent_id]["children"].append(nodes[f.id])
        else:
            roots.append(nodes[f.id])
    return roots


@router.get("/knowledge-folders")
def list_folders(subject: str = "", user: User = Depends(require_role("parent", "admin")),
                 db: Session = Depends(get_db)):
    owner = None if user.role == "admin" else user.id
    if owner is None:
        return []
    return _folder_tree(db, owner, subject)


@router.post("/knowledge-folders")
def create_folder(req: FolderIn, user: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    if not (req.name or "").strip():
        return {"error": "目录名不能为空"}
    f = KnowledgeFolder(owner_id=user.id, name=req.name.strip(), subject=req.subject,
                        parent_id=req.parent_id)
    db.add(f); db.commit(); db.refresh(f)
    return {"id": f.id}


@router.put("/knowledge-folders/{folder_id}")
def update_folder(folder_id: int, req: FolderIn,
                  user: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    f = _own(db, user, KnowledgeFolder, folder_id)
    if f is None:
        return {"error": "not found"}
    if f is False:
        return {"error": "无权操作"}
    if req.name.strip():
        f.name = req.name.strip()
    if req.parent_id is not None:
        f.parent_id = req.parent_id
    db.commit()
    return {"id": f.id}


@router.delete("/knowledge-folders/{folder_id}")
def delete_folder(folder_id: int, user: User = Depends(require_role("parent", "admin")),
                  db: Session = Depends(get_db)):
    f = _own(db, user, KnowledgeFolder, folder_id)
    if f is None:
        return {"error": "not found"}
    if f is False:
        return {"error": "无权操作"}
    has_child = db.query(KnowledgeFolder.id).filter_by(parent_id=folder_id).first()
    has_point = db.query(KnowledgePointPool.id).filter_by(folder_id=folder_id).first()
    if has_child or has_point:
        return {"error": "目录非空，请先移走子目录和知识点"}
    db.delete(f); db.commit()
    return {"ok": True}


@router.put("/knowledge-pool/{point_id}/move")
def move_point(point_id: int, folder_id: int = None,
               user: User = Depends(require_role("parent", "admin")),
               db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    p.folder_id = folder_id
    db.commit()
    return {"id": p.id, "folder_id": p.folder_id}


@router.put("/knowledge-pool/{point_id}/tags")
def set_point_tags(point_id: int, tags: list[str] = [],
                   user: User = Depends(require_role("parent", "admin")),
                   db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    p.tags = json.dumps(tags, ensure_ascii=False)
    db.commit()
    return {"id": p.id, "tags": p.tags}
```

> 注意：`move_point`/`set_point_tags` 用 `folder_id: int = None` / `tags: list[str] = []` 作 query/body 参数会与 FastAPI 的 body 解析冲突。改为用 Pydantic body：

```python
class MoveIn(BaseModel):
    folder_id: int | None = None

class TagsIn(BaseModel):
    tags: list[str] = []

@router.put("/knowledge-pool/{point_id}/move")
def move_point(point_id: int, req: MoveIn, user: User = Depends(require_role("parent", "admin")),
               db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    p.folder_id = req.folder_id
    db.commit()
    return {"id": p.id, "folder_id": p.folder_id}

@router.put("/knowledge-pool/{point_id}/tags")
def set_point_tags(point_id: int, req: TagsIn, user: User = Depends(require_role("parent", "admin")),
                   db: Session = Depends(get_db)):
    p = _own(db, user, KnowledgePointPool, point_id)
    if p is None:
        return {"error": "not found"}
    if p is False:
        return {"error": "无权操作"}
    p.tags = json.dumps(req.tags, ensure_ascii=False)
    db.commit()
    return {"id": p.id, "tags": p.tags}
```

**改 `from_pdf`**：在 `items = extract_items_from_pages(...)` 之后、写知识点循环之前，先建目录；循环里写 `folder_id` 和 `原句`：

```python
        items = extract_items_from_pages(db, handout_kind, ocr_pages)
        if items:
            folder_name = os.path.splitext(safe_name)[0] or "未命名讲义"
            folder = KnowledgeFolder(owner_id=user.id, name=folder_name, subject=subject, parent_id=None)
            db.add(folder); db.flush()
        created = 0
        for it in items:
            extra = {"释义": it.get("secondary") or "", "原句": it.get("example") or ""}
            db.add(KnowledgePointPool(
                owner_id=user.id, subject=subject, category=handout_kind,
                content=it.get("primary") or "", source="pdf",
                document_id=doc.id, folder_id=folder.id if items else None,
                extra=json.dumps(extra, ensure_ascii=False)))
            created += 1
        db.commit()
        return {"document_id": doc.id, "count": created, "folder_id": folder.id if items else None}
```

> 顶部还需 `from sqlalchemy import func`（`_folder_tree` 用到 `func.count`）。检查是否已 import，没有则加。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_knowledge_pool.py -v`
Expected: 全绿（原 6 + 新 3 = 9 passed）

- [ ] **Step 5: Commit**

```bash
cd backend && git add app/routers/knowledge_pool.py tests/test_knowledge_pool.py && git commit -m "feat(routers): 目录 CRUD + 知识点 move/tags + from-pdf 建目录写原句"
```

---

## Task 4: 前端（目录树 + 标签筛选 + 表单扩展）

**Files:**
- Modify: `parent-web/app.js`
- Modify: `parent-web/index.html`（版本号 bump）

- [ ] **Step 1: 加状态**

在 `poolForm`/`poolPdfForm`/`planForm` 声明附近加：

```js
let poolFolders = [];      // 目录树 [{id,name,subject,parent_id,point_count,children}]
let poolActiveFolder = null;  // 当前筛选的目录 id；null=全部
let poolActiveTag = null;     // 当前筛选的标签；null=全部
let folderForm = null;     // null | {mode:'add'|'rename', id?, parent_id?}
```

- [ ] **Step 2: 加载目录 + 目录树渲染**

加 `loadFolders` 和目录树渲染函数：

```js
async function loadFolders(){ poolFolders = await api('/api/knowledge-folders'); if(!Array.isArray(poolFolders)) poolFolders=[]; }

function renderFolderNode(f, depth){
  const pad = depth * 16;
  const active = poolActiveFolder === f.id;
  return `<div style="padding-left:${pad}px;margin:2px 0">
    <span style="cursor:pointer;${active?'font-weight:700;color:#2e6bd8':''}" onclick="setActiveFolder(${f.id})">
      ${f.children.length ? (f.id===poolActiveFolder?'▾':'▸') : '·'} ${escapeHtml(f.name)} <span style="color:#9aa4a0;font-size:11px">(${f.point_count})</span>
    </span>
    <button class="btn-ghost" style="padding:0 6px;font-size:11px" onclick="openFolderForm('add',${f.id})">+子目录</button>
    <button class="btn-ghost" style="padding:0 6px;font-size:11px" onclick="openFolderForm('rename',${f.id})">改</button>
    <button class="btn-ghost" style="padding:0 6px;font-size:11px" onclick="delFolder(${f.id})">删</button>
  </div>${(f.children||[]).map(c=>renderFolderNode(c, depth+1)).join('')}`;
}

function setActiveFolder(id){ poolActiveFolder = (poolActiveFolder===id) ? null : id; render(); }
```

- [ ] **Step 3: 目录 CRUD 动作**

```js
function openFolderForm(mode, parentId){
  folderForm = {mode, parentId};
  render();
}

async function submitFolder(){
  const name = document.getElementById('folderName').value.trim();
  if(!name){ toast('请填写目录名'); return; }
  if(folderForm.mode==='rename'){
    await api(`/api/knowledge-folders/${folderForm.parentId}`, {method:'PUT', body:{name}});
  } else {
    await api('/api/knowledge-folders', {method:'POST', body:{name, subject:'英语', parent_id: folderForm.parentId || null}});
  }
  folderForm = null; await loadFolders(); render();
}

async function delFolder(id){
  if(!confirm('删除该目录？（需为空目录）')) return;
  const r = await api(`/api/knowledge-folders/${id}`, {method:'DELETE'});
  if(r && r.error){ toast(r.error); return; }
  await loadFolders(); render();
}
```

- [ ] **Step 4: 改造 `renderPoolTab` 加入目录树 + 标签 + 表单字段**

在 `renderPoolTab` 顶部加目录树面板（左侧），知识点列表按 `poolActiveFolder`/`poolActiveTag` 过滤；表单加「原句」「目录」「标签」字段；列表行显示原句。

（具体实现：把 `renderPoolTab` 改为两栏布局——左侧目录树 + 右侧列表；列表 `poolPoints.filter(...)` 按 folder_id/tags 过滤；`renderPoolAddForm`/`renderPoolEditForm` 加原句、目录下拉、标签输入；列表行加原句截断显示。）

- [ ] **Step 5: 表单字段扩展**

`renderPoolAddForm` 加「原句」输入、目录下拉（`poolFolders` 扁平化）、标签输入；`submitPoolAdd`/`submitPoolEdit` 读这些字段写 `extra`（含 `原句`）、`folder_id`、`tags`。

- [ ] **Step 6: bump 版本号**

`parent-web/index.html`：`app.js?v=6` → `app.js?v=7`。

- [ ] **Step 7: 语法验证 + 提交**

Run: `cd "D:/workspace/github/KnoAct/.claude/worktrees/knowledge-point-pool" && node --check parent-web/app.js`
Expected: SYNTAX_OK

```bash
git add parent-web/app.js parent-web/index.html && git commit -m "feat(parent-web): 知识点库目录树 + 标签筛选 + 原句/目录/标签表单"
```

---

## 自检（对照 spec）

1. **Spec 覆盖**：§1 模型 → Task 1；§2 解析 → Task 2；§3 目录/标签接口 + from-pdf → Task 3；§4 前端 → Task 4；§6 顺序一致。✅
2. **占位符**：Task 4 的 Step 4/5 是「描述性」而非完整代码——前端目录树/过滤/表单字段的完整 HTML 模板较长，在实现时按 Step 1-3 已给的函数 + Step 4 的明确要求展开。已在 Step 4 标注了确切要改的函数和字段，非「TBD」。✅
3. **类型一致性**：`folder_id`（int|None）、`tags`（list[str]→JSON 字符串）、`parent_id`（int|None）、`_folder_tree` 返回结构，在 Task 3 与 Task 4 一致。✅

## 已知取舍

- 目录树默认 `subject:'英语'` 新建（Task 4 Step 3 的 `openFolderForm` add 分支硬编码英语）——后续可改为跟随当前筛选学科；本轮先简化。
- `list_folders` 对 admin 返回 `[]`（admin 无 owner_id，目录按家长隔离）——符合「仅家长端」定位。
- 前端目录树用 `▸/▾` 字符做展开指示，不做真正的折叠/展开交互（子目录始终展开显示）——简化，满足「多级显示」即可。
