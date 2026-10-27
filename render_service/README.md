# KnoAct 渲染服务（render_service）

独立渲染服务：把数学概念渲染成带旁白音轨的 manim 动画视频。

## 启动

必须从**仓库根目录**启动（用包形式 import，避免相对导入失败），并指定**绝对路径的 `DATABASE_URL`**（否则 SQLite 相对路径随 cwd 漂移，TTS 读到空库）：

```bash
cd /d/workspace/github/KnoAct
export PATH="$PATH:/c/Users/Admin/ffmpeg/ffmpeg-9.0.2-full_build/bin"
DATABASE_URL="sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db" \
  python -m uvicorn render_service.app:app --port 8011
```

注意：`python -m uvicorn app:app`（在 render_service 目录内）会因相对导入
（`from .queue import ...`）报 `ImportError`。必须用 `render_service.app:app` 包形式。

## 端点

- `POST /render` 入参 `{task_id?, prompt, narration?, voice?}`，立即返回 `202`/`200` + `{task_id, status: "queued"}`。
- `GET /render/{task_id}` 返回 `{task_id, status, video_url, error, progress}`。
- `/media/` 静态托管渲染产物 mp4。

## 依赖

- Python 3.10 + `manim`（0.19.x）+ `ffmpeg`（系统级）+ LaTeX（MiKTeX，数学公式排版）。
- TTS/LLM provider 复用主服务 `backend/app/services/`，通过 `DATABASE_URL` 连同一个库读配置。

## 沙箱（执行 LLM 生成的 manim 代码）

LLM 生成的 manim 代码本质是要执行的 Python 代码。渲染时经 `render_service/sandbox.py`
做受限执行，参照 DeepTutor 的 sandbox 分层：

- 环境变量 `KNOACT_RENDER_SANDBOX` 选后端：`subprocess`（默认）/ `docker` / `off`。
- `subprocess` —— **APPLICATION 级**（默认）：清洗环境变量（剔除 `DATABASE_URL`/API key
  等敏感值）+ 限定 cwd 到任务目录 + 输出截断。**不做 OS 级隔离**，LLM 代码若主动
  `os.system` 读盘/联网仍可逃逸——与 DeepTutor 对 APPLICATION 级的定位一致。
- `docker` —— **SYSTEM 级**：把 manim 命令转发到独立 runner sidecar 容器执行
  （无网络 + 非 root + `cap_drop ALL` + 只读根 FS + 只写 media 卷）。
- `off` —— 拒绝执行未沙箱代码。

### 启用 docker（SYSTEM 级）沙箱

```bash
# 1. 构建并启动 runner sidecar 容器（带 manim + ffmpeg + TeX Live 重依赖）
docker compose -f render_service/docker-compose.yml up -d --build

# 2. 主渲染服务用 docker 后端 + 指向 runner
KNOACT_RENDER_SANDBOX=docker \
KNOACT_RENDER_RUNNER_URL=http://localhost:8901 \
DATABASE_URL="sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db" \
  python -m uvicorn render_service.app:app --port 8011
```

runner 地址由 `KNOACT_RENDER_RUNNER_URL` 指定（默认 `http://localhost:8901`）。
runner 不可达时**报错而非降级到 subprocess**，避免静默失去隔离。

runner 组件（`render_service/runner/`）：
- `server.py` —— 纯标准库 HTTP server，`GET /health` + `POST /exec`，唯一执行 manim 的地方。
- `Dockerfile` —— `python:3.11-slim` + ffmpeg + TeX Live 精简子集 + manim，非 root 用户。
- `docker-compose.yml` —— 安全加固：`no-new-privileges` + `cap_drop ALL` + `read_only` +
  tmpfs + `pids_limit`/`mem_limit`，不发布端口，`./render_service/media` 挂载为 `/outputs`。
