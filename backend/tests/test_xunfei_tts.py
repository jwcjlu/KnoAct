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
