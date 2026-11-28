from app.services.tts_warmup import collect_dictation_warmup_texts


def test_collect_speak_text_and_word():
    items = [
        {"word": "事", "speak_text": "事，事情的事"},
        {"word": "hello"},
        {"word": "同", "speak_text": "同"},
        {"word": "x", "speak_text": "x", "dictation_cue": '{"compound":"事情"}'},
    ]
    texts = collect_dictation_warmup_texts(items)
    assert "事，事情的事" in texts
    assert "事" in texts
    assert "hello" in texts
    assert texts.count("同") == 1
    assert not any("compound" in t or "{" in t for t in texts)


def test_collect_from_json_string():
    import json

    raw = json.dumps([{"word": "啊", "speak_text": "啊，惊讶的啊"}], ensure_ascii=False)
    texts = collect_dictation_warmup_texts(raw)
    assert "啊，惊讶的啊" in texts and "啊" in texts


def test_collect_caps_at_40():
    items = [{"word": f"w{i}", "speak_text": f"s{i}"} for i in range(30)]
    texts = collect_dictation_warmup_texts(items)
    assert len(texts) <= 40


def test_warmup_dictation_task_calls_cached_synth(db, monkeypatch, tmp_path):
    from datetime import date
    import json

    from app.models import Task
    from app.services import tts as tts_mod
    from app.services import tts_warmup as wu
    from conftest import make_account

    monkeypatch.setattr(tts_mod, "_SYNTH_CACHE_DIR", str(tmp_path / "synth"))
    seen = []

    def fake_cached(db, text, *, voice="", speed=1.0, child_id=None):
        seen.append(text)
        return b"ID3" + b"\x00" * 300

    monkeypatch.setattr(wu, "synthesize_commercial_cached", fake_cached)

    class Stub:
        name = "qwen"
        voice = "Cherry"
        model = "m"

        def synthesize(self, *a, **k):
            return b"ID3" + b"\x00" * 300

    monkeypatch.setattr(wu, "get_tts", lambda db, child_id=None: Stub())

    u = make_account(db, "u_warmup_synth", "child")
    db.commit()
    content = json.dumps(
        [
            {"word": "事", "speak_text": "事，事情的事"},
            {"word": "go"},
        ],
        ensure_ascii=False,
    )
    t = Task(
        user_id=u.id,
        task_type="dictation",
        subject="语文",
        title="t",
        detail="d",
        content=content,
        points=20,
        date=date.today(),
    )
    db.add(t)
    db.commit()
    db.refresh(t)

    wu.warmup_dictation_task(t.id)
    assert "事，事情的事" in seen
    assert "事" in seen
    assert "go" in seen
    assert not any("{" in x for x in seen)


def test_warmup_skips_fake(db, monkeypatch):
    from app.services import tts_warmup as wu
    from app.services.tts import FakeTTS

    called = []
    monkeypatch.setattr(wu, "get_tts", lambda db, child_id=None: FakeTTS())
    monkeypatch.setattr(
        wu,
        "synthesize_commercial_cached",
        lambda *a, **k: called.append(1) or b"x",
    )
    assert wu._should_skip_warmup(FakeTTS()) is True
    assert called == []


def test_warmup_item_failure_continues(db, monkeypatch, tmp_path):
    from datetime import date
    import json

    from app.models import Task
    from app.services import tts_warmup as wu
    from conftest import make_account

    texts_ok = []

    def flaky(db, text, **kwargs):
        if "fail" in text:
            raise RuntimeError("boom")
        texts_ok.append(text)
        return b"ID3" + b"\x00" * 300

    monkeypatch.setattr(wu, "synthesize_commercial_cached", flaky)

    class Stub:
        name = "qwen"
        voice = ""

    monkeypatch.setattr(wu, "get_tts", lambda db, child_id=None: Stub())

    u = make_account(db, "u_warmup_fail", "child")
    db.commit()
    content = json.dumps(
        [
            {"word": "fail"},
            {"word": "ok"},
        ],
        ensure_ascii=False,
    )
    t = Task(
        user_id=u.id,
        task_type="dictation",
        subject="语文",
        title="t",
        detail="d",
        content=content,
        points=20,
        date=date.today(),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    wu.warmup_dictation_task(t.id)
    assert "ok" in texts_ok


def test_schedule_only_new_dictation_ids(monkeypatch):
    from app.services import task_gen

    scheduled = []
    monkeypatch.setattr(
        "app.services.tts_warmup.schedule_dictation_warmup",
        lambda task_id: scheduled.append(task_id),
    )
    task_gen._schedule_dictation_warmups([11, 22])
    assert scheduled == [11, 22]


def test_schedule_swallows_errors(monkeypatch):
    from app.services import task_gen

    def boom(_tid):
        raise RuntimeError("nope")

    monkeypatch.setattr("app.services.tts_warmup.schedule_dictation_warmup", boom)
    task_gen._schedule_dictation_warmups([1])