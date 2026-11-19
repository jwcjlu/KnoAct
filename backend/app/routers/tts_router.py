"""语音合成端点：真实 provider 返回音频字节；fake/失败时尽量返回公开朗读 MP3。"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..database import get_db
from ..models import User
from ..services.tts import get_tts, synthesize_public_mp3

router = APIRouter(prefix="/api/tts", tags=["tts"])


def _browser_tts_fallback(*, configured: bool, reason: str = ""):
    # 最终兜底：Web 可走 speechSynthesis；安卓中文常无语音包，应尽量不落到这里
    return {
        "provider": "fake",
        "use_browser_tts": True,
        "configured": configured,
        "reason": (reason or "")[:200],
    }


@router.get("/synthesize")
def synthesize(
    text: str = Query(...),
    voice: str = Query(""),
    speed: float = Query(1.0),
    db: Session = Depends(get_db),
    _auth: User = Depends(get_current_user),
):
    tts = get_tts(db)
    configured = tts.name != "fake"
    upstream_err = ""
    if configured:
        try:
            audio = tts.synthesize(text, voice=voice, speed=speed)
            return Response(content=audio, media_type="audio/mpeg")
        except Exception as e:
            upstream_err = str(e)
    # fake 或商用合成失败：公开朗读兜底（解决安卓语文听写无中文 TTS / 中转站欠费）
    try:
        return Response(content=synthesize_public_mp3(text), media_type="audio/mpeg")
    except Exception as e:
        reason = upstream_err or str(e)
        return _browser_tts_fallback(configured=configured, reason=reason)
