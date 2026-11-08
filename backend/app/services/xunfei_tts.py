"""科大讯飞在线语音合成（WebSocket v2）。"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from email.utils import formatdate
from urllib.parse import urlencode

_XUNFEI_HOST = "tts-api.xfyun.cn"
_XUNFEI_PATH = "/v2/tts"
_XUNFEI_WSS = f"wss://{_XUNFEI_HOST}{_XUNFEI_PATH}"

_VOICE_ALIASES = {
    "讯飞女声": "xiaoyan",
    "讯飞男声": "aisjiuxu",
    "标准普通话": "xiaoyan",
    "xiaoyan": "xiaoyan",
    "aisjiuxu": "aisjiuxu",
    "aisxping": "aisxping",
}


def map_xunfei_voice(voice: str) -> str:
    v = (voice or "").strip()
    if not v:
        return "xiaoyan"
    return _VOICE_ALIASES.get(v, v)


def map_speed_to_xunfei(speed: float) -> int:
    try:
        s = float(speed)
    except (TypeError, ValueError):
        s = 1.0
    return max(0, min(100, int(round(50 * s))))


def assemble_auth_url(api_key: str, api_secret: str) -> str:
    date = formatdate(timeval=None, localtime=False, usegmt=True)
    signature_origin = (
        f"host: {_XUNFEI_HOST}\n"
        f"date: {date}\n"
        f"GET {_XUNFEI_PATH} HTTP/1.1"
    )
    digest = hmac.new(
        api_secret.encode("utf-8"),
        signature_origin.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    signature = base64.b64encode(digest).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    query = urlencode({"authorization": authorization, "date": date, "host": _XUNFEI_HOST})
    return f"{_XUNFEI_WSS}?{query}"


def synthesize_xunfei(
    *,
    text: str,
    app_id: str,
    api_key: str,
    api_secret: str,
    voice: str = "",
    speed: float = 1.0,
    timeout: float = 30.0,
) -> bytes:
    import websocket

    app_id = (app_id or "").strip()
    api_key = (api_key or "").strip()
    api_secret = (api_secret or "").strip()
    if not app_id or not api_key or not api_secret:
        raise RuntimeError("讯飞 TTS 需配置 APPID、APIKey、APISecret")
    body = (text or "").strip()
    if not body:
        raise ValueError("合成文本为空")
    if len(body.encode("utf-8")) > 7900:
        body = body[:2000]

    url = assemble_auth_url(api_key, api_secret)
    vcn = map_xunfei_voice(voice)
    frame = {
        "common": {"app_id": app_id},
        "business": {
            "aue": "lame",
            "sfl": 1,
            "vcn": vcn,
            "speed": map_speed_to_xunfei(speed),
            "tte": "UTF8",
        },
        "data": {
            "status": 2,
            "text": base64.b64encode(body.encode("utf-8")).decode("ascii"),
        },
    }
    ws = websocket.create_connection(url, timeout=timeout)
    audio = bytearray()
    try:
        ws.send(json.dumps(frame, ensure_ascii=False))
        while True:
            raw = ws.recv()
            if not raw:
                break
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="replace")
            msg = json.loads(raw)
            code = msg.get("code", -1)
            if code != 0:
                raise RuntimeError(msg.get("message") or f"讯飞 TTS 错误 code={code}")
            data = msg.get("data") or {}
            chunk = data.get("audio") or ""
            if chunk:
                audio.extend(base64.b64decode(chunk))
            if data.get("status") == 2:
                break
    finally:
        ws.close()
    if not audio:
        raise RuntimeError("讯飞 TTS 未返回音频")
    return bytes(audio)
