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
