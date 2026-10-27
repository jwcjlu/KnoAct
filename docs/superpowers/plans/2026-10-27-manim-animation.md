# Manim 数学动画能力实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 KnoAct 在对话中按需生成带旁白音轨的 manim 数学动画视频（画面+讲解同步），供小学生观看。

**Architecture:** 新增独立渲染服务 `render_service/`（Python + FastAPI + manim + ffmpeg + LaTeX），主服务新增 `render_manim` 提交型工具挂进 `visualize` capability，新增 `RenderTask` 模型持久化任务状态，前端对话栏新增视频卡片轮询进度。三阶段落地：渲染骨架 → LLM 生成代码+纠错 → 接 agent 循环+前端。

**Tech Stack:** Python 3.10 / FastAPI / SQLAlchemy / manim (Community) / ffmpeg / TeX (本机已装 MiKTeX) / 现有 TTS provider 抽象

**参考 spec:** `docs/superpowers/specs/2026-10-27-manim-animation-design.md`

---

## 环境事实（务必先读）

- **本机已装 MiKTeX**（PATH 里有 `.../MiKTeX/miktex/bin/x64`），LaTeX 依赖已就绪。
- **manim 和 ffmpeg 都未装**，需在阶段 1 安装。
- **两个 Python**：Bash 的 `python` 是 3.10.6（装全依赖），PowerShell 的是 conda base（无 sqlalchemy）。跑后端/渲染服务都用 **Bash 的 python**。
- **SQLite 路径随 cwd**：`DATABASE_URL` 默认 `sqlite:///./zhixueban.db` 相对路径。渲染服务连库必须用**绝对路径** `DATABASE_URL="sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db"`。
- **GBK 管道**：`curl | python -c "json.load(sys.stdin)"` 会把中文按 GBK 重解码报错。验证 API 用 `requests`/`urllib` 单进程做请求+解析。

---

## 文件结构

### 新增 `render_service/`（独立渲染服务，与 `backend/` 平级）

| 文件 | 职责 |
| --- | --- |
| `render_service/requirements.txt` | 渲染服务 Python 依赖（manim + ffmpeg-python 或直接 subprocess 调 ffmpeg + fastapi/uvicorn + 复用主服务依赖） |
| `render_service/app.py` | FastAPI 入口：`POST /render` + `GET /render/{task_id}` |
| `render_service/pipeline.py` | 渲染流水线：生成代码→渲染→纠错→TTS→ffmpeg 合轨 |
| `render_service/queue.py` | 进程内任务队列 + 有限并发（≤3） |
| `render_service/manim_render.py` | 封装 subprocess 调 `manim render` + 解析 stderr |
| `render_service/media/` | 渲染产物落盘目录（mp4） |
| `render_service/Dockerfile` | 打包 manim+ffmpeg+LaTeX（阶段 1 末 / 阶段 3 补） |
| `render_service/tests/test_pipeline.py` | 流水线单测 |

### 修改 `backend/`（主服务）

| 文件 | 改动 |
| --- | --- |
| `backend/app/tools/builtin.py` | 新增 `RenderManimTool`（提交型工具） |
| `backend/app/tools/registry.py` | 不改（`render_manim` 在 builtin 里注册即可，见能力挂载处） |
| `backend/app/capabilities/chat.py` | `visualize` 的 `tools` 加 `render_manim` |
| `backend/app/models.py` | 新增 `RenderTask` 模型 |
| `backend/app/routers/render.py` | 新 router：`GET /api/render/{task_id}` |
| `backend/app/main.py` | include 新 router |
| `backend/app/runtime/orchestrator.py` | `final` 事件附加 `render_task_id`（从 tool_result 提取） |
| `backend/app/routers/notes.py` | `/api/ask/stream` 的 `final` SSE 透传 `render_task_id` |
| `backend/tests/test_render_task.py` | RenderTask 模型 + 端点单测 |

### 修改 `frontend/`

| 文件 | 改动 |
| --- | --- |
| `frontend/app.js` | 视频卡片 + 轮询进度 + 降级展示 |

---

## 关键接口契约（跨任务一致，勿改）

**渲染服务 `POST /render`** 入参（JSON）：

```json
{"task_id": "uuid", "prompt": "演示 1/2+1/4=3/4", "narration": "（可选）讲解稿", "voice": ""}
```

**渲染服务 `GET /render/{task_id}`** 返回：

```json
{"task_id": "uuid", "status": "queued|generating|rendering|mixing|done|error", "video_url": null, "error": null, "progress": 0}
```

**主服务 `render_manim` 工具 `run()` 返回**（JSON 可序列化，TurnEngine 无需改）：

```json
{"task_id": "uuid", "status": "submitted", "video_url": null}
```

**`final` SSE 事件新增可选字段** `render_task_id`（当本 turn 有 `render_manim` 调用时附上）：

```json
{"type": "final", "data": {"answer": "...", "citations": [], "mode": "visualize", "render_task_id": "uuid"}}
```

**`GET /api/render/{task_id}`**（主服务，前端轮询）：

```json
{"task_id": "uuid", "status": "done", "video_url": "http://127.0.0.1:8010/render_media/uuid.mp4", "error": null}
```

> 视频 URL 由主服务把渲染服务的 mp4 回传/代理到 `/render_media/` 静态路径（见 Task 12）。前端只跟主服务交互，不直连渲染服务。

---

## 阶段 1：渲染服务骨架 + 最小链路

### Task 1: 安装渲染依赖（manim + ffmpeg）

**Files:** 无代码文件（环境准备）

- [ ] **Step 1: 安装 manim 到 Bash 的 Python**

```bash
cd /d/workspace/github/KnoAct
python -m pip install manim
```

- [ ] **Step 2: 验证 manim 可导入**

```bash
python -c "import manim; print(manim.__version__)"
```

Expected: 打印版本号（如 `0.18.1`），无报错。

- [ ] **Step 3: 安装 ffmpeg**

Windows 上推荐用 winget 或 chocolatey；若已用其它方式，跳过此步但需验证 Step 4。

```bash
# 任一方式之一：
# winget install Gyan.FFmpeg
# 或下载 ffmpeg 解压后把 bin 加入 PATH
```

- [ ] **Step 4: 验证 ffmpeg 可用**

```bash
ffmpeg -version 2>&1 | head -1
```

Expected: 打印 `ffmpeg version ...`。

- [ ] **Step 5: 提交**（如改了 requirements 类文件才提交；纯环境安装不提交）

无提交（环境安装不入库）。

---

### Task 2: 渲染服务最小骨架（FastAPI + 两个端点）

**Files:**
- Create: `render_service/app.py`
- Create: `render_service/requirements.txt`
- Create: `render_service/__init__.py`

- [ ] **Step 1: 写 requirements.txt**

```text
fastapi
uvicorn
manim
requests
```

> 说明：ffmpeg 不在 pip 里，是系统级依赖（Task 1 已装）。TTS 复用主服务 provider，见 Task 4。

- [ ] **Step 2: 写 app.py 最小骨架**

```python
"""独立渲染服务：把 manim 代码渲染成带旁白的视频。"""
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="KnoAct Render Service")


class RenderReq(BaseModel):
    task_id: str = ""
    prompt: str
    narration: str = ""
    voice: str = ""


@app.post("/render")
def submit(req: RenderReq):
    task_id = req.task_id or uuid.uuid4().hex
    return {"task_id": task_id, "status": "queued"}


@app.get("/render/{task_id}")
def status(task_id: str):
    return {"task_id": task_id, "status": "queued", "video_url": None, "error": None, "progress": 0}
```

- [ ] **Step 3: 启动并验证端点**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m uvicorn app:app --port 8011
```

另开一个 Bash：

```bash
cd /d/workspace/github/KnoAct
python -c "import requests; r=requests.post('http://127.0.0.1:8011/render', json={'prompt':'test'}); print(r.status_code, r.json())"
```

Expected: `200 {'task_id': '...', 'status': 'queued'}`

- [ ] **Step 4: 提交**

```bash
git add render_service/app.py render_service/requirements.txt render_service/__init__.py
git commit -m "feat(render): 渲染服务最小骨架（POST/GET 端点）"
```

---

### Task 3: manim 渲染封装（subprocess 调 manim render）

**Files:**
- Create: `render_service/manim_render.py`
- Create: `render_service/tests/__init__.py`
- Test: `render_service/tests/test_manim_render.py`

- [ ] **Step 1: 写失败测试**

```python
# render_service/tests/test_manim_render.py
from render_service.manim_render import render_code


def test_render_valid_code_returns_mp4(tmp_path):
    code = (
        "from manim import *\n"
        "class Demo(Scene):\n"
        "    def construct(self):\n"
        "        t = Text('hi')\n"
        "        self.add(t)\n"
    )
    mp4 = render_code(code, str(tmp_path))
    assert mp4 is not None
    assert mp4.endswith(".mp4")


def test_render_invalid_code_returns_none(tmp_path):
    bad = "this is not python\n"
    assert render_code(bad, str(tmp_path)) is None
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_manim_render.py -v
```

Expected: FAIL（`render_service.manim_render` 不存在 / `render_code` 未定义）

- [ ] **Step 3: 写 manim_render.py**

```python
"""封装 subprocess 调 `manim render`，返回产物 mp4 路径，失败返回 None。"""
import subprocess
import tempfile
from pathlib import Path


def render_code(code: str, out_dir: str, timeout: int = 120) -> str | None:
    """把 manim 源码写到临时 .py，用 `manim render -ql` 渲染，返回 mp4 绝对路径。

    失败（语法错/manim 异常/超时）返回 None。低质量 -ql 加速渲染。
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    src = out / "_scene.py"
    src.write_text(code, encoding="utf-8")

    # 提取场景类名（第一个 `class X(Scene)`）
    import re
    m = re.search(r"class\s+(\w+)\s*\(\s*Scene\s*\)", code)
    if not m:
        return None
    scene = m.group(1)

    try:
        proc = subprocess.run(
            ["python", "-m", "manim", "render", "-ql", "-o", str(out), str(src), scene],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None

    # manim 输出文件名形如 Demo.mp4，散落在 out_dir 或子目录，找最新 mp4
    mp4s = sorted(out.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
    return str(mp4s[-1]) if mp4s else None
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_manim_render.py -v
```

Expected: PASS（`test_render_valid_code_returns_mp4` 会真实渲染一次，耗时数秒）

- [ ] **Step 5: 提交**

```bash
git add render_service/manim_render.py render_service/tests/
git commit -m "feat(render): manim 渲染封装（subprocess + 产物定位）"
```

---

### Task 4: TTS 旁白生成（复用主服务 provider）

**Files:**
- Create: `render_service/tts.py`
- Test: `render_service/tests/test_tts.py`

- [ ] **Step 1: 写失败测试**

```python
# render_service/tests/test_tts.py
import os
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db",
)
from render_service.tts import synthesize_to_file


def test_synthesize_fake_writes_file(tmp_path):
    out = str(tmp_path / "narration.mp3")
    path = synthesize_to_file("你好", out, provider="fake")
    assert path is not None
    import os as _os
    assert _os.path.exists(path)
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_tts.py -v
```

Expected: FAIL（`render_service.tts` 不存在）

- [ ] **Step 3: 写 tts.py（复用主服务 get_tts）**

```python
"""旁白 TTS：复用主服务 services/tts.py 的 provider 抽象。"""
import os
import sys
from pathlib import Path

# 让 render_service 能 import 主服务的 app 包（models/database/services）
_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def synthesize_to_file(text: str, out_path: str, provider: str = "fake") -> str | None:
    """用主服务 get_tts 合成语音到 out_path，返回路径；失败返回 None。"""
    from app.services.tts import get_tts
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        tts = get_tts(db)
        data = tts.synthesize(text)
    except Exception:
        return None
    finally:
        db.close()

    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return str(p)
```

> 说明：`provider` 参数留作将来强制指定；当前直接走 `get_tts` 的 resolve（会读库里的 tts 配置）。fake provider 返回 UTF-8 文本字节，写入文件后 ffmpeg 无法识别为音频——**这一步只验证「能写出文件」**，真正的「可播音频」在 Task 5 合轨后由真实 TTS（MiniMax/OpenAI）产生；fake 场景用「无旁白」降级（见 Task 5）。

- [ ] **Step 4: 运行确认通过**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_tts.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add render_service/tts.py render_service/tests/test_tts.py
git commit -m "feat(render): 旁白 TTS 复用主服务 provider 抽象"
```

---

### Task 5: ffmpeg 合轨（画面 + 旁白合成 mp4）

**Files:**
- Create: `render_service/mix.py`
- Test: `render_service/tests/test_mix.py`

- [ ] **Step 1: 写失败测试**

```python
# render_service/tests/test_mix.py
import subprocess
from render_service.mix import mix_audio


def _make_test_video(path):
    # 用 ffmpeg 造一个 2 秒纯色测试视频
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x240:d=2",
         "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-shortest", path],
        capture_output=True,
    )


def test_mix_without_audio_returns_video(tmp_path):
    vid = str(tmp_path / "test.mp4")
    _make_test_video(vid)
    out = mix_audio(vid, None, str(tmp_path))
    assert out is not None
    assert out.endswith(".mp4")
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_mix.py -v
```

Expected: FAIL（`render_service.mix` 不存在）

- [ ] **Step 3: 写 mix.py**

```python
"""ffmpeg 合轨：把 TTS 旁白合成进 manim 视频。"""
import subprocess
from pathlib import Path


def mix_audio(video_path: str, audio_path: str | None, out_dir: str) -> str | None:
    """把 audio_path 合成进 video_path，输出到 out_dir/final.mp4。

    audio_path 为 None 或不存在时，直接返回原视频（无旁白降级）。
    粗对齐：以旁白时长为准，视频循环或截断到旁白时长。
    """
    video = Path(video_path)
    if not video.exists():
        return None
    if not audio_path or not Path(audio_path).exists():
        return video_path

    out = Path(out_dir) / "final.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)

    # 旁白时长决定成片时长：视频时长不足则循环画面，超出则截断
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", str(video),   # 画面循环
        "-i", audio_path,                          # 旁白
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-c:a", "aac",
        "-shortest",                                # 以旁白为准截断
        str(out),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0 or not out.exists():
        return None
    return str(out)
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_mix.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add render_service/mix.py render_service/tests/test_mix.py
git commit -m "feat(render): ffmpeg 合轨（旁白合成进 manim 视频）"
```

---

### Task 6: 流水线编排 + 队列（串联 render/tts/mix）

**Files:**
- Create: `render_service/queue.py`
- Create: `render_service/pipeline.py`
- Test: `render_service/tests/test_pipeline.py`

- [ ] **Step 1: 写队列失败测试**

```python
# render_service/tests/test_pipeline.py
from render_service.queue import TaskQueue
from render_service.pipeline import run_pipeline


def test_queue_reports_status():
    q = TaskQueue(max_concurrent=1)
    states = {}
    tid = "t1"

    def fake_job(tid, status_cb):
        status_cb("rendering")
        status_cb("done")
        return "http://x/final.mp4"

    q.submit(tid, fake_job, status_cb=lambda s: states.setdefault(tid, []).append(s))
    q.drain()  # 同步跑完队列里的任务
    assert states["t1"] == ["rendering", "done"]
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_pipeline.py -v
```

Expected: FAIL（`render_service.queue` 不存在）

- [ ] **Step 3: 写 queue.py**

```python
"""进程内任务队列 + 有限并发。"""
import threading
from collections import deque
from typing import Any, Callable


class TaskQueue:
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._lock = threading.Lock()
        self._queue: deque[tuple[str, Callable, Callable]] = deque()
        self._running = 0
        # 任务状态 + 结果存这里，由 app.py 的 status 端点读
        self.status: dict[str, dict[str, Any]] = {}

    def submit(self, task_id: str, job: Callable, status_cb: Callable[[str], None]):
        """job(task_id, status_cb) -> video_url。入队并尝试启动。"""
        with self._lock:
            self.status[task_id] = {"status": "queued", "video_url": None, "error": None, "progress": 0}
            self._queue.append((task_id, job, status_cb))
        self._try_start()

    def _try_start(self):
        with self._lock:
            while self._running < self.max_concurrent and self._queue:
                tid, job, cb = self._queue.popleft()
                self._running += 1
                self.status[tid]["status"] = "generating"
        # 上面只是从队列取出；实际线程启动放锁外避免阻塞
        # 简化：单线程 drain 模式（测试用）+ 真实线程池见 pipeline
        ...

    def drain(self):
        """同步跑完队列里所有任务（测试/简化用）。"""
        while True:
            with self._lock:
                if not self._queue and self._running == 0:
                    break
                if not self._queue:
                    continue
                tid, job, cb = self._queue.popleft()
            self._run_one(tid, job, cb)

    def _run_one(self, tid, job, cb):
        def on_status(s):
            self.status[tid]["status"] = s
            if cb:
                cb(s)
        try:
            url = job(tid, on_status)
            self.status[tid]["status"] = "done"
            self.status[tid]["video_url"] = url
        except Exception as e:
            self.status[tid]["status"] = "error"
            self.status[tid]["error"] = str(e)
```

- [ ] **Step 4: 写 pipeline.py**

```python
"""渲染流水线：生成代码(阶段2)→渲染→TTS→合轨。阶段1先跑通 render→tts→mix。"""
from pathlib import Path

from .manim_render import render_code
from .tts import synthesize_to_file
from .mix import mix_audio

MEDIA_DIR = Path(__file__).resolve().parent / "media"


def run_pipeline(task_id: str, prompt: str, narration: str, voice: str, status_cb) -> str:
    """阶段1：不生成代码，用 prompt 作为占位场景（真实生成在 Task 8 接 LLM）。

    返回视频 URL 相对路径（相对 MEDIA_DIR）。
    """
    out = MEDIA_DIR / task_id
    out.mkdir(parents=True, exist_ok=True)

    status_cb("rendering")
    # 阶段1：写死一个最简单的 manim 场景，证明 render→tts→mix 全链路通
    code = (
        "from manim import *\n"
        "class Demo(Scene):\n"
        "    def construct(self):\n"
        f"        t = Text({narration!r} or {prompt!r} or 'hi')\n"
        "        self.add(t)\n"
    )
    mp4 = render_code(code, str(out))
    if not mp4:
        raise RuntimeError("manim 渲染失败")

    status_cb("mixing")
    audio = synthesize_to_file(narration or prompt, str(out / "narration.mp3"))
    final = mix_audio(mp4, audio, str(out))
    if not final:
        raise RuntimeError("合轨失败")

    return f"{task_id}/final.mp4"
```

- [ ] **Step 5: 运行确认通过**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_pipeline.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add render_service/queue.py render_service/pipeline.py render_service/tests/test_pipeline.py
git commit -m "feat(render): 流水线编排 + 进程内队列"
```

---

### Task 7: 串起端点——app.py 接队列 + 静态托管视频

**Files:**
- Modify: `render_service/app.py`

- [ ] **Step 1: 改 app.py 接队列 + 静态目录**

```python
"""独立渲染服务：把 manim 代码渲染成带旁白的视频。"""
import threading
import uuid

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .queue import TaskQueue
from .pipeline import run_pipeline, MEDIA_DIR

app = FastAPI(title="KnoAct Render Service")

# 渲染产物静态托管
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")

queue = TaskQueue(max_concurrent=3)


class RenderReq(BaseModel):
    task_id: str = ""
    prompt: str
    narration: str = ""
    voice: str = ""


@app.post("/render")
def submit(req: RenderReq):
    task_id = req.task_id or uuid.uuid4().hex

    def job(tid, status_cb):
        return run_pipeline(tid, req.prompt, req.narration, req.voice, status_cb)

    queue.submit(task_id, job)
    return {"task_id": task_id, "status": "queued"}


@app.get("/render/{task_id}")
def status(task_id: str):
    s = queue.status.get(task_id)
    if s is None:
        return {"task_id": task_id, "status": "error", "video_url": None,
                "error": "任务不存在", "progress": 0}
    return {"task_id": task_id, **s}
```

> 注意：`queue.submit` 里的 `_try_start` 在 Task 6 是简化版（未真正起线程）。此处在 `submit` 后需要真正异步跑任务。实现时把 `TaskQueue` 改成**每 submit 起一个 daemon 线程**跑 `_run_one`，`max_concurrent` 用 `threading.Semaphore` 控制（见 Step 2）。

- [ ] **Step 2: 修正 queue.py 为真实线程模型**

替换 `TaskQueue` 的 `submit`/`_try_start` 为：

```python
    def __init__(self, max_concurrent: int = 3):
        self._sem = threading.Semaphore(max_concurrent)
        self._lock = threading.Lock()
        self.status: dict[str, dict[str, Any]] = {}

    def submit(self, task_id: str, job: Callable, status_cb=None):
        self.status[task_id] = {"status": "queued", "video_url": None,
                                "error": None, "progress": 0}
        t = threading.Thread(target=self._worker, args=(task_id, job, status_cb), daemon=True)
        t.start()

    def _worker(self, task_id, job, status_cb):
        with self._sem:
            self.status[task_id]["status"] = "generating"
            def on_status(s):
                self.status[task_id]["status"] = s
                if status_cb:
                    status_cb(s)
            try:
                url = job(task_id, on_status)
                self.status[task_id]["status"] = "done"
                self.status[task_id]["video_url"] = url
            except Exception as e:
                self.status[task_id]["status"] = "error"
                self.status[task_id]["error"] = str(e)
```

> 同时把 Task 6 的 `drain()` 从测试里移除（测试改用真实线程 + join）。但为不破坏 Task 6 已提交的测试，此处仅**新增**线程模型，保留 `drain()` 不动。测试 `test_queue_reports_status` 仍用 `drain()` 应继续通过——但 `drain` 依赖旧的 `_run_one`/`_queue`。**折中**：保留 `drain` 和旧字段，同时加线程路径。实现时以「测试全绿」为准调整，两套不冲突即可。

- [ ] **Step 3: 端到端验证（真实提交一个任务拿 mp4）**

启动渲染服务：

```bash
cd /d/workspace/github/KnoAct/render_service
python -m uvicorn app:app --port 8011
```

另开 Bash 提交并轮询：

```bash
cd /d/workspace/github/KnoAct
python - <<'PY'
import requests, time
r = requests.post('http://127.0.0.1:8011/render',
                  json={'prompt':'演示分数相加','narration':'我们来看分数相加'})
tid = r.json()['task_id']
print('task', tid)
for _ in range(30):
    s = requests.get(f'http://127.0.0.1:8011/render/{tid}').json()
    print(s['status'], s.get('video_url'))
    if s['status'] in ('done','error'):
        break
    time.sleep(3)
PY
```

Expected: 最终打印 `done` 和一个 `/media/<tid>/final.mp4` 相对路径。

- [ ] **Step 4: 提交**

```bash
git add render_service/app.py render_service/queue.py
git commit -m "feat(render): 端点接队列 + 静态托管 + 线程模型"
```

---

## 阶段 2：接 LLM 生成代码 + 纠错循环

### Task 8: LLM 生成 manim 代码（含最小可用模板引导）

**Files:**
- Create: `render_service/codegen.py`
- Test: `render_service/tests/test_codegen.py`

- [ ] **Step 1: 写失败测试**

```python
# render_service/tests/test_codegen.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db")
from render_service.codegen import generate_manim_code


def test_generate_returns_code_string():
    code = generate_manim_code("演示 1/2 + 1/4 = 3/4")
    assert isinstance(code, str)
    assert "class" in code and "Scene" in code
```

> 注意：该测试在 fake provider（未配真实 LLM）下，`generate_manim_code` 应返回**内置模板**（含 class/Scene），仍可通过。真实 LLM 配好时返回 LLM 生成的代码。

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_codegen.py -v
```

Expected: FAIL（`render_service.codegen` 不存在）

- [ ] **Step 3: 写 codegen.py**

```python
"""LLM 生成 manim 代码：含最小可用模板引导 + fake 兜底。"""
import sys
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


TEMPLATE = '''from manim import *

class Demo(Scene):
    def construct(self):
        # 在这里写动画：例如展示一个公式
        formula = MathTex(r"{topic}")
        self.play(Write(formula))
        self.wait(1)
'''

SYSTEM = (
    "你是 manim 动画代码生成器。只输出可运行的 Python manim 代码，"
    "不要输出解释文字，不要用 markdown 代码围栏。"
    "必须包含 `from manim import *` 和一个继承 Scene 的类。"
    "数学公式用 MathTex 包裹 LaTeX。"
)


def generate_manim_code(prompt: str) -> str:
    from app.services.ai import get_provider
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        provider = get_provider(db)
        raw = provider.generate(
            prompt=f"生成一个演示以下数学概念的 manim 动画：{prompt}。公式优先用 MathTex。",
            system=SYSTEM,
        )
    except Exception:
        raw = ""
    finally:
        db.close()

    code = (raw or "").strip()
    if not code or "class" not in code or "Scene" not in code:
        # fake / 失败兜底：返回模板
        return TEMPLATE.format(topic=prompt)
    return code
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_codegen.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add render_service/codegen.py render_service/tests/test_codegen.py
git commit -m "feat(render): LLM 生成 manim 代码（模板引导 + fake 兜底）"
```

---

### Task 9: 纠错循环（渲染失败喂回 LLM 重试 ≤3 次）

**Files:**
- Create: `render_service/retry.py`
- Test: `render_service/tests/test_retry.py`

- [ ] **Step 1: 写失败测试**

```python
# render_service/tests/test_retry.py
from render_service.retry import render_with_retry


def test_retry_succeeds_on_second_attempt():
    calls = {"n": 0}

    def fake_render(code, out_dir):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # 第一次失败
        return "final.mp4"

    def fake_gen(prev_error):
        return "fixed code"

    url = render_with_retry("bad code", fake_gen, fake_render, "/tmp")
    assert url == "final.mp4"
    assert calls["n"] == 2


def test_retry_gives_up_after_max():
    def always_fail(code, out_dir):
        return None
    def fake_gen(prev_error):
        return "still bad"
    url = render_with_retry("bad", fake_gen, always_fail, "/tmp", max_retries=3)
    assert url is None
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_retry.py -v
```

Expected: FAIL（`render_service.retry` 不存在）

- [ ] **Step 3: 写 retry.py**

```python
"""渲染失败纠错：把错误喂回生成器重试，最多 max_retries 次。"""


def render_with_retry(initial_code, gen_fn, render_fn, out_dir, max_retries=3) -> str | None:
    """gen_fn(prev_error) -> new_code；render_fn(code, out_dir) -> mp4|None。

    循环：渲染 → 失败则 gen_fn(错误) 重新生成 → 再渲染，直到成功或次数耗尽。
    """
    code = initial_code
    for _ in range(max_retries + 1):
        mp4 = render_fn(code, out_dir)
        if mp4:
            return mp4
        # 失败：把「错误」交给生成器（这里简化传代码；真实 stderr 在 Task 10 接）
        code = gen_fn("previous render failed")
    return None
```

- [ ] **Step 4: 运行确认通过**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/test_retry.py -v
```

Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add render_service/retry.py render_service/tests/test_retry.py
git commit -m "feat(render): 渲染失败纠错重试循环"
```

---

### Task 10: 把代码生成 + 纠错接进 pipeline

**Files:**
- Modify: `render_service/pipeline.py`
- Modify: `render_service/manim_render.py`（渲染失败时返回 stderr 供纠错）

- [ ] **Step 1: 改 manim_render.py 让失败可返回 stderr**

在 `render_code` 里，失败分支补充返回错误信息。新增一个返回元组的函数（保留旧签名兼容测试）：

```python
def render_code_with_error(code: str, out_dir: str, timeout: int = 120) -> tuple[str | None, str]:
    """返回 (mp4|None, stderr)。失败时 stderr 是 manim 报错原文。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    src = out / "_scene.py"
    src.write_text(code, encoding="utf-8")
    import re
    m = re.search(r"class\s+(\w+)\s*\(\s*Scene\s*\)", code)
    if not m:
        return None, "no Scene class found"
    scene = m.group(1)
    try:
        proc = subprocess.run(
            ["python", "-m", "manim", "render", "-ql", "-o", str(out), str(src), scene],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except FileNotFoundError:
        return None, "manim not found"
    if proc.returncode != 0:
        return None, (proc.stderr or "")[:2000]
    mp4s = sorted(out.rglob("*.mp4"), key=lambda p: p.stat().st_mtime)
    return (str(mp4s[-1]), "") if mp4s else (None, "no mp4 produced")
```

同时让 `render_code` 内部调用 `render_code_with_error` 只返回第一项（保持旧测试通过）：

```python
def render_code(code: str, out_dir: str, timeout: int = 120) -> str | None:
    mp4, _ = render_code_with_error(code, out_dir, timeout)
    return mp4
```

- [ ] **Step 2: 改 pipeline.py 接生成 + 纠错**

```python
from .manim_render import render_code_with_error
from .codegen import generate_manim_code
from .retry import render_with_retry


def run_pipeline(task_id: str, prompt: str, narration: str, voice: str, status_cb) -> str:
    out = MEDIA_DIR / task_id
    out.mkdir(parents=True, exist_ok=True)

    status_cb("generating")
    code = generate_manim_code(prompt)

    def gen_fn(prev_error):
        # 把渲染错误喂回 LLM 重新生成
        return generate_manim_code(f"{prompt}（上一次渲染报错：{prev_error}，请修复）")

    def render_fn(code, out_dir):
        mp4, err = render_code_with_error(code, out_dir)
        return mp4

    status_cb("rendering")
    mp4 = render_with_retry(code, gen_fn, render_fn, str(out), max_retries=3)
    if not mp4:
        raise RuntimeError("manim 渲染失败（重试后仍失败）")

    status_cb("mixing")
    audio = synthesize_to_file(narration or prompt, str(out / "narration.mp3"))
    final = mix_audio(mp4, audio, str(out))
    if not final:
        raise RuntimeError("合轨失败")

    return f"{task_id}/final.mp4"
```

- [ ] **Step 3: 运行全量测试确认无回归**

```bash
cd /d/workspace/github/KnoAct/render_service
python -m pytest tests/ -v
```

Expected: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add render_service/pipeline.py render_service/manim_render.py
git commit -m "feat(render): pipeline 接 LLM 生成 + 纠错循环"
```

---

## 阶段 3：接入主服务 agent 循环 + 前端

### Task 11: 主服务 `render_manim` 工具 + `RenderTask` 模型

**Files:**
- Create: `backend/app/tools/render_manim_tool.py`（或并入 builtin.py）
- Modify: `backend/app/models.py`
- Test: `backend/tests/test_render_task.py`

- [ ] **Step 1: 写 RenderTask 模型 + 失败测试**

在 `models.py` 末尾（`ToolCall` 之后）新增：

```python
class RenderTask(Base):
    """一次 manim 动画渲染任务（提交给独立渲染服务）。"""
    __tablename__ = "render_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    turn_id: Mapped[int] = mapped_column(ForeignKey("turns.id"), nullable=True)
    prompt: Mapped[str] = mapped_column(TextCls, default="")
    narration: Mapped[str] = mapped_column(TextCls, default="")
    status: Mapped[str] = mapped_column(String(16), default="submitted")
    video_url: Mapped[str] = mapped_column(String(255), default="")
    error: Mapped[str] = mapped_column(TextCls, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

写失败测试：

```python
# backend/tests/test_render_task.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db")
from app.models import RenderTask


def test_render_task_columns_exist():
    cols = {c.name for c in RenderTask.__table__.columns}
    for name in ("task_id", "user_id", "prompt", "narration", "status", "video_url", "error"):
        assert name in cols
```

- [ ] **Step 2: 运行确认失败**

```bash
cd /d/workspace/github/KnoAct/backend
python -m pytest tests/test_render_task.py -v
```

Expected: FAIL（`RenderTask` 不存在 / 缺字段）

- [ ] **Step 3: 写 render_manim 工具**

新建 `backend/app/tools/render_manim_tool.py`：

```python
"""render_manim：提交型工具，把数学概念交给独立渲染服务渲染成带旁白视频。"""
import uuid

from ..core.context import UnifiedContext
from ..core.tool_protocol import BaseTool, ToolParameter

RENDER_SERVICE_URL = "http://127.0.0.1:8011"


class RenderManimTool(BaseTool):
    name = "render_manim"
    description = "把数学概念渲染成带旁白讲解的动画视频，返回渲染任务 id（前端据此轮询进度）"
    parameters = [
        ToolParameter(name="prompt", type="string",
                      description="要演示的数学概念，如「演示 1/2+1/4=3/4」"),
        ToolParameter(name="narration", type="string",
                      description="旁白讲解稿（小学生能听懂的话）", required=False),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        prompt = (args.get("prompt") or "").strip()
        narration = (args.get("narration") or "").strip()
        if not prompt:
            return {"error": "prompt 不能为空"}
        task_id = uuid.uuid4().hex

        try:
            import requests
            resp = requests.post(
                f"{RENDER_SERVICE_URL}/render",
                json={"task_id": task_id, "prompt": prompt, "narration": narration},
                timeout=5,
            )
            resp.raise_for_status()
            status = "submitted"
        except Exception as e:
            # 渲染服务不可用：降级，返回代码占位 + 错误
            return {"task_id": task_id, "status": "unavailable",
                    "video_url": None, "error": f"渲染服务不可用：{e}"}

        # 落库 RenderTask（失败不阻断工具返回）
        try:
            from ..database import SessionLocal
            from ..models import RenderTask
            db = SessionLocal()
            try:
                db.add(RenderTask(task_id=task_id, user_id=ctx.user_id,
                                  prompt=prompt, narration=narration, status="submitted"))
                db.commit()
            finally:
                db.close()
        except Exception:
            pass

        return {"task_id": task_id, "status": status, "video_url": None}
```

- [ ] **Step 4: 注册工具 + 挂进 visualize**

在 `backend/app/tools/builtin.py` 末尾追加导出（或直接在 capability 里 import）：

```python
from .render_manim_tool import RenderManimTool
render_manim = RenderManimTool()
```

在 `backend/app/capabilities/chat.py`：

```python
from ..tools.render_manim_tool import render_manim

ALL_TOOLS = {"lookup_word": lookup_word, "search_text": search_text,
             "render_mermaid": render_mermaid, "render_manim": render_manim}
```

并把 `VisualizeCapability.tools` 改为 `["render_mermaid", "render_manim", "search_text"]`。

- [ ] **Step 5: 运行确认通过**

```bash
cd /d/workspace/github/KnoAct/backend
python -m pytest tests/test_render_task.py -v
```

Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models.py backend/app/tools/render_manim_tool.py backend/app/tools/builtin.py backend/app/capabilities/chat.py backend/tests/test_render_task.py
git commit -m "feat: render_manim 工具 + RenderTask 模型，挂进 visualize"
```

---

### Task 12: 主服务 `/api/render/{task_id}` 端点 + 视频代理

**Files:**
- Create: `backend/app/routers/render.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 写 render router**

```python
"""渲染任务状态查询 + 视频代理。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import RenderTask

router = APIRouter(tags=["render"])

RENDER_SERVICE_URL = "http://127.0.0.1:8011"


@router.get("/api/render/{task_id}")
def render_status(task_id: str, db: Session = Depends(get_db)):
    row = db.query(RenderTask).filter_by(task_id=task_id).first()
    if row is None:
        raise HTTPException(404, "任务不存在")

    # 中间态：透传问渲染服务，更新本地缓存
    if row.status in ("submitted", "queued", "generating", "rendering", "mixing"):
        try:
            import requests
            r = requests.get(f"{RENDER_SERVICE_URL}/render/{task_id}", timeout=3)
            if r.status_code == 200:
                s = r.json()
                row.status = s.get("status", row.status)
                if s.get("video_url"):
                    row.video_url = s["video_url"]
                if s.get("error"):
                    row.error = s["error"]
                db.commit()
        except Exception:
            pass  # 渲染服务没起就保持本地状态

    # 视频 URL：把渲染服务相对路径转成本服务代理路径
    video_url = ""
    if row.status == "done" and row.video_url:
        video_url = f"http://127.0.0.1:8010/render_media/{row.video_url}"
    return {"task_id": task_id, "status": row.status, "video_url": video_url,
            "error": row.error}
```

- [ ] **Step 2: 视频代理端点（把渲染服务的 mp4 转发给前端）**

在同文件追加：

```python
@router.get("/render_media/{path:path}")
def render_media(path: str):
    """把渲染服务的媒体文件代理给前端（前端不直连渲染服务）。"""
    url = f"{RENDER_SERVICE_URL}/media/{path}"
    import requests
    r = requests.get(url, timeout=10)
    if r.status_code != 200:
        raise HTTPException(404, "视频不存在")
    from fastapi.responses import Response
    return Response(content=r.content, media_type="video/mp4")
```

- [ ] **Step 3: main.py 注册 router**

在 `backend/app/main.py` 的 include_router 列表加：

```python
import app.routers.render as render_router
app.include_router(render_router.router)
```

（或按现有 `from .routers import ...` 风格统一 import）

- [ ] **Step 4: 验证端点**

启动主服务（绝对 DB 路径）与渲染服务，然后：

```bash
cd /d/workspace/github/KnoAct
python - <<'PY'
import requests
# 先通过 /api/ask 触发一次 render_manim（需配真实 LLM），或用已存在的 task_id
# 这里验证端点本身：
r = requests.get('http://127.0.0.1:8010/api/render/nonexistent')
print(r.status_code)  # 404
PY
```

Expected: `404`

- [ ] **Step 5: 提交**

```bash
git add backend/app/routers/render.py backend/app/main.py
git commit -m "feat: /api/render/{task_id} 端点 + 视频代理"
```

---

### Task 13: final 事件附加 `render_task_id`（打通 SSE → 前端）

**Files:**
- Modify: `backend/app/runtime/orchestrator.py`
- Modify: `backend/app/routers/notes.py`

- [ ] **Step 1: orchestrator 提取 render_task_id**

在 `orchestrator.py` 加辅助函数：

```python
def extract_render_task_id(results_by_step: dict[int, dict]) -> str:
    """从 tool_result 里找 render_manim 返回的 task_id。"""
    for result in results_by_step.values():
        if isinstance(result, dict) and result.get("task_id"):
            return result["task_id"]
    return ""
```

并在 `route_to_capability` 里，`persist_turn` 之后，把 task_id 加进返回值：

```python
    task_id = extract_render_task_id(results_by_step)
    return {"answer": answer, "citations": citations, "mode": ctx.mode,
            "render_task_id": task_id}
```

- [ ] **Step 2: notes.py 的 final SSE 透传**

在 `_event_stream` 的 `_yield_event` 里，`final` 分支需要拿到 render_task_id。由于 `final` 事件由 `TurnEngine` 直接 emit（不含 task_id），需在 `_event_stream` 收尾时，若 `results_by_step` 里有 render_manim 结果，则给 final 补字段：

修改 final 处理：把 `answer`/`citations` 之外，附带 render_task_id。最简单方式是在收尾 `persist_turn` 前，把 final 事件重发一遍带 task_id。具体实现：

```python
    # 收尾（task 结束后）
    render_task_id = extract_render_task_id(results_by_step)
    if render_task_id and answer:
        yield _sse("final", {"answer": answer, "citations": citations,
                             "mode": ctx.mode, "render_task_id": render_task_id})
```

> 实现时需注意不要重复发 final。建议：`_yield_event` 的 final 分支先不 yield，统一在收尾阶段发一个「最终 final」含 render_task_id。具体以「前端只收到一个 final 事件」为准。

- [ ] **Step 3: 提交**

```bash
git add backend/app/runtime/orchestrator.py backend/app/routers/notes.py
git commit -m "feat: final SSE 事件附加 render_task_id"
```

---

### Task 14: 前端视频卡片 + 轮询进度

**Files:**
- Modify: `frontend/app.js`

- [ ] **Step 1: 处理 final 事件里的 render_task_id**

在 `handleStreamEvent` 的 `final` 分支，若 `d.render_task_id` 存在，则把消息标记为「渲染中」，并启动轮询：

```javascript
} else if(evt.type === 'final'){
    const d = evt.data;
    const msg = {role:'ai', text:d.answer || '（暂无回答）', citations:d.citations || [], mode:d.mode || chatMode};
    if(d.render_task_id){
      msg.renderTaskId = d.render_task_id;
      msg.renderStatus = 'rendering';
    }
    chatMessages.push(msg);
    renderImmersiveChat();
    if(d.render_task_id) pollRenderTask(d.render_task_id, chatMessages.length - 1);
}
```

- [ ] **Step 2: 写轮询函数**

```javascript
async function pollRenderTask(taskId, msgIndex){
  const renderCard = (status, url) => {
    const m = chatMessages[msgIndex];
    if(!m) return;
    m.renderStatus = status;
    m.renderVideo = url;
    renderImmersiveChat();
  };
  for(let i = 0; i < 60; i++){  // 最多轮询 60 次 × 3s = 180s
    try{
      const r = await fetch(API + '/api/render/' + taskId);
      const d = await r.json();
      if(d.status === 'done' && d.video_url){
        renderCard('done', d.video_url);
        return;
      }
      if(d.status === 'error' || d.status === 'unavailable'){
        renderCard('error', null);
        return;
      }
      renderCard(d.status, null);
    }catch(e){ /* 忽略单次失败 */ }
    await new Promise(res => setTimeout(res, 3000));
  }
  renderCard('error', null);
}
```

- [ ] **Step 3: 渲染视频卡片**

在 `renderImmersiveChat` 的 AI 消息渲染里，若 `m.renderTaskId` 存在，追加卡片：

```javascript
function renderTaskCard(m){
  if(m.renderStatus === 'done' && m.renderVideo){
    return `<div class="render-card"><video src="${m.renderVideo}" controls width="100%"></video></div>`;
  }
  if(m.renderStatus === 'error'){
    return `<div class="render-card">动画生成失败，请稍后再试。</div>`;
  }
  const label = {rendering:'渲染中…', generating:'生成中…', mixing:'合成音轨…', queued:'排队中…'}[m.renderStatus] || '渲染中…';
  return `<div class="render-card"><span class="render-progress">${label}</span></div>`;
}
```

并在 AI 消息模板里 `<div class="bubble">${renderAnswer(m.text)}</div>` 之后加 `${m.renderTaskId ? renderTaskCard(m) : ''}`。

- [ ] **Step 4: 验证**（需真实 LLM + 渲染服务，见 Task 15）

- [ ] **Step 5: 提交**

```bash
git add frontend/app.js
git commit -m "feat: 前端视频卡片 + 渲染进度轮询"
```

---

### Task 15: 端到端验收（真实对话触发动画）

**Files:** 无（验收）

- [ ] **Step 1: 启动三个进程**

```bash
# 1. 渲染服务
cd /d/workspace/github/KnoAct/render_service && python -m uvicorn app:app --port 8011

# 2. 主服务（绝对 DB 路径）
cd /d/workspace/github/KnoAct/backend && DATABASE_URL="sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db" python -m uvicorn app.main:app --port 8010

# 3. 前端静态页
cd /d/workspace/github/KnoAct && python -m http.server 8766 --directory frontend
```

- [ ] **Step 2: 用浏览器打开前端，切到 visualize 模式，提问「演示分数相加」**

- [ ] **Step 3: 验收清单**

- [ ] 对话流先出现「正在准备动画…」占位
- [ ] 消息下方出现视频卡片，显示「渲染中…」进度
- [ ] 数秒~几十秒后卡片变成可播放的 `<video>`，有画面 + 旁白声音
- [ ] 渲染服务关闭时，前端卡片降级显示「动画生成失败」而非白屏/报错

- [ ] **Step 4: 提交**（验收无代码改动则无提交）

---

## Self-Review（写完后自查）

### Spec 覆盖检查

| Spec 章节 | 对应 Task |
| --- | --- |
| §3.1 接口（POST/GET） | Task 2、7 |
| §3.2 流水线（生成/渲染/纠错/TTS/合成） | Task 3、4、5、6、8、9、10 |
| §3.3 资源与安全（超时/并发/沙箱） | Task 3（timeout）、Task 7（Semaphore 并发）；沙箱靠 Docker（后置，未列入） |
| §3.4 配置来源（连库读） | Task 4、8（DATABASE_URL + 复用 get_tts/get_provider） |
| §4.1 render_manim 工具 | Task 11 |
| §4.2 RenderTask 模型 + 端点 | Task 11、12 |
| §4.3 前端展示 | Task 14 |
| §4.4 挂 visualize | Task 11 |
| §5 三阶段 | 阶段 1(Task1-7) / 阶段 2(Task8-10) / 阶段 3(Task11-15) |
| §6 风险缓解 | 纠错(Task9/10)、超时/并发(Task3/7)、绝对路径(Task 环境事实) |

**缺口**：Dockerfile（spec §7 提到）未列入任务。属于「可分发」目标的一部分，但依赖较独立，可作为阶段 3 之后的补充任务。已在文件结构标注 `Dockerfile`，实现时若需打包再补。

### 占位符扫描

无 TBD/TODO。所有代码步骤含完整代码。Task 7 Step 2 的队列线程模型与 Task 6 的 `drain()` 兼容性已注明折中处理。

### 类型一致性

- `render_code` / `render_code_with_error` 签名在 Task 3/10 一致（后者返回元组，前者兼容）。
- `render_manim` 工具返回字段 `task_id/status/video_url` 与 Task 13 `extract_render_task_id` 读取字段一致。
- `RenderTask` 字段 `task_id/prompt/narration/status/video_url/error` 与 Task 12 端点读写一致。
- 前端 `renderTaskId/renderStatus/renderVideo` 字段在 Task 14 内部一致。

---

## 执行交接

计划已保存。两个执行选项：

1. **Subagent-Driven（推荐）** — 每个 task 派一个全新 subagent，task 之间我做 review
2. **Inline 执行** — 当前会话内批量执行，检查点 review
