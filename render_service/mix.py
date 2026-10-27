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
