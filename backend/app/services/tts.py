from abc import ABC, abstractmethod
from sqlalchemy.orm import Session


class TTSProvider(ABC):
    name = "base"

    def __init__(self, voice: str = "", api_key: str = ""):
        self.voice = voice
        self.api_key = api_key

    @abstractmethod
    def synthesize(self, text: str, voice: str = "", speed: float = 1.0) -> bytes:
        ...


class MiniMaxTTS(TTSProvider):
    name = "minimax"

    def synthesize(self, text, voice="", speed=1.0):
        if not self.api_key:
            raise RuntimeError("MiniMax API Key 未配置")
        raise NotImplementedError("MiniMax TTS 待接入")


class XunfeiTTS(TTSProvider):
    name = "xunfei"

    def synthesize(self, text, voice="", speed=1.0):
        if not self.api_key:
            raise RuntimeError("讯飞 API Key 未配置")
        raise NotImplementedError("讯飞 TTS 待接入")


class FakeTTS(TTSProvider):
    """本地兜底：返回占位字节。前端实际播放走浏览器 speechSynthesis。"""
    name = "fake"

    def synthesize(self, text, voice="", speed=1.0):
        return text.encode("utf-8")


PROVIDERS = {"minimax": MiniMaxTTS, "xunfei": XunfeiTTS, "fake": FakeTTS}


def get_tts(db: Session) -> TTSProvider:
    from ..models import ModelConfig
    cfg = {r.key: r.value for r in db.query(ModelConfig).all()}
    provider_name = cfg.get("tts_provider", "fake")
    voice = cfg.get("tts_voice", "")
    api_key = cfg.get("tts_key", "")
    cls = PROVIDERS.get(provider_name, FakeTTS)
    return cls(voice=voice, api_key=api_key)
