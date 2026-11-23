from app import models  # noqa: F401  ensure model tables registered before create_all
from app.services.tts import get_tts, TTSProvider, FakeTTS, tts_lang_for_text


def test_get_tts_default_fake(db):
    p = get_tts(db)
    assert isinstance(p, TTSProvider)


def test_tts_config_switch(db):
    from app.models import ModelConfig
    db.add(ModelConfig(key="tts_provider", value="xunfei"))
    db.add(ModelConfig(key="tts_voice", value="讯飞女声"))
    db.commit()
    p = get_tts(db)
    assert p.name == "xunfei"
    assert p.voice == "讯飞女声"


def test_synthesize_returns_bytes():
    p = FakeTTS()
    audio = p.synthesize("徘徊", voice="童声", speed=1.0)
    assert isinstance(audio, bytes) and audio


def test_tts_lang_for_text():
    assert tts_lang_for_text("箩") == "zh"
    assert tts_lang_for_text("糕饼") == "zh"
    assert tts_lang_for_text("hello") == "en"
    assert tts_lang_for_text("go fishing") == "en"


def test_public_tts_chunks_do_not_split_chinese_by_two_chars():
    """中文长句绝不能按 2 字硬切——那会变成「两个字两个字地蹦」，
    而且会切断词（「来学/习小」）。整句应当一次合成。"""
    from app.services.tts import _public_tts_chunks

    text = "今天我们来学习小数除法"
    assert _public_tts_chunks(text) == [text]

    # 常规长度（<= 上限）整句不切
    parts = _public_tts_chunks("你好，这是语音合成测试")
    assert parts == ["你好，这是语音合成测试"]


def test_public_tts_chunks_split_only_when_too_long():
    """超长文本才切，且以句末标点为界、不切断词。"""
    from app.services.tts import _public_tts_chunks

    sentence = "同学们好，我们开始上课。"
    parts = _public_tts_chunks(sentence * 12)
    assert len(parts) > 1
    assert all(len(p) <= 100 for p in parts)
    # 每段都以完整的句子单位收尾，不会出现「来学」「习小」这种硬切
    for p in parts:
        assert p.endswith("。"), p


def test_minimax_missing_key_raises():
    from app.services.tts import MiniMaxTTS
    p = MiniMaxTTS(api_key="")
    try:
        p.synthesize("徘徊")
        assert False, "应抛出 RuntimeError"
    except RuntimeError:
        pass


def test_public_fallback_uses_youdao_only_for_words(monkeypatch):
    """有道是词典接口（实测长句稳定 500），只该用于词条；长句直接走 Google，
    避免先失败一次再多等一个超时。"""
    from app.services import tts as tts_mod

    calls = []
    monkeypatch.setattr(tts_mod, "_fetch_youdao_mp3",
                        lambda piece, lang: calls.append(("youdao", piece)) or b"Y" * 300)
    monkeypatch.setattr(tts_mod, "_fetch_google_mp3",
                        lambda piece, lang: calls.append(("google", piece)) or b"G" * 300)

    assert tts_mod._fetch_public_mp3("徘徊", "zh") == b"Y" * 300
    assert calls[-1][0] == "youdao"

    long_text = "今天我们来学习小数除法"
    assert tts_mod._fetch_public_mp3(long_text, "zh") == b"G" * 300
    assert calls[-1] == ("google", long_text)


def test_dict_word_detection():
    r"""词条判定必须挡住长句，否则会去撞有道 500 白等超时。

    中文没有空格，不能靠词数判断——这是实际踩到的坑：修复前
    「今天我们来学习小数除法」因为 split() 只有 1 个元素而被误判成词条。
    """
    from app.services.tts import _is_dict_word

    # 词条
    for w in ("weekend", "快乐", "向日葵", "平行四边形", "ice cream", "T-shirt"):
        assert _is_dict_word(w), w
    # 长句 / 含标点 / 超长中文
    for w in (
        "What do we do at the weekend",      # 6 个词
        "今天我们来学习小数除法",              # 11 个汉字
        "快乐。",                             # 含标点
        "hello, world",
        "",
    ):
        assert not _is_dict_word(w), w


def test_word_audio_returns_none_when_not_a_word():
    """长句不该走真人词典录音（返回 None，由调用方回落合成 TTS）。"""
    from app.services.tts import word_audio

    assert word_audio("今天我们来学习小数除法") is None


def test_word_audio_uses_cache(monkeypatch, tmp_path):
    """真人录音必须落磁盘缓存：听写会反复点「听发音」，不能每次都下载。"""
    from app.services import tts as tts_mod

    monkeypatch.setattr(tts_mod, "_CACHE_DIR", str(tmp_path))
    calls = []
    monkeypatch.setattr(tts_mod, "_fetch_real_human_mp3",
                        lambda piece, lang: calls.append(piece) or b"A" * 400)

    first = tts_mod.word_audio("快乐")
    assert first == b"A" * 400
    assert len(calls) == 1

    # 第二次应命中缓存，不再请求
    again = tts_mod.word_audio("快乐")
    assert again == b"A" * 400
    assert len(calls) == 1, "第二次应从缓存读取，不应再请求外网"


def test_word_audio_returns_none_on_uncollected_word(monkeypatch, tmp_path):
    """词典未收录（稳定 500）时返回 None，交回合成 TTS 兜底。"""
    from app.services import tts as tts_mod

    monkeypatch.setattr(tts_mod, "_CACHE_DIR", str(tmp_path))

    def boom(piece, lang):
        raise RuntimeError("public_tts_http_500")

    monkeypatch.setattr(tts_mod, "_fetch_real_human_mp3", boom)
    assert tts_mod.word_audio("春暖花开") is None


def test_tts_endpoint_fake_uses_browser_when_public_fails(setup_db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.database import SessionLocal
    from conftest import make_account, auth_headers

    monkeypatch.setattr(tts_router, "synthesize_public_mp3", lambda text: (_ for _ in ()).throw(RuntimeError("no_net")))
    # 关掉真人录音，专测合成链路（真机词库里没有「徘徊」以外的词条）
    monkeypatch.setattr(tts_router, "word_audio", lambda text: None)
    s = SessionLocal()
    u = make_account(s, "u_tts", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=徘徊", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body["use_browser_tts"] is True
    assert body.get("configured") is False


def test_tts_endpoint_fake_returns_public_mp3(setup_db, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.database import SessionLocal
    from conftest import make_account, auth_headers

    fake_mp3 = b"ID3" + b"\x00" * 300
    monkeypatch.setattr(tts_router, "synthesize_public_mp3", lambda text: fake_mp3)
    monkeypatch.setattr(tts_router, "word_audio", lambda text: None)
    s = SessionLocal()
    u = make_account(s, "u_tts_mp3", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=箩", headers=h)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/mpeg")
    assert resp.content == fake_mp3


def test_tts_endpoint_prefers_real_human_recording(setup_db, monkeypatch):
    """真人录音可用时必须优先，不能走合成。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.database import SessionLocal
    from conftest import make_account, auth_headers

    human = b"ID3" + b"H" * 400
    monkeypatch.setattr(tts_router, "word_audio", lambda text: human)

    def _boom(*_a, **_k):
        raise AssertionError("有真人录音时不应调用合成")

    monkeypatch.setattr(tts_router, "synthesize_public_mp3", _boom)
    s = SessionLocal()
    u = make_account(s, "u_tts_real", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=快乐", headers=h)
    assert resp.status_code == 200
    assert resp.content == human


def test_tts_endpoint_real_false_skips_human(setup_db, monkeypatch):
    """real=false 时应跳过真人录音（试听/课文朗读走合成，音色可控）。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.database import SessionLocal
    from conftest import make_account, auth_headers

    synth = b"ID3" + b"S" * 400
    monkeypatch.setattr(tts_router, "word_audio", lambda text: b"ID3" + b"H" * 400)
    monkeypatch.setattr(tts_router, "synthesize_public_mp3", lambda text: synth)
    s = SessionLocal()
    u = make_account(s, "u_tts_noreal", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=快乐&real=false", headers=h)
    assert resp.status_code == 200
    assert resp.content == synth


def test_tts_endpoint_synthesize_fail_degrades_to_public_then_browser(setup_db, monkeypatch):
    """配置了真实 provider 但合成失败时：先公开朗读，再浏览器兜底；不 502。"""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.models import ModelConfig
    from app.routers import tts_router
    from app.routers.tts_router import router
    from app.database import SessionLocal
    from conftest import make_account, auth_headers

    monkeypatch.setattr(tts_router, "synthesize_public_mp3", lambda text: (_ for _ in ()).throw(RuntimeError("no_net")))
    monkeypatch.setattr(tts_router, "word_audio", lambda text: None)
    s = SessionLocal()
    s.add(ModelConfig(key="tts_provider", value="xunfei"))
    s.add(ModelConfig(key="tts_key", value="dummy"))
    u = make_account(s, "u_tts_xf", "child")
    s.commit()
    h = auth_headers(u)
    s.close()
    app = FastAPI()
    app.include_router(router)
    resp = TestClient(app).get("/api/tts/synthesize?text=算", headers=h)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("use_browser_tts") is True
    assert body.get("provider") == "fake"
    assert body.get("configured") is True
