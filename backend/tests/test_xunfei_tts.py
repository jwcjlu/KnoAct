import base64
import json

from app.services.xunfei_tts import assemble_auth_url, map_speed_to_xunfei, map_xunfei_voice, synthesize_xunfei
from app.services.tts import XunfeiTTS


def test_map_xunfei_voice_aliases():
    assert map_xunfei_voice("讯飞女声") == "xiaoyan"
    assert map_xunfei_voice("aisjiuxu") == "aisjiuxu"


def test_map_speed_to_xunfei():
    assert map_speed_to_xunfei(1.0) == 50
    assert map_speed_to_xunfei(2.0) == 100


def test_assemble_auth_url_contains_params():
    url = assemble_auth_url("test_api_key", "test_api_secret")
    assert url.startswith("wss://tts-api.xfyun.cn/v2/tts?")
    assert "authorization=" in url
    assert "host=tts-api.xfyun.cn" in url


def test_synthesize_collects_audio_chunks(monkeypatch):
    frames = [
        json.dumps({"code": 0, "data": {"audio": base64.b64encode(b"abc").decode("ascii"), "status": 1}}),
        json.dumps({"code": 0, "data": {"audio": "", "status": 2}}),
    ]

    class FakeWS:
        def send(self, _payload):
            return None

        def recv(self):
            if not frames:
                return ""
            return frames.pop(0)

        def close(self):
            return None

    monkeypatch.setattr("websocket.create_connection", lambda *_a, **_k: FakeWS())
    audio = synthesize_xunfei(
        text="你好",
        app_id="app",
        api_key="key",
        api_secret="secret",
        voice="讯飞女声",
    )
    assert audio == b"abc"


def test_xunfei_tts_provider_requires_credentials():
    p = XunfeiTTS(api_key="k", app_id="", api_secret="")
    try:
        p.synthesize("测")
        assert False, "应抛出配置错误"
    except RuntimeError as e:
        assert "APPID" in str(e)


def test_long_text_is_split_not_silently_truncated():
    """超长文本以前被 `body = body[:2000]` 无声砍掉后半篇（念到一半突然停）。
    必须切段后逐段合成，字节完整覆盖。"""
    from app.services.xunfei_tts import _MAX_BYTES, _split_for_xunfei

    text = "同学们好，我们开始上课。" * 1000      # 12000 字 / 36000 字节
    parts = _split_for_xunfei(text)
    assert len(parts) > 1
    assert all(len(p.encode("utf-8")) <= _MAX_BYTES for p in parts)
    assert "".join(parts) == text, "切段必须无丢失、无重叠"


def test_short_text_not_split():
    from app.services.xunfei_tts import _split_for_xunfei

    assert _split_for_xunfei("今天我们来学习小数除法") == ["今天我们来学习小数除法"]


def test_long_text_synthesizes_each_chunk(monkeypatch):
    """长文本应当发多次请求，且返回的音频是各段拼接。"""
    from app.services import xunfei_tts

    sent = []

    class FakeWS:
        def send(self, payload):
            sent.append(json.loads(payload)["data"]["text"])

        def recv(self):
            audio = base64.b64encode(b"A").decode("ascii")
            return json.dumps({"code": 0, "data": {"audio": audio, "status": 2}})

        def close(self):
            return None

    monkeypatch.setattr("websocket.create_connection", lambda *_a, **_k: FakeWS())
    out = xunfei_tts.synthesize_xunfei(
        text="同学们好，我们开始上课。" * 500,
        app_id="app", api_key="key", api_secret="secret",
    )
    assert len(sent) > 1, "长文本应分多次请求"
    assert out == b"A" * len(sent), "各段音频应拼成一个 MP3"
