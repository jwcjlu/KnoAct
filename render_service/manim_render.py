"""封装 subprocess 调 `manim render`，返回产物 mp4 路径，失败返回 None。"""
import subprocess
from pathlib import Path


def render_code(code: str, out_dir: str, timeout: int = 120) -> str | None:
    """把 manim 源码写到临时 .py，用 `manim render -ql` 渲染，返回 mp4 绝对路径。

    失败（语法错/manim 异常/超时）返回 None。低质量 -ql 加速渲染。
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    src = out / "_scene.py"
    src.write_text(code, encoding="utf-8")

    import re
    m = re.search(r"class\s+(\w+)\s*\(\s*Scene\s*\)", code)
    if not m:
        return None
    scene = m.group(1)

    try:
        proc = subprocess.run(
            ["python", "-m", "manim", "render", "-ql", "--media_dir", str(out), str(src), scene],
            capture_output=True, text=True, timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0:
        return None

    # 排除 partial_movie_files（manim 合并前的中间分段），只认最终成片。
    mp4s = sorted(
        (p for p in out.rglob("*.mp4") if "partial_movie_files" not in p.parts),
        key=lambda p: p.stat().st_mtime,
    )
    return str(mp4s[-1]) if mp4s else None
