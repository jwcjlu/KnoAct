# 模型与服务配置层 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 KnoAct 扁平的 `ModelConfig` AI 配置改造成「7 个角色 + 可复用连接」的模型与服务配置层。

**Architecture:** 新增 `ModelConnection` / `ModelProfile` / `RoleBinding` 三张表，代码内维护 provider 注册表，统一经 `resolve(db, role)` 解析出最终配置。现有 `get_provider()` / `get_tts()` 签名不变、内部改读 `resolve()`，因此所有调用方零改动。老键保留为降级来源，新表为空时行为与改造前完全一致。

**Tech Stack:** FastAPI + SQLAlchemy 2.0（`Mapped` / `mapped_column`）+ SQLite + pytest；前端单文件原生 JS（`frontend/app.js`，无框架）。

**设计文档:** `docs/superpowers/specs/2026-10-26-model-service-config-design.md`

---

## 文件结构

| 文件 | 职责 | 动作 |
|---|---|---|
| `backend/app/models.py` | 三张新表 | 修改（追加） |
| `backend/app/services/provider_registry.py` | Provider 常量注册表 | 创建 |
| `backend/app/services/model_config.py` | `resolve()` / 掩码 / 目录读写 | 创建 |
| `backend/app/routers/config_router.py` | catalog / probe / test 接口 | 修改 |
| `backend/app/services/ai.py` | `get_provider` / `ocr_image` 改读 `resolve` | 修改 |
| `backend/app/services/tts.py` | `get_tts` 改读 `resolve` | 修改 |
| `backend/migrate_model_catalog.py` | 老键迁移 + `--verify` | 创建 |
| `frontend/app.js` | 设置页重构 | 修改 |
| `backend/tests/test_model_config.py` | 解析 / 掩码测试 | 创建 |
| `backend/tests/test_config_catalog.py` | 接口测试 | 创建 |

**测试运行方式**（工作目录必须是 `backend/`）：

```bash
cd backend && python -m pytest tests/test_model_config.py -q
```

**注意**：本仓库的 Bash `python` 是 `Python310`（有依赖）；不要用终端面板的 conda python（缺 sqlalchemy）。

---

## Task 1: 三张新表

**Files:**
- Modify: `backend/app/models.py`（在文件末尾追加）

- [ ] **Step 1: 追加三个模型**

在 `backend/app/models.py` 末尾（`Task` 类之后）追加：

```python
class ModelConnection(Base):
    """一套凭证 + 端点，可被多个角色复用。"""
    __tablename__ = "model_connections"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(32))     # openai|deepseek|glm|minimax|xunfei|fake
    name: Mapped[str] = mapped_column(String(128), default="")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    api_key: Mapped[str] = mapped_column(String(512), default="")
    extra_headers: Mapped[str] = mapped_column(TextCls, default="")  # JSON 文本
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelProfile(Base):
    """某角色下的一档模型选择。"""
    __tablename__ = "model_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(16))          # llm|task|embedding|search|tts|stt|imagegen
    connection_id: Mapped[int] = mapped_column(ForeignKey("model_connections.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    name: Mapped[str] = mapped_column(String(128), default="")
    options: Mapped[str] = mapped_column(TextCls, default="")  # JSON 文本
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RoleBinding(Base):
    """角色 → 当前启用哪一档。主键即 role。"""
    __tablename__ = "role_bindings"
    role: Mapped[str] = mapped_column(String(16), primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("model_profiles.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="inherit")  # 仅 task 使用
```

- [ ] **Step 2: 验证建表**

```bash
cd backend && python -c "
import os; os.environ['DATABASE_URL']='sqlite:///./test_models_tmp.db'
from app.database import Base, engine
from app.models import ModelConnection, ModelProfile, RoleBinding
Base.metadata.create_all(bind=engine)
print('tables ok')
import pathlib; pathlib.Path('test_models_tmp.db').unlink(missing_ok=True)
"
```

Expected: 打印 `tables ok`，无异常。

- [ ] **Step 3: 跑现有测试确认没打破**

```bash
cd backend && python -m pytest tests/test_models.py -q
```

Expected: 全部 PASS。

- [ ] **Step 4: 提交**

```bash
git add backend/app/models.py
git commit -m "feat: 模型与服务三张表（连接/档位/绑定）"
```

---

## Task 2: Provider 注册表与 resolve()

**Files:**
- Create: `backend/app/services/provider_registry.py`
- Create: `backend/app/services/model_config.py`
- Test: `backend/tests/test_model_config.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_model_config.py`：

```python
import pytest

from app.database import SessionLocal
from app.models import ModelConfig, ModelConnection, ModelProfile, RoleBinding
from app.services.model_config import resolve


def _clear(db):
    for m in (RoleBinding, ModelProfile, ModelConnection, ModelConfig):
        db.query(m).delete()
    db.commit()


def test_resolve_defaults_to_fake_when_nothing_configured():
    db = SessionLocal()
    _clear(db)
    r = resolve(db, "llm")
    assert r.provider == "fake"
    assert r.source == "default"
    db.close()


def test_resolve_reads_legacy_keys():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_model", value="deepseek-chat"))
    db.add(ModelConfig(key="ai_key", value="sk-legacy"))
    db.add(ModelConfig(key="ai_base_url", value=""))
    db.commit()
    r = resolve(db, "llm")
    assert r.provider == "deepseek"
    assert r.model == "deepseek-chat"
    assert r.api_key == "sk-legacy"
    assert r.source == "legacy"
    db.close()


def test_resolve_prefers_binding_over_legacy():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_key", value="sk-legacy"))
    conn = ModelConnection(provider="openai", name="中转站",
                           base_url="https://x/v1", api_key="sk-new")
    db.add(conn); db.flush()
    prof = ModelProfile(role="llm", connection_id=conn.id, model="gpt-4o")
    db.add(prof); db.flush()
    db.add(RoleBinding(role="llm", profile_id=prof.id))
    db.commit()

    r = resolve(db, "llm")
    assert r.provider == "openai"
    assert r.model == "gpt-4o"
    assert r.api_key == "sk-new"
    assert r.base_url == "https://x/v1"
    assert r.source == "binding"
    db.close()


def test_task_inherits_llm_by_default():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_model", value="deepseek-chat"))
    db.commit()
    r = resolve(db, "task")
    assert r.model == "deepseek-chat"
    assert r.role == "task"
    db.close()


def test_task_reference_uses_own_profile():
    db = SessionLocal()
    _clear(db)
    conn = ModelConnection(provider="openai", name="c", api_key="sk-task")
    db.add(conn); db.flush()
    prof = ModelProfile(role="task", connection_id=conn.id, model="gpt-4o-mini")
    db.add(prof); db.flush()
    db.add(RoleBinding(role="task", profile_id=prof.id, mode="reference"))
    db.commit()
    r = resolve(db, "task")
    assert r.model == "gpt-4o-mini"
    assert r.source == "binding"
    db.close()


def test_resolve_tts_legacy_keys():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="tts_provider", value="minimax"))
    db.add(ModelConfig(key="tts_model", value="speech-01-turbo"))
    db.add(ModelConfig(key="tts_key", value="mm-key"))
    db.add(ModelConfig(key="tts_voice", value="male-qn-qingse"))
    db.commit()
    r = resolve(db, "tts")
    assert r.provider == "minimax"
    assert r.model == "speech-01-turbo"
    assert r.options.get("voice") == "male-qn-qingse"
    db.close()


def test_llm_options_carry_vision_model_from_legacy():
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="openai"))
    db.add(ModelConfig(key="vision_model", value="qwen3-vl-plus"))
    db.commit()
    r = resolve(db, "llm")
    assert r.options.get("vision_model") == "qwen3-vl-plus"
    db.close()
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd backend && python -m pytest tests/test_model_config.py -q
```

Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.model_config'`

- [ ] **Step 3: 创建注册表**

创建 `backend/app/services/provider_registry.py`：

```python
"""Provider 白名单：代码常量，不是用户数据。"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSpec:
    id: str
    label: str
    needs_base_url: bool
    default_model: str = ""


OPENAI = ProviderSpec("openai", "中转站 / OpenAI 兼容", True, "gpt-4o")
DEEPSEEK = ProviderSpec("deepseek", "DeepSeek", False, "deepseek-chat")
GLM = ProviderSpec("glm", "GLM（智谱）", False, "glm-4-flash")
MINIMAX = ProviderSpec("minimax", "MiniMax", False, "speech-01-turbo")
XUNFEI = ProviderSpec("xunfei", "科大讯飞", False, "")
FAKE = ProviderSpec("fake", "本地兜底", False, "")

REGISTRY: dict[str, tuple[ProviderSpec, ...]] = {
    "llm":       (OPENAI, DEEPSEEK, GLM, FAKE),
    "task":      (OPENAI, DEEPSEEK, GLM, FAKE),
    "embedding": (OPENAI, FAKE),
    "search":    (OPENAI, FAKE),
    "tts":       (OPENAI, MINIMAX, XUNFEI, FAKE),
    "stt":       (OPENAI, FAKE),
    "imagegen":  (OPENAI, FAKE),
}

ROLES: tuple[str, ...] = tuple(REGISTRY.keys())


def find(provider_id: str, role: str = "llm") -> ProviderSpec:
    for spec in REGISTRY.get(role, REGISTRY["llm"]):
        if spec.id == provider_id:
            return spec
    return FAKE
```

- [ ] **Step 4: 实现 resolve()**

创建 `backend/app/services/model_config.py`：

```python
"""模型与服务：统一解析出口 + 密钥掩码。"""
import copy
import json
from dataclasses import dataclass, field, replace as dc_replace

from sqlalchemy.orm import Session

from ..models import ModelConfig, ModelConnection, ModelProfile, RoleBinding
from .provider_registry import find

MASK = "***"


@dataclass(frozen=True)
class Resolved:
    role: str
    provider: str
    model: str = ""
    base_url: str = ""
    api_key: str = ""
    extra_headers: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)
    source: str = "default"


def _json_dict(raw: str) -> dict:
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


def _cfg(db: Session) -> dict:
    return {r.key: r.value for r in db.query(ModelConfig).all()}


def _legacy(db: Session, role: str) -> Resolved | None:
    """老键降级。没有可用老键时返回 None。"""
    cfg = _cfg(db)
    if role == "llm":
        provider = cfg.get("ai_provider", "")
        if provider in ("", "fake"):
            return None
        return Resolved(
            role="llm",
            provider=provider,
            model=cfg.get("ai_model", ""),
            base_url=cfg.get("ai_base_url", ""),
            api_key=cfg.get("ai_key", ""),
            options={"vision_model": cfg["vision_model"]} if cfg.get("vision_model") else {},
            source="legacy",
        )
    if role == "tts":
        provider = cfg.get("tts_provider", "")
        if provider in ("", "fake"):
            return None
        opts = {}
        if cfg.get("tts_voice"):
            opts["voice"] = cfg["tts_voice"]
        if cfg.get("tts_speed"):
            opts["speed"] = cfg["tts_speed"]
        if cfg.get("tts_repeat"):
            opts["repeat"] = cfg["tts_repeat"]
        return Resolved(
            role="tts",
            provider=provider,
            model=cfg.get("tts_model", ""),
            base_url=cfg.get("tts_base_url", ""),
            api_key=cfg.get("tts_key", ""),
            options=opts,
            source="legacy",
        )
    if role == "task":
        return None  # task 另外处理：继承 llm
    # embedding / search / stt / imagegen 没有专属老键，退回 llm
    return None


def resolve(db: Session, role: str) -> Resolved:
    """三级降级：binding → legacy → default。绝不抛异常。"""
    binding = db.get(RoleBinding, role)

    # task 默认跟随 llm
    if role == "task" and (binding is None or binding.mode == "inherit"):
        inherited = resolve(db, "llm")
        return dc_replace(inherited, role="task", source=inherited.source)

    if binding is not None and binding.profile_id:
        prof = db.get(ModelProfile, binding.profile_id)
        if prof is not None:
            conn = db.get(ModelConnection, prof.connection_id) if prof.connection_id else None
            if conn is not None:
                return Resolved(
                    role=role,
                    provider=conn.provider,
                    model=prof.model or find(conn.provider, role).default_model,
                    base_url=conn.base_url,
                    api_key=conn.api_key,
                    extra_headers=_json_dict(conn.extra_headers),
                    options=_json_dict(prof.options),
                    source="binding",
                )

    legacy = _legacy(db, role)
    if legacy is not None:
        return legacy

    if role in ("embedding", "search", "stt", "imagegen"):
        inherited = resolve(db, "llm")
        if inherited.source != "default":
            return dc_replace(inherited, role=role, source="legacy")

    return Resolved(role=role, provider="fake", source="default")


def redact(obj):
    """深拷贝并把非空 api_key 换成 MASK。"""
    out = copy.deepcopy(obj)
    if isinstance(out, dict):
        if out.get("api_key"):
            out["api_key"] = MASK
        for v in out.values():
            if isinstance(v, (dict, list)):
                redact(v)
    elif isinstance(out, list):
        for item in out:
            redact(item)
    return out


def restore(old_rows: list[dict], new_rows: list[dict]) -> list[dict]:
    """密钥掩码往返：新值为 MASK 时沿用已存 key，否则按新值处理。

    - MASK + 有 id 且老行存在 → 用老 key
    - MASK + 无 id（新建）     → 视为空，避免把字面量 "***" 存进库
    - 空串                     → 清空
    - 其它                     → 视为新 key
    """
    by_id = {r.get("id"): r for r in (old_rows or []) if r.get("id")}
    out = []
    for row in (new_rows or []):
        row = dict(row)
        if row.get("api_key") == MASK:
            rid = row.get("id")
            row["api_key"] = by_id[rid]["api_key"] if rid in by_id else ""
        out.append(row)
    return out
```

- [ ] **Step 5: 运行测试**

```bash
cd backend && python -m pytest tests/test_model_config.py -q
```

Expected: 7 passed。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/provider_registry.py backend/app/services/model_config.py backend/tests/test_model_config.py
git commit -m "feat: provider 注册表与 resolve 三级降级链"
```

---

## Task 3: 密钥掩码测试

**Files:**
- Test: `backend/tests/test_model_config.py`（追加）

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_model_config.py` 末尾追加：

```python
from app.services.model_config import MASK, redact, restore


def test_redact_masks_non_empty_keys_only():
    rows = [
        {"id": 1, "api_key": "sk-secret"},
        {"id": 2, "api_key": ""},
    ]
    out = redact(rows)
    assert out[0]["api_key"] == MASK
    assert out[1]["api_key"] == ""
    # 原对象不被修改
    assert rows[0]["api_key"] == "sk-secret"


def test_restore_keeps_stored_key_when_masked():
    old = [{"id": 1, "api_key": "sk-secret"}]
    new = [{"id": 1, "api_key": MASK, "name": "改个名"}]
    out = restore(old, new)
    assert out[0]["api_key"] == "sk-secret"
    assert out[0]["name"] == "改个名"


def test_restore_clears_when_empty_string():
    old = [{"id": 1, "api_key": "sk-secret"}]
    new = [{"id": 1, "api_key": ""}]
    assert restore(old, new)[0]["api_key"] == ""


def test_restore_updates_when_new_key_given():
    old = [{"id": 1, "api_key": "sk-secret"}]
    new = [{"id": 1, "api_key": "sk-brand-new"}]
    assert restore(old, new)[0]["api_key"] == "sk-brand-new"


def test_new_row_with_mask_becomes_empty():
    out = restore([], [{"api_key": MASK, "name": "新建"}])
    assert out[0]["api_key"] == ""
```

- [ ] **Step 2: 运行测试**

```bash
cd backend && python -m pytest tests/test_model_config.py -q
```

Expected: 12 passed（掩码函数已在 Task 2 实现）。

- [ ] **Step 3: 提交**

```bash
git add backend/tests/test_model_config.py
git commit -m "test: 密钥掩码往返与边界"
```

---

## Task 4: catalog 读写接口

**Files:**
- Modify: `backend/app/routers/config_router.py`
- Test: `backend/tests/test_config_catalog.py`（创建）

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_config_catalog.py`：

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.models import ModelConfig, ModelConnection, ModelProfile, RoleBinding
from app.routers.config_router import router as config_router


def _client():
    app = FastAPI()
    app.include_router(config_router)
    return TestClient(app)


def _clear(db):
    for m in (RoleBinding, ModelProfile, ModelConnection, ModelConfig):
        db.query(m).delete()
    db.commit()


def test_get_catalog_lists_all_roles_and_registry(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    body = c.get("/api/config/catalog").json()
    assert set(body["services"].keys()) == {
        "llm", "task", "embedding", "search", "tts", "stt", "imagegen"
    }
    assert "registry" in body
    assert "connections" in body


def test_put_catalog_persists_connection_and_binding(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    payload = {
        "connections": [
            {"id": None, "provider": "openai", "name": "中转站",
             "base_url": "https://x/v1", "api_key": "sk-real"}
        ],
        "services": {
            "llm": {"profile_id": None, "connection_id": None,
                    "connection_index": 0, "model": "gpt-4o", "options": "{}",
                    "mode": "inherit"},
        },
    }
    assert c.put("/api/config/catalog", json=payload).json()["ok"] is True

    body = c.get("/api/config/catalog").json()
    assert body["connections"][0]["name"] == "中转站"
    assert body["connections"][0]["api_key"] == "***"
    assert body["services"]["llm"]["model"] == "gpt-4o"

    db = SessionLocal()
    assert db.query(ModelConnection).count() == 1
    assert db.query(ModelProfile).count() == 1
    assert db.query(RoleBinding).filter_by(role="llm").count() == 1
    db.close()


def test_put_catalog_does_not_clobber_masked_key(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    first = {
        "connections": [{"id": None, "provider": "deepseek", "name": "ds",
                         "base_url": "", "api_key": "sk-original"}],
        "services": {"llm": {"connection_index": 0, "model": "deepseek-chat",
                             "options": "{}", "mode": "inherit"}},
    }
    c.put("/api/config/catalog", json=first)
    got = c.get("/api/config/catalog").json()

    # 原样回传（key 是 MASK），不应把真 key 覆盖成 ***
    second = {"connections": got["connections"], "services": got["services"]}
    c.put("/api/config/catalog", json=second)

    db = SessionLocal()
    assert db.query(ModelConnection).first().api_key == "sk-original"
    db.close()


def test_deleting_connection_nulls_profile_reference(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    c.put("/api/config/catalog", json={
        "connections": [{"id": None, "provider": "openai", "name": "a",
                         "base_url": "https://x/v1", "api_key": "k"}],
        "services": {"llm": {"connection_index": 0, "model": "gpt-4o",
                             "options": "{}", "mode": "inherit"}},
    })
    got = c.get("/api/config/catalog").json()
    c.put("/api/config/catalog", json={
        "connections": [],
        "services": got["services"],
    })
    db = SessionLocal()
    prof = db.query(ModelProfile).filter_by(role="llm").first()
    assert prof is not None
    assert prof.connection_id is None
    db.close()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_config_catalog.py -q
```

Expected: FAIL（404，路由不存在）。

- [ ] **Step 3: 实现 catalog 接口**

在 `backend/app/routers/config_router.py` **顶部导入区**补充：

```python
from ..models import ModelConnection, ModelProfile, RoleBinding
from ..services.model_config import MASK, redact, resolve
from ..services.provider_registry import REGISTRY, ROLES
```

在文件末尾追加：

```python
# ---------------- 模型与服务（7 角色）----------------

def _dump_catalog(db) -> dict:
    conns = db.query(ModelConnection).order_by(ModelConnection.id).all()
    out_conns = [
        {"id": c.id, "provider": c.provider, "name": c.name,
         "base_url": c.base_url, "api_key": c.api_key,
         "extra_headers": c.extra_headers}
        for c in conns
    ]
    index_of = {c["id"]: i for i, c in enumerate(out_conns)}

    services = {}
    for role in ROLES:
        binding = db.get(RoleBinding, role)
        prof = db.get(ModelProfile, binding.profile_id) if binding and binding.profile_id else None
        resolved = resolve(db, role)
        services[role] = {
            "connection_id": prof.connection_id if prof else None,
            "connection_index": index_of.get(prof.connection_id if prof else None),
            "model": prof.model if prof else "",
            "options": prof.options if prof else "",
            "mode": binding.mode if binding else "inherit",
            "effective": {
                "provider": resolved.provider,
                "model": resolved.model,
                "source": resolved.source,
            },
        }
    return {
        "registry": {role: [s.__dict__ for s in specs] for role, specs in REGISTRY.items()},
        "connections": redact(out_conns),
        "services": services,
    }


@router.get("/catalog")
def get_catalog(db: Session = Depends(get_db)):
    return _dump_catalog(db)


@router.put("/catalog")
def put_catalog(req: dict, db: Session = Depends(get_db)):
    old_conns = [
        {"id": c.id, "api_key": c.api_key}
        for c in db.query(ModelConnection).all()
    ]
    incoming = restore(old_conns, req.get("connections") or [])

    by_id = {c.id: c for c in db.query(ModelConnection).all()}
    kept_ids = set()
    ordered_ids = []
    for row in incoming:
        rid = row.get("id")
        if rid and rid in by_id:
            conn = by_id[rid]
        else:
            conn = ModelConnection()
            db.add(conn)
        conn.provider = row.get("provider") or "openai"
        conn.name = row.get("name") or ""
        conn.base_url = row.get("base_url") or ""
        conn.api_key = row.get("api_key") or ""
        conn.extra_headers = row.get("extra_headers") or ""
        db.flush()
        kept_ids.add(conn.id)
        ordered_ids.append(conn.id)

    # 删除未回传的连接：引用它的档位置 NULL，不级联删档位
    for cid, conn in by_id.items():
        if cid not in kept_ids:
            db.query(ModelProfile).filter_by(connection_id=cid).update(
                {"connection_id": None}, synchronize_session=False
            )
            db.delete(conn)
    db.flush()

    for role, svc in (req.get("services") or {}).items():
        if role not in ROLES:
            continue
        binding = db.get(RoleBinding, role) or RoleBinding(role=role)
        db.add(binding)
        binding.mode = svc.get("mode") or "inherit"

        idx = svc.get("connection_index")
        conn_id = ordered_ids[idx] if isinstance(idx, int) and 0 <= idx < len(ordered_ids) else None
        model = svc.get("model") or ""
        options = svc.get("options") or ""

        if conn_id is None and not model:
            binding.profile_id = None
            continue

        prof = db.get(ModelProfile, binding.profile_id) if binding.profile_id else None
        if prof is None:
            prof = ModelProfile(role=role)
            db.add(prof)
            db.flush()
        prof.connection_id = conn_id
        prof.model = model
        prof.options = options
        binding.profile_id = prof.id

    db.commit()
    return {"ok": True}
```

- [ ] **Step 4: 运行测试**

```bash
cd backend && python -m pytest tests/test_config_catalog.py -q
```

Expected: 4 passed。

- [ ] **Step 5: 跑全套确认没打破现有 config**

```bash
cd backend && python -m pytest tests/test_config.py -q
```

Expected: 2 passed。

- [ ] **Step 6: 提交**

```bash
git add backend/app/routers/config_router.py backend/tests/test_config_catalog.py
git commit -m "feat: catalog 读写接口（含密钥掩码往返）"
```

---

## Task 5: 探针与分角色测试

**Files:**
- Modify: `backend/app/routers/config_router.py`
- Test: `backend/tests/test_config_catalog.py`（追加）

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_config_catalog.py` 末尾追加：

```python
def test_probe_requires_base_url_for_openai(setup_db):
    c = _client()
    r = c.post("/api/config/probe", json={
        "provider": "openai", "base_url": "", "api_key": "sk-x"
    }).json()
    assert r["status"] == "invalid_url"


def test_probe_restores_masked_key(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    c.put("/api/config/catalog", json={
        "connections": [{"id": None, "provider": "openai", "name": "a",
                         "base_url": "http://127.0.0.1:1/v1", "api_key": "sk-real"}],
        "services": {},
    })
    # 用 MASK 去探测，后端应换回真 key；连不上是预期的
    r = c.post("/api/config/probe", json={
        "provider": "openai", "base_url": "http://127.0.0.1:1/v1",
        "api_key": "***", "connection_id": 1,
    }).json()
    assert r["status"] in ("unreachable", "timeout", "http_error")


def test_test_endpoint_task_inherit_short_circuits(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    r = c.post("/api/config/test", json={"role": "task"}).json()
    assert r["ok"] is True
    assert "继承" in r.get("note", "")


def test_test_endpoint_stt_is_skipped(setup_db):
    db = SessionLocal(); _clear(db); db.close()
    c = _client()
    r = c.post("/api/config/test", json={"role": "stt"}).json()
    assert r["ok"] is True
    assert "跳过" in r.get("note", "")
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_config_catalog.py -q
```

Expected: 新增 4 条 FAIL（路由 404 / 字段不存在）。

- [ ] **Step 3: 实现探针与测试接口**

在 `backend/app/routers/config_router.py` 末尾追加：

```python
class ProbeReq(BaseModel):
    provider: str = "openai"
    base_url: str = ""
    api_key: str = ""
    connection_id: int | None = None


class RoleTestReq(BaseModel):
    role: str = "llm"


@router.post("/probe")
def probe(req: ProbeReq, db: Session = Depends(get_db)):
    """凭据探针：GET {base_url}/models，不发推理、不计费。"""
    api_key = req.api_key
    if api_key == MASK and req.connection_id:
        conn = db.get(ModelConnection, req.connection_id)
        api_key = conn.api_key if conn else ""

    if req.provider == "openai":
        if not req.base_url:
            return {"status": "invalid_url", "models": [],
                    "warning": "中转站需要 Base URL"}
    else:
        return {"status": "connected", "models": [], "warning": "内置 provider，跳过探测"}

    from ..services.ai import OpenAICompatibleProvider
    p = OpenAICompatibleProvider(model="", api_key=api_key, base_url=req.base_url)
    try:
        models = p.list_models()
    except Exception as e:
        msg = str(e)
        if "401" in msg or "403" in msg or "Unauthorized" in msg:
            return {"status": "auth_error", "models": []}
        return {"status": "unreachable", "models": []}
    return {"status": "connected", "models": [{"id": m} for m in models]}


@router.post("/test")
def test_config_v2(req: RoleTestReq, db: Session = Depends(get_db)):
    """按角色分派真实调用测试。"""
    role = req.role
    if role == "stt":
        return {"ok": True, "role": role, "note": "语音识别未实现，跳过"}
    if role == "task":
        binding = db.get(RoleBinding, "task")
        if binding is None or binding.mode == "inherit":
            return {"ok": True, "role": role, "note": "继承语言模型"}

    r = resolve(db, role)
    if role == "llm":
        from ..services.ai import FakeProvider, GLMProvider, DeepSeekProvider, OpenAICompatibleProvider
        cls = {"openai": OpenAICompatibleProvider, "deepseek": DeepSeekProvider,
               "glm": GLMProvider}.get(r.provider, FakeProvider)
        p = (cls(model=r.model, api_key=r.api_key, base_url=r.base_url)
             if cls is OpenAICompatibleProvider else cls(model=r.model, api_key=r.api_key))
        try:
            reply = p.generate(prompt="请回复「连接成功」四个字，不要其他内容。", system="你是连通性测试助手。")
            return {"ok": True, "role": role, "provider": r.provider,
                    "model": r.model, "sample": reply[:200]}
        except Exception as e:
            return {"ok": False, "role": role, "provider": r.provider,
                    "model": r.model, "error": str(e)[:300]}
    if role == "tts":
        from ..services.tts import get_tts
        try:
            audio = get_tts(db).synthesize("测试")
            return {"ok": True, "role": role, "bytes": len(audio)}
        except Exception as e:
            return {"ok": False, "role": role, "error": str(e)[:300]}
    if role == "embedding":
        from openai import OpenAI
        try:
            client = OpenAI(api_key=r.api_key, base_url=r.base_url)
            resp = client.embeddings.create(model=r.model, input="测试")
            return {"ok": True, "role": role, "dimension": len(resp.data[0].embedding)}
        except Exception as e:
            return {"ok": False, "role": role, "error": str(e)[:300]}
    if role == "imagegen":
        ok = bool(r.api_key and (r.base_url or r.provider != "openai"))
        return {"ok": ok, "role": role, "note": "仅校验配置，不生成"}
    return {"ok": True, "role": role, "note": "未实现，跳过"}
```

- [ ] **Step 4: 运行测试**

```bash
cd backend && python -m pytest tests/test_config_catalog.py -q
```

Expected: 8 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/config_router.py backend/tests/test_config_catalog.py
git commit -m "feat: 凭据探针与分角色连通测试"
```

---

## Task 6: 接线到现有调用方

**Files:**
- Modify: `backend/app/services/ai.py`
- Modify: `backend/app/services/tts.py`
- Test: `backend/tests/test_model_config.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_model_config.py` 末尾追加：

```python
def test_get_provider_uses_highest_priority_source():
    from app.services.ai import get_provider
    db = SessionLocal()
    _clear(db)
    conn = ModelConnection(provider="deepseek", name="ds", api_key="sk-binding")
    db.add(conn); db.flush()
    prof = ModelProfile(role="llm", connection_id=conn.id, model="deepseek-reasoner")
    db.add(prof); db.flush()
    db.add(RoleBinding(role="llm", profile_id=prof.id))
    db.commit()

    p = get_provider(db)
    assert p.name == "deepseek"
    assert p.model == "deepseek-reasoner"
    assert p.api_key == "sk-binding"
    db.close()


def test_get_provider_falls_back_to_fake_without_config():
    from app.services.ai import get_provider
    db = SessionLocal()
    _clear(db)
    p = get_provider(db)
    assert p.name == "fake"
    db.close()


def test_get_tts_uses_binding():
    from app.services.tts import get_tts
    db = SessionLocal()
    _clear(db)
    conn = ModelConnection(provider="minimax", name="mm", api_key="mm-key")
    db.add(conn); db.flush()
    prof = ModelProfile(role="tts", connection_id=conn.id, model="speech-01-turbo",
                        options='{"voice": "female-shaonv"}')
    db.add(prof); db.flush()
    db.add(RoleBinding(role="tts", profile_id=prof.id))
    db.commit()

    t = get_tts(db)
    assert t.name == "minimax"
    assert t.api_key == "mm-key"
    db.close()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_model_config.py -q
```

Expected: 新增 3 条 FAIL。

- [ ] **Step 3: 改 ai.py 的 get_provider 与 ocr_image**

把 `backend/app/services/ai.py` 中的 `get_provider` 与 `ocr_image` 替换为：

```python
def get_provider(db: Session) -> AIProvider:
    from .model_config import resolve
    r = resolve(db, "llm")
    cls = PROVIDERS.get(r.provider, FakeProvider)
    if cls is OpenAICompatibleProvider:
        return cls(model=r.model, api_key=r.api_key, base_url=r.base_url)
    return cls(model=r.model, api_key=r.api_key)


def ocr_image(db: Session, image_bytes: bytes, instruction: str = "识别图片中的全部文字，原样输出，不要解释。") -> str:
    """用视觉模型对扫描版教材页面做 OCR。

    视觉模型取自 llm 档位的 options.vision_model，未设则回落老键，再没有则报错。
    """
    from openai import OpenAI
    import base64
    from .model_config import resolve

    r = resolve(db, "llm")
    vision_model = r.options.get("vision_model", "")
    if not vision_model:
        from ..models import ModelConfig
        row = db.query(ModelConfig).filter_by(key="vision_model").first()
        vision_model = row.value if row else "qwen3-vl-plus"
    if not r.api_key or not r.base_url:
        raise RuntimeError("中转站 API Key / Base URL 未配置，无法 OCR")
    client = OpenAI(api_key=r.api_key, base_url=r.base_url)
    b64 = base64.b64encode(image_bytes).decode()
    resp = client.chat.completions.create(
        model=vision_model,
        messages=[{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            {"type": "text", "text": instruction},
        ]}],
    )
    return resp.choices[0].message.content or ""
```

同时删除已无用的 `_cfg` 函数（若无其他引用）。

- [ ] **Step 4: 改 tts.py 的 get_tts**

把 `backend/app/services/tts.py` 中的 `get_tts` 替换为：

```python
def get_tts(db: Session) -> TTSProvider:
    from .model_config import resolve
    r = resolve(db, "tts")
    voice = r.options.get("voice", "")
    cls = PROVIDERS.get(r.provider, FakeTTS)
    if cls is OpenAITTS:
        return cls(voice=voice, api_key=r.api_key, base_url=r.base_url, model=r.model)
    return cls(voice=voice, api_key=r.api_key)
```

- [ ] **Step 5: 运行全部相关测试**

```bash
cd backend && python -m pytest tests/test_model_config.py tests/test_ai.py tests/test_tts.py tests/test_notes.py tests/test_task_gen.py -q
```

Expected: 全部 PASS。

- [ ] **Step 6: 提交**

```bash
git add backend/app/services/ai.py backend/app/services/tts.py backend/tests/test_model_config.py
git commit -m "refactor: get_provider/get_tts/ocr 改读统一 resolve 出口"
```

---

## Task 7: 迁移脚本

**Files:**
- Create: `backend/migrate_model_catalog.py`
- Test: `backend/tests/test_model_config.py`（追加）

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_model_config.py` 末尾追加：

```python
def test_migration_moves_legacy_keys_to_tables():
    from migrate_model_catalog import migrate
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_model", value="deepseek-chat"))
    db.add(ModelConfig(key="ai_key", value="sk-legacy"))
    db.add(ModelConfig(key="tts_provider", value="minimax"))
    db.add(ModelConfig(key="tts_key", value="mm-key"))
    db.add(ModelConfig(key="vision_model", value="qwen3-vl-plus"))
    db.commit()

    migrate(db)

    llm = resolve(db, "llm")
    assert llm.source == "binding"
    assert llm.provider == "deepseek"
    assert llm.model == "deepseek-chat"
    assert llm.api_key == "sk-legacy"
    assert llm.options.get("vision_model") == "qwen3-vl-plus"

    tts = resolve(db, "tts")
    assert tts.source == "binding"
    assert tts.api_key == "mm-key"
    db.close()


def test_migration_is_idempotent():
    from migrate_model_catalog import migrate
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="deepseek"))
    db.add(ModelConfig(key="ai_key", value="sk-legacy"))
    db.commit()

    migrate(db)
    migrate(db)

    assert db.query(ModelConnection).count() == 1
    assert db.query(ModelProfile).filter_by(role="llm").count() == 1
    db.close()


def test_migration_skips_fake_provider():
    from migrate_model_catalog import migrate
    db = SessionLocal()
    _clear(db)
    db.add(ModelConfig(key="ai_provider", value="fake"))
    db.commit()
    migrate(db)
    assert db.query(ModelConnection).count() == 0
    db.close()
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && python -m pytest tests/test_model_config.py -q
```

Expected: 新增 3 条 FAIL（`ModuleNotFoundError: migrate_model_catalog`）。

- [ ] **Step 3: 写迁移脚本**

创建 `backend/migrate_model_catalog.py`：

```python
"""把 ModelConfig 老键迁移成 ModelConnection/ModelProfile/RoleBinding。

幂等：已迁移过的角色跳过；老键保留不删，继续作为降级来源。

用法：
    cd backend && python migrate_model_catalog.py            # 执行迁移
    cd backend && python migrate_model_catalog.py --verify   # 只打印对照，不写库
"""
import sys

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ModelConfig, ModelConnection, ModelProfile, RoleBinding
from app.services.model_config import resolve
from app.services.provider_registry import ROLES


def _cfg(db: Session) -> dict:
    return {r.key: r.value for r in db.query(ModelConfig).all()}


def _upsert(db: Session, role: str, provider: str, model: str, api_key: str,
            base_url: str, options: dict) -> None:
    if db.get(RoleBinding, role):
        return  # 已迁移过

    conn = ModelConnection(provider=provider, name=f"{provider}（迁移）",
                           base_url=base_url, api_key=api_key)
    db.add(conn)
    db.flush()
    import json as _json
    prof = ModelProfile(role=role, connection_id=conn.id, model=model,
                        options=_json.dumps(options) if options else "")
    db.add(prof)
    db.flush()
    db.add(RoleBinding(role=role, profile_id=prof.id))
    db.flush()


def migrate(db: Session) -> None:
    cfg = _cfg(db)

    ai_provider = cfg.get("ai_provider", "")
    if ai_provider and ai_provider != "fake":
        opts = {}
        if cfg.get("vision_model"):
            opts["vision_model"] = cfg["vision_model"]
        _upsert(db, "llm", ai_provider, cfg.get("ai_model", ""),
                cfg.get("ai_key", ""), cfg.get("ai_base_url", ""), opts)

    tts_provider = cfg.get("tts_provider", "")
    if tts_provider and tts_provider != "fake":
        opts = {}
        for k, key in (("voice", "tts_voice"), ("speed", "tts_speed"),
                       ("repeat", "tts_repeat")):
            if cfg.get(key):
                opts[k] = cfg[key]
        _upsert(db, "tts", tts_provider, cfg.get("tts_model", ""),
                cfg.get("tts_key", ""), cfg.get("tts_base_url", ""), opts)

    db.commit()


def verify(db: Session) -> None:
    cfg = _cfg(db)
    print("老键:")
    for k in sorted(cfg):
        if k.startswith(("ai_", "tts_", "vision_")):
            print(f"  {k} = {cfg[k]!r}")
    print("\n解析结果:")
    for role in ROLES:
        r = resolve(db, role)
        print(f"  {role:10s} provider={r.provider:10s} model={r.model:24s} source={r.source}")


if __name__ == "__main__":
    s = SessionLocal()
    try:
        if "--verify" in sys.argv:
            verify(s)
        else:
            migrate(s)
            print("迁移完成。")
            verify(s)
    finally:
        s.close()
```

- [ ] **Step 4: 运行测试**

```bash
cd backend && python -m pytest tests/test_model_config.py -q
```

Expected: 18 passed。

- [ ] **Step 5: 提交**

```bash
git add backend/migrate_model_catalog.py backend/tests/test_model_config.py
git commit -m "feat: 老配置迁移脚本（幂等 + --verify）"
```

---

## Task 8: 前端设置页

**Files:**
- Modify: `frontend/index.html`（追加 CSS）
- Modify: `frontend/app.js`（替换设置页）

**参考实现**：`prototype/index.html` 中已实现并验证过的同名函数（`renderModelServices` / `renderMsNav` / `renderMsRole` / `renderMsConnections` 及交互函数）。本任务是把它们**接到真实 API**：原型里的本地常量 `MODEL_CONNECTIONS` / `MODEL_ROLES` / `modelServices` 改为从 `/api/config/catalog` 拉取。

> 注意：`prototype/index.html` 是演示页，本任务**不要修改它**。

- [ ] **Step 1: 追加 CSS**

在 `frontend/index.html` 的 `<style>` 末尾追加（与原型一致）：

```css
  /* 模型与服务：左角色导航 + 右配置面板 */
  .ms-wrap{display:grid;grid-template-columns:236px minmax(0,1fr);gap:20px;margin-top:24px;align-items:start}
  .ms-nav{border:1px solid var(--line3);background:var(--card);border-radius:20px;padding:12px;position:sticky;top:24px}
  .ms-nav .nav-title{font-size:11px;font-weight:700;letter-spacing:.08em;color:var(--gray3);padding:8px 10px 10px}
  .ms-item{display:flex;align-items:center;gap:10px;width:100%;padding:10px;border-radius:12px;font-size:13px;font-weight:600;color:var(--ink3);text-align:left;transition:.15s}
  .ms-item:hover{background:#f5f6f4}
  .ms-item.on{background:var(--blue-soft);color:var(--blue)}
  .ms-item .dot{width:6px;height:6px;border-radius:50%;margin-left:auto;flex-shrink:0}
  .ms-item .dot.ok{background:var(--green2)}
  .ms-item .dot.warn{background:var(--gold2)}
  .ms-item .dot.off{background:#d7dcd6}
  .ms-item .off-tag{margin-left:auto;font-size:10px;color:var(--gray3);font-weight:500;background:#f3f5f2;border-radius:6px;padding:2px 6px}
  .ms-main{border:1px solid var(--line3);background:var(--card);border-radius:24px;padding:24px}
  .ms-main .head{display:flex;align-items:center;gap:12px}
  .ms-main .head .ic{width:40px;height:40px;border-radius:12px;display:grid;place-items:center}
  .ms-main .head .ic.blue{background:var(--blue-soft);color:var(--blue2)}
  .ms-main .head .ic.green{background:var(--green-soft);color:var(--green2)}
  .ms-main .head .ic.purple{background:var(--purple-soft);color:var(--purple)}
  .ms-main .head .ic.orange{background:var(--orange-soft);color:var(--orange2)}
  .ms-main .head h3{font-size:16px;font-weight:700}
  .ms-main .head .sub{margin-top:2px;font-size:12px;color:#8e9691}
  .ms-field{margin-top:18px;max-width:560px}
  .ms-label{font-size:13px;color:var(--gray2);margin-bottom:8px;display:flex;align-items:center;gap:6px}
  .ms-input,.ms-select{width:100%;border:1px solid var(--line3);border-radius:12px;padding:10px 12px;font-size:13px;font-family:inherit;background:var(--card);color:var(--ink)}
  .ms-input:focus,.ms-select:focus{outline:none;border-color:var(--blue-border);box-shadow:0 0 0 3px rgba(49,88,232,.08)}
  .ms-input:disabled,.ms-select:disabled{background:#f7f8f6;color:var(--gray3)}
  .ms-row{display:flex;gap:10px;align-items:center}
  .ms-hint{font-size:12px;color:var(--gray3);margin-top:6px;line-height:19px}
  .ms-badge{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:700;border-radius:999px;padding:3px 9px;margin-left:auto}
  .ms-badge.ok{background:var(--green-soft);color:var(--green)}
  .ms-badge.idle{background:#f3f5f2;color:var(--gray3)}
  .ms-badge.warn{background:var(--orange-soft);color:var(--orange2)}
  .ms-card{border:1px solid #e7e9e6;border-radius:16px;padding:14px 16px;display:flex;align-items:center;gap:12px}
  .ms-card+.ms-card{margin-top:10px}
  .ms-card .c-l{min-width:0;flex:1}
  .ms-card .c-name{font-size:14px;font-weight:700;display:flex;align-items:center;gap:8px}
  .ms-card .c-meta{margin-top:3px;font-size:12px;color:#8e9691;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .ms-card .c-k{font-family:ui-monospace,Menlo,monospace;font-size:11px;color:var(--gray3)}
  .ms-empty{border:1px dashed #dfe4dd;border-radius:16px;padding:28px 16px;text-align:center;font-size:13px;color:var(--gray3)}
  .ms-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:24px;padding-top:18px;border-top:1px solid #eef1ec}
```

- [ ] **Step 2: 确认图标可用**

```bash
grep -n "^function icon" -A 3 frontend/app.js | head -6
grep -o "^  [a-z-]*:" frontend/app.js | sort | head -40
```

本任务用到 `brain` / `clock` / `text` / `chart` / `headphones` / `sparkles` / `book`。
若 `clock` 或 `text` 不在图标表中，先补进 `frontend/app.js` 的 `ICONS`：

```javascript
  clock:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  text:'<path d="M4 6h16M4 12h10M4 18h7"/>',
```

- [ ] **Step 3: 替换设置页状态**

在 `frontend/app.js` 中，`renderSettingsTab(){` 定义之前插入：

```javascript
// ---- 模型与服务（7 角色）----
let msCatalog = null;                 // /api/config/catalog 的结果
let msRoleTab = 'llm';
let msProbe = {};                     // role -> 提示文本
let msConnEdit = null;
let msSaving = false;

const MS_ROLES = [
  {id:'llm',       name:'语言模型',     icon:'brain',      color:'purple', wired:true,  desc:'对话、追问、讲解、出题', model:true},
  {id:'task',      name:'后台任务模型', icon:'clock',      color:'blue',   wired:true,  desc:'任务生成、课文提取、批量出题', model:true},
  {id:'embedding', name:'嵌入模型',     icon:'text',       color:'green',  wired:false, desc:'课文语义检索（为引用定位预留）', model:true},
  {id:'search',    name:'搜索',         icon:'chart',      color:'orange', wired:false, desc:'联网查资料（暂未接入）', model:false},
  {id:'tts',       name:'语音',         icon:'headphones', color:'orange', wired:true,  desc:'听写朗读、课文朗读', model:true},
  {id:'stt',       name:'语音识别',     icon:'headphones', color:'blue',   wired:false, desc:'跟读评测（暂未接入）', model:true},
  {id:'imagegen',  name:'多模态生成',   icon:'sparkles',   color:'green',  wired:false, desc:'课文配图与示意动画（暂未接入）', model:true}
];

async function loadModelCatalog(){
  msCatalog = await api('/api/config/catalog');
  return msCatalog;
}
function msSvc(role){ return (msCatalog && msCatalog.services && msCatalog.services[role]) || {}; }
function msConns(){ return (msCatalog && msCatalog.connections) || []; }
function msConnAt(i){ const c = msConns(); return (typeof i === 'number' && i >= 0 && i < c.length) ? c[i] : null; }
function msRoleMeta(id){ return MS_ROLES.find(r => r.id === id) || MS_ROLES[0]; }
function msStatus(role){
  const svc = msSvc(role);
  if(role === 'task' && (svc.mode || 'inherit') === 'inherit') return 'ok';
  if(svc.connection_index === null || svc.connection_index === undefined) return 'off';
  return svc.model ? 'ok' : 'warn';
}
```

- [ ] **Step 4: 替换 renderSettingsTab 为分发到新页**

把 `function renderSettingsTab(){ ... }` 整个函数体替换为：

```javascript
function renderSettingsTab(){
  if(!msCatalog){
    loadModelCatalog().then(()=>render());
    return `<div class="ms-empty">正在加载模型配置…</div>`;
  }
  return `<div class="ms-wrap">${msNavHtml()}${msRoleTab==='connections' ? msConnectionsHtml() : msRoleHtml()}</div>`;
}
```

- [ ] **Step 5: 追加渲染与交互函数**

在 `renderSettingsTab` 之后追加（结构照搬 `prototype/index.html` 的同名函数，数据源改为 `msCatalog`）：

```javascript
function msNavHtml(){
  const items = MS_ROLES.map(r=>{
    const st = msStatus(r.id);
    return `<button class="ms-item ${msRoleTab===r.id?'on':''}" onclick="msSelectRole('${r.id}')">
      ${icon(r.icon,16)}<span>${r.name}</span>
      ${r.wired ? `<span class="dot ${st}"></span>` : `<span class="off-tag">未接入</span>`}
    </button>`;
  }).join('');
  return `<aside class="ms-nav">
    <div class="nav-title">模型与服务</div>
    ${items}
    <div style="border-top:1px solid #eef1ec;margin:10px 0 4px"></div>
    <button class="ms-item ${msRoleTab==='connections'?'on':''}" onclick="msSelectRole('connections')">
      ${icon('book',16)}<span>提供方</span>
    </button>
  </aside>`;
}

function msConnectionsHtml(){
  const cards = msConns().map((c,i)=>{
    const editing = msConnEdit === i;
    return `<div class="ms-card" style="align-items:flex-start">
      <div class="c-l">
        <div class="c-name">${escapeAttr(c.name||'未命名')}<span class="ms-badge idle">${escapeAttr(c.provider)}</span></div>
        <div class="c-meta">${escapeAttr(c.base_url||'默认端点')} · <span class="c-k">${escapeAttr(c.api_key||'未配置')}</span></div>
        ${editing ? `
          <div class="ms-field"><div class="ms-label">名称</div>
            <input class="ms-input" value="${escapeAttr(c.name||'')}" oninput="msConnField(${i},'name',this.value)"></div>
          <div class="ms-field"><div class="ms-label">Base URL</div>
            <input class="ms-input" value="${escapeAttr(c.base_url||'')}" placeholder="留空使用默认端点" oninput="msConnField(${i},'base_url',this.value)"></div>
          <div class="ms-field"><div class="ms-label">API Key</div>
            <input class="ms-input" type="password" value="" placeholder="${c.api_key?'已保存，留空则不修改':'sk-...'}" oninput="msConnField(${i},'_newKey',this.value)">
            <div class="ms-hint">密钥只在提供方录一次，所有角色共用。</div></div>` : ''}
      </div>
      <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-end">
        <button class="btn-ghost" onclick="msToggleConnEdit(${i})">${editing?'收起':'编辑'}</button>
        <button class="btn-ghost" style="color:#c05b4a" onclick="msRemoveConn(${i})">删除</button>
      </div>
    </div>`;
  }).join('');
  return `<section class="ms-main">
    <div class="head"><div class="ic blue">${icon('book',20)}</div>
      <div><h3>提供方</h3><div class="sub">添加提供方与认证信息，然后测试连接</div></div></div>
    <div style="margin-top:18px">${cards || `<div class="ms-empty">还没有提供方，先添加一个吧</div>`}</div>
    <div class="ms-actions">
      <button class="btn-ghost" style="padding:10px 20px" onclick="msAddConn()">＋ 添加提供方</button>
      <button class="btn-primary" style="padding:10px 24px" onclick="msSaveAll()" ${msSaving?'disabled':''}>保存配置</button>
    </div>
  </section>`;
}

function msRoleHtml(){
  const r = msRoleMeta(msRoleTab);
  const svc = msSvc(r.id);
  const st = msStatus(r.id);
  const stText = st==='ok'?'已配置':st==='warn'?'待选模型':'未配置';
  const stCls = st==='ok'?'ok':st==='warn'?'warn':'idle';
  const inherit = r.id==='task' && (svc.mode||'inherit')==='inherit';
  const connOpts = `<option value="">— 不使用连接 —</option>` + msConns().map((c,i)=>
    `<option value="${i}" ${svc.connection_index===i?'selected':''}>${escapeAttr(c.name||c.provider)}</option>`).join('');

  const summary = MS_ROLES.filter(x=>x.wired).map(x=>{
    const s = msSvc(x.id);
    const inh = x.id==='task' && (s.mode||'inherit')==='inherit';
    const eff = s.effective || {};
    const val = inh ? '跟随语言模型' : (eff.provider ? `${eff.provider} · ${eff.model||'未选模型'}` : '未配置');
    return `<div style="display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #f1f4ef">
      <span style="font-size:12px;color:var(--gray2);width:88px;flex-shrink:0">${x.name}</span>
      <span style="font-size:12px;color:var(--ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escapeAttr(val)}</span>
    </div>`;
  }).join('');

  return `<section class="ms-main">
    <div class="head">
      <div class="ic ${r.color}">${icon(r.icon,20)}</div>
      <div><h3>${r.name}</h3><div class="sub">${r.desc}</div></div>
      <span class="ms-badge ${stCls}">${stText}</span>
    </div>
    ${!r.wired ? `<div class="ms-hint" style="margin-top:14px;background:#f7f8f6;border-radius:12px;padding:10px 12px">
      该角色暂未接入业务，配置会保存，但不会影响现有功能。</div>` : ''}
    ${r.id==='task' ? `<div class="ms-field">
      <label style="display:flex;align-items:center;gap:10px;font-size:14px;font-weight:600;cursor:pointer">
        <input type="checkbox" ${inherit?'checked':''} onchange="msToggleInherit(this.checked)">
        跟随语言模型（推荐）
      </label>
      <div class="ms-hint">开启后后台任务沿用语言模型的配置；只有在想用更便宜 / 更快的模型时才需要单独配置。</div>
    </div>` : ''}
    ${inherit ? '' : `
      <div class="ms-field"><div class="ms-label">提供方</div>
        <select class="ms-select" onchange="msSetConn(this.value)">${connOpts}</select>
        ${msConns().length ? '' : `<div class="ms-hint">先到「提供方」里添加一套凭证，再回到这里选择。</div>`}
      </div>
      ${r.model ? `<div class="ms-field"><div class="ms-label">模型</div>
        <div class="ms-row">
          <input class="ms-input" value="${escapeAttr(svc.model||'')}" placeholder="填模型名，或点右侧拉取" oninput="msSetModel(this.value)">
          <button class="btn-ghost" style="white-space:nowrap" onclick="msFetchModels()">拉取模型</button>
        </div>
        <div class="ms-hint">${msProbe[r.id]||'选择提供方后，可拉取该账号下可用的模型列表。'}</div>
      </div>` : ''}
      ${r.id==='tts' ? `<div class="ms-field"><div class="ms-label">音色</div>
        <select class="ms-select" onchange="msSetOption('voice',this.value)">
          ${['male-qn-qingse','female-shaonv','presenter_male','alloy','nova'].map(v=>
            `<option value="${v}" ${(svc.options||'').includes(v)?'selected':''}>${v}</option>`).join('')}
        </select></div>` : ''}
    `}
    <div class="ms-actions">
      ${r.id==='tts' ? `<button class="btn-ghost" style="padding:10px 20px" onclick="testVoice()">试听语音</button>` : ''}
      <button class="btn-ghost" style="padding:10px 20px" onclick="msTestRole('${r.id}')">测试连接</button>
      <button class="btn-primary" style="padding:10px 24px" onclick="msSaveAll()" ${msSaving?'disabled':''}>保存配置</button>
    </div>
    <div style="margin-top:22px;padding-top:18px;border-top:1px solid #eef1ec">
      <div style="font-size:12px;font-weight:700;color:var(--gray2);letter-spacing:.04em;margin-bottom:4px">当前生效配置</div>
      ${summary}
    </div>
  </section>`;
}

function msSelectRole(id){ msRoleTab = id; msConnEdit = null; render(); }
function msToggleConnEdit(i){ msConnEdit = msConnEdit === i ? null : i; render(); }
function msConnField(i, field, val){
  const c = msConns()[i]; if(!c) return;
  if(field === '_newKey'){ c._newKey = val; return; }
  c[field] = val;
}
function msAddConn(){
  msCatalog.connections.push({id:null, provider:'openai', name:'新提供方',
    base_url:'', api_key:'', extra_headers:''});
  msConnEdit = msConns().length - 1;
  msRoleTab = 'connections'; render();
}
function msRemoveConn(i){
  msCatalog.connections.splice(i, 1);
  Object.keys(msCatalog.services||{}).forEach(role=>{
    const s = msCatalog.services[role];
    if(s.connection_index === i){ s.connection_index = null; s.model = ''; }
    else if(typeof s.connection_index === 'number' && s.connection_index > i){ s.connection_index -= 1; }
  });
  if(msConnEdit === i) msConnEdit = null;
  render();
}
function msSetConn(val){
  const s = msSvc(msRoleTab);
  s.connection_index = val === '' ? null : parseInt(val);
  s.model = '';
  render();
}
function msSetModel(val){ msSvc(msRoleTab).model = val; }
function msSetOption(key, val){
  const s = msSvc(msRoleTab);
  let opts = {};
  try{ opts = s.options ? JSON.parse(s.options) : {}; }catch(e){ opts = {}; }
  opts[key] = val;
  s.options = JSON.stringify(opts);
}
async function msToggleInherit(on){
  msSvc('task').mode = on ? 'inherit' : 'reference';
  await msSaveAll();
}
async function msFetchModels(){
  const s = msSvc(msRoleTab);
  const conn = msConnAt(s.connection_index);
  if(!conn){ msProbe[msRoleTab] = '请先选择提供方。'; render(); return; }
  msProbe[msRoleTab] = '正在拉取…'; render();
  const r = await api('/api/config/probe', {method:'POST', body:{
    provider: conn.provider, base_url: conn.base_url,
    api_key: conn.api_key, connection_id: conn.id || null
  }});
  if(r.status === 'connected' && r.models && r.models.length){
    msProbe[msRoleTab] = `连接成功 · 可用模型 ${r.models.length} 个`;
    msCatalog.modelsByConn = msCatalog.modelsByConn || {};
    msCatalog.modelsByConn[s.connection_index] = r.models.map(m=>m.id);
  } else {
    msProbe[msRoleTab] = `连接失败：${r.status}${r.warning?' · '+r.warning:''}`;
  }
  render();
}
async function msTestRole(role){
  msProbe[role] = '正在测试…'; render();
  const r = await api('/api/config/test', {method:'POST', body:{role}});
  msProbe[role] = r.ok ? `测试通过${r.note?'（'+r.note+'）':''}${r.sample?'：'+r.sample.slice(0,30):''}`
                       : `测试失败：${r.error||'未知错误'}`;
  render();
}
async function msSaveAll(){
  if(msSaving) return;
  msSaving = true;
  const payload = {
    connections: msConns().map(c=>({
      id: c.id || null, provider: c.provider, name: c.name,
      base_url: c.base_url, api_key: c._newKey || c.api_key || '',
      extra_headers: c.extra_headers || ''
    })),
    services: {}
  };
  Object.keys(msCatalog.services||{}).forEach(role=>{
    const s = msCatalog.services[role];
    payload.services[role] = {
      connection_index: s.connection_index === undefined ? null : s.connection_index,
      model: s.model || '', options: s.options || '', mode: s.mode || 'inherit'
    };
  });
  const r = await api('/api/config/catalog', {method:'PUT', body:payload});
  msSaving = false;
  if(r.ok){ await loadModelCatalog(); toast('模型与服务配置已保存'); }
  else { toast('保存失败'); }
  render();
}
```

- [ ] **Step 6: 加频道切换入口（旧版回退开关）**

在 `renderSettingsTab` 的返回里增加一个轻量开关。把 Step 3 中的 `renderSettingsTab` 改为：

```javascript
let msLegacyView = false;
function renderSettingsTab(){
  if(msLegacyView){ return renderSettingsTabLegacy(); }
  if(!msCatalog){
    loadModelCatalog().then(()=>render());
    return `<div class="ms-empty">正在加载模型配置…</div>`;
  }
  return `<div style="display:flex;justify-content:flex-end;margin-bottom:-8px">
    <button class="btn-ghost" onclick="msLegacyView=true;render()">切换到旧版设置</button>
  </div>
  <div class="ms-wrap">${msNavHtml()}${msRoleTab==='connections' ? msConnectionsHtml() : msRoleHtml()}</div>`;
}
```

把原来的旧实现整段重命名为 `renderSettingsTabLegacy()`（保留原代码不动，仅改名），并在其中加一个返回按钮：

```javascript
function renderSettingsTabLegacy(){
  return `<div style="display:flex;justify-content:flex-end;margin-bottom:12px">
    <button class="btn-ghost" onclick="msLegacyView=false;render()">切换到新版设置</button>
  </div>` + _legacySettingsBody();
}
```

再把改名前的原函数体放进 `_legacySettingsBody()`（即原来 `renderSettingsTab` 内 `return` 的模板字符串，原样保留）。

- [ ] **Step 7: 验证前端能加载**

```bash
cd backend && python -m http.server 8766 --directory ../frontend
```

在浏览器打开 `http://127.0.0.1:8766/` →「家长端」→「设置」，确认：

1. 左侧 7 个角色 + 提供方可见
2. 点「提供方」能看到连接卡片（或空态）
3. 点「语言模型」能看到提供方/模型下拉
4. 点「切换到旧版设置」能回到旧表单，再切回新版
5. 浏览器控制台无报错

- [ ] **Step 8: 提交**

```bash
git add frontend/index.html frontend/app.js
git commit -m "feat: 设置页改为模型与服务（7 角色 + 复用连接）"
```

---

## Task 9: 端到端验证

- [ ] **Step 1: 跑后端全套测试**

```bash
cd backend && python -m pytest -q
```

Expected: 新增测试全 PASS。**注意**：`test_seed.py` 与 `test_pdf_router.py` 有两条**改造前就存在**的失败（知识点计数、KeyError 'extracted'），与本阶段无关，确认失败原因与改造前一致即可。

- [ ] **Step 2: 迁移真实库**

```bash
cd backend && python migrate_model_catalog.py --verify
```

Expected: 打印老键与 7 个角色的解析结果，`llm`/`tts` 的 `source` 为 `legacy`。

```bash
cd backend && python migrate_model_catalog.py
```

Expected: 迁移完成，再打印一次对照，此时 `llm`/`tts` 的 `source` 变为 `binding`，且 provider/model/key 与迁移前一致。

- [ ] **Step 3: 启动后端确认行为不变**

```bash
cd backend && python -m uvicorn app.main:app --port 8010 --host 127.0.0.1
```

打开前端，验证：对话页能正常问答（`/api/ask`）、听写朗读能用（`/api/tts/synthesize`）。这两条走的就是改过的 `get_provider` / `get_tts`。

- [ ] **Step 4: 提交（如有残留修改）**

```bash
git status --short
```

若有非预期改动，逐一核对后再决定是否提交。

---

## 完成标准

- [ ] `resolve()` 三级降级链有三条对应测试
- [ ] `task` 继承与 `reference` 覆盖各有一条测试
- [ ] 密钥掩码往返四条边界测试通过
- [ ] catalog 读写接口 4 条测试通过
- [ ] 探针与分角色测试 4 条测试通过
- [ ] 迁移脚本幂等且 `--verify` 输出与老键一致
- [ ] `get_provider` / `get_tts` / `ocr_image` 全部改读 `resolve()`，现有调用方零改动
- [ ] 设置页 7 角色 UI 可用，旧版可一键回退
- [ ] `/api/config` 扁平 KV 接口保持可用
