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
