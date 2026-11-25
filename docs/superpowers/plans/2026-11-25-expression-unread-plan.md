# 「孩子讲的」未读提示 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 家长端导航的「报告」上显示一个红点，告诉家长「孩子又讲了几条」；家长打开报告页后红点消失。

**Architecture:** 复用现有 `ChildConfig`（孩子级 key-value）存一个「家长最后查看时间」的时间戳。新增两个轻量端点：一个返回未读数，一个把「已看到现在」记下来。前端在导航渲染时显示红点，进入报告 Tab 时上报已读。

**Tech Stack:** FastAPI + SQLAlchemy、pytest、parent-web 原生 JS

**依据：** `docs/superpowers/specs/2026-11-25-feynman-teach-ai-design.md`（这个功能的价值取决于家长会不会看，所以必须有发现机制）

---

## 设计约束

| 约束 | 原因 |
| --- | --- |
| **不判定、不评价** | 与整个表达练习功能一致——只告诉「有几条新的」，不说「讲得好不好」 |
| **不新增表** | `ChildConfig` 就是干这个的（孩子级 key-value，跨学年沿用） |
| **红点不能刷屏** | 家长每看一次就清空；没新的就不显示 |
| **失败不影响报告页** | 未读查询挂了，报告页照常能用 |

## 存储设计

`ChildConfig(user_id, key='expression_seen_at', value='ISO8601')`

- **未读数** = `expression_notes` 里 `created_at > seen_at` 且属于该孩子的条数
- `seen_at` 不存在时（家长从没看过）→ 全部笔记都算未读
- 家长进报告页 → 写入 `now()`

**为什么不用「每条已读」**：这功能是「窗户」不是工单系统，逐条已读太重。时间戳足够回答「有没有新的」。

---

## File Structure

| 文件 | 职责 | 动作 |
| --- | --- | --- |
| `backend/app/routers/expression.py` | 加 `GET /unread-count`、`POST /mark-seen` | Modify |
| `backend/tests/test_expression.py` | 追加测试 | Modify |
| `parent-web/app.js` | 红点渲染 + 进入报告时上报 | Modify |

---

## Task 1: 后端两个端点

**Files:**
- Modify: `backend/app/routers/expression.py`
- Test: `backend/tests/test_expression.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_expression.py`：

```python
def test_unread_count_counts_all_when_never_seen():
    """家长从没看过 → 全部笔记都算未读。"""
    uid, h = _seed_child(prefix="u1")
    kp_id = _seed_kp_with_mastery(uid, "比喻", prefix="u1")
    for text in ("第一条", "第二条"):
        _client().post("/api/expression/notes", json={
            "user_id": uid, "knowledge_point_id": kp_id, "text": text
        }, headers=h)

    r = _client().get(f"/api/expression/unread-count?user_id={uid}", headers=h)
    assert r.status_code == 200
    assert r.json()["count"] == 2


def test_unread_count_zero_after_mark_seen():
    uid, h = _seed_child(prefix="u2")
    kp_id = _seed_kp_with_mastery(uid, "拟人", prefix="u2")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "看过之前的"
    }, headers=h)

    assert _client().post("/api/expression/mark-seen",
                          json={"user_id": uid}, headers=h).status_code == 200
    r = _client().get(f"/api/expression/unread-count?user_id={uid}", headers=h)
    assert r.json()["count"] == 0


def test_unread_count_rises_when_new_note_after_seen():
    """标记已读后再写一条，未读数变 1。"""
    uid, h = _seed_child(prefix="u3")
    kp_id = _seed_kp_with_mastery(uid, "排比", prefix="u3")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "旧的"
    }, headers=h)
    _client().post("/api/expression/mark-seen", json={"user_id": uid}, headers=h)

    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "新的"
    }, headers=h)

    r = _client().get(f"/api/expression/unread-count?user_id={uid}", headers=h)
    assert r.json()["count"] == 1


def test_mark_seen_is_idempotent_and_monotonic():
    """连续两次 mark-seen 不报错，且不会把已读时间往回退。"""
    uid, h = _seed_child(prefix="u4")
    kp_id = _seed_kp_with_mastery(uid, "夸张", prefix="u4")
    _client().post("/api/expression/notes", json={
        "user_id": uid, "knowledge_point_id": kp_id, "text": "x"
    }, headers=h)
    for _ in range(2):
        assert _client().post("/api/expression/mark-seen",
                              json={"user_id": uid}, headers=h).status_code == 200
    assert _client().get(f"/api/expression/unread-count?user_id={uid}",
                         headers=h).json()["count"] == 0


def test_unread_count_is_per_child():
    """两个孩子互不影响。"""
    uid_a, h_a = _seed_child(prefix="u5a")
    uid_b, h_b = _seed_child(prefix="u5b")
    kp_a = _seed_kp_with_mastery(uid_a, "A的", prefix="u5a")
    kp_b = _seed_kp_with_mastery(uid_b, "B的", prefix="u5b")
    _client().post("/api/expression/notes", json={
        "user_id": uid_a, "knowledge_point_id": kp_a, "text": "A"
    }, headers=h_a)
    _client().post("/api/expression/notes", json={
        "user_id": uid_b, "knowledge_point_id": kp_b, "text": "B1"
    }, headers=h_b)
    _client().post("/api/expression/notes", json={
        "user_id": uid_b, "knowledge_point_id": kp_b, "text": "B2"
    }, headers=h_b)

    assert _client().get(f"/api/expression/unread-count?user_id={uid_a}",
                         headers=h_a).json()["count"] == 1
    assert _client().get(f"/api/expression/unread-count?user_id={uid_b}",
                         headers=h_b).json()["count"] == 2


def test_unread_count_rejects_other_child():
    uid, h = _seed_child(prefix="u6")
    other_uid, _oh = _seed_child(prefix="u6b")
    r = _client().get(f"/api/expression/unread-count?user_id={other_uid}", headers=h)
    assert r.status_code == 403
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_expression.py -k unread -v`

Expected: FAIL，404（端点不存在）

- [ ] **Step 3: 实现**

在 `backend/app/routers/expression.py` 追加。先看文件顶部 import，需要补 `ChildConfig` 与 `datetime`（`datetime` 可能已由其他代码引入）。

```python
SEEN_AT_KEY = "expression_seen_at"


def _get_seen_at(db: Session, user_id: int) -> datetime | None:
    row = db.query(ChildConfig).filter_by(user_id=user_id, key=SEEN_AT_KEY).first()
    if row is None or not row.value:
        return None
    try:
        return datetime.fromisoformat(row.value)
    except ValueError:
        return None


class SeenReq(BaseModel):
    user_id: int


@router.get("/unread-count")
def unread_count(user_id: int = Depends(resolve_target_user_id),
                 _auth: User = Depends(require_learning_user),
                 db: Session = Depends(get_db)):
    """孩子讲了几条家长还没看过的。不判定内容，只数条数。"""
    _require_grade(user_id, db)
    q = db.query(ExpressionNote).filter_by(user_id=user_id)
    seen_at = _get_seen_at(db, user_id)
    if seen_at is not None:
        q = q.filter(ExpressionNote.created_at > seen_at)
    return {"count": q.count()}


@router.post("/mark-seen")
def mark_seen(req: SeenReq, user: User = Depends(require_learning_user),
              db: Session = Depends(get_db)):
    """把「家长看到哪儿了」推到当前时刻。单调：不会往回退。"""
    ensure_user_access(user, req.user_id, db)
    _require_grade(req.user_id, db)
    now = datetime.utcnow()
    row = db.query(ChildConfig).filter_by(
        user_id=req.user_id, key=SEEN_AT_KEY).first()
    if row is None:
        db.add(ChildConfig(user_id=req.user_id, key=SEEN_AT_KEY,
                           value=now.isoformat()))
    else:
        prev = None
        try:
            prev = datetime.fromisoformat(row.value) if row.value else None
        except ValueError:
            prev = None
        if prev is None or now > prev:
            row.value = now.isoformat()
    db.commit()
    return {"ok": True, "seen_at": now.isoformat()}
```

**注意 import**：文件顶部需要 `from ..models import ... ChildConfig`（加进现有的 models import 行），以及 `from datetime import datetime`（如果还没引入）。

- [ ] **Step 4: 运行确认通过**

Run: `cd backend && python -m pytest tests/test_expression.py -v`
Expected: 全部 PASS（原 28 + 新 6 = 34）

再确认没影响别的：
Run: `cd backend && python -m pytest tests/test_expression.py tests/test_fk_cleanup.py tests/test_models.py -v`

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/expression.py backend/tests/test_expression.py
git commit -m "feat(expression): 未读数与已读标记（家长端红点用）"
```

---

## Task 2: 家长端红点

**Files:**
- Modify: `parent-web/app.js`

- [ ] **Step 1: 加状态与加载函数**

在 `let expressionNotes = [];` 附近加：

```javascript
let expressionUnread = 0;
async function loadExpressionUnread(){
  if(!uid){ expressionUnread = 0; return 0; }
  const u = uid;
  try{
    const r = await api(`/api/expression/unread-count?user_id=${u}`);
    if(u !== uid) return expressionUnread;
    expressionUnread = Number(r.count) || 0;
  }catch(_){
    if(u === uid) expressionUnread = 0;
  }
  return expressionUnread;
}
async function markExpressionSeen(){
  if(!uid) return;
  try{ await api('/api/expression/mark-seen', {method:'POST', body:{user_id: uid}}); }
  catch(_){ return; }
  expressionUnread = 0;
  renderNav();
}
```

**注意 `if(u !== uid)` 守卫**——与 `loadExpressionNotes` 保持一致，防止切换孩子的竞态。

- [ ] **Step 2: 导航上加红点**

把 `renderNav()` 改成：

```javascript
function renderNav(){
  document.getElementById('nav').innerHTML = PARENT_TABS.map(([label,ic])=>{
    const dot = (label==='报告' && expressionUnread>0)
      ? `<span class="nav-dot" title="孩子又讲了 ${expressionUnread} 条">${expressionUnread}</span>`
      : '';
    return `<button class="nav-item ${parentTab===label?'active':''}" onclick="setParentTab('${label}')">${icon(ic,19)}${label}${dot}</button>`;
  }).join('');
}
```

- [ ] **Step 3: 加样式**

在 `parent-web/index.html` 的样式区（跟着 `.nav-item` 的样式，找现有位置）加：

```css
.nav-dot{
  margin-left:6px;min-width:16px;height:16px;padding:0 4px;border-radius:8px;
  background:#d64545;color:#fff;font-size:10px;font-weight:700;line-height:16px;
  text-align:center;display:inline-block;
}
```

- [ ] **Step 4: 进报告页时标记已读**

在 `setParentTab` 里，`parentTab=t;` 之后、`renderNav()` 之前加：

```javascript
  if(t==='报告'){ markExpressionSeen(); }
```

并在报告页的加载 `Promise.all` 里**不**加 `loadExpressionUnread`（因为进去就要清零了）。

**但离开报告页时要更新红点**——在 `reloadChildData()` 和 `init()` 里加 `loadExpressionUnread()`：

在 `init()` 的 `try{ await reloadChildData(); }catch(e){}` 之后加：

```javascript
  try{ await loadExpressionUnread(); }catch(e){}
  renderNav();
```

（`renderNav()` 在 `init()` 开头已经调过一次，这里再调一次让红点更新。）

在 `switchChild()` 的 `expressionNotes = [];` 那行旁边加 `expressionUnread = 0;`，并在 `reloadChildData()` 之后重新拉一次：

```javascript
  try{ await loadExpressionUnread(); }catch(e){}
```

- [ ] **Step 5: 验证**

```bash
node --check parent-web/app.js
```

Expected: 通过

然后手动验证（后端已在 8010 运行，需是新代码）：

1. 用孩子账号在 `http://127.0.0.1:8082` 写一条讲解
2. 家长端 `http://127.0.0.1:8767` 刷新 → **「报告」上出现数字 1**
3. 点「报告」→ 红点消失
4. 孩子再写一条 → 家长端刷新 → 红点变 1

- [ ] **Step 6: 提交**

```bash
git add parent-web/app.js parent-web/index.html
git commit -m "feat(parent-web): 报告 Tab 显示孩子讲解的未读数"
```

---

## 自检记录

**Spec 覆盖**

| 要求 | 任务 |
| --- | --- |
| 不判定、不评价 | 红点只显示条数，无任何质量评价 |
| 不新增表 | 复用 `ChildConfig` |
| 红点不刷屏 | `mark-seen` 在进报告页时调用，`expressionUnread` 清零 |
| 失败不影响报告页 | `loadExpressionUnread` / `markExpressionSeen` 都有 try/catch，失败只是没红点 |
| 切换孩子不串数据 | `if(u !== uid)` 守卫 + `switchChild` 清零 |

**Placeholder 扫描**：无 TBD；代码步骤都有完整代码。

**类型一致性**：
- `ChildConfig.value` 是 `LongText`，存 ISO 字符串，`fromisoformat` 往返一致。
- `unread-count` 返回 `{count: int}`，前端 `Number(r.count) || 0`。
- `mark-seen` 接收 `{user_id}`，返回 `{ok, seen_at}`。

**已知取舍**：
- 用时间戳而非逐条已读：删除旧笔记时语义仍然正确（时间不回退）。
- `mark-seen` 单调：即使时钟回拨或并发，也不会把 seen_at 改小。
