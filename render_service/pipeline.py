"""渲染流水线：生成代码→渲染(纠错重试)→TTS→合轨。"""
from pathlib import Path

from .manim_render import render_code_with_error
from .codegen import generate_manim_code
from .retry import render_with_retry
from .tts import synthesize_to_file
from .mix import mix_audio

MEDIA_DIR = Path(__file__).resolve().parent / "media"


def run_pipeline(task_id: str, prompt: str, narration: str, voice: str, status_cb) -> str:
    out = MEDIA_DIR / task_id
    out.mkdir(parents=True, exist_ok=True)

    status_cb("generating")
    code = generate_manim_code(prompt)

    def gen_fn(prev_error):
        # 把渲染错误喂回 LLM 重新生成
        return generate_manim_code(f"{prompt}（上一次渲染报错：{prev_error}，请修复）")

    def render_fn(code, out_dir):
        mp4, _err = render_code_with_error(code, out_dir)
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

    # 返回相对 MEDIA_DIR 的真实产物路径（mix_audio 降级时可能是原始 manim mp4）
    return str(Path(final).relative_to(MEDIA_DIR)).replace("\\", "/")
