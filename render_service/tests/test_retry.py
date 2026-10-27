# render_service/tests/test_retry.py
from render_service.retry import render_with_retry


def test_retry_succeeds_on_second_attempt():
    calls = {"n": 0}

    def fake_render(code, out_dir):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # 第一次失败
        return "final.mp4"

    def fake_gen(prev_error):
        return "fixed code"

    url = render_with_retry("bad code", fake_gen, fake_render, "/tmp")
    assert url == "final.mp4"
    assert calls["n"] == 2


def test_retry_gives_up_after_max():
    def always_fail(code, out_dir):
        return None
    def fake_gen(prev_error):
        return "still bad"
    url = render_with_retry("bad", fake_gen, always_fail, "/tmp", max_retries=3)
    assert url is None
