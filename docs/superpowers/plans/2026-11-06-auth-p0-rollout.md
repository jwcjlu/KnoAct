# P0 API 鉴权收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成审计 spec P0（SEC-01/02/03 核心、ID-04）：所有敏感 API 必须 Bearer 登录，且 `user_id` 与 token 身份一致（或家长代查孩子、admin 全局）。

**Architecture:** 扩展 `core/access.py`：`resolve_target_user_id`（已有）、新增 `require_parent_or_admin`（管理类）、`require_authenticated`（仅登录）；学习类继续 `require_learning_user` + resolve。按 router 分批改签名，测试用 `conftest.auth_headers` / `make_account` / `bound_child_headers`。

**Tech Stack:** FastAPI Depends、现有 JWT、`pytest` 全量回归。

**Spec:** `docs/superpowers/specs/2026-11-06-product-architecture-audit-design.md`（第 3、6 节 P0）

---

## 文件结构

| 路径 | 变更 |
|------|------|
| `backend/app/core/access.py` | 新增 `require_parent_or_admin`、`optional: assert_resource_owner` |
| `backend/app/core/deps.py` | 可选：`get_current_user_optional` 仅用于 health（不用） |
| `backend/app/routers/*.py` | 各 router 加 Depends（见下表） |
| `backend/tests/test_access_control.py` | **新建** 越权矩阵测试 |
| `backend/tests/conftest.py` | 扩展 `bound_child_headers`、`parent_headers` 辅助 |
| 各现有 `test_*.py` | 补 Bearer 头（批量） |
| `README.md` / `AGENTS.md` | JWT_SECRET、admin 初始密码部署说明（ID-04） |
| `frontend/app.js` | **最小**：登录页提示已废弃（P1 可跳转）；本 plan 仅保证 API 401 后不误用 |

---

## 端点分类（实施清单）

| 类别 | Routers | 依赖组合 |
|------|---------|----------|
| **学习-孩子** | points, mistakes, mastery, math, progress, learning（剩余）, quiz（submit/generate 孩子侧） | `require_learning_user` + `resolve_target_user_id` |
| **学习-混合** | tasks（approve/confirm/generate） | parent: `require_role("parent")` + 孩子归属；child: learning |
| **家长管理** | pdf, goals, questions（写）, knowledge（写）, users GET, config GET 写已保护 | `require_role("parent","admin")` + 资源 scope |
| **只读公开** | tts synthesize, render_media | `get_current_user`（任意登录用户）或 rate limit（SEC-03 简化为需登录） |
| **Agent** | notes `/api/ask`, `/api/ask/stream` | `require_learning_user` + body 内 user/lesson 归属校验 |
| **屏幕时间** | screen_time | parent 管孩子 groups；child report 仅 self |
| **Buckets** | buckets | resolve child user_id |

---

## Task 1: 基础设施 + 越权测试骨架

**Files:**
- Modify: `backend/app/core/access.py`
- Create: `backend/tests/test_access_control.py`
- Modify: `backend/tests/conftest.py`

- [x] **Step 1: 写失败测试 — 两孩子互访 points 403**

```python
# test_access_control.py
def test_child_cannot_read_other_balance(setup_db, client, db):
    parent = make_account(db, "p1", "parent")
    a = make_account(db, "kid_a", "child", parent=parent)
    b = make_account(db, "kid_b", "child", parent=parent)
    r = client.get(f"/api/points/balance?user_id={b.id}", headers=auth_headers(a))
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "forbidden"
```

- [x] **Step 2: 在 access.py 增加文档字符串；确认 resolve 对 parent 代查 b 时 parent token 200（预备测试）**

- [x] **Step 3: conftest 增加 `bound_pair(db)` → parent, child, headers**

- [x] **Step 4: pytest test_access_control.py -v（FAIL）**

- [ ] **Step 5: commit** `test(auth): access control matrix skeleton`

---

## Task 2: points + mistakes + mastery + goals（读写在 user_id 上）

**Files:**
- Modify: `backend/app/routers/points.py`, `mistakes.py`, `mastery.py`, `goals.py`
- Modify: `backend/tests/test_mistakes.py`, 等相关测试

- [x] **Step 1:** 每个 GET/POST 加 `user: require_learning_user`（或 parent 读孩子用 `get_current_user` + resolve）
- [x] **Step 2:** `user_id` 参数改为 `Depends(resolve_target_user_id)`
- [ ] **Step 3:** test_access_control 每 router 1 条越权 + 1 条 parent 代查 OK
- [x] **Step 4:** `pytest tests/test_mistakes.py tests/test_access_control.py -q`
- [ ] **Step 5: commit** `feat(auth): protect points mistakes mastery goals`

---

## Task 3: learning 剩余端点 + math + progress

**Files:**
- Modify: `backend/app/routers/learning.py`, `math.py`, `progress.py`

- [x] **Step 1:** 已保护的 dictation/words、listening 补 `resolve_target_user_id`
- [x] **Step 2:** grade/complete/assignment/review 等全部 learning + math；阅读材料与数学材料按教材绑定校验（`ensure_lesson_document_access`）
- [x] **Step 3:** 更新 `test_learning.py`, `test_math*.py` 带 token / 绑定 `UserDocument`
- [ ] **Step 4: commit**

---

## Task 4: tasks 全端点 + home 已 OK 复核

**Files:**
- Modify: `backend/app/routers/tasks.py`

- [x] **Step 1:** list/submit 加 `resolve_target_user_id`（当前仅 learning_user）
- [x] **Step 2:** approve/confirm/generate/knowledge-review → parent + 孩子 `parent_id` 校验
- [x] **Step 3:** test_tasks_router 全绿
- [ ] **Step 4: commit**

---

## Task 5: quiz + notes(ask) + annotations

**Files:**
- Modify: `quiz.py`, `notes.py`, `annotations.py`

- [x] **Step 1:** quiz generate/submit — learning_user + resolve + 教材绑定校验
- [x] **Step 2:** ask/ask_stream — learning_user；教材课经 `UserDocument` 校验
- [x] **Step 3:** annotations — Bearer + `ensure_user_access` + 教材绑定；notes 列表支持 `user_id` 查询
- [ ] **Step 4: commit**

---

## Task 6: SEC-02 家长资源 pdf + questions + knowledge 写

**Files:**
- Modify: `pdf.py`, `questions.py`, `knowledge.py`, `users.py` GET

- [x] **Step 1:** pdf upload/bind/extract → `require_role("parent","admin")`
- [x] **Step 2:** questions/knowledge 写操作 parent/admin；knowledge 列表/删改按已绑定教材范围
- [x] **Step 3:** `GET /api/users` 需 parent/admin，parent 只能查 role=child&parent_id=self
- [x] **Step 4:** test_pdf_router, test_users 更新
- [ ] **Step 5: commit**

---

## Task 7: screen_time + buckets

**Files:**
- Modify: `screen_time.py`, `buckets.py`

- [x] **Step 1:** report — child self；groups/usage — parent 代查 resolve
- [x] **Step 2:** buckets GET — resolve user_id
- [ ] **Step 3: commit**

---

## Task 8: tts + render（SEC-03 简版）

**Files:**
- Modify: `tts_router.py`, `render.py`

- [x] **Step 1:** synthesize / render_status 需登录；`/render_media` 同步需 Bearer
- [ ] **Step 2:** 匿名 401 测试（TTS 已有；render 媒体代理可选手测）
- [ ] **Step 3: commit**

---

## Task 9: 全量 pytest + 前端 token 冒烟

**Files:**
- 所有 failing tests 补 `auth_headers`
- Spot-check: `student-app` 已带 Bearer；`parent-web` pdf 上传带 token

- [x] **Step 1:** `cd backend && python -m pytest -q` 全绿（本批 360 passed）
- [ ] **Step 2:** 手动：student 登录 → home/points/wrongbook 200
- [ ] **Step 3:** 手动：parent 登录 → pdf 列表 200；无 token 401
- [ ] **Step 4: commit** `test: fix bearer headers across suite`

---

## Task 10: ID-04 部署文档

**Files:**
- Modify: `AGENTS.md`, `README.md`, `.env.example`（若有）

- [x] **Step 1:** 文档：`JWT_SECRET` 必填（生产）、`ADMIN_INITIAL_PASSWORD` 首次登录改密
- [x] **Step 2:** `main.py` 启动时若未设置强 JWT 或使用默认 admin 初始密码 → log warning（pytest 跳过）
- [x] **Step 3: commit** `docs: production auth env requirements`

---

## 验收（与审计 spec 对齐）

- [x] 两 child token 互访 `user_id` → **403 forbidden**（`test_access_control`）
- [x] parent token 访问 `user_id=旗下孩子` → **200**（`test_access_control`）
- [ ] 无 Bearer → **401**（除 `/api/auth/*` 注册登录、/health）
- [x] `pytest` 全绿
- [ ] Flutter `flutter test` 无回归（API 401 时 client 行为已测）

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| 旧 frontend 无 token 全挂 | P0 预期；P1 CLI-02 跳转或删 frontend |
| 测试量大 | 按 Task 分批 commit，每批 pytest |
| annotations 归属复杂 | Task 5 最小 authenticated；迭代加 lesson 链校验 |

---

## 执行方式

Plan 路径：`docs/superpowers/plans/2026-11-06-auth-p0-rollout.md`

**1. Subagent-Driven** — 每 Task 一子 agent  
**2. Inline** — 本会话连续 Task 1–10

P0 完成后，再开 **`2026-11-06-product-alignment`** plan（PRD-01、CLI-01/02）。
