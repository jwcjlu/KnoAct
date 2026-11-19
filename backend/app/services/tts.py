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

    def __init__(self, voice: str = "", api_key: str = "", app_id: str = "", api_secret: str = ""):
        super().__init__(voice=voice, api_key=api_key)
        self.app_id = app_id
        self.api_secret = api_secret

    def synthesize(self, text, voice="", speed=1.0):
        from .xunfei_tts import synthesize_xunfei

        return synthesize_xunfei(
            text=text,
            app_id=self.app_id,
            api_key=self.api_key,
            api_secret=self.api_secret,
            voice=voice or self.voice,
            speed=speed,
        )


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


def tts_lang_for_text(text: str) -> str:
    """听写短词语言：含汉字 → zh，否则 en。"""
    for ch in text or "":
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


def _public_tts_chunks(text: str) -> list[str]:
    """有道中文接口基本只吃 1～2 字；英文可稍长。按标点切开再按长度切段。"""
    import re

    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    lang = tts_lang_for_text(text)
    max_len = 2 if lang == "zh" else 40
    parts = [p.strip() for p in re.split(r"[，。！？、；：,.!?;:\s]+", text) if p.strip()]
    if not parts:
        parts = [text]
    out: list[str] = []
    for part in parts:
        if len(part) <= max_len:
            out.append(part)
            continue
        for i in range(0, len(part), max_len):
            out.append(part[i : i + max_len])
    return out[:12]  # 试听/听写足够；避免一次打太多请求


def _looks_like_mp3(data: bytes, ctype: str = "") -> bool:
    if not data or len(data) < 200:
        return False
    ctype = (ctype or "").lower()
    if "json" in ctype or data[:1] == b"{":
        return False
    return True


def _fetch_youdao_mp3(piece: str, lang: str) -> bytes:
    import requests
    from urllib.parse import quote

    if lang == "zh":
        url = f"https://dict.youdao.com/dictvoice?le=zh&audio={quote(piece)}"
    else:
        url = f"https://dict.youdao.com/dictvoice?audio={quote(piece)}"
    resp = requests.get(
        url,
        timeout=12,
        headers={"User-Agent": "Mozilla/5.0 (compatible; KnoAct/1.0)"},
    )
    data = resp.content or b""
    if resp.status_code != 200 or not _looks_like_mp3(data, resp.headers.get("Content-Type") or ""):
        raise RuntimeError(f"public_tts_http_{resp.status_code}")
    return data


def _fetch_google_mp3(piece: str, lang: str) -> bytes:
    import requests
    from urllib.parse import quote

    tl = "zh-CN" if lang == "zh" else "en"
    url = (
        "https://translate.google.com/translate_tts"
        f"?ie=UTF-8&client=tw-ob&tl={tl}&q={quote(piece)}"
    )
    resp = requests.get(
        url,
        timeout=12,
        headers={"User-Agent": "Mozilla/5.0 (compatible; KnoAct/1.0)"},
    )
    data = resp.content or b""
    if resp.status_code != 200 or not _looks_like_mp3(data, resp.headers.get("Content-Type") or ""):
        raise RuntimeError(f"public_tts_google_{resp.status_code}")
    return data


def _fetch_public_mp3(piece: str, lang: str) -> bytes:
    try:
        return _fetch_youdao_mp3(piece, lang)
    except Exception:
        return _fetch_google_mp3(piece, lang)


def synthesize_public_mp3(text: str) -> bytes:
    """商用 TTS 不可用时的朗读兜底（有道 → Google）。

    安卓多数机型预装英文 TTS、未装中文语音包：英语听写能播、语文听写静音。
    此兜底对中英文都返回可播放的 audio/mpeg，供 Flutter AudioPlayer 播放。
    """
    text = (text or "").strip()
    if not text or len(text) > 120:
        raise RuntimeError("public_tts_unsupported_text")
    lang = tts_lang_for_text(text)
    chunks = _public_tts_chunks(text)
    if not chunks:
        raise RuntimeError("public_tts_empty")
    # 单段直接返回；多段简单拼接 MPEG 帧（听写/试听足够）
    parts = [_fetch_public_mp3(c, lang) for c in chunks]
    return b"".join(parts)


PROVIDERS = {"minimax": MiniMaxTTS, "xunfei": XunfeiTTS, "openai": OpenAITTS, "fake": FakeTTS}


def _xunfei_credentials(r) -> tuple[str, str]:
    opts = r.options or {}
    hdr = r.extra_headers if isinstance(r.extra_headers, dict) else {}
    app_id = (opts.get("app_id") or hdr.get("app_id") or "").strip()
    api_secret = (opts.get("api_secret") or hdr.get("api_secret") or "").strip()
    return app_id, api_secret


def get_tts(db: Session, child_id: int | None = None) -> TTSProvider:
    from .model_config import resolve
    r = resolve(db, "tts", child_id)
    voice = r.options.get("voice", "")
    cls = PROVIDERS.get(r.provider, FakeTTS)
    if cls is OpenAITTS:
        return cls(voice=voice, api_key=r.api_key, base_url=r.base_url, model=r.model)
    if cls is XunfeiTTS:
        app_id, api_secret = _xunfei_credentials(r)
        return cls(voice=voice, api_key=r.api_key, app_id=app_id, api_secret=api_secret)
    return cls(voice=voice, api_key=r.api_key)
