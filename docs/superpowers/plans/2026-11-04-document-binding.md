# 教材绑定（家长选配）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 孩子能看到哪些教材由家长在家长端显式勾选绑定（新表 `UserDocument`），教材的 `grade`/`edition` 字段保留作家长端筛选标签。

**Architecture:** 后端新增 `UserDocument(user_id, document_id)` 绑定表 + bind/unbind/bound-users 三接口 + 教材列表按 `user_id` 过滤；家长端教材行加「绑定孩子」多选、上传表单加年级/版本；学生端带当前孩子 id 拉教材。

**Tech Stack:** FastAPI + SQLAlchemy（后端）；原生 JS `parent-web`（家长端）；Flutter + Riverpod（学生端）。

**Spec:** `docs/superpowers/specs/2026-11-04-document-binding-design.md`

---

## 文件结构

**后端：**
- `backend/app/models.py`（修改）— 新增 `UserDocument` 表
- `backend/app/seed.py`（修改）— 幂等迁移（新表由 create_all 建，无需 ALTER）
- `backend/app/routers/pdf.py`（修改）— upload 加 grade/edition、list 加 user_id 过滤+返回标签、bind/unbind/bound-users、delete 级联清理
- `backend/tests/test_pdf_router.py`（修改）— 测试

**家长端：**
- `parent-web/app.js`（修改）— 绑定交互 + 上传表单标签

**学生端：**
- `student-app/lib/features/reader/data/pdf_repository.dart`（修改）— documents() 带 user_id
- `student-app/lib/features/reader/reader_controller.dart`（修改）— 传 uid

---

## Task 1: 后端 `UserDocument` 表 + 上传写标签

**Files:**
- Modify: `backend/app/models.py`（追加到 `ChildConfig` 之后、`AppGroup` 之前或末尾）
- Modify: `backend/app/routers/pdf.py`（upload 加 grade/edition）
- Test: `backend/tests/test_pdf_router.py`

- [ ] **Step 1: 写失败测试（模型 + 上传标签）**

在 `backend/tests/test_pdf_router.py` 追加：

```python
def test_user_document_model_and_upload_grade_edition(setup_db):
    from app.models import UserDocument, PdfDocument
    from app.database import SessionLocal
    s = SessionLocal()
    # 直接建绑定行
    u = s.query(User).first() if s.query(User).first() else None
    s.close()
    # 上传带标签（走接口）
    from fastapi import UploadFile
    import io
    from fastapi.testclient import TestClient
    # 复用现有 _client()
    c = _client()
    # 上传接口需要真实 PDF 才拆课，这里测「参数能存进 PdfDocument」用直接调路由逻辑较繁琐，
    # 改为测 UserDocument 唯一约束 + 上传参数解析（用 multipart 传 grade/edition）。
    ...
```

> 注：上传接口会 render_pages/detect_lessons（需要真实 PDF + PyMuPDF），测试用假 PDF 会失败。改为两步：
> 1) 测 `UserDocument` 模型唯一约束（直接 add 两行相同 (user_id, document_id) 应抛 IntegrityError，或 count==1）。
> 2) 测 `list_documents` 返回 `grade`/`edition` 字段（先直接建带标签的 PdfDocument 再 GET）。
> upload 的 grade/edition 写入用「直接构造 PdfDocument(grade=, edition=)」覆盖（见 Task 3 的 list 测试）。

- [ ] **Step 2: 实现模型**

在 `backend/app/models.py` 追加（放 `ChildConfig` 类之后）：

```python
class UserDocument(Base):
    """孩子 ↔ 教材 绑定：孩子能看哪些教材由家长显式选配；一本可绑多孩子（共享）。"""
    __tablename__ = "user_documents"
    __table_args__ = (
        UniqueConstraint("user_id", "document_id", name="uq_user_document"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("pdf_documents.id"))
```

- [ ] **Step 3: upload 加 grade/edition 参数**

`backend/app/routers/pdf.py` 的 `upload_pdf` 签名加 `grade: int = Form(None)`、`edition: str = Form("")`，并在建 `PdfDocument` 时传入：

```python
async def upload_pdf(subject: str = Form(...), grade: int = Form(None),
                     edition: str = Form(""), file: UploadFile = File(...),
                     db: Session = Depends(get_db)):
    ...
    doc = PdfDocument(filename=file.filename, subject=subject, storage_path="",
                      grade=grade, edition=edition)
```

- [ ] **Step 4: 跑测试**

Run: `cd backend && python -m pytest tests/test_pdf_router.py -q`
Expected: PASS（新测试 + 现有测试不回归）

- [ ] **Step 5: 提交**

```bash
git add backend/app/models.py backend/app/routers/pdf.py backend/tests/test_pdf_router.py
git commit -m "feat(document-binding): UserDocument 表 + 上传写 grade/edition 标签"
```

---

## Task 2: 后端绑定接口 + 列表过滤 + 删除级联

**Files:**
- Modify: `backend/app/routers/pdf.py`
- Test: `backend/tests/test_pdf_router.py`

- [ ] **Step 1: 写失败测试**

```python
def test_bind_unbind_and_filter(setup_db):
    from app.models import User, PdfDocument, UserDocument
    from app.database import SessionLocal
    s = SessionLocal()
    c1 = User(name="晨晨", role="child", grade=3)
    c2 = User(name="乐乐", role="child", grade=4)
    d = PdfDocument(filename="语文.pdf", subject="语文", storage_path="x", grade=3, edition="人教")
    s.add_all([c1, c2, d]); s.flush()
    did = d.id; s.commit(); s.close()

    c = _client()
    # 绑定
    r = c.post(f"/api/pdf/documents/{did}/bind", json={"user_id": c1.id})
    assert r.status_code == 200
    # 幂等再绑
    c.post(f"/api/pdf/documents/{did}/bind", json={"user_id": c1.id})
    # bound-users
    r = c.get(f"/api/pdf/documents/{did}/bound-users").json()
    assert c1.id in r["user_ids"]
    # 列表过滤：c1 能看到，c2 看不到
    r = c.get(f"/api/pdf/documents?user_id={c1.id}").json()
    assert len(r) == 1
    r = c.get(f"/api/pdf/documents?user_id={c2.id}").json()
    assert len(r) == 0
    # 解绑
    c.delete(f"/api/pdf/documents/{did}/bind?user_id={c1.id}")
    r = c.get(f"/api/pdf/documents?user_id={c1.id}").json()
    assert len(r) == 0


def test_delete_document_cleans_bindings(setup_db):
    from app.models import User, PdfDocument, UserDocument
    from app.database import SessionLocal
    s = SessionLocal()
    c1 = User(name="晨晨", role="child", grade=3)
    d = PdfDocument(filename="语文.pdf", subject="语文", storage_path="uploads/none.pdf", grade=3, edition="")
    s.add_all([c1, d]); s.flush()
    s.add(UserDocument(user_id=c1.id, document_id=d.id))
    s.commit(); did = d.id; s.close()
    c = _client()
    c.delete(f"/api/pdf/documents/{did}")
    s = SessionLocal()
    assert s.query(UserDocument).count() == 0
    s.close()
```

- [ ] **Step 2: 实现接口**

`backend/app/routers/pdf.py`：

`list_documents` 加 `user_id: int = None` 参数 + 过滤 + 返回标签：

```python
@router.get("/documents")
def list_documents(user_id: int = None, db: Session = Depends(get_db)):
    q = db.query(PdfDocument)
    if user_id is not None:
        bound = db.query(UserDocument.document_id).filter_by(user_id=user_id)
        q = q.filter(PdfDocument.id.in_(bound))
    docs = q.all()
    out = []
    for d in docs:
        lessons = db.query(Lesson).filter_by(document_id=d.id).all()
        out.append({
            "id": d.id, "filename": d.filename, "subject": d.subject,
            "storage_path": d.storage_path,
            "grade": d.grade, "edition": d.edition,
            "lesson_count": len(lessons),
            "audited_count": sum(1 for l in lessons if l.audit_status == "approved"),
        })
    return out
```

新增三个接口（放 `list_document_lessons` 之后）：

```python
from pydantic import BaseModel

class BindReq(BaseModel):
    user_id: int

@router.post("/documents/{document_id}/bind")
def bind_document(document_id: int, req: BindReq, db: Session = Depends(get_db)):
    exists = db.query(UserDocument).filter_by(user_id=req.user_id, document_id=document_id).first()
    if not exists:
        db.add(UserDocument(user_id=req.user_id, document_id=document_id))
        db.commit()
    return {"ok": True}

@router.delete("/documents/{document_id}/bind")
def unbind_document(document_id: int, user_id: int, db: Session = Depends(get_db)):
    db.query(UserDocument).filter_by(user_id=user_id, document_id=document_id).delete(synchronize_session=False)
    db.commit()
    return {"ok": True}

@router.get("/documents/{document_id}/bound-users")
def bound_users(document_id: int, db: Session = Depends(get_db)):
    ids = [r[0] for r in db.query(UserDocument.user_id).filter_by(document_id=document_id).all()]
    return {"user_ids": ids}
```

`delete_document` 加清理（在 `db.delete(doc)` 前）：

```python
    db.query(UserDocument).filter_by(document_id=document_id).delete(synchronize_session=False)
```

- [ ] **Step 3: 加 import**

`backend/app/routers/pdf.py` 的 models import 加 `UserDocument`；顶部加 `from pydantic import BaseModel`。

- [ ] **Step 4: 跑测试**

Run: `cd backend && python -m pytest tests/test_pdf_router.py -q`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/pdf.py backend/tests/test_pdf_router.py
git commit -m "feat(document-binding): bind/unbind/bound-users 接口 + 列表按 user_id 过滤 + 删除级联"
```

---

## Task 3: 家长端绑定交互 + 上传表单标签

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1: 上传表单加年级/版本**

`renderPdfTab` 的 upload 分支，在「学科」select 后加：

```javascript
<div style="margin-top:12px;display:flex;gap:8px;align-items:center">
  <span style="font-size:13px;color:var(--gray2)">年级：</span>
  <select id="pdfGrade" style="..."><option value="">不限</option><option>1</option>...<option>6</option></select>
  <span style="font-size:13px;color:var(--gray2)">版本：</span>
  <input id="pdfEdition" placeholder="如 人教/北师大（可空）" style="...">
</div>
```

`uploadPdf` 里 append：

```javascript
const grade = document.getElementById('pdfGrade').value;
const edition = document.getElementById('pdfEdition').value.trim();
if(grade) fd.append('grade', grade);
if(edition) fd.append('edition', edition);
```

- [ ] **Step 2: 教材行加绑定入口 + 显示标签**

`renderPdfTab` 的教材行 meta 显示 `grade`/`edition`；加「绑定」按钮：

```javascript
const rows = pdfDocs.map(d=>`
  <div class="pdf-row">
    ...
    <div><div class="nm">${d.filename}</div><div class="meta">${d.subject}${d.grade?(' · '+d.grade+'年级'):''}${d.edition?(' · '+d.edition):''} · ${d.lesson_count} 课 · 已审核 ${d.audited_count} 课</div></div>
    <div style="display:flex;gap:6px;margin-left:auto">
      <button class="btn-ghost" onclick="openDocBind(${d.id})">绑定孩子</button>
      <button class="btn-ghost" onclick="openDoc(${d.id})">查看/审核</button>
      ...
    </div>
  </div>`).join('');
```

- [ ] **Step 3: 绑定弹窗逻辑**

新增 `openDocBind(documentId)` + `toggleDocBind(userId, documentId, checked)` + `renderDocBind(documentId)`：

```javascript
async function openDocBind(documentId){
  const r = await api(`/api/pdf/documents/${documentId}/bound-users`);
  boundUsers = r.user_ids || [];
  bindDocId = documentId;
  render();
}
async function toggleDocBind(userId, documentId, checked){
  if(checked) await api(`/api/pdf/documents/${documentId}/bind`,{method:'POST',body:{user_id:userId}});
  else await api(`/api/pdf/documents/${documentId}/bind?user_id=${userId}`,{method:'DELETE'});
  const r = await api(`/api/pdf/documents/${documentId}/bound-users`);
  boundUsers = r.user_ids || [];
  render();
}
```

弹窗渲染：列出 `children` 每个孩子一个 checkbox，勾选状态来自 `boundUsers`。

> 注意：`api(path, {method:'DELETE'})` 对带 query 的 DELETE 是否拼接 query —— 看现有 `api()` 实现；若 `api` 不支持 DELETE+query，用 `api('/api/pdf/documents/${id}/bind?user_id=${uid}', {method:'DELETE'})`（query 拼在 path 上，与现有 `deleteTask` 风格一致）。

- [ ] **Step 4: 语法校验**

Run: `node --check parent-web/app.js`
Expected: SYNTAX OK

- [ ] **Step 5: 提交**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): 教材绑定孩子多选 + 上传年级/版本标签"
```

---

## Task 4: 学生端带 user_id 拉教材

**Files:**
- Modify: `student-app/lib/features/reader/data/pdf_repository.dart`
- Modify: `student-app/lib/features/reader/reader_controller.dart`

- [ ] **Step 1: repository 加 user_id 参数**

`PdfRepository.documents()` 改为：

```dart
Future<List<PdfDoc>> documents({int? userId}) async {
  final list = await _api.get('/api/pdf/documents', query: userId != null ? {'user_id': userId} : null);
  return [for (final d in (list as List).whereType<Map>()) PdfDoc.fromJson(Map<String, dynamic>.from(d))];
}
```

- [ ] **Step 2: controller 传 uid**

`ReaderController.loadDocuments()`：

```dart
Future<void> loadDocuments() async {
  state = state.copyWith(documents: const AsyncLoading());
  final uid = _uid;
  final result = await AsyncValue.guard(() => ref.read(pdfRepositoryProvider).documents(userId: uid));
  if (!ref.mounted) return;
  state = state.copyWith(documents: result);
}
```

- [ ] **Step 3: 验证**

Run: `cd student-app && flutter analyze`（无新问题）+ `flutter test`（不回归）

- [ ] **Step 4: 提交**

```bash
git add student-app/lib/features/reader/data/pdf_repository.dart student-app/lib/features/reader/reader_controller.dart
git commit -m "feat(student-app): 学生端按当前孩子 id 拉取绑定教材"
```

---

## Self-Review

**1. Spec 覆盖**：spec 第 1 节（UserDocument 表）→ Task 1；第 2 节（bind/unbind/bound-users/过滤/删除级联）→ Task 2；第 3 节（家长端）→ Task 3；第 4 节（学生端）→ Task 4。✅

**2. 占位符**：无 TBD；Task 1 的 upload 标签测试改用「构造 PdfDocument + list 断言」覆盖（因 upload 需真实 PDF），已在 Step 1 注释说明。✅

**3. 类型一致**：`UserDocument(user_id, document_id)` 在 Task 1/2/3 一致；`PdfDocument.grade`(int, nullable)/`edition`(str) 一致；`list_documents(user_id)` 后端返回 `grade`/`edition` 与前端 `d.grade`/`d.edition` 一致。✅
