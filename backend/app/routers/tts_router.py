"""语音合成端点：真实 provider 返回音频字节；fake/失败时尽量返回公开朗读 MP3。"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..database import get_db
from ..models import User
from ..services.tts import get_tts, sniff_audio_media_type, synthesize_public_mp3, word_audio

router = APIRouter(prefix="/api/tts", tags=["tts"])


def _browser_tts_fallback(*, configured: bool, reason: str = ""):
    # 最终兜底：Web 可走 speechSynthesis；安卓中文常无语音包，应尽量不落到这里
    return {
        "provider": "fake",
        "use_browser_tts": True,
        "configured": configured,
        "reason": (reason or "")[:200],
    }


def _configured_speed(db) -> float:
    """取配置里家长设的语速（tts profile 的 options.speed），默认 1.0。

    家长端「语音 → 语速」滑块写的就是这个值；调用方没显式传 speed 时以它为准，
    否则滑块调了没用。
    """
    from ..services.model_config import resolve

    try:
        raw = (resolve(db, "tts").options or {}).get("speed")
        val = float(raw)
    except (TypeError, ValueError):
        return 1.0
    return max(0.5, min(2.0, val))


@router.get("/synthesize")
def synthesize(
    text: str = Query(...),
    voice: str = Query(""),
    # speed 必须允许为空：只有调用方显式指定时才覆盖配置。
    # 原来默认 1.0 且被原样传给 provider，导致家长端「语速」滑块配的
    # 值（tts profile options.speed）被 1.0 顶掉，怎么调都是原速。
    speed: float | None = Query(None),
    # 听写词条优先用真人词典录音：合成音念单词的听感与真人差距明显，
    # 而听写的唯一要求就是「听起来像真人念的」。
    real: bool = Query(True),
    db: Session = Depends(get_db),
    _auth: User = Depends(get_current_user),
):
    # 1) 真人录音优先（仅词条形态；整句/课文跳过，词典接口不支持）
    if real:
        human = word_audio(text)
        if human:
            return Response(content=human, media_type="audio/mpeg")

    # 2) 合成 TTS
    tts = get_tts(db)
    configured = tts.name != "fake"
    if speed is None:
        speed = _configured_speed(db)
    upstream_err = ""
    if configured:
        try:
            audio = tts.synthesize(text, voice=voice, speed=speed)
            return Response(content=audio, media_type=sniff_audio_media_type(audio))
        except Exception as e:
            upstream_err = str(e)
    # 3) fake 或商用合成失败：公开朗读兜底（安卓无中文语音包 / 中转站欠费）
    try:
        return Response(content=synthesize_public_mp3(text), media_type="audio/mpeg")
    except Exception as e:
        reason = upstream_err or str(e)
        return _browser_tts_fallback(configured=configured, reason=reason)
