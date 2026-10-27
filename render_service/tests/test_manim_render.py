# render_service/tests/test_manim_render.py
from render_service.manim_render import render_code


def test_render_valid_code_returns_mp4(tmp_path):
    code = (
        "from manim import *\n"
        "class Demo(Scene):\n"
        "    def construct(self):\n"
        "        t = Text('hi')\n"
        "        self.add(t)\n"
        "        self.play(FadeIn(t))\n"
    )
    mp4 = render_code(code, str(tmp_path))
    assert mp4 is not None
    assert mp4.endswith(".mp4")


def test_render_invalid_code_returns_none(tmp_path):
    bad = "this is not python\n"
    assert render_code(bad, str(tmp_path)) is None
