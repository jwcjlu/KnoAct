from abc import ABC, abstractmethod

from sqlalchemy.orm import Session

import re

_CJK_RANGE_RE = re.compile(r"[\u4e00-\u9fff]")
_PUNCT_RE = re.compile(r"[，。！？；：、,\.!\?;:]")


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


class QwenTTS(TTSProvider):
    name = "qwen"

    def __init__(self, voice: str = "", api_key: str = "", base_url: str = "", model: str = ""):
        super().__init__(voice=voice, api_key=api_key)
        self.base_url = base_url
        self.model = model or "qwen3-tts-flash"

    def synthesize(self, text, voice="", speed=1.0):
        from .qwen_tts import synthesize_qwen

        return synthesize_qwen(
            text=text,
            api_key=self.api_key,
            voice=voice or self.voice or "Cherry",
            model=self.model,
            base_url=self.base_url,
            speed=speed,
        )


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
    """把文本切成公开接口能一次合成的段。

    ⚠️ 中文**绝不能按 2 字硬切**。原来的实现按 `max_len = 2` 切段，理由是
    「有道中文接口基本只吃 1～2 字」；但那样每 2 个字都是一次独立录音，
    逐段拼起来的音频语调断续、段间还有录音头尾的静音，
    听起来就是「两个字两个字地蹦出来」，而且会把词切断（「来学/习小」）。

    有道是**词典发音**接口，本来就只该用于单词；长句交给 Google
    （实测 120 字整段可合成，语调连贯）。超长文本才按句末标点切，
    并把相邻短句并到接近上限，尽可能少切。
    """
    import re

    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    lang = tts_lang_for_text(text)
    max_len = 100 if lang == "zh" else 180
    if len(text) <= max_len:
        return [text]

    # 先按句末标点切句（保留标点），短句相邻合并
    parts = [p for p in re.split(r"(?<=[。！？；!?;])", text) if p.strip()]
    out: list[str] = []
    buf = ""
    for part in parts:
        if len(buf) + len(part) <= max_len:
            buf += part
            continue
        if buf.strip():
            out.append(buf.strip())
        # 单句本身超长 → 退到最近的逗号/顿号再切，避免切断词
        while len(part) > max_len:
            cut = max(part.rfind("，", 0, max_len),
                      part.rfind(",", 0, max_len),
                      part.rfind("、", 0, max_len))
            cut = cut + 1 if cut > 0 else max_len
            out.append(part[:cut].strip())
            part = part[cut:]
        buf = part
    if buf.strip():
        out.append(buf.strip())
    # 上限与 synthesize_public_mp3 的 3000 字输入上限匹配：每段最多 100 字，
    # 40 段足以覆盖 3000 字，不会静默丢掉课文尾巴。
    return out[:40]


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


def _is_dict_word(piece: str) -> bool:
    r"""是不是「词典词条」形态（有道 dictvoice 只吃词条，整句稳定 500）。

    判据分中英文，因为**中文没有空格**，不能靠词数判断：
    - 含任何标点（，。！？；：、,.!?;:）→ 不是词条
    - 含汉字 → 按字数限制（词典词条多为 2~6 字，留到 8 字）；
      长中文句子没有标点时也会走到这里，必须靠字数挡住，否则会去撞 500 白等超时
    - 英文/其它 → 按空格词数限制（`ice cream`=2、`T-shirt`=1 可用；
      `What do we do at the weekend`=6 会 500）
    """
    body = (piece or "").strip()
    if not body:
        return False
    if _PUNCT_RE.search(body):
        return False
    if _CJK_RANGE_RE.search(body):
        return len(body) <= 8
    return len(body.split()) <= 4


def _fetch_real_human_mp3(piece: str, lang: str) -> bytes:
    r"""取真人词典录音（目前只有有道这一条可用来源）。

    听写场景下真人录音听感远胜合成音，所以优先走这里；但词典收录有限
    （「春暖花开」「小数除法」这类词条稳定 500），调用方必须准备好回落。
    实测中文词典词条覆盖约 90%，英文单词覆盖 100%。
    """
    if not _is_dict_word(piece):
        raise RuntimeError("public_tts_not_a_word")
    return _fetch_youdao_mp3(piece, lang)


def _fetch_public_mp3(piece: str, lang: str) -> bytes:
    """单段公开朗读兜底（真人录音失败后用）。

    有道是**词典**接口，只对词条有效；这里按形态分流，避免拿整句去
    撞 500 再多等一个超时：
    - 词条形态 → 先试有道真人录音，失败再 Google
    - 整句/含标点 → 直接 Google（实测 120 字整段可合成，语调连贯）
    """
    if _is_dict_word(piece):
        try:
            return _fetch_youdao_mp3(piece, lang)
        except Exception:
            pass
    return _fetch_google_mp3(piece, lang)


def synthesize_public_mp3(text: str) -> bytes:
    """商用 TTS 不可用时的朗读兜底（有道 → Google）。

    安卓多数机型预装英文 TTS、未装中文语音包：英语听写能播、语文听写静音。
    此兜底对中英文都返回可播放的 audio/mpeg，供 Flutter AudioPlayer 播放。

    上限 3000 字：课文朗读会一次传整段，原来的 120 字上限会让长课文直接
    抛错退回浏览器合成（音色突变，安卓还可能静音）。分段逻辑见
    `_public_tts_chunks`，超长才按句切，不按 2 字硬切。
    """
    text = (text or "").strip()
    if not text or len(text) > 3000:
        raise RuntimeError("public_tts_unsupported_text")
    lang = tts_lang_for_text(text)
    chunks = _public_tts_chunks(text)
    if not chunks:
        raise RuntimeError("public_tts_empty")
    # 单段直接返回；多段简单拼接 MPEG 帧（听写/试听足够）
    parts = [_fetch_public_mp3(c, lang) for c in chunks]
    return b"".join(parts)


# ===== 听写真人录音 + 磁盘缓存 =====
#
# 听写会反复点「听发音」，同一个词不该每次都去外网下载；而且真人录音
# 是固定内容，天然可缓存。缓存目录在 backend/uploads/ 下（已 gitignore）。

_CACHE_DIR = "uploads/tts_cache"


def _cache_path(text: str, lang: str) -> str:
    """缓存文件路径。用 sha1 命名：避免中文/标点进文件名，也不同词撞车。"""
    import hashlib
    import os

    key = hashlib.sha1(f"{lang}:{text}".encode("utf-8")).hexdigest()[:20]
    return os.path.join(_CACHE_DIR, f"{lang}_{key}.mp3")


def _read_cache(path: str) -> bytes | None:
    import os

    try:
        if os.path.isfile(path) and os.path.getsize(path) > 200:
            with open(path, "rb") as fh:
                return fh.read()
    except OSError:
        pass
    return None


def _write_cache(path: str, data: bytes) -> None:
    import os

    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        # 先写临时文件再改名：避免并发请求读到写了一半的文件
        tmp = f"{path}.{os.getpid()}.tmp"
        with open(tmp, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except OSError:
        pass


def _cache_drop(path: str) -> None:
    r"""删掉缓存（用于「缓存的是错误内容」时自愈，例如旧版本写进去的坏音频）。"""
    import os

    try:
        os.remove(path)
    except OSError:
        pass


def word_audio(text: str, *, allow_public: bool = True) -> bytes | None:
    r"""听写发音：真人词典录音优先，带磁盘缓存。

    返回 None 表示「真人录音拿不到」——调用方应当改用合成 TTS，
    不要在这里静默改成别的音源，否则音色会在同一课里来回跳。

    `allow_public=False` 时只用缓存（离线/无外网时仍可复习已听过的词）。
    """
    body = (text or "").strip()
    if not body or not _is_dict_word(body):
        return None
    lang = tts_lang_for_text(body)
    path = _cache_path(body, lang)

    cached = _read_cache(path)
    if cached is not None:
        return cached
    if not allow_public:
        return None
    try:
        data = _fetch_real_human_mp3(body, lang)
    except Exception:
        return None
    if data:
        _write_cache(path, data)
    return data or None


PROVIDERS = {
    "minimax": MiniMaxTTS,
    "xunfei": XunfeiTTS,
    "openai": OpenAITTS,
    "qwen": QwenTTS,
    "fake": FakeTTS,
}


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
    if cls is QwenTTS:
        return cls(
            voice=voice,
            api_key=r.api_key,
            base_url=r.base_url or "",
            model=r.model or "qwen3-tts-flash",
        )
    return cls(voice=voice, api_key=r.api_key)
