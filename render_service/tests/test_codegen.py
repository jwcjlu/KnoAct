# render_service/tests/test_codegen.py
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///D:/workspace/github/KnoAct/backend/zhixueban.db")
from render_service.codegen import generate_manim_code


def test_generate_returns_code_string():
    code = generate_manim_code("演示 1/2 + 1/4 = 3/4")
    assert isinstance(code, str)
    assert "class" in code and "Scene" in code
