# 学库宝拉题预览勾选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 家长从学库宝拉题时，先预览本页题目并勾选，再只把勾选题写入待审核队列。

**Architecture:** 后端把现有 `sync-xuekubao` 的「拉取 + normalize + 学科校验」抽成共用函数；新增 `preview-xuekubao`（不写库）与 `import-drafts`（写勾选草稿为 `pending`）。家长端 `xkbPicker` 改为两步：选知识点 → 预览勾选 → 确认导入。

**Tech Stack:** FastAPI + SQLAlchemy + pytest；`parent-web` 原生 JS（复用 `renderQuestionHtml`）。

**Spec:** `docs/superpowers/specs/2026-11-15-xuekubao-preview-select-design.md`

**关键约束（来自 AGENTS.md）：**
- 测试在 `backend/` 下跑：`python -m pytest tests/<file> -v`（用 Bash python，勿用未装依赖的 conda）。
- `DATABASE_URL` 相对路径随 cwd；测试已由 `conftest.py` 指到 `test.db`。

---

## File Structure

| 路径 | 职责 |
|------|------|
| `backend/app/routers/bank.py` | 抽取 `_fetch_xuekubao_drafts` / `_assert_draft_subject` / `_draft_to_dict` / `_dict_to_draft`；新增 `preview-xuekubao`、`import-drafts`；`sync-xuekubao` 改调共用逻辑 |
| `backend/tests/test_xuekubao_preview.py` | 预览不写库、导入 pending、学科 400 |
| `parent-web/app.js` | `xkbPicker` 两步状态机 + 预览 UI + API |
| `parent-web/index.html` | 预览列表/勾选相关 CSS（可选，能塞进现有 `.xkb-*` 则少改） |

---

### Task 1: 抽取学库宝拉取共用逻辑 + 序列化 helper

**Files:**
- Modify: `backend/app/routers/bank.py`
- Test: `backend/tests/test_xuekubao_preview.py`（本 Task 先写 helper 单测可跳过，Task 2 起测端点）

- [ ] **Step 1: 在 `bank.py` 增加 helper（紧挨 `_persist_drafts` 之后）**

```python
from dataclasses import asdict

def _draft_to_dict(d: QuestionDraft) -> dict:
    return asdict(d)

def _dict_to_draft(item: dict) -> QuestionDraft | None:
    if not isinstance(item, dict):
        return None
    q = (item.get("question") or "").strip()
    if not q:
        return None
    return QuestionDraft(
        qtype=(item.get("qtype") or "short_answer").strip(),
        question=q,
        options=item.get("options") or [],
        answer_json=item.get("answer_json") or {},
        answer=(item.get("answer") or "").strip(),
        analysis=(item.get("analysis") or "").strip(),
        difficulty=(item.get("difficulty") or "medium"),
        tags=item.get("tags") if isinstance(item.get("tags"), dict) else {},
        passage_title=(item.get("passage_title") or "").strip(),
        passage_content=(item.get("passage_content") or "").strip(),
    )

def _assert_draft_subject(bank: QuestionBank, drafts: list[QuestionDraft]) -> None:
    bank_subj = (bank.subject or "").strip()
    if not bank_subj:
        return
    for d in drafts:
        q_subj = (d.tags.get("subject_name") or "").strip()
        if q_subj and q_subj != bank_subj:
            raise HTTPException(
                status_code=400,
                detail=f"所选知识点属于「{q_subj}」，与当前卷子「{bank_subj}」不符，请先切换到对应学科的卷子再导入",
            )

def _fetch_xuekubao_drafts(db, bank: QuestionBank, req: XuekubaoSyncReq) -> tuple[list[QuestionDraft], Any]:
    """拉取并 normalize；不做 persist。返回 (drafts, raw)。未配置/拉失败抛 HTTPException。"""
    adapter = xuekubao_adapter(db)
    if not adapter.configured():
        raise HTTPException(
            status_code=503,
            detail="学库宝 API 未配置：请在「设置 → 题库来源」填写 Access Key，或设置环境变量 XUEKUBAO_ACCESS_KEY",
        )
    raw = adapter.fetch_by_knowledge(
        knowledge_id=req.knowledge_id.strip(),
        page=req.page,
        qtype_id=req.qtype_id,
        diff=req.diff,
        year=req.year,
        fetch_answers=req.fetch_answers,
    )
    items = raw.get("data") if isinstance(raw.get("data"), list) else _extract_items_safe(raw)
    err = str(raw.get("errorCode") or "")
    if not items and err not in ("0", "200", ""):
        raise HTTPException(
            status_code=502,
            detail=raw.get("message") or raw.get("errorCode") or "拉取失败",
        )
    drafts = adapter.normalize(raw)[: max(1, min(req.max_import, 50))]
    _assert_draft_subject(bank, drafts)
    return drafts, raw
```

（若文件顶部尚无 `from typing import Any`，补上；`asdict` 从 `dataclasses` 导入。）

- [ ] **Step 2: 改写 `sync_xuekubao_bank` 体，改为调用 helper**

```python
@router.post("/{bank_id}/sync-xuekubao")
def sync_xuekubao_bank(...):
    bank = _require_bank(bank_id, user, db)
    drafts, raw = _fetch_xuekubao_drafts(db, bank, req)
    if not drafts:
        return {
            "count": 0,
            "ids": [],
            "message": "未解析到题目，请核对 knowledge_id 或改用 import-third-party",
            "data_count": raw.get("dataCount"),
        }
    ids = _persist_drafts(db, bank, drafts, "xuekubao")
    db.commit()
    return {"count": len(ids), "ids": ids, "data_count": raw.get("dataCount")}
```

- [ ] **Step 3: 跑现有相关测试确认未破坏**

Run: `cd backend && python -m pytest tests/test_bank.py tests/test_xuekubao_adapter.py -v --tb=short`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/bank.py
git commit -m "refactor(bank): 抽取学库宝拉取与学科校验共用逻辑"
```

---

### Task 2: `POST .../preview-xuekubao`（TDD）

**Files:**
- Create: `backend/tests/test_xuekubao_preview.py`
- Modify: `backend/app/routers/bank.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_xuekubao_preview.py
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models import Question, QuestionBank
from app.core.source_adapter import QuestionDraft
from conftest import auth_headers, make_account

client = TestClient(app)


class _FakeXkb:
    def configured(self):
        return True

    def fetch_by_knowledge(self, **kwargs):
        return {"data": [{"_": 1}], "errorCode": "0", "dataCount": 9}

    def normalize(self, raw):
        return [
            QuestionDraft(
                qtype="single_choice",
                question='如图<br/><img src="https://img.cuotixue.com/a.jpg">',
                options=[{"label": "A", "value": 0}],
                answer="A",
                tags={"source": "xuekubao", "subject_name": "数学"},
            ),
            QuestionDraft(
                qtype="fill_blank",
                question="填空题干",
                answer="1",
                tags={"subject_name": "数学"},
            ),
        ]


def _math_bank_headers():
    db = SessionLocal()
    p = make_account(db, "xkb_prev_parent", "parent")
    bank = QuestionBank(user_id=p.id, title="数学练习", subject="数学", source="manual")
    db.add(bank)
    db.commit()
    bid, h = bank.id, auth_headers(p)
    db.close()
    return h, bid


def test_preview_xuekubao_returns_drafts_without_persist(client, setup_db, monkeypatch):
    import app.routers.bank as bank_mod
    monkeypatch.setattr(bank_mod, "xuekubao_adapter", lambda db: _FakeXkb())
    h, bid = _math_bank_headers()
    before = SessionLocal().query(Question).count()
    r = client.post(
        f"/api/banks/{bid}/preview-xuekubao",
        headers=h,
        json={"knowledge_id": "15190", "page": 1, "max_import": 20},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data["drafts"]) == 2
    assert data["drafts"][0]["question"].startswith("如图")
    assert data["page"] == 1
    assert data.get("data_count") == 9
    db = SessionLocal()
    assert db.query(Question).count() == before
    db.close()


def test_preview_xuekubao_subject_mismatch_400(client, setup_db, monkeypatch):
    import app.routers.bank as bank_mod

    class _Wrong(_FakeXkb):
        def normalize(self, raw):
            return [QuestionDraft(qtype="short_answer", question="语文题", tags={"subject_name": "语文"})]

    monkeypatch.setattr(bank_mod, "xuekubao_adapter", lambda db: _Wrong())
    h, bid = _math_bank_headers()
    r = client.post(
        f"/api/banks/{bid}/preview-xuekubao",
        headers=h,
        json={"knowledge_id": "1", "page": 1},
    )
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_xuekubao_preview.py::test_preview_xuekubao_returns_drafts_without_persist -v`  
Expected: FAIL（404 或路由不存在）

- [ ] **Step 3: 实现端点**

在 `sync_xuekubao_bank` 旁添加：

```python
@router.post("/{bank_id}/preview-xuekubao")
def preview_xuekubao_bank(
    bank_id: int,
    req: XuekubaoSyncReq,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """拉题预览：normalize + 学科校验，不写库。"""
    bank = _require_bank(bank_id, user, db)
    drafts, raw = _fetch_xuekubao_drafts(db, bank, req)
    if not drafts:
        return {
            "drafts": [],
            "page": req.page,
            "data_count": raw.get("dataCount"),
            "message": "未解析到题目，请核对 knowledge_id 或改用 import-third-party",
        }
    return {
        "drafts": [_draft_to_dict(d) for d in drafts],
        "page": req.page,
        "data_count": raw.get("dataCount"),
    }
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_xuekubao_preview.py -v`  
Expected: 两个 preview 相关测试 PASS（import 测试若尚未写可先 skip / 本文件暂只含上述两个）

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/bank.py backend/tests/test_xuekubao_preview.py
git commit -m "feat(bank): 新增 preview-xuekubao 拉题预览不写库"
```

---

### Task 3: `POST .../import-drafts`（TDD）

**Files:**
- Modify: `backend/tests/test_xuekubao_preview.py`
- Modify: `backend/app/routers/bank.py`

- [ ] **Step 1: 追加失败测试**

```python
class ImportDraftsReq:  # 仅文档；实际请求用 json
    pass


def test_import_drafts_persists_pending(client, setup_db):
    h, bid = _math_bank_headers()
    items = [
        {
            "qtype": "single_choice",
            "question": "预览勾选题 A",
            "options": [{"label": "1", "value": 0}],
            "answer": "1",
            "answer_json": {"correct_index": 0},
            "tags": {"subject_name": "数学"},
        },
        {
            "qtype": "fill_blank",
            "question": "预览勾选题 B",
            "answer": "2",
            "tags": {"subject_name": "数学"},
        },
    ]
    r = client.post(
        f"/api/banks/{bid}/import-drafts",
        headers=h,
        json={"source": "xuekubao", "items": items},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] == 2
    assert len(data["ids"]) == 2
    db = SessionLocal()
    qs = db.query(Question).filter(Question.id.in_(data["ids"])).all()
    assert len(qs) == 2
    assert all(q.status == "pending" for q in qs)
    assert all(q.bank_id == bid for q in qs)
    db.close()


def test_import_drafts_subject_mismatch_400(client, setup_db):
    h, bid = _math_bank_headers()
    r = client.post(
        f"/api/banks/{bid}/import-drafts",
        headers=h,
        json={
            "source": "xuekubao",
            "items": [{"qtype": "short_answer", "question": "x", "tags": {"subject_name": "语文"}}],
        },
    )
    assert r.status_code == 400


def test_import_drafts_rejects_too_many(client, setup_db):
    h, bid = _math_bank_headers()
    items = [{"qtype": "short_answer", "question": f"q{i}", "tags": {}} for i in range(51)]
    r = client.post(
        f"/api/banks/{bid}/import-drafts",
        headers=h,
        json={"source": "xuekubao", "items": items},
    )
    assert r.status_code == 400
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_xuekubao_preview.py::test_import_drafts_persists_pending -v`  
Expected: FAIL 404

- [ ] **Step 3: 实现 `ImportDraftsReq` + 端点**

```python
class ImportDraftsReq(BaseModel):
    source: str = "xuekubao"
    items: list[dict] = []


@router.post("/{bank_id}/import-drafts")
def import_drafts(
    bank_id: int,
    req: ImportDraftsReq,
    user: User = Depends(require_role("parent", "admin")),
    db: Session = Depends(get_db),
):
    """写入已标准化草稿（预览勾选后确认）。"""
    bank = _require_bank(bank_id, user, db)
    if len(req.items) > 50:
        raise HTTPException(status_code=400, detail="单次最多导入 50 道题")
    drafts = []
    for it in req.items:
        d = _dict_to_draft(it)
        if d:
            drafts.append(d)
    if not drafts:
        raise HTTPException(status_code=400, detail="没有可导入的题目")
    _assert_draft_subject(bank, drafts)
    tag = (req.source or "xuekubao").strip() or "xuekubao"
    ids = _persist_drafts(db, bank, drafts, tag)
    db.commit()
    return {"count": len(ids), "ids": ids}
```

- [ ] **Step 4: 全文件测试通过**

Run: `cd backend && python -m pytest tests/test_xuekubao_preview.py -v`  
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/bank.py backend/tests/test_xuekubao_preview.py
git commit -m "feat(bank): 新增 import-drafts 写入预览勾选的题目"
```

---

### Task 4: 家长端 `xkbPicker` 状态扩展 + 拉取预览

**Files:**
- Modify: `parent-web/app.js`（`xkbPicker` 初始化、`paintXkbModal`、`confirmXuekubaoSync`）

- [ ] **Step 1: 扩展 picker 初始状态**

找到 `let xkbPicker = {` / `openXuekubaoPicker` 里重置处，改为包含：

```javascript
// 字段语义见 design §2.1
// step: 'pick' | 'preview'
xkbPicker = {
  open: true, loading: false, error: '', tree: [], sel: ['','','',''],
  chapters: null, knowledge: [], filter: '', picked: null, page: 1,
  step: 'pick', drafts: [], selected: {}, previewLoading: false, dataCount: null,
};
```

`openXuekubaoPicker` 重置时同样带上这些字段，且 `step: 'pick'`、`drafts: []`、`selected: {}`。

- [ ] **Step 2: 步骤 1 主按钮改文案与 handler**

在 `paintXkbModal` 的 foot（`step === 'pick'` 或默认）中：

```html
<button type="button" class="btn-primary" ${!xkbPicker.picked || xkbPicker.loading || xkbPicker.previewLoading ? 'disabled' : ''} onclick="loadXuekubaoPreview()">拉取预览</button>
```

- [ ] **Step 3: 实现 `loadXuekubaoPreview`**

替换原 `confirmXuekubaoSync`（或让旧名转调新函数）：

```javascript
async function loadXuekubaoPreview(){
  if(!bankSelectedId || !xkbPicker.picked) return;
  xkbPicker.previewLoading = true;
  xkbPicker.error = '';
  paintXkbModal();
  try{
    const r = await api(`/api/banks/${bankSelectedId}/preview-xuekubao`, {
      method:'POST',
      body:{
        knowledge_id: xkbPicker.picked,
        page: Math.max(1, xkbPicker.page || 1),
        max_import: 20,
        fetch_answers: true,
      },
    });
    if(r && r.detail) throw new Error(typeof r.detail === 'string' ? r.detail : (r.detail.msg || JSON.stringify(r.detail)));
    const drafts = Array.isArray(r && r.drafts) ? r.drafts : [];
    if(!drafts.length){
      xkbPicker.error = (r && r.message) || '本页没有题目';
      xkbPicker.previewLoading = false;
      paintXkbModal();
      return;
    }
    xkbPicker.drafts = drafts;
    xkbPicker.dataCount = r.data_count;
    xkbPicker.selected = {};
    drafts.forEach((_, i) => { xkbPicker.selected[i] = true; });
    xkbPicker.step = 'preview';
  }catch(e){
    xkbPicker.error = (e && e.message) || '拉取预览失败';
  }
  xkbPicker.previewLoading = false;
  paintXkbModal();
}
```

注意：若项目里 `api()` 对非 2xx 已 throw，按现有 `confirmXuekubaoSync` / `loadXkbChapters` 错误处理风格对齐即可。

- [ ] **Step 4: 手工冒烟（可选）** — 打开家长端弹窗，点「拉取预览」，Network 应见 `preview-xuekubao` 且 DB 无新题（有后端时）。

- [ ] **Step 5: Commit**

```bash
git add parent-web/app.js
git commit -m "feat(parent-web): 学库宝弹窗改为拉取预览入口"
```

---

### Task 5: 预览勾选 UI + 导入已选

**Files:**
- Modify: `parent-web/app.js`（`paintXkbModal` 分支）
- Modify: `parent-web/index.html`（CSS）

- [ ] **Step 1: 在 `index.html` 增加预览样式**（紧挨现有 `.xkb-*`）

```css
.xkb-preview-toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px;font-size:13px;color:#5c6761}
.xkb-preview-list{display:flex;flex-direction:column;gap:10px;max-height:min(52vh,420px);overflow:auto}
.xkb-preview-item{display:flex;gap:10px;align-items:flex-start;padding:12px;border:1px solid #e8ece8;border-radius:12px;background:#fafbf9}
.xkb-preview-item input{margin-top:4px;flex-shrink:0}
.xkb-preview-body{flex:1;min-width:0;font-size:13px;line-height:1.5;color:#333}
.xkb-preview-body img{max-width:100%;height:auto;vertical-align:middle;margin:6px 0}
.xkb-qtype{display:inline-block;font-size:10px;font-weight:700;border-radius:5px;padding:1px 6px;margin-right:6px;background:#edf1ff;color:#4566e8}
.xkb-panel.wide{width:min(720px,100%)}
```

- [ ] **Step 2: `paintXkbModal` 按 `step` 分支渲染**

伪结构（嵌入现有 `el.innerHTML = ...`）：

```javascript
function xkbSelectedCount(){
  return (xkbPicker.drafts || []).reduce((n,_,i)=>n+(xkbPicker.selected[i]?1:0),0);
}
function xkbToggleAll(on){
  (xkbPicker.drafts||[]).forEach((_,i)=>{ xkbPicker.selected[i]=!!on; });
  paintXkbModal();
}
function xkbToggleOne(i, on){
  xkbPicker.selected[i]=!!on;
  paintXkbModal();
}
function xkbBackToPick(){
  xkbPicker.step = 'pick';
  xkbPicker.drafts = [];
  xkbPicker.selected = {};
  xkbPicker.dataCount = null;
  paintXkbModal();
}

// paintXkbModal 内：
const panelClass = xkbPicker.step === 'preview' ? 'xkb-panel wide' : 'xkb-panel';
if(xkbPicker.step === 'preview'){
  const n = xkbSelectedCount();
  const m = (xkbPicker.drafts||[]).length;
  const items = (xkbPicker.drafts||[]).map((d,i)=>{
    const checked = xkbPicker.selected[i] ? 'checked' : '';
    const label = (typeof QTYPE_LABEL !== 'undefined' && QTYPE_LABEL[d.qtype]) ? QTYPE_LABEL[d.qtype] : (d.qtype||'题目');
    const opts = Array.isArray(d.options) ? d.options : [];
    const optHtml = opts.length
      ? `<div style="margin-top:6px;font-size:12px;color:#5c6761">${opts.map(o=>`<div>${renderQuestionHtml(o.label||'')}</div>`).join('')}</div>`
      : '';
    return `<label class="xkb-preview-item">
      <input type="checkbox" ${checked} onchange="xkbToggleOne(${i}, this.checked)">
      <div class="xkb-preview-body">
        <span class="xkb-qtype">${escapeAttr(label)}</span>
        ${renderQuestionHtml(d.question||'')}
        ${optHtml}
      </div>
    </label>`;
  }).join('');
  el.innerHTML = `<div class="${panelClass}" role="dialog">
    <div class="hd">
      <h4>预览并勾选题目</h4>
      <p>本页 ${m} 道${xkbPicker.dataCount!=null?`（来源约 ${escapeAttr(String(xkbPicker.dataCount))} 道）`:''} · 不跨页保留勾选</p>
    </div>
    <div class="bd">
      ${xkbPicker.error ? `<div style="color:#c05b4a;font-size:13px;margin-bottom:10px">${escapeAttr(xkbPicker.error)}</div>` : ''}
      <div class="xkb-preview-toolbar">
        <button type="button" class="btn-ghost" onclick="xkbToggleAll(true)">全选</button>
        <button type="button" class="btn-ghost" onclick="xkbToggleAll(false)">全不选</button>
        <span>已选 ${n} / ${m}</span>
        <label style="margin-left:auto;display:flex;align-items:center;gap:6px">页码
          <input type="number" min="1" max="50" value="${xkbPicker.page||1}" style="width:64px;padding:4px 8px;border-radius:8px;border:1px solid var(--line3)"
            onchange="xkbPicker.page=Math.max(1,parseInt(this.value,10)||1);loadXuekubaoPreview()">
        </label>
      </div>
      <div class="xkb-preview-list">${items}</div>
    </div>
    <div class="xkb-foot">
      <button type="button" class="btn-ghost" onclick="xkbBackToPick()">返回</button>
      <button type="button" class="btn-primary" ${n<1 || xkbPicker.previewLoading ? 'disabled' : ''} onclick="confirmXuekubaoImportSelected()">导入已选 (${n})</button>
    </div>
  </div>`;
  return;
}
// else: 现有 pick UI …
```

若 `QTYPE_LABEL` 不存在，用 `parent-web` 里已有的 `QTYPE_LABEL` / `BANK_QTYPE_*` 常量名（grep 后对齐，不要新建第二套）。

- [ ] **Step 3: 实现确认导入**

```javascript
async function confirmXuekubaoImportSelected(){
  if(!bankSelectedId) return;
  const items = (xkbPicker.drafts||[]).filter((_,i)=>xkbPicker.selected[i]);
  if(!items.length){ toast('请至少勾选一道题'); return; }
  xkbPicker.previewLoading = true;
  paintXkbModal();
  try{
    const r = await api(`/api/banks/${bankSelectedId}/import-drafts`, {
      method:'POST',
      body:{ source:'xuekubao', items },
    });
    if(r && r.detail) throw new Error(typeof r.detail==='string'?r.detail:JSON.stringify(r.detail));
    if(r && r.count > 0){
      toast(`已导入 ${r.count} 道题，请到审核台确认`);
      closeXuekubaoPicker();
      await loadBankList();
      render();
      return;
    }
    toast((r && r.message) || '导入失败');
  }catch(e){
    toast((e && e.message) || '导入失败');
  }
  xkbPicker.previewLoading = false;
  paintXkbModal();
}
```

- [ ] **Step 4: Commit**

```bash
git add parent-web/app.js parent-web/index.html
git commit -m "feat(parent-web): 学库宝预览勾选后导入已选题目"
```

---

### Task 6: 端到端核对 + 回归

**Files:** 无新增（验证）

- [ ] **Step 1: 后端回归**

Run: `cd backend && python -m pytest tests/test_xuekubao_preview.py tests/test_bank.py tests/test_xuekubao_adapter.py -v`  
Expected: PASS

- [ ] **Step 2: 手工清单（有学库宝密钥时）**

1. 家长端 → 题库管理 → 选「数学练习」→ 学库宝选题  
2. 选知识点 → 拉取预览 → 看到图/题干，非 HTML 源码  
3. 取消勾选一半 → 导入已选 → toast 数量正确  
4. 审核台仅出现勾选的题，`pending`  
5. 换页码重新拉取 → 勾选状态重置（不跨页）  
6. 对语文卷误选数学知识点 → 预览阶段 400/错误提示  

- [ ] **Step 3: 最终 commit（若有修正）**

仅在有修复时提交，例如：

```bash
git commit -m "fix(parent-web): 学库宝预览勾选边界与错误提示"
```

---

## 执行方式

实现时优先用 **subagent-driven-development**：每个 Task 一个子代理，按 TDD 步骤推进，Task 间用本 plan 的 checkbox 勾选进度。
