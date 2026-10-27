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
