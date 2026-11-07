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


_MIN_LISTENING_QUESTIONS = 3
_MAX_LISTENING_QUESTIONS = 5

_LISTENING_MC_SCHEMA = (
    '{"dialogue":"short English dialogue","questions":['
    '{"id":"q1","question":"question in English","options":["A","B","C","D"],"correct_index":0}'
    "]}"
)

_LISTENING_FALLBACK_DIALOGUE = "A: What can you do? B: I can sing. A: That is great!"

_LISTENING_TEMPLATE_QUESTIONS = [
    {
        "id": "q1",
        "question": "What can B do?",
        "options": ["Sing", "Dance", "Run", "Jump"],
        "correct_index": 0,
    },
    {
        "id": "q2",
        "question": "Who asks about skills?",
        "options": ["A", "B", "Tom", "Lily"],
        "correct_index": 0,
    },
    {
        "id": "q3",
        "question": "How does A respond?",
        "options": ["That is great", "I am tired", "Go away", "Not now"],
        "correct_index": 0,
    },
    {
        "id": "q4",
        "question": "What is the topic of the dialogue?",
        "options": ["Abilities", "Food", "Weather", "Travel"],
        "correct_index": 0,
    },
    {
        "id": "q5",
        "question": "Which line is from B?",
        "options": ["I can sing.", "What can you do?", "That is great!", "See you."],
        "correct_index": 0,
    },
]


def _normalize_question_item(q: dict, index: int) -> dict | None:
    if not isinstance(q, dict):
        return None
    question_text = (q.get("question") or q.get("prompt") or "").strip()
    if not question_text:
        question_text = "What is the main idea of the dialogue?"
    raw_options = q.get("options") or q.get("choices") or []
    if not isinstance(raw_options, list):
        raw_options = []
    options = [str(o).strip() for o in raw_options if str(o).strip()]
    while len(options) < 4:
        options.append(f"Option {len(options) + 1}")
    options = options[:4]
    try:
        ci = int(q.get("correct_index", 0))
    except (TypeError, ValueError):
        ci = 0
    ci = max(0, min(3, ci))
    qid = (q.get("id") or f"q{index + 1}")
    if isinstance(qid, str):
        qid = qid.strip() or f"q{index + 1}"
    else:
        qid = f"q{index + 1}"
    return {
        "id": qid,
        "question": question_text,
        "options": options,
        "correct_index": ci,
    }


def normalize_listening(raw: dict) -> dict:
    """Pad/truncate listening material to 3–5 MC questions, 4 options each."""
    dialogue = (raw.get("dialogue") or "").strip() or _LISTENING_FALLBACK_DIALOGUE
    raw_questions = raw.get("questions") or []
    if not isinstance(raw_questions, list):
        raw_questions = []

    questions: list[dict] = []
    for i, item in enumerate(raw_questions):
        if len(questions) >= _MAX_LISTENING_QUESTIONS:
            break
        normalized = _normalize_question_item(item, i)
        if normalized:
            questions.append(normalized)

    tpl_i = 0
    while len(questions) < _MIN_LISTENING_QUESTIONS:
        tpl = _LISTENING_TEMPLATE_QUESTIONS[tpl_i % len(_LISTENING_TEMPLATE_QUESTIONS)]
        questions.append({
            **tpl,
            "id": f"q{len(questions) + 1}",
        })
        tpl_i += 1

    return {"dialogue": dialogue, "questions": questions[:_MAX_LISTENING_QUESTIONS]}


def _listening_fake_fallback() -> dict:
    return normalize_listening({
        "dialogue": _LISTENING_FALLBACK_DIALOGUE,
        "questions": _LISTENING_TEMPLATE_QUESTIONS[:_MIN_LISTENING_QUESTIONS],
    })


class GenerateListeningTool(BaseTool):
    name = "generate_listening"
    description = "用小学生已学单词编一段英语对话，并出 3～5 道英文四选一理解题"
    parameters = []

    def run(self, args, ctx: UnifiedContext) -> dict:
        provider = _get_provider(ctx)
        words = args.get("words") or []
        kps = args.get("knowledge_points") or []
        system = (
            "You are an elementary English teacher. "
            "Write a short English dialogue and 3 to 5 multiple-choice comprehension questions. "
            "All dialogue and questions MUST be in English. "
            f"Return JSON only: {_LISTENING_MC_SCHEMA}"
        )
        try:
            if words or kps:
                word_s = ", ".join(str(w) for w in words)
                kp_s = ", ".join(str(k) for k in kps)
                prompt = (
                    f"Create a short English dialogue (4–6 lines) for elementary students.\n"
                    f"Use these learned words: {word_s}\n"
                    f"Related topics: {kp_s}\n"
                    f"Then write 3 to 5 multiple-choice questions about the dialogue (4 options each).\n"
                    f"Return JSON only: {_LISTENING_MC_SCHEMA}"
                )
            else:
                prompt = (
                    "Create a short English dialogue (4–6 lines) for elementary students "
                    "using common learned words, then write 3 to 5 multiple-choice "
                    f"comprehension questions (4 options each). Return JSON only: {_LISTENING_MC_SCHEMA}"
                )
            text = provider.generate(prompt=prompt, system=system, json_mode=True)
            data = json.loads(text)
            return normalize_listening(data if isinstance(data, dict) else {})
        except Exception:
            return _listening_fake_fallback()


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
