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
