"""出题/材料生成工具：generate_listening / generate_quiz_questions / generate_diagnostic_questions。"""
import json

from ..core.context import UnifiedContext
from ..core.tool_protocol import BaseTool, ToolParameter


def _get_provider(ctx: UnifiedContext | None = None):
    from ..database import SessionLocal
    from ..services.ai import get_provider
    child_id = (ctx.user_id or None) if ctx is not None else None
    db = SessionLocal()
    try:
        return get_provider(db, child_id=child_id)
    finally:
        db.close()


def _get_db_session():
    from ..database import SessionLocal
    return SessionLocal()


class GenerateListeningTool(BaseTool):
    name = "generate_listening"
    description = "用小学生已学单词编一段英语对话，并出一道理解题"
    parameters = []

    def run(self, args, ctx: UnifiedContext) -> dict:
        provider = _get_provider(ctx)
        words = args.get("words") or []
        kps = args.get("knowledge_points") or []
        try:
            if words or kps:
                word_s = "、".join(words)
                kp_s = "、".join(kps)
                prompt = (
                    f"用以下已学单词编一段 3 句的英语对话，并出 1 道理解题。\n"
                    f"已学单词：{word_s}\n"
                    f"知识点：{kp_s}\n"
                    '只返回 JSON，格式：{"dialogue":"对话内容","question":"题目","answer":"答案"}'
                )
            else:
                prompt = ('用小学生已学单词编一段 3 句的英语对话，并出 1 道理解题。'
                          '只返回 JSON，格式：{"dialogue":"对话内容","question":"题目","answer":"答案"}')
            text = provider.generate(prompt=prompt, system="你是英语老师。", json_mode=True)
            data = json.loads(text)
            return {
                "dialogue": (data.get("dialogue") or "").strip(),
                "question": (data.get("question") or "").strip(),
                "answer": (data.get("answer") or "").strip(),
            }
        except Exception:
            return {
                "dialogue": "A: What can you do? B: I can sing.",
                "question": "对话里 B 会做什么？",
                "answer": "唱歌",
            }


class GenerateQuizQuestionsTool(BaseTool):
    name = "generate_quiz_questions"
    description = "针对课文出选择题（带证据校验，可选知识点关联）"
    parameters = [
        ToolParameter(name="text", type="string", description="课文内容"),
        ToolParameter(name="n", type="integer", description="题目数量", required=False),
        ToolParameter(name="knowledge_points", type="string", description="知识点 JSON 数组文本", required=False),
        ToolParameter(name="subject", type="string", description="学科：语文/英语/数学", required=False),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        from ..services.quiz import generate_quiz, QuizGenerationError
        db = _get_db_session()
        try:
            text = (args.get("text") or "").strip()
            n = args.get("n") or 3
            kps_raw = args.get("knowledge_points") or ""
            kps = json.loads(kps_raw) if kps_raw else None
            subject = (args.get("subject") or "语文").strip() or "语文"
            questions = generate_quiz(db, text, n=n, knowledge_points=kps, subject=subject)
            return {"questions": questions}
        except QuizGenerationError as e:
            return {"questions": [], "error": str(e)}
        finally:
            db.close()


class GenerateDiagnosticQuestionsTool(BaseTool):
    name = "generate_diagnostic_questions"
    description = "针对一段课文，提出 1-4 个高信息量诊断性问题（选项可为空）"
    parameters = [
        ToolParameter(name="context", type="string", description="课文内容"),
        ToolParameter(name="subject", type="string", description="学科：语文/英语/数学", required=False),
    ]

    def run(self, args, ctx: UnifiedContext) -> dict:
        provider = _get_provider(ctx)
        context = (args.get("context") or "").strip()
        if not context:
            return {"intro": "", "questions": []}
        subject = (args.get("subject") or "语文").strip() or "语文"
        if subject == "英语":
            system = (
                "You are an elementary English tutor asking diagnostic questions about the reading passage. "
                "Ask 1-4 high-value questions the student can answer from the text. "
                'Return JSON only: {"intro":"short intro in English","questions":[{"id":"q1","prompt":"question in English",'
                '"options":[{"label":"choice in English"}]}]}. options may be []. '
                "All text MUST be in English; do not use Chinese."
            )
        else:
            system = (
                "你是小学生的学习助手，正在主动提问。请针对下面这段课文，"
                "一次性提出 1-4 个只有学生能补充的高信息量诊断性问题，不要重复已知信息。"
                '只返回 JSON：{"intro":"简短引导语","questions":[{"id":"q1","prompt":"问题",'
                '"options":[{"label":"选项"}]}]}。选项可为空数组，表示自由作答。'
            )
        try:
            raw = provider.generate(prompt=f"课文：\n{context[:6000]}", system=system, json_mode=True)
            data = json.loads(raw)
            return {"intro": data.get("intro", ""), "questions": data.get("questions") or []}
        except Exception:
            return {"intro": "", "questions": []}


generate_listening = GenerateListeningTool()
generate_quiz_questions = GenerateQuizQuestionsTool()
generate_diagnostic_questions = GenerateDiagnosticQuestionsTool()
