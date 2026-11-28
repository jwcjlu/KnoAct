# 千问 Qwen-TTS 供应商实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 TTS 角色白名单中增加 `qwen`，用纯 HTTP 调用百炼 Qwen-TTS（`qwen3-tts-flash`），听写/朗读可合成可播放音频；失败仍走现有降级链。

**Architecture:** 对齐讯飞模式——协议与切分/WAV 合并在 `services/qwen_tts.py`；`tts.QwenTTS` 薄封装；`provider_registry` 只把 `qwen` 挂到 `tts`（不挂 llm/task）。Router 对商用合成结果做魔数探测设置 `media_type`，不改 `synthesize` 返回类型。

**Tech Stack:** FastAPI、`requests`、stdlib `wave`/`struct`、pytest + monkeypatch（不引入 dashscope SDK）。

**设计文档：** `docs/superpowers/specs/2026-11-28-qwen-tts-provider-design.md`

---

## 文件结构

- 修改 `backend/app/services/provider_registry.py` — `QWEN` + 挂到 `tts`
- 新建 `backend/app/services/qwen_tts.py` — 语种映射、切分、WAV 合并、HTTP 合成
- 修改 `backend/app/services/tts.py` — `QwenTTS`、`PROVIDERS`、`get_tts`、`sniff_audio_media_type`
- 修改 `backend/app/routers/tts_router.py` — 商用成功响应用嗅探结果作 `media_type`
- 新建 `backend/tests/test_qwen_tts.py` — 全部单测

---

### Task 1: Registry 加入 qwen（仅 tts）

**Files:**
- Modify: `backend/app/services/provider_registry.py`
- Test: `backend/tests/test_qwen_tts.py`（新建，先写 registry 断言）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_qwen_tts.py
from app.services.provider_registry import REGISTRY, find


def test_qwen_in_tts_not_in_llm():
    ids = {s.id for s in REGISTRY["tts"]}
    assert "qwen" in ids
    assert "qwen" not in {s.id for s in REGISTRY["llm"]}
    spec = find("qwen", "tts")
    assert spec.id == "qwen"
    assert spec.default_model == "qwen3-tts-flash"
    assert spec.needs_base_url is False
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_qwen_in_tts_not_in_llm -v`

Expected: FAIL（`qwen` 不在 tts）

- [ ] **Step 3: 最小实现**

在 `provider_registry.py` 中，于 `FAKE` 附近增加：

```python
QWEN = ProviderSpec("qwen", "千问", False, "qwen3-tts-flash")
```

并把 `REGISTRY["tts"]` 改为：

```python
"tts": (OPENAI, MINIMAX, XUNFEI, QWEN, FAKE),
```

**不要**改 `llm` / `task`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_qwen_in_tts_not_in_llm -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/provider_registry.py backend/tests/test_qwen_tts.py
git commit -m "feat(tts): 注册千问 qwen 为 TTS 供应商"
```

---

### Task 2: 语种映射与文本切分

**Files:**
- Create: `backend/app/services/qwen_tts.py`
- Modify: `backend/tests/test_qwen_tts.py`

- [ ] **Step 1: 写失败测试**

追加到 `test_qwen_tts.py`：

```python
from app.services.qwen_tts import map_language_type, split_for_qwen, _MAX_CHARS


def test_map_language_type():
    assert map_language_type("箩") == "Chinese"
    assert map_language_type("hello") == "English"
    assert map_language_type("123") == "Auto"


def test_split_short_unchanged():
    assert split_for_qwen("今天学习小数") == ["今天学习小数"]


def test_split_long_by_sentence_and_hard_cut():
    # 多句超过 600 字 → 按句切开，每段 ≤600
    sentence = "同学们好，我们开始上课。"  # 12 字
    text = sentence * 60  # 720 字
    parts = split_for_qwen(text)
    assert len(parts) > 1
    assert all(len(p) <= _MAX_CHARS for p in parts)
    assert "".join(parts) == text

    # 单句无标点且 >600 → 硬切
    long_one = "啊" * 650
    parts2 = split_for_qwen(long_one)
    assert len(parts2) == 2
    assert len(parts2[0]) == 600
    assert "".join(parts2) == long_one
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_map_language_type tests/test_qwen_tts.py::test_split_short_unchanged tests/test_qwen_tts.py::test_split_long_by_sentence_and_hard_cut -v`

Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

新建 `backend/app/services/qwen_tts.py`：

```python
"""阿里云百炼 Qwen-TTS 非实时语音合成（HTTP）。"""
from __future__ import annotations

import io
import re
import struct
import wave

_MAX_CHARS = 600
_DEFAULT_BASE = "https://dashscope.aliyuncs.com/api/v1"
_PATH = "/services/aigc/multimodal-generation/generation"


def map_language_type(text: str) -> str:
    from .tts import tts_lang_for_text

    lang = tts_lang_for_text(text or "")
    if lang == "zh":
        return "Chinese"
    if lang == "en":
        return "English"
    return "Auto"


def split_for_qwen(text: str, max_chars: int = _MAX_CHARS) -> list[str]:
    """按句切分；单句仍超限则硬切。保证拼接还原原文。"""
    body = text or ""
    if len(body) <= max_chars:
        return [body] if body.strip() else []

    parts = [p for p in re.split(r"(?<=[。！？；!?;])", body) if p]
    out: list[str] = []
    buf = ""
    for part in parts:
        while len(part) > max_chars:
            out.append(part[:max_chars])
            part = part[max_chars:]
        if len(buf + part) <= max_chars:
            buf += part
            continue
        if buf:
            out.append(buf)
        buf = part
    if buf:
        out.append(buf)
    return out
```

（WAV 合并与 `synthesize_qwen` 留到后续 Task，本文件先只有上述函数亦可；若 import 循环：`map_language_type` 内延迟 import `tts_lang_for_text` 已避免。）

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_map_language_type tests/test_qwen_tts.py::test_split_short_unchanged tests/test_qwen_tts.py::test_split_long_by_sentence_and_hard_cut -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/qwen_tts.py backend/tests/test_qwen_tts.py
git commit -m "feat(tts): 千问语种映射与 600 字切分"
```

---

### Task 3: WAV 安全合并

**Files:**
- Modify: `backend/app/services/qwen_tts.py`
- Modify: `backend/tests/test_qwen_tts.py`

- [ ] **Step 1: 写失败测试**

```python
import io
import wave


def _pcm_wav(pcm: bytes, *, rate=24000, channels=1, sampwidth=2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(sampwidth)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def test_merge_wav_segments():
    from app.services.qwen_tts import merge_audio_segments

    a = _pcm_wav(b"\x00\x01" * 100)
    b = _pcm_wav(b"\x02\x03" * 50)
    merged = merge_audio_segments([a, b])
    assert merged[:4] == b"RIFF"
    with wave.open(io.BytesIO(merged), "rb") as w:
        assert w.getnframes() == 100 + 50


def test_merge_single_passthrough():
    from app.services.qwen_tts import merge_audio_segments

    a = _pcm_wav(b"\x00\x01" * 10)
    assert merge_audio_segments([a]) == a


def test_merge_fmt_mismatch_raises():
    from app.services.qwen_tts import merge_audio_segments

    a = _pcm_wav(b"\x00\x01" * 10, rate=24000)
    b = _pcm_wav(b"\x00\x01" * 10, rate=16000)
    try:
        merge_audio_segments([a, b])
        assert False, "应因 fmt 不一致失败"
    except RuntimeError:
        pass
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_merge_wav_segments tests/test_qwen_tts.py::test_merge_single_passthrough tests/test_qwen_tts.py::test_merge_fmt_mismatch_raises -v`

Expected: FAIL

- [ ] **Step 3: 实现 `merge_audio_segments`**

追加到 `qwen_tts.py`：

```python
def _read_wav_pcm(data: bytes) -> tuple[bytes, int, int, int]:
    if not data.startswith(b"RIFF"):
        raise RuntimeError("qwen_tts_not_wav")
    with wave.open(io.BytesIO(data), "rb") as w:
        return w.readframes(w.getnframes()), w.getframerate(), w.getnchannels(), w.getsampwidth()


def merge_audio_segments(chunks: list[bytes]) -> bytes:
    if not chunks:
        raise RuntimeError("qwen_tts_empty_audio")
    if len(chunks) == 1:
        return chunks[0]
    pcms = []
    rate = ch = sw = None
    for raw in chunks:
        pcm, r, c, s = _read_wav_pcm(raw)
        if rate is None:
            rate, ch, sw = r, c, s
        elif (r, c, s) != (rate, ch, sw):
            raise RuntimeError("qwen_tts_wav_fmt_mismatch")
        pcms.append(pcm)
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(sw)
        w.setframerate(rate)
        w.writeframes(b"".join(pcms))
    return out.getvalue()
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_merge_wav_segments tests/test_qwen_tts.py::test_merge_single_passthrough tests/test_qwen_tts.py::test_merge_fmt_mismatch_raises -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/qwen_tts.py backend/tests/test_qwen_tts.py
git commit -m "feat(tts): 千问多段 WAV 安全合并"
```

---

### Task 4: HTTP synthesize_qwen

**Files:**
- Modify: `backend/app/services/qwen_tts.py`
- Modify: `backend/tests/test_qwen_tts.py`

- [ ] **Step 1: 写失败测试**

```python
def test_synthesize_requires_api_key():
    from app.services.qwen_tts import synthesize_qwen

    try:
        synthesize_qwen(text="你好", api_key="")
        assert False
    except RuntimeError as e:
        assert "Key" in str(e) or "key" in str(e).lower()


def test_synthesize_posts_and_downloads(monkeypatch):
    from app.services import qwen_tts as mod

    calls = {"post": 0, "get": 0}
    wav = _pcm_wav(b"\x00\x01" * 20)

    class FakeResp:
        def __init__(self, status, payload=None, content=b""):
            self.status_code = status
            self._payload = payload or {}
            self.content = content
            self.text = str(payload)

        def json(self):
            return self._payload

    def fake_post(url, headers=None, json=None, timeout=None):
        calls["post"] += 1
        assert "multimodal-generation" in url
        assert headers["Authorization"].startswith("Bearer sk-test")
        assert json["model"] == "qwen3-tts-flash"
        assert json["input"]["voice"] == "Cherry"
        assert json["input"]["language_type"] == "Chinese"
        assert "rate" not in json["input"] and "speed" not in json["input"]
        return FakeResp(200, {
            "output": {"audio": {"url": "https://example.com/a.wav"}},
            "code": "",
        })

    def fake_get(url, timeout=None):
        calls["get"] += 1
        assert url == "https://example.com/a.wav"
        return FakeResp(200, content=wav)

    monkeypatch.setattr(mod.requests, "post", fake_post)
    monkeypatch.setattr(mod.requests, "get", fake_get)

    out = mod.synthesize_qwen(text="你好", api_key="sk-test", voice="Cherry")
    assert out == wav
    assert calls["post"] == 1 and calls["get"] == 1
```

（`qwen_tts.py` 顶部需 `import requests`。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_synthesize_requires_api_key tests/test_qwen_tts.py::test_synthesize_posts_and_downloads -v`

Expected: FAIL

- [ ] **Step 3: 实现 `synthesize_qwen`**

```python
import requests


def synthesize_qwen(
    *,
    text: str,
    api_key: str,
    voice: str = "Cherry",
    model: str = "qwen3-tts-flash",
    base_url: str = "",
    speed: float = 1.0,  # 接受但不写入请求体（本期）
) -> bytes:
    if not (api_key or "").strip():
        raise RuntimeError("千问 API Key 未配置")
    body = (text or "").strip()
    if not body:
        raise RuntimeError("千问 TTS 文本为空")

    base = (base_url or "").rstrip("/") or _DEFAULT_BASE
    url = f"{base}{_PATH}"
    chunks_text = split_for_qwen(body)
    if not chunks_text:
        raise RuntimeError("千问 TTS 文本为空")

    audio_parts: list[bytes] = []
    for piece in chunks_text:
        payload = {
            "model": model or "qwen3-tts-flash",
            "input": {
                "text": piece,
                "voice": (voice or "Cherry").strip() or "Cherry",
                "language_type": map_language_type(piece),
            },
        }
        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"千问 TTS 失败：{resp.status_code} {resp.text[:200]}")
        data = resp.json()
        code = data.get("code") or ""
        if code:
            raise RuntimeError(f"千问 TTS 错误 code={code} {str(data.get('message') or '')[:160]}")
        audio_url = ((data.get("output") or {}).get("audio") or {}).get("url") or ""
        if not audio_url:
            raise RuntimeError("千问 TTS 未返回音频 URL")
        ar = requests.get(audio_url, timeout=60)
        if ar.status_code != 200 or not ar.content:
            raise RuntimeError(f"千问 TTS 下载失败：{ar.status_code}")
        audio_parts.append(ar.content)

    return merge_audio_segments(audio_parts)
```

注意：`speed` 参数保留以兼容 `TTSProvider.synthesize(..., speed=)`，**不写入 JSON**。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_synthesize_requires_api_key tests/test_qwen_tts.py::test_synthesize_posts_and_downloads -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/qwen_tts.py backend/tests/test_qwen_tts.py
git commit -m "feat(tts): 千问 Qwen-TTS HTTP 非实时合成"
```

---

### Task 5: QwenTTS 封装 + get_tts 接线

**Files:**
- Modify: `backend/app/services/tts.py`
- Modify: `backend/tests/test_qwen_tts.py`

- [ ] **Step 1: 写失败测试**

```python
from app.database import SessionLocal
from app.models import ModelConnection, ModelProfile, RoleBinding
from app.services.tts import get_tts, QwenTTS
# 复用 test_model_config._clear 或同等清表逻辑，避免脏 binding


def test_qwen_tts_requires_key():
    p = QwenTTS(api_key="")
    try:
        p.synthesize("测")
        assert False
    except RuntimeError:
        pass


def test_get_tts_uses_qwen_binding():
    from tests.test_model_config import _clear  # 若不可 import，内联同样的 delete

    db = SessionLocal()
    _clear(db)
    conn = ModelConnection(provider="qwen", name="qw", api_key="sk-qwen")
    db.add(conn)
    db.flush()
    prof = ModelProfile(
        role="tts",
        connection_id=conn.id,
        model="qwen3-tts-flash",
        options='{"voice":"Cherry"}',
    )
    db.add(prof)
    db.flush()
    db.add(RoleBinding(role="tts", profile_id=prof.id))
    db.commit()

    t = get_tts(db)
    assert isinstance(t, QwenTTS)
    assert t.name == "qwen"
    assert t.api_key == "sk-qwen"
    assert t.model == "qwen3-tts-flash"
    assert t.voice == "Cherry"
    db.close()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_qwen_tts_requires_key tests/test_qwen_tts.py::test_get_tts_uses_qwen_binding -v`

Expected: FAIL（`QwenTTS` 未定义）

- [ ] **Step 3: 实现**

在 `tts.py` 的 `FakeTTS` 之前插入：

```python
class QwenTTS(TTSProvider):
    name = "qwen"

    def __init__(self, voice: str = "", api_key: str = "", base_url: str = "", model: str = ""):
        super().__init__(voice=voice, api_key=api_key)
        self.base_url = base_url
        self.model = model or "qwen3-tts-flash"

    def synthesize(self, text, voice="", speed=1.0):
        from .qwen_tts import synthesize_qwen

        return synthesize_qwen(
            text=text,
            api_key=self.api_key,
            voice=voice or self.voice or "Cherry",
            model=self.model,
            base_url=self.base_url,
            speed=speed,
        )
```

更新：

```python
PROVIDERS = {
    "minimax": MiniMaxTTS,
    "xunfei": XunfeiTTS,
    "openai": OpenAITTS,
    "qwen": QwenTTS,
    "fake": FakeTTS,
}
```

在 `get_tts` 中，于 `XunfeiTTS` 分支后、`return cls(...)` 前增加：

```python
    if cls is QwenTTS:
        return cls(
            voice=voice,
            api_key=r.api_key,
            base_url=r.base_url or "",
            model=r.model or "qwen3-tts-flash",
        )
```

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_qwen_tts_requires_key tests/test_qwen_tts.py::test_get_tts_uses_qwen_binding -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tts.py backend/tests/test_qwen_tts.py
git commit -m "feat(tts): 接线 QwenTTS 到 get_tts"
```

---

### Task 6: Router media_type 魔数探测

**Files:**
- Modify: `backend/app/services/tts.py` — 增加 `sniff_audio_media_type`
- Modify: `backend/app/routers/tts_router.py`
- Modify: `backend/tests/test_qwen_tts.py`（及必要时 `test_tts.py`）

- [ ] **Step 1: 写失败测试**

```python
from app.services.tts import sniff_audio_media_type


def test_sniff_audio_media_type():
    assert sniff_audio_media_type(b"RIFF...." + b"\x00" * 20) == "audio/wav"
    assert sniff_audio_media_type(b"ID3" + b"\x00" * 20) == "audio/mpeg"
    assert sniff_audio_media_type(b"\xff\xfb" + b"\x00" * 20) == "audio/mpeg"
    assert sniff_audio_media_type(b"????") == "audio/mpeg"  # 默认仍 mpeg，兼容旧客户端
```

端点测试（照抄 `test_tts.py` 的 app/client 样板）：

```python
def test_tts_endpoint_qwen_returns_wav_content_type(setup_db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.database import SessionLocal
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.services.tts import TTSProvider
    from conftest import make_account, auth_headers

    wav = _pcm_wav(b"\x00\x01" * 40)

    class Stub(TTSProvider):
        name = "qwen"

        def synthesize(self, text, voice="", speed=1.0):
            return wav

    monkeypatch.setattr(tts_router, "get_tts", lambda db: Stub())
    monkeypatch.setattr(tts_router, "word_audio", lambda text: None)

    s = SessionLocal()
    u = make_account(s, "u_tts_qwen_wav", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=你好", headers=h)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/wav")
    assert resp.content[:4] == b"RIFF"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py::test_sniff_audio_media_type -v`

Expected: FAIL

- [ ] **Step 3: 实现嗅探 + router**

`tts.py`：

```python
def sniff_audio_media_type(data: bytes) -> str:
    if data.startswith(b"RIFF"):
        return "audio/wav"
    if data.startswith(b"ID3") or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    return "audio/mpeg"
```

`tts_router.py` 商用成功分支改为：

```python
            audio = tts.synthesize(text, voice=voice, speed=speed)
            from ..services.tts import sniff_audio_media_type
            return Response(content=audio, media_type=sniff_audio_media_type(audio))
```

真人词典与 public 分支保持 `audio/mpeg`。

- [ ] **Step 4: 跑相关测试**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py tests/test_tts.py -v`

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/tts.py backend/app/routers/tts_router.py backend/tests/test_qwen_tts.py backend/tests/test_tts.py
git commit -m "fix(tts): 按魔数设置合成音频 Content-Type"
```

---

### Task 7: 全量回归与手测清单

**Files:** 无新代码（除非修失败）

- [ ] **Step 1: 跑 TTS / model_config 相关测试**

Run: `cd backend && python -m pytest tests/test_qwen_tts.py tests/test_tts.py tests/test_xunfei_tts.py tests/test_model_config.py -v`

Expected: PASS

- [ ] **Step 2: 手测清单（有 Key 时）**

1. 运营后台新建 Connection：`provider=qwen`，填百炼 API Key  
2. TTS Profile：model=`qwen3-tts-flash`，voice=`Cherry`  
3. RoleBinding 绑定 `tts`  
4. `GET /api/tts/synthesize?text=快乐`（登录）→ 可播放；`Content-Type` 为 wav 或 mpeg  
5. 错误 Key → 不 500，降级 public/browser  

- [ ] **Step 3: 最终 commit（若有修复）**

无修复则跳过。有修复则按改动写消息提交。

---

## 完成定义

- [x] Spec 要求的文件均已改/建  
- [ ] `qwen` 仅在 `tts` 白名单  
- [ ] 缺 Key / 上游失败走降级，不 500  
- [ ] 多段 WAV 可合并且 fmt 不一致会失败  
- [ ] Router 对 WAV 返回正确 Content-Type  
- [ ] 本期请求不传 speed  
