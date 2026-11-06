"""语音合成端点：真实 provider 返回音频字节，fake 时前端用浏览器 speechSynthesis。"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..database import get_db
from ..models import User
from ..services.tts import get_tts

router = APIRouter(prefix="/api/tts", tags=["tts"])


@router.get("/synthesize")
def synthesize(
    text: str = Query(...),
    voice: str = Query(""),
    speed: float = Query(1.0),
    db: Session = Depends(get_db),
    _auth: User = Depends(get_current_user),
):
    tts = get_tts(db)
    if tts.name == "fake":
        # 前端走浏览器 speechSynthesis，无需后端音频
        return {"provider": "fake", "use_browser_tts": True}
    try:
        audio = tts.synthesize(text, voice=voice, speed=speed)
    except Exception as e:
        return Response(status_code=502, content=f'{{"error": "{str(e)}"}}', media_type="application/json")
    return Response(content=audio, media_type="audio/mpeg")
