# 商业 TTS 磁盘缓存 + 听写预热 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 商用 TTS 合成结果落盘复用；听写任务生成后后台预热 `speak_text`/`word`，降低孩子首听冷启动。

**Architecture:** 在 `tts.py` 增加与真人 `tts_cache` 分离的 `tts_synth_cache`（键含 provider/model/voice/speed/text）；`tts_router` 商用路径先查缓存再合成。新建 `tts_warmup.py`：从听写 task `content` 收集文本、串行合成写缓存；`generate_tasks_for_user` commit 后按 task 启 daemon 线程（自开 `SessionLocal`）。不改前端。

**Tech Stack:** FastAPI、SQLAlchemy、stdlib `hashlib`/`os`/`threading`、pytest + monkeypatch。

**设计文档：** `docs/superpowers/specs/2026-11-28-tts-synth-cache-warmup-design.md`

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `backend/app/services/tts.py` | 新增 synth 缓存读写 + `synthesize_commercial_cached`；复用现有 `_read_cache`/`_write_cache` 模式 |
| `backend/app/routers/tts_router.py` | 商用路径改调 `synthesize_commercial_cached` |
| `backend/app/services/tts_warmup.py` | **新建**：收集文本、预热、调度线程 |
| `backend/app/services/task_gen.py` | `generate_tasks_for_user` commit 后调度听写预热 |
| `backend/tests/test_tts_synth_cache.py` | **新建**：缓存键/命中/路由 |
| `backend/tests/test_tts_warmup.py` | **新建**：收集、预热、失败静默、fake 跳过 |

**不改：** Flutter / frontend / parent-web；`word_audio` / `uploads/tts_cache`；各 TTS provider 内部。

---

### Task 1: synth 缓存键与读写

**Files:**
- Modify: `backend/app/services/tts.py`（在 `# ===== 听写真人录音 + 磁盘缓存 =====` 段落后追加 synth 段）
- Create: `backend/tests/test_tts_synth_cache.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_tts_synth_cache.py
import os
from app.services import tts as tts_mod


def test_synth_cache_path_stable_and_sensitive(tmp_path, monkeypatch):
    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))
    a = tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Cherry", 1.0, "你好")
    b = tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Cherry", 1.0, "你好")
    assert a == b
    assert "qwen_" in os.path.basename(a)
    # speed / voice / provider / model / text 任一不同 → 路径不同
    assert a != tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Cherry", 1.2, "你好")
    assert a != tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Ethan", 1.0, "你好")
    assert a != tts_mod._synth_cache_path("minimax", "qwen3-tts-flash", "Cherry", 1.0, "你好")
    assert a != tts_mod._synth_cache_path("qwen", "other-model", "Cherry", 1.0, "你好")
    assert a != tts_mod._synth_cache_path("qwen", "qwen3-tts-flash", "Cherry", 1.0, "你好啊")


def test_synth_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))
    data = b"ID3" + b"\x00" * 300
    tts_mod.put_synth_cache("qwen", "m", "v", 1.0, "测", data)
    assert tts_mod.find_synth_cache("qwen", "m", "v", 1.0, "测") == data
    assert tts_mod.find_synth_cache("qwen", "m", "v", 1.2, "测") is None
```

对外 API 以 `put_synth_cache` / `find_synth_cache` / `_synth_cache_path` 为准（内部可复用 `_read_cache` / `_write_cache`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_tts_synth_cache.py::test_synth_cache_path_stable_and_sensitive tests/test_tts_synth_cache.py::test_synth_cache_roundtrip -v`

Expected: FAIL（符号不存在）

- [ ] **Step 3: 最小实现**

在 `tts.py` 追加（可复用已有 `_read_cache` / `_write_cache`）：

```python
_SYNTH_CACHE_DIR = "uploads/tts_synth_cache"


def _synth_cache_key(provider: str, model: str, voice: str, speed: float, text: str) -> str:
    import hashlib
    raw = f"{provider}|{model}|{voice}|{speed:.2f}|{text}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _synth_ext_for_bytes(data: bytes) -> str:
    mt = sniff_audio_media_type(data)
    if "wav" in mt:
        return ".wav"
    if "mpeg" in mt or "mp3" in mt:
        return ".mp3"
    return ".bin"


def _synth_cache_path(provider: str, model: str, voice: str, speed: float, text: str, ext: str = ".bin") -> str:
    import os
    key = _synth_cache_key(provider, model, voice, speed, text)
    return os.path.join(_SYNTH_CACHE_DIR, f"{provider}_{key}{ext}")


def find_synth_cache(provider: str, model: str, voice: str, speed: float, text: str) -> bytes | None:
    """尝试常见扩展名读盘（写时带真实 ext，读时不知 ext）。"""
    import os
    key = _synth_cache_key(provider, model, voice, speed, text)
    base = os.path.join(_SYNTH_CACHE_DIR, f"{provider}_{key}")
    for ext in (".mp3", ".wav", ".bin", ""):
        hit = _read_cache(base + ext if ext else base)
        if hit is not None:
            return hit
    return None


def put_synth_cache(provider: str, model: str, voice: str, speed: float, text: str, data: bytes) -> str:
    path = _synth_cache_path(provider, model, voice, speed, text, _synth_ext_for_bytes(data))
    _write_cache(path, data)
    return path
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_tts_synth_cache.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tts.py backend/tests/test_tts_synth_cache.py
git commit -m "feat(tts): 商业合成磁盘缓存读写与键"
```

---

### Task 2: `synthesize_commercial_cached`

**Files:**
- Modify: `backend/app/services/tts.py`
- Modify: `backend/tests/test_tts_synth_cache.py`

- [ ] **Step 1: 写失败测试**

```python
def test_synthesize_commercial_cached_hits_disk(db, tmp_path, monkeypatch):
    from app.services import tts as tts_mod
    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))

    calls = {"n": 0}

    class Stub:
        name = "qwen"
        voice = "Cherry"
        model = "qwen3-tts-flash"

        def synthesize(self, text, voice="", speed=1.0):
            calls["n"] += 1
            return b"ID3" + b"\x01" * 300

    monkeypatch.setattr(tts_mod, "get_tts", lambda db, child_id=None: Stub())
    monkeypatch.setattr(
        "app.services.model_config.resolve",
        lambda db, role, child_id=None: type("R", (), {
            "provider": "qwen", "model": "qwen3-tts-flash",
            "options": {"voice": "Cherry", "speed": 1.0},
        })(),
    )

    a = tts_mod.synthesize_commercial_cached(db, "你好", voice="", speed=1.0)
    b = tts_mod.synthesize_commercial_cached(db, "你好", voice="", speed=1.0)
    assert a == b and calls["n"] == 1


def test_synthesize_commercial_cached_skips_fake(db, monkeypatch):
    from app.services import tts as tts_mod
    monkeypatch.setattr(tts_mod, "get_tts", lambda db, child_id=None: tts_mod.FakeTTS())
    try:
        tts_mod.synthesize_commercial_cached(db, "你好")
        assert False, "fake 应抛错让调用方走降级，且不写缓存"
    except RuntimeError as e:
        assert "fake" in str(e).lower() or "skip" in str(e).lower()
```

`resolve` 的 monkeypatch 路径以实现为准：若 `synthesize_commercial_cached` 内 `from .model_config import resolve`，需 patch `app.services.tts.resolve` 或把 provider/model 从 Stub + resolve 一并取得。更简单：函数内用 `get_tts` 的 `name`/`voice`/`model`（缺 model 用 `resolve().model or ""`）。

推荐实现签名：

```python
def synthesize_commercial_cached(
    db: Session,
    text: str,
    *,
    voice: str = "",
    speed: float = 1.0,
    child_id: int | None = None,
) -> bytes:
    """商用合成 + synth 缓存。fake 抛 RuntimeError；不写公开/真人缓存。"""
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_tts_synth_cache.py::test_synthesize_commercial_cached_hits_disk -v`

Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
def synthesize_commercial_cached(db, text, *, voice="", speed=1.0, child_id=None) -> bytes:
    import logging
    from .model_config import resolve

    text = (text or "").strip()
    if not text:
        raise RuntimeError("empty_tts_text")
    tts = get_tts(db, child_id)
    if tts.name == "fake":
        raise RuntimeError("tts_fake_skip_cache")
    r = resolve(db, "tts", child_id)
    provider = tts.name
    model = (getattr(tts, "model", None) or r.model or "").strip()
    use_voice = (voice or tts.voice or r.options.get("voice") or "").strip()
    cached = find_synth_cache(provider, model, use_voice, float(speed), text)
    if cached is not None:
        logging.getLogger(__name__).info(
            "tts_synth_cache hit provider=%s text_len=%s", provider, len(text)
        )
        return cached
    logging.getLogger(__name__).info(
        "tts_synth_cache miss provider=%s text_len=%s", provider, len(text)
    )
    audio = tts.synthesize(text, voice=use_voice, speed=speed)
    if audio and len(audio) > 200:
        put_synth_cache(provider, model, use_voice, float(speed), text, audio)
        logging.getLogger(__name__).info(
            "tts_synth_cache write provider=%s text_len=%s", provider, len(text)
        )
    return audio
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_tts_synth_cache.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tts.py backend/tests/test_tts_synth_cache.py
git commit -m "feat(tts): synthesize_commercial_cached 命中跳过上游"
```

---

### Task 3: 路由接入商用缓存

**Files:**
- Modify: `backend/app/routers/tts_router.py`
- Modify: `backend/tests/test_tts_synth_cache.py`（或扩展 `test_qwen_tts.py` 风格的 TestClient 测）

- [ ] **Step 1: 写失败测试**

```python
def test_synthesize_endpoint_uses_synth_cache(setup_db, monkeypatch, tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.database import SessionLocal
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.services import tts as tts_mod
    from app.services.tts import TTSProvider
    from conftest import make_account, auth_headers

    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))
    calls = {"n": 0}

    class Stub(TTSProvider):
        name = "qwen"
        model = "qwen3-tts-flash"

        def __init__(self):
            super().__init__(voice="Cherry", api_key="x")

        def synthesize(self, text, voice="", speed=1.0):
            calls["n"] += 1
            return b"ID3" + b"\x02" * 300

    # 路由改为 get_tts(db, child_id) 后，补丁签名必须兼容第二参，否则 TypeError
    monkeypatch.setattr(tts_router, "get_tts", lambda db, child_id=None: Stub())
    monkeypatch.setattr(tts_router, "word_audio", lambda text: None)
    monkeypatch.setattr(tts_mod, "get_tts", lambda db, child_id=None: Stub())

    s = SessionLocal()
    u = make_account(s, "u_synth_cache", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    r1 = c.get("/api/tts/synthesize?text=你好&real=false", headers=h)
    r2 = c.get("/api/tts/synthesize?text=你好&real=false", headers=h)
    assert r1.status_code == 200 and r2.status_code == 200
    assert calls["n"] == 1
```

`real=false` 跳过真人，强制走商用路径。若 `conftest.setup_db` 名称不同，对齐仓库现有 fixture（见 `test_qwen_tts.py`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_tts_synth_cache.py::test_synthesize_endpoint_uses_synth_cache -v`

Expected: FAIL 或 `calls["n"] == 2`（尚未走缓存）

- [ ] **Step 3: 改路由**

`tts_router.py` 商用段改为（**必须**把 `_auth.id` 当 `child_id` 传入，与预热一致；孩子 TTS overlay 时缓存键才对得上）：

```python
from ..services.tts import (
    get_tts, sniff_audio_media_type, synthesize_public_mp3,
    word_audio, synthesize_commercial_cached,
)
# ...
    child_id = _auth.id if getattr(_auth, "role", None) == "child" else None
    tts = get_tts(db, child_id)
    configured = tts.name != "fake"
    if speed is None:
        speed = _configured_speed(db)  # 若 _configured_speed 已支持 child_id，改为传入 child_id
        # 推荐：扩展 _configured_speed(db, child_id=None)，内部 resolve(db, "tts", child_id)
    if configured:
        try:
            audio = synthesize_commercial_cached(
                db, text, voice=voice, speed=speed, child_id=child_id,
            )
            return Response(content=audio, media_type=sniff_audio_media_type(audio))
        except Exception as e:
            upstream_err = str(e)
```

同步改 `_configured_speed(db, child_id=None)`，内部 `resolve(db, "tts", child_id)`。预热与路由**两边都传**同一套 `child_id` 语义，禁止一边带一边不带。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_tts_synth_cache.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/tts_router.py backend/tests/test_tts_synth_cache.py
git commit -m "feat(tts): /api/tts/synthesize 商用路径走磁盘缓存"
```

---

### Task 4: 从听写 content 收集预热文本

**Files:**
- Create: `backend/app/services/tts_warmup.py`
- Create: `backend/tests/test_tts_warmup.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_tts_warmup.py
from app.services.tts_warmup import collect_dictation_warmup_texts


def test_collect_speak_text_and_word():
    items = [
        {"word": "事", "speak_text": "事，事情的事"},
        {"word": "hello"},  # 无 speak_text
        {"word": "同", "speak_text": "同"},  # 与 word 相同 → 只一条
        {"word": "x", "speak_text": "x", "dictation_cue": '{"compound":"事情"}'},
    ]
    texts = collect_dictation_warmup_texts(items)
    assert "事，事情的事" in texts
    assert "事" in texts  # ≠ speak_text
    assert "hello" in texts
    assert texts.count("同") == 1
    # 不得把 cue JSON 当合成文本
    assert not any("compound" in t or "{" in t for t in texts)


def test_collect_from_json_string():
    import json
    raw = json.dumps([{"word": "啊", "speak_text": "啊，惊讶的啊"}], ensure_ascii=False)
    texts = collect_dictation_warmup_texts(raw)
    assert "啊，惊讶的啊" in texts and "啊" in texts


def test_collect_caps_at_40():
    items = [{"word": f"w{i}", "speak_text": f"s{i}"} for i in range(30)]
    texts = collect_dictation_warmup_texts(items)
    assert len(texts) <= 40
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_tts_warmup.py::test_collect_speak_text_and_word -v`

Expected: FAIL

- [ ] **Step 3: 最小实现**

```python
# backend/app/services/tts_warmup.py
from __future__ import annotations
import json
import logging

logger = logging.getLogger(__name__)
_MAX_TEXTS_PER_TASK = 40


def collect_dictation_warmup_texts(content) -> list[str]:
    """从听写 task.content（list 或 JSON 字符串）收集去重后的可播文本。"""
    if isinstance(content, str):
        try:
            content = json.loads(content or "[]")
        except json.JSONDecodeError:
            return []
    if not isinstance(content, list):
        return []
    out: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = (s or "").strip()
        if not s or s in seen:
            return
        seen.add(s)
        out.append(s)

    for item in content:
        if not isinstance(item, dict):
            continue
        speak = (item.get("speak_text") or "").strip()
        word = (item.get("word") or "").strip()
        if speak:
            add(speak)
        if word and word != speak:
            add(word)
        elif word and not speak:
            add(word)
        if len(out) >= _MAX_TEXTS_PER_TASK:
            break
    return out[:_MAX_TEXTS_PER_TASK]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_tts_warmup.py -v`

Expected: PASS（仅 collect 相关）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tts_warmup.py backend/tests/test_tts_warmup.py
git commit -m "feat(tts): 听写预热文本收集（speak_text/word）"
```

---

### Task 5: 预热执行与调度（daemon + SessionLocal）

**Files:**
- Modify: `backend/app/services/tts_warmup.py`
- Modify: `backend/tests/test_tts_warmup.py`

- [ ] **Step 1: 写失败测试**

```python
def test_warmup_dictation_task_calls_cached_synth(db, monkeypatch, tmp_path):
    from app.models import Task
    from app.services import tts_warmup as wu
    from app.services import tts as tts_mod
    from conftest import make_account
    from datetime import date
    import json

    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))
    seen = []

    def fake_cached(db, text, *, voice="", speed=1.0, child_id=None):
        seen.append(text)
        return b"ID3" + b"\x00" * 300

    monkeypatch.setattr(wu, "synthesize_commercial_cached", fake_cached)

    class Stub:
        name = "qwen"
        voice = "Cherry"
        model = "m"
        def synthesize(self, *a, **k):
            return b"ID3" + b"\x00" * 300
    monkeypatch.setattr(wu, "get_tts", lambda db, child_id=None: Stub())

    u = make_account(db, "u_warmup_synth", "child")
    db.commit()
    content = json.dumps([
        {"word": "事", "speak_text": "事，事情的事"},
        {"word": "go"},
    ], ensure_ascii=False)
    t = Task(
        user_id=u.id, task_type="dictation", subject="语文",
        title="t", detail="d", content=content, points=20,
        date=date.today(),
    )
    db.add(t)
    db.commit()
    db.refresh(t)

    wu.warmup_dictation_task(t.id)
    assert "事，事情的事" in seen
    assert "事" in seen
    assert "go" in seen
    assert not any("{" in x for x in seen)


def test_warmup_skips_fake(db, monkeypatch):
    from app.services import tts_warmup as wu
    from app.services.tts import FakeTTS
    called = []
    monkeypatch.setattr(wu, "get_tts", lambda db, child_id=None: FakeTTS())
    monkeypatch.setattr(
        wu, "synthesize_commercial_cached",
        lambda *a, **k: called.append(1) or b"x",
    )
    # 需要真实 task id；或直接测内部早退
    assert wu._should_skip_warmup(FakeTTS()) is True
    assert called == []


def test_warmup_item_failure_continues(db, monkeypatch, tmp_path):
    from app.models import Task
    from app.services import tts_warmup as wu
    from conftest import make_account
    from datetime import date
    import json

    texts_ok = []

    def flaky(db, text, **kwargs):
        if "fail" in text:
            raise RuntimeError("boom")
        texts_ok.append(text)
        return b"ID3" + b"\x00" * 300

    monkeypatch.setattr(wu, "synthesize_commercial_cached", flaky)
    class Stub:
        name = "qwen"
        voice = ""
    monkeypatch.setattr(wu, "get_tts", lambda db, child_id=None: Stub())

    u = make_account(db, "u_warmup_fail", "child")
    db.commit()
    content = json.dumps([
        {"word": "fail"},
        {"word": "ok"},
    ], ensure_ascii=False)
    t = Task(
        user_id=u.id, task_type="dictation", subject="语文",
        title="t", detail="d", content=content, points=20, date=date.today(),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    wu.warmup_dictation_task(t.id)  # 不得抛
    assert "ok" in texts_ok
```

`Task` 必填字段对齐 `models.Task`。**一律**先 `make_account` 再建 Task，禁止写死 `user_id=1`（开 FK 会 `IntegrityError`）。

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_tts_warmup.py -v`

Expected: FAIL（缺 `warmup_dictation_task`）

- [ ] **Step 3: 实现预热与调度**

```python
# 续 tts_warmup.py
from .tts import get_tts, synthesize_commercial_cached
from .model_config import resolve


def _should_skip_warmup(tts) -> bool:
    return getattr(tts, "name", "") == "fake"


def _configured_speed(db, child_id=None) -> float:
    try:
        raw = (resolve(db, "tts", child_id).options or {}).get("speed")
        val = float(raw)
    except (TypeError, ValueError):
        return 1.0
    return max(0.5, min(2.0, val))


def warmup_dictation_task(task_id: int) -> None:
    """自开 Session；失败吞掉。供线程目标调用。"""
    from ..database import SessionLocal
    from ..models import Task

    db = SessionLocal()
    try:
        task = db.query(Task).filter_by(id=task_id, task_type="dictation").first()
        if not task:
            return
        tts = get_tts(db, task.user_id)
        if _should_skip_warmup(tts):
            logger.info("warmup skip fake task_id=%s", task_id)
            return
        texts = collect_dictation_warmup_texts(task.content)
        logger.info(
            "warmup start task_id=%s user_id=%s n=%s",
            task_id, task.user_id, len(texts),
        )
        speed = _configured_speed(db, task.user_id)
        voice = (tts.voice or "")
        for text in texts:
            try:
                synthesize_commercial_cached(
                    db, text, voice=voice, speed=speed, child_id=task.user_id,
                )
            except Exception as e:
                logger.info(
                    "warmup item_fail task_id=%s text_len=%s err=%s",
                    task_id, len(text), str(e)[:120],
                )
        logger.info("warmup done task_id=%s", task_id)
    except Exception as e:
        logger.info("warmup abort task_id=%s err=%s", task_id, str(e)[:120])
    finally:
        db.close()


def schedule_dictation_warmup(task_id: int) -> None:
    """短命 daemon 线程；不阻塞调用方。"""
    import threading
    threading.Thread(
        target=warmup_dictation_task, args=(task_id,), daemon=True, name=f"tts-warmup-{task_id}",
    ).start()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_tts_warmup.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tts_warmup.py backend/tests/test_tts_warmup.py
git commit -m "feat(tts): 听写任务后台预热（失败静默）"
```

---

### Task 6: 接入 `generate_tasks_for_user`

**Files:**
- Modify: `backend/app/services/task_gen.py`
- Modify: `backend/tests/test_tts_warmup.py`（或现有 `test_task_gen*.py`）

- [ ] **Step 1: 写失败测试**

只测「本轮新建 dictation」调度（**不要**做扫全日 dictation 的 helper）：

```python
def test_schedule_only_new_dictation_ids(monkeypatch):
    from app.services import task_gen
    scheduled = []
    monkeypatch.setattr(
        "app.services.tts_warmup.schedule_dictation_warmup",
        lambda task_id: scheduled.append(task_id),
    )
    task_gen._schedule_dictation_warmups([11, 22])
    assert scheduled == [11, 22]


def test_schedule_swallows_errors(monkeypatch):
    from app.services import task_gen

    def boom(_tid):
        raise RuntimeError("nope")

    monkeypatch.setattr("app.services.tts_warmup.schedule_dictation_warmup", boom)
    task_gen._schedule_dictation_warmups([1])  # 不得抛
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_tts_warmup.py::test_schedule_only_new_dictation_ids -v`

Expected: FAIL

- [ ] **Step 3: 接线（仅本轮新建 id）**

在 `task_gen.py`：

```python
def _schedule_dictation_warmups(task_ids: list[int]) -> None:
    from .tts_warmup import schedule_dictation_warmup
    for tid in task_ids:
        try:
            schedule_dictation_warmup(tid)
        except Exception:
            pass
```

在 `generate_tasks_for_user` 里收集本轮新建的 dictation id：

```python
def generate_tasks_for_user(...):
    warmed_ids: list[int] = []   # 必须在 for subject 之外初始化
    for subject in subjects:
        ...
        for gen in gens:
            if gen is not None:
                gen.user_id = user_id
                gen.date = day
                gen.bucket_id = bucket.id
                db.add(gen)
                db.flush()
                if gen.task_type == "dictation" and gen.id:
                    warmed_ids.append(gen.id)
        # bank practice 等若产生 dictation 也 append 到同一 warmed_ids
    db.commit()   # 现有那一次 commit（函数末尾）
    _schedule_dictation_warmups(warmed_ids)
```

**硬约束：** `warmed_ids = []` 放在 `for subject in subjects:` **之外**；若放进循环内每科清空，最终只会预热最后一科，语文/英语会静默丢失。

**不要**实现「按 user+day 扫全部 dictation」的 helper。只收集 `task_type == "dictation"`（`_gen_review` 是 `review`，不要误收）。在现有结构上加 `flush`/`warmed_ids`，**不要**整段替换函数。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_tts_warmup.py tests/test_tts_synth_cache.py -v`

Expected: PASS

另跑（若存在）：`cd backend && python -m pytest tests/test_task_gen.py -v` 或相关任务生成测试，确认无回归。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/task_gen.py backend/tests/test_tts_warmup.py
git commit -m "feat(tts): 听写任务生成后调度后台预热"
```

---

### Task 7: 回归烟测

- [ ] **Step 1: 全量相关测试**

修 `tests/test_qwen_tts.py`（及同类端点测）：路由已走 `synthesize_commercial_cached` → 内部调 `app.services.tts.get_tts`，**只** patch `tts_router.get_tts` 不够（configured 用 Stub 过了，合成仍拿真实 fake → 降级公开 MP3，`audio/wav` 断言挂）。范本对齐 Task 3：

```python
monkeypatch.setattr(tts_router, "get_tts", lambda db, child_id=None: Stub())
monkeypatch.setattr(tts_mod, "get_tts", lambda db, child_id=None: Stub())
# 或直接 monkeypatch.setattr(tts_router, "synthesize_commercial_cached", lambda db, text, **kw: wav)
```

Run:

```bash
cd backend && python -m pytest tests/test_tts_synth_cache.py tests/test_tts_warmup.py tests/test_tts.py tests/test_qwen_tts.py -v
```

Expected: PASS

- [ ] **Step 2: 手工烟测（可选）**

1. 配置非 fake TTS，调用两次 `GET /api/tts/synthesize?text=你好&real=false`，第二次应明显更快 / 日志 `tts_synth_cache hit`。
2. 触发 `generate_tasks_for_user` 后日志出现 `warmup start` / `warmup done`。
3. 确认 `uploads/tts_synth_cache/` 与 `uploads/tts_cache/` 分离。

- [ ] **Step 3: Commit（若有测试修复）**

无代码改动可跳过。

---

## 实现注意

1. **PowerShell**：命令用 `;` 连接，不用 `&&`（或始终 `cd backend` 后单条跑 pytest）。
2. **课堂报读未合并时**：content 无 `speak_text`，预热只收集 `word`，符合 spec。
3. **不要**把 `dictation_cue` JSON 加入预热列表。
4. **不要**在无 HTTP 请求的 `task_gen` 里用 `BackgroundTasks`。
5. 工作目录跑后端须在 `backend/`，缓存相对路径 `uploads/tts_synth_cache` 落在 cwd 下。
