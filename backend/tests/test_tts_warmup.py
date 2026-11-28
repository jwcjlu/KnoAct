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