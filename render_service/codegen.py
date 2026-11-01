"""LLM 生成 manim 代码：含最小可用模板引导 + fake 兜底。"""
import sys
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parents[1] / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


TEMPLATE = '''from manim import *

class Demo(Scene):
    def construct(self):
        # 在这里写动画：例如展示一个公式
        formula = MathTex(r"{topic}")
        self.play(Write(formula))
        self.wait(1)
'''

SYSTEM = (
    "你是 manim 动画代码生成器。只输出可运行的 Python manim 代码，"
    "不要输出解释文字，不要用 markdown 代码围栏。"
    "必须包含 `from manim import *` 和一个继承 Scene 的类。"
    "数学公式用 MathTex 包裹 LaTeX。"
)


def generate_manim_code(prompt: str, timeout: float = 300.0) -> str:
    from app.services.ai import get_provider
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        provider = get_provider(db)
        raw = provider.generate(
            prompt=f"生成一个演示以下数学概念的 manim 动画：{prompt}。公式优先用 MathTex。",
            system=SYSTEM,
            timeout=timeout,
        )
    except Exception:
        raw = ""
    finally:
        db.close()

    code = (raw or "").strip()
    if not code or "class" not in code or "Scene" not in code:
        # 超时 / 失败 / fake 兜底：返回模板，保证能渲染出视频
        return TEMPLATE.format(topic=prompt)
    return code
