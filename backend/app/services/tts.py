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

    # MiniMax T2A v2：返回 base64 编码的 MP3
    URL = "https://api.minimax.chat/v1/t2a_v2?GroupId={group_id}"

    def synthesize(self, text, voice="", speed=1.0):
        import base64
        import requests
        if not self.api_key:
            raise RuntimeError("MiniMax API Key 未配置")
        # GroupId 复用 API Key 前半段（实际项目应由用户单独配置 group_id）
        group_id = self.api_key.split("-")[0]
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "speech-01-turbo",
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice or "male-qn-qingse",
                "speed": speed,
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
        }
        resp = requests.post(self.URL.format(group_id=group_id), headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"MiniMax TTS 失败：{resp.status_code} {resp.text[:200]}")
        data = resp.json()
        audio_b64 = data.get("data", {}).get("audio")
        if not audio_b64:
            raise RuntimeError("MiniMax TTS 返回无音频")
        return base64.b64decode(audio_b64)


class XunfeiTTS(TTSProvider):
    name = "xunfei"

    def synthesize(self, text, voice="", speed=1.0):
        if not self.api_key:
            raise RuntimeError("讯飞 API Key 未配置")
        # 讯飞在线语音合成需 WebSocket + 鉴权签名，此处留待接入（前端用浏览器 speechSynthesis 兜底）
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
