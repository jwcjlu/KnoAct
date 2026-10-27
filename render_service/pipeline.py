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
        "        self.play(FadeIn(t))\n"
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
