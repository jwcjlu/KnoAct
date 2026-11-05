# 完整账号体系 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用唯一 `login_name` + 密码/短信验证码登录、JWT 会话、资料字段、家庭绑定与受限模式，以及运营 Admin 代建用户，替换「姓名即登录、无鉴权」模型。

**Architecture:** 在 `User` 上扩展凭证与资料列；新增 `OtpCode` / `RefreshToken` / 家庭绑定表；`services/security.py`（bcrypt + JWT）与 `services/sms.py`（fake 可测）；`core/deps.py` 提供 `get_current_user`；auth/family/admin 路由 P0 鉴权；学习类 API 加 `parent_required` 与 P1 `user_id` 归属校验；三端带 Bearer token。

**Tech Stack:** FastAPI, SQLAlchemy, PyJWT, passlib[bcrypt], Flutter (Riverpod/dio), parent-web/admin-web 原生 JS。

**Spec:** `docs/superpowers/specs/2026-11-05-account-system-design.md`

---

## 文件结构

**后端（新建）**

| 路径 | 职责 |
|------|------|
| `backend/app/core/deps.py` | Bearer 解析、`get_current_user`、`require_role` |
| `backend/app/core/access.py` | `assert_child_access`、`parent_required` 装饰/依赖 |
| `backend/app/services/security.py` | 密码 hash/verify、JWT 签发/校验 |
| `backend/app/services/sms.py` | `SmsProvider` fake + 预留阿里云 |
| `backend/app/services/otp.py` | 生成/校验 OTP、限流 |
| `backend/app/services/user_factory.py` | `create_user` / `create_child_user`（含 `ensure_bucket`） |
| `backend/app/routers/family.py` | 邀请码、绑定请求 |
| `backend/app/routers/admin_users.py` | `/api/admin/*` |

**后端（修改）**

| 路径 | 职责 |
|------|------|
| `backend/app/models.py` | User 新字段 + OtpCode/RefreshToken/Family* 表 |
| `backend/app/seed.py` | 幂等迁移、`name`→`login_name`、seed admin |
| `backend/app/routers/auth.py` | register/login/otp/me/profile |
| `backend/app/routers/users.py` | 创建孩子改走 factory；列表返回 login_name/display_name |
| `backend/app/main.py` | include family + admin routers |
| `backend/requirements.txt` | PyJWT, passlib[bcrypt] |
| `backend/tests/test_auth.py` | 重写/扩展 |
| `backend/tests/test_family.py` | 新建 |
| `backend/tests/test_admin_users.py` | 新建 |

**Flutter student-app**

| 路径 | 职责 |
|------|------|
| `lib/features/auth/` | 注册、密码/OTP 登录、token 存储 |
| `lib/features/profile/` | 资料编辑 |
| `lib/features/family/` | 绑定家长（受限模式） |
| `lib/core/api_client.dart` | Authorization 头、401 处理 |
| `lib/core/router.dart` | 受限路由守卫 |

**Web**

| 路径 | 职责 |
|------|------|
| `parent-web/app.js` | 注册/登录/token、邀请与绑定请求 |
| `admin-web/index.html`, `admin-web/app.js` | 运营后台 MVP |

**部署（可选 Task 末）**

| 路径 | 职责 |
|------|------|
| `docker-compose.yml` | admin-web 静态服务端口 |

---

## Task 1: 依赖与 security 基础

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/security.py`
- Test: `backend/tests/test_security.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_security.py
from app.services.security import hash_password, verify_password, create_access_token, decode_access_token

def test_password_hash_roundtrip():
    h = hash_password("abc12345")
    assert verify_password("abc12345", h)
    assert not verify_password("wrong", h)

def test_jwt_roundtrip():
    token = create_access_token({"sub": 42})
    payload = decode_access_token(token)
    assert payload["sub"] == 42
```

- [ ] **Step 2: 安装依赖并跑测试（应 FAIL）**

Run: `cd backend && pip install -r requirements.txt && python -m pytest tests/test_security.py -v`

- [ ] **Step 3: 实现 `security.py`**

```python
import os, time, jwt
from passlib.context import CryptContext

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET = os.environ.get("JWT_SECRET", "dev-change-me")
ACCESS_TTL = int(os.environ.get("JWT_ACCESS_TTL", "3600"))

def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_access_token(claims: dict, ttl: int = ACCESS_TTL) -> str:
    payload = {**claims, "exp": int(time.time()) + ttl}
    return jwt.encode(payload, SECRET, algorithm="HS256")

def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])
```

`requirements.txt` 追加：
```
PyJWT==2.10.1
passlib[bcrypt]==1.7.4
```

- [ ] **Step 4: 测试 PASS 后提交**

```bash
git add backend/requirements.txt backend/app/services/security.py backend/tests/test_security.py
git commit -m "feat(auth): password hashing and JWT helpers"
```

---

## Task 2: User 模型扩展 + 数据库迁移

**Files:**
- Modify: `backend/app/models.py`, `backend/app/seed.py`
- Test: `backend/tests/test_auth_migration.py`

- [ ] **Step 1: 写迁移测试**

```python
# backend/tests/test_auth_migration.py
def test_users_have_login_name_after_seed(setup_db, db):
    from app.models import User
    u = db.query(User).first()
    assert u is not None
    assert getattr(u, "login_name", None)
```

- [ ] **Step 2: 在 `User` 增加字段**

保留 `name` 列一期兼容（读写时同步 `display_name`），新增：
`login_name`, `password_hash`, `display_name`, `birth_month`, `gender`, `interests`,
`phone`, `email`, `phone_verified`, `email_verified`（Boolean default False）。

`role` 文档注释增加 `admin`。

- [ ] **Step 3: `_migrate_account_columns()` in seed.py**

幂等 `ALTER TABLE users ADD COLUMN ...`；SQLite/MySQL 分支与现有 `_migrate_*` 一致。

迁移数据：`UPDATE users SET login_name = name, display_name = name WHERE login_name IS NULL`；
重复 `login_name` 加 `_<id>` 后缀；默认 `password_hash` 空表示「须重置」（或 seed 设默认密码 `ChangeMe123`）。

- [ ] **Step 4: seed admin 用户**

`login_name=admin`, `role=admin`, 密码来自 env `ADMIN_INITIAL_PASSWORD` 或文档固定 dev 值。

- [ ] **Step 5: pytest + commit**

Run: `cd backend && python -m pytest tests/test_auth_migration.py tests/test_seed.py -q`

```bash
git commit -m "feat(auth): User account columns and login_name migration"
```

---

## Task 3: OtpCode + RefreshToken + 家庭表

**Files:**
- Modify: `backend/app/models.py`, `backend/app/seed.py`
- Create: `backend/app/services/otp.py`, `backend/app/services/sms.py`
- Test: `backend/tests/test_otp.py`

- [ ] **Step 1: 模型**

`OtpCode`, `RefreshToken`, `FamilyInvite`, `FamilyBindRequest`（字段见 spec）。

- [ ] **Step 2: fake SMS + OTP 服务**

`send_sms(phone, text)` 在测试 env 写日志；`issue_otp(db, user_id, purpose)` 返回 6 位码（测试固定 `123456` 当 `SMS_FAKE_CODE=1`）。

- [ ] **Step 3: 测试 OTP verify + 过期**

- [ ] **Step 4: commit**

```bash
git commit -m "feat(auth): OTP and refresh token models with fake SMS"
```

---

## Task 4: `user_factory` + 重写 `auth` 路由

**Files:**
- Create: `backend/app/services/user_factory.py`
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/tests/test_auth.py`（删除「按名自动建号」期望）

- [ ] **Step 1: 失败测试 — 注册唯一性与登录**

```python
def test_register_unique_login_name(client):
    r = client.post("/api/auth/register", json={"login_name": "kid01", "password": "pass1234", "role": "child"})
    assert r.status_code == 200
    assert "access_token" in r.json()
    r2 = client.post("/api/auth/register", json={"login_name": "kid01", "password": "pass1234", "role": "child"})
    assert r2.status_code == 409

def test_login_password(client):
    client.post("/api/auth/register", json={"login_name": "kid02", "password": "pass1234", "role": "child"})
    r = client.post("/api/auth/login", json={"login_name": "kid02", "password": "pass1234"})
    assert r.status_code == 200
    assert r.json()["access_token"]
```

- [ ] **Step 2: 实现 register/login/logout/refresh/me/profile**

校验 `login_name` 正则 `^[a-zA-Z0-9_]{3,32}$`；密码 ≥8 且含字母数字。

删除旧逻辑：`if not user: User(name=req.name...)`。保留 archived → 403。

环境变量 `KNOACT_LEGACY_NAME_LOGIN=1` 时短期兼容旧 `{name}` login（映射 login_name=name），默认 **0**。

- [ ] **Step 3: OTP send/login 测试**

需先 `PATCH /me/credentials` 绑手机并 verify（或测试里直接写库 `phone_verified=True`）。

- [ ] **Step 4: pytest tests/test_auth.py -q && commit**

---

## Task 5: `core/deps.py` 鉴权依赖

**Files:**
- Create: `backend/app/core/deps.py`, `backend/app/core/access.py`
- Test: `backend/tests/test_deps.py`

- [ ] **Step 1: `get_current_user` 从 Authorization Bearer 取 sub=user_id**

- [ ] **Step 2: `require_role(*roles)`**

- [ ] **Step 3: `resolve_target_user_id(current, requested_user_id)`**

规则：child 只能 self；parent 可访问 `parent_id==current.id` 的孩子；admin 全部。

- [ ] **Step 4: commit**

---

## Task 6: 家庭绑定 `/api/family`

**Files:**
- Create: `backend/app/routers/family.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_family.py`

- [ ] **Step 1: 测试邀请码绑定**

家长 register → invite → 孩子 register → bind → 孩子 `parent_id` 非空，`GET /me` 的 `parent_bound=true`。

- [ ] **Step 2: 测试 bind request 审批流**

- [ ] **Step 3: 实现路由（均需 Bearer + role）**

- [ ] **Step 4: commit**

---

## Task 7: 受限模式 `parent_required`

**Files:**
- Modify: `backend/app/core/access.py`
- Modify: `backend/app/routers/home.py`, `backend/app/routers/tasks.py`, `backend/app/routers/learning.py`（代表学习入口）
- Test: `backend/tests/test_parent_required.py`

- [ ] **Step 1: 测试未绑定孩子访问 home snapshot 403**

```python
def test_unbound_child_home_forbidden(client, db):
    # register child, token, GET /api/home/snapshot?user_id=X without parent_id
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "parent_required"
```

- [ ] **Step 2: 在以上 router 加 Depends：child 且无 parent_id → 403**

family/bind 与 auth/me 不受限。

- [ ] **Step 3: P1 — 同一 router 校验 token user_id 与 query user_id（家长代查除外）**

- [ ] **Step 4: commit**

---

## Task 8: Admin API `/api/admin`

**Files:**
- Create: `backend/app/routers/admin_users.py`
- Modify: `backend/app/main.py`, `backend/app/routers/users.py`
- Test: `backend/tests/test_admin_users.py`

- [ ] **Step 1: 非 admin 访问 403**

- [ ] **Step 2: admin 创建 child + parent_id + ensure_bucket**

复用 `user_factory.create_child_user`.

- [ ] **Step 3: 列表/搜索/重置密码/改 parent_id/archive**

- [ ] **Step 4: commit**

---

## Task 9: 保护 config 写接口 + children 路由

**Files:**
- Modify: `backend/app/routers/config_router.py`, `backend/app/routers/users.py`
- Test: 扩展 `backend/tests/test_config.py`、 `test_children_api.py`

- [ ] **Step 1: POST config 需 parent 或 admin token**

- [ ] **Step 2: POST /api/children 需 parent token 且 parent_id 匹配 body**

Admin 代建走 `/api/admin/users` 而非公开 children POST。

- [ ] **Step 3: commit**

---

## Task 10: student-app 认证与资料

**Files:**
- Modify: `lib/core/api_client.dart`, `lib/features/auth/*`, `lib/core/router.dart`
- Create: `lib/features/family/bind_parent_page.dart`, `lib/features/profile/profile_edit_page.dart`
- Test: `test/features/auth/*`

- [ ] **Step 1: Session 存 access_token + login_name + user_id**

- [ ] **Step 2: ApiClient 拦截器加 Bearer；401 → logout**

- [ ] **Step 3: LoginPage：密码登录 + OTP 入口；RegisterPage**

- [ ] **Step 4: router — 未登录 /login；已登录无 parent_bound → BindParentPage；否则 Shell**

- [ ] **Step 5: Profile 编辑调 PATCH /me/profile**

- [ ] **Step 6: flutter analyze && flutter test && commit**

Run: `cd student-app && flutter analyze && flutter test`

---

## Task 11: parent-web 账号体系

**Files:**
- Modify: `parent-web/app.js`, `parent-web/index.html`（如需登录 UI 容器）

- [ ] **Step 1: api() 读 localStorage token 加 Authorization**

- [ ] **Step 2: 替换 renderLogin — register/login 表单（login_name + password）**

- [ ] **Step 3: 启动时 GET /api/me 校验 token，取 parent id**

- [ ] **Step 4: 设置页 — 生成邀请码、绑定请求列表 approve/reject**

- [ ] **Step 5: showAddChild 改为说明「请孩子在 App 注册后输入邀请码」或保留调 admin（可选）**

- [ ] **Step 6: 手动浏览器验证 + commit**

---

## Task 12: admin-web MVP

**Files:**
- Create: `admin-web/index.html`, `admin-web/app.js`, `admin-web/config.js`（可选）
- Modify: `docker-compose.yml`（加服务 `:8768` 类似 parent-web）

- [ ] **Step 1: 登录页 admin login_name + password**

- [ ] **Step 2: 用户表格 — GET /api/admin/users?role=**

- [ ] **Step 3: 创建用户表单（child/parent, login_name, password, parent_id, grade）**

- [ ] **Step 4: 行内操作 — 重置密码、归档、编辑 parent_id**

- [ ] **Step 5: commit + README/AGENTS 一句端口说明**

---

## Task 13: P1 批量 router 归属校验（可分子 PR）

**Files:** 所有带 `user_id` query/body 的 routers（`mistakes`, `goals`, `points`, `buckets`, `screen_time`, …）

- [ ] **Step 1: 列出 `grep user_id backend/app/routers` 清单**

- [ ] **Step 2: 每个端点加 `resolve_target_user_id` 或 Depends**

- [ ] **Step 3: 为每个领域补 1 个越权测试**

- [ ] **Step 4: full pytest + commit**

Run: `cd backend && python -m pytest -q`

---

## Task 14: 文档与 AGENTS 更新

**Files:**
- Modify: `AGENTS.md`（认证段落）
- Modify: `docs/superpowers/specs/2026-11-05-account-system-design.md` 状态 → 已实施

- [ ] **Step 1: 记录 dev 默认账号、JWT_SECRET、关闭 legacy login**

- [ ] **Step 2: commit**

---

## 验收清单（与 spec 对齐）

- [ ] `login_name` 全局唯一
- [ ] 孩子未绑定家长时学习 API 返回 `parent_required`
- [ ] App 可改 display_name / birth_month / gender / interests
- [ ] 密码登录 + OTP 登录（已绑手机）
- [ ] Admin 代建学生并指定家长；家长端可见
- [ ] 越权访问他人 `user_id` 被拒绝（Task 13 完成）

---

## 风险与顺序

1. **先 Task 1–8** 再动 Flutter，避免前后端同时 breaking。
2. **legacy login 开关** 便于 parent-web 未改完前本地联调。
3. **MySQL docker** 与 SQLite 开发均跑迁移测试。
4. 旧测试大量用 `User(name=...)` — 逐步改为 `login_name` + factory helper `make_user()` in conftest。

---

## 执行方式

Plan 保存于 `docs/superpowers/plans/2026-11-05-account-system.md`。

**1. Subagent-Driven（推荐）** — 每 Task 派生子 agent，Task 间人工/主 agent 审查。

**2. Inline Execution** — 本会话按 Task 顺序执行，每 2–3 Task 设检查点。
