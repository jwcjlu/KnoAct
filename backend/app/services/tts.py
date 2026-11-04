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
        # TODO: 讯飞在线语音合成需 WebSocket + 鉴权签名，未实现（前端用浏览器 speechSynthesis 兜底）
        raise NotImplementedError("讯飞 TTS 待接入")


class OpenAITTS(TTSProvider):
    """中转站 / OpenAI 兼容 TTS：走 /v1/audio/speech 标准接口。

    base_url 指向中转站地址（如 https://aiapi.icloudsky.com/v1），
    voice 用 OpenAI 标准音色（alloy/echo/fable/onyx/nova/shimmer）或中转站自定义音色。
    """
    name = "openai"

    def __init__(self, voice: str = "", api_key: str = "", base_url: str = "", model: str = ""):
        super().__init__(voice=voice, api_key=api_key)
        self.base_url = base_url
        self.model = model or "speech-2.8-hd"

    def synthesize(self, text, voice="", speed=1.0):
        from openai import OpenAI
        if not self.api_key:
            raise RuntimeError("API Key 未配置")
        if not self.base_url:
            raise RuntimeError("中转站 Base URL 未配置")
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        voice = voice or self.voice or "alloy"
        resp = client.audio.speech.create(
            model=self.model,
            voice=voice,
            input=text,
            speed=speed,
        )
        return resp.content


class FakeTTS(TTSProvider):
    """本地兜底：返回占位字节。前端实际播放走浏览器 speechSynthesis。"""
    name = "fake"

    def synthesize(self, text, voice="", speed=1.0):
        return text.encode("utf-8")


PROVIDERS = {"minimax": MiniMaxTTS, "xunfei": XunfeiTTS, "openai": OpenAITTS, "fake": FakeTTS}


def get_tts(db: Session, child_id: int | None = None) -> TTSProvider:
    from .model_config import resolve
    r = resolve(db, "tts", child_id)
    voice = r.options.get("voice", "")
    cls = PROVIDERS.get(r.provider, FakeTTS)
    if cls is OpenAITTS:
        return cls(voice=voice, api_key=r.api_key, base_url=r.base_url, model=r.model)
    return cls(voice=voice, api_key=r.api_key)
