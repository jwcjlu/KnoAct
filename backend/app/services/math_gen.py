"""数学出题 + 数值归一判分：计算题/应用题，答案是唯一数字。

出题走 AI provider，失败回退兜底题；判分做数值归一（去单位、中文数字转阿拉伯、
分数/小数归一）后比较，保证 "8" / "8.0" / "八" 判为相等。
"""
import json
import re

from sqlalchemy.orm import Session

from .ai import get_provider

# 兜底题：AI 不可用/解析失败时返回，保证任何环境都能出题
FALLBACK_MATH_CALC = [
    {"question": "3 + 5 = ？", "answer": "8"},
    {"question": "12 - 7 = ？", "answer": "5"},
    {"question": "4 × 6 = ？", "answer": "24"},
]
FALLBACK_MATH_WORD = [
    {"question": "小明有 8 个苹果，吃了 3 个，还剩几个？", "answer": "5"},
    {"question": "图书角有 15 本书，借走 7 本，还剩几本？", "answer": "8"},
]
FALLBACK_MATH_QUESTIONS = FALLBACK_MATH_CALC[:2] + FALLBACK_MATH_WORD[:1]


def _repeat_fallback(fallback: list[dict], n: int) -> list[dict]:
    if n <= 0:
        return []
    out: list[dict] = []
    while len(out) < n:
        for q in fallback:
            out.append(dict(q))
            if len(out) >= n:
                break
    return out


def _parse_questions_json(raw: str, n: int) -> list[dict]:
    try:
        data = json.loads(raw)
        qs = data.get("questions") or []
        out = []
        for q in qs:
            question = (q.get("question") or "").strip()
            answer = str(q.get("answer") or "").strip()
            if question and answer:
                out.append({"question": question, "answer": answer})
        return out[:n] if out else []
    except Exception:
        return []


def _generate_math_typed(db: Session, text: str, n: int, *, kind: str, fallback: list[dict]) -> list[dict]:
    """kind: calc（短计算）| word（应用题）。"""
    if n <= 0:
        return []
    if not text or not text.strip():
        return _repeat_fallback(fallback, n)
    provider = get_provider(db)
    if provider.name == "fake":
        return _repeat_fallback(fallback, n)
    if kind == "calc":
        kind_desc = "纯计算题（加减乘除，题干简短，不要情境应用）"
    else:
        kind_desc = "应用题（有情境文字，一步或两步运算，适合小学生）"
    prompt = (
        f"针对下面这段小学数学教材内容，出 {n} 道{kind_desc}。\n"
        f"每题答案必须是唯一确定的数字（不用写单位，不用写算式过程，只写结果数字）。\n"
        '只返回 JSON，格式：{"questions":[{"question":"题目","answer":"数字"}]}。\n\n'
        f"教材内容：\n{text[:800]}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学数学老师。", json_mode=True)
        out = _parse_questions_json(raw, n)
        return out if out else _repeat_fallback(fallback, n)
    except Exception:
        return _repeat_fallback(fallback, n)


def generate_math_calc(db: Session, text: str, n: int = 2) -> list[dict]:
    """短计算题，答案为数字字符串。"""
    return _generate_math_typed(db, text, n, kind="calc", fallback=FALLBACK_MATH_CALC)


def generate_math_word(db: Session, text: str, n: int = 2) -> list[dict]:
    """应用题，答案为数字字符串。"""
    return _generate_math_typed(db, text, n, kind="word", fallback=FALLBACK_MATH_WORD)


def generate_math_questions_split(db: Session, text: str, n_calc: int = 2, n_word: int = 2) -> dict:
    """返回 {"calc": [...], "word": [...]}。"""
    return {
        "calc": generate_math_calc(db, text, n_calc),
        "word": generate_math_word(db, text, n_word),
    }

# 中文数字 → 阿拉伯（含大写常用与「两」）
_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}

# 常见中文单位（判分时剔除，避免「8 个」vs「8」被判不等）
_UNITS_RE = re.compile(r"(个|只|元|角|分|米|厘米|毫米|克|千克|公斤|秒|分|小时|天|页|题|道|次|辆|本|支|张|块|条|头|匹|位|名|岁|度|倍|%|％)")


def _cn_to_int(s: str) -> int | None:
    """中文数字串转整数，如「八」→8、「十二」→12、「二十五」→25。非纯中文数字返回 None。"""
    total, section, num = 0, 0, 0
    for ch in s:
        if ch in _CN_DIGITS:
            num = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if unit == 10:
                section = (num or 1) * unit
            else:
                section = (section + num) * unit
            num = 0
        else:
            return None
    return total + section + num


def normalize_answer(s: str) -> str:
    """数值归一：去空格/单位 → 中文数字转阿拉伯 → 尽量转 float 规范字符串。

    返回归一后的字符串（如 "8"、"8.0"、"5"）。无法归一为数值时返回原样去空格小写。
    """
    if s is None:
        return ""
    t = str(s).strip().lower()
    if not t:
        return ""
    # 去中文单位（「8 个」→「8」）
    t = _UNITS_RE.sub("", t)
    t = t.replace(" ", "").replace("　", "")
    # 全中文数字 → 阿拉伯（「八」→「8」，「十二」→「12」）
    if t and all(ch in _CN_DIGITS or ch in _CN_UNITS for ch in t):
        v = _cn_to_int(t)
        if v is not None:
            return str(v)
    # 分数「3/4」→ 小数
    m = re.fullmatch(r"(\d+)\s*/\s*(\d+)", t)
    if m and int(m.group(2)) != 0:
        return str(round(int(m.group(1)) / int(m.group(2)), 6))
    # 数值 → float 规范（去尾随 0）
    try:
        return str(round(float(t), 6))
    except ValueError:
        return t


def grade_math_answer(user_answer: str, expected_answer: str) -> bool:
    """数值判分：归一后按数值相等比较（浮点容差 1e-6）。"""
    u = normalize_answer(user_answer)
    e = normalize_answer(expected_answer)
    if not u or not e:
        return False
    try:
        return abs(float(u) - float(e)) < 1e-6
    except ValueError:
        # 非纯数值（如文字答案），退回归一字符串精确比较
        return u == e


CONFIDENCE_THRESHOLD = 0.75

_PHOTO_GRADE_SYSTEM = (
    "你是小学数学老师，批改孩子在纸上写的应用题作答。"
    "只根据图片内容判断，不要编造图片里没有的步骤或数字。"
)


def _photo_grade_status(steps_plausible: bool, answer_match: bool, confidence: float) -> str:
    if steps_plausible and answer_match and confidence >= CONFIDENCE_THRESHOLD:
        return "ok"
    return "pending_review"


def _fake_photo_grade(image_bytes: bytes, expected_answer: str) -> dict:
    """测试/无 AI 时确定性批改：默认高置信且答案与标答一致 → ok。"""
    fail = {
        "final_answer": "",
        "steps_plausible": False,
        "confidence": 0.0,
        "reason": "无法识别图片",
        "ai_status": "failed",
        "ai_correct": False,
    }
    if not image_bytes:
        return fail
    if image_bytes == b"__FORCE_FAIL__":
        return fail
    final = expected_answer
    steps = True
    confidence = 0.92
    if image_bytes == b"__FORCE_PENDING__":
        final = "99"
        confidence = 0.5
    answer_match = grade_math_answer(str(final), expected_answer)
    ai_status = _photo_grade_status(steps, answer_match, confidence)
    return {
        "final_answer": str(final),
        "steps_plausible": steps,
        "confidence": confidence,
        "reason": "fake provider",
        "ai_status": ai_status,
        "ai_correct": bool(answer_match and steps),
    }


def _vision_photo_grade(db: Session, image_bytes: bytes, question: str, expected_answer: str) -> dict:
    """调用视觉模型，要求返回 JSON 字段。"""
    import base64
    from openai import OpenAI
    from .model_config import resolve

    r = resolve(db, "llm")
    vision_model = r.options.get("vision_model", "")
    if not vision_model:
        from ..models import ModelConfig
        row = db.query(ModelConfig).filter_by(key="vision_model").first()
        vision_model = row.value if row else "qwen3-vl-plus"
    if not r.api_key or not r.base_url:
        raise RuntimeError("vision not configured")
    client = OpenAI(api_key=r.api_key, base_url=r.base_url)
    b64 = base64.b64encode(image_bytes).decode()
    prompt = (
        f"题干：{question}\n标准答案（仅数字）：{expected_answer}\n"
        "请阅读图片中的手写算式与最终答案，返回 JSON："
        '{"final_answer":"孩子写的最终数字答案","steps_plausible":true或false,'
        '"confidence":0到1的小数,"reason":"一句话说明"}'
    )
    resp = client.chat.completions.create(
        model=vision_model,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


def grade_math_work_photo(
    db: Session,
    image_bytes: bytes,
    question: str,
    expected_answer: str,
) -> dict:
    """应用题纸上作答 AI 批改。读图失败 → ai_status=failed（仍待家长确认）。"""
    fail = {
        "final_answer": "",
        "steps_plausible": False,
        "confidence": 0.0,
        "reason": "无法识别图片",
        "ai_status": "failed",
        "ai_correct": False,
    }
    if not image_bytes:
        return fail

    provider = get_provider(db)
    if provider.name == "fake":
        return _fake_photo_grade(image_bytes, expected_answer)

    try:
        raw = _vision_photo_grade(db, image_bytes, question, expected_answer)
        data = json.loads(raw)
    except Exception:
        return fail

    final = str(data.get("final_answer") or "").strip()
    steps = bool(data.get("steps_plausible"))
    try:
        confidence = float(data.get("confidence", 0))
    except (TypeError, ValueError):
        confidence = 0.0
    reason = str(data.get("reason") or "").strip() or "已批改"
    answer_match = grade_math_answer(final, expected_answer) if final else False
    ai_status = _photo_grade_status(steps, answer_match, confidence)
    return {
        "final_answer": final,
        "steps_plausible": steps,
        "confidence": confidence,
        "reason": reason,
        "ai_status": ai_status,
        "ai_correct": bool(answer_match and steps),
    }


def parse_math_task_content(raw: str) -> dict:
    """解析 Task.content：新格式 {calc, word}；旧 flat 数组视为全 calc。"""
    if not (raw or "").strip():
        return {"calc": [], "word": []}
    try:
        data = json.loads(raw)
    except ValueError:
        return {"calc": [], "word": []}
    if isinstance(data, list):
        return {"calc": data, "word": []}
    if isinstance(data, dict):
        return {
            "calc": list(data.get("calc") or []),
            "word": list(data.get("word") or []),
        }
    return {"calc": [], "word": []}


def math_content_ready_to_submit(content: dict) -> tuple[bool, str]:
    """数学任务可否提交：calc 均已判分；word 均有照片且 AI 已结束。"""
    calc = content.get("calc") or []
    word = content.get("word") or []
    for c in calc:
        if "is_correct" not in c and "user_correct" not in c:
            return False, "calc_not_graded"
    for w in word:
        if not (w.get("photo_path") or "").strip():
            return False, "word_photo_missing"
        st = (w.get("ai_status") or "").strip()
        if st not in ("ok", "pending_review", "failed"):
            return False, "word_ai_incomplete"
    return True, ""


def generate_math_questions(db: Session, text: str, n: int = 3) -> list[dict]:
    """针对本课知识点出 n 道数学题（计算题 + 应用题混合），返回 [{question, answer}]。

    answer 约定为唯一数字字符串（不带单位、不带算式过程）。任何异常回退兜底题。
    """
    if n <= 0:
        return []
    n_calc = max(1, n // 2 + n % 2)
    n_word = n - n_calc
    split = generate_math_questions_split(db, text, n_calc=n_calc, n_word=n_word)
    merged = split["calc"] + split["word"]
    return merged[:n] if merged else _repeat_fallback(FALLBACK_MATH_QUESTIONS, n)
