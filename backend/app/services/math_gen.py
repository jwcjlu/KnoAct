"""数学出题 + 数值归一判分：计算题/应用题，答案是唯一数字。

出题走 AI provider，失败回退兜底题；判分做数值归一（去单位、中文数字转阿拉伯、
分数/小数归一）后比较，保证 "8" / "8.0" / "八" 判为相等。
"""
import json
import re

from sqlalchemy.orm import Session

from .ai import get_provider

# 兜底题：AI 不可用/解析失败时返回，保证任何环境都能出题
FALLBACK_MATH_QUESTIONS = [
    {"question": "3 + 5 = ？", "answer": "8"},
    {"question": "12 - 7 = ？", "answer": "5"},
    {"question": "小明有 8 个苹果，吃了 3 个，还剩几个？", "answer": "5"},
]

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


def generate_math_questions(db: Session, text: str, n: int = 3) -> list[dict]:
    """针对本课知识点出 n 道数学题（计算题 + 应用题），返回 [{question, answer}]。

    answer 约定为唯一数字字符串（不带单位、不带算式过程）。任何异常回退兜底题。
    """
    if not text or not text.strip():
        return FALLBACK_MATH_QUESTIONS
    provider = get_provider(db)
    if provider.name == "fake":
        return FALLBACK_MATH_QUESTIONS
    prompt = (
        f"针对下面这段小学数学教材内容，出 {n} 道练习题（计算题和应用题混合），适合小学生作答。\n"
        f"每题答案必须是唯一确定的数字（不用写单位，不用写算式过程，只写结果数字）。\n"
        '只返回 JSON，格式：{"questions":[{"question":"题目","answer":"数字"}]}。\n\n'
        f"教材内容：\n{text[:800]}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学数学老师。", json_mode=True)
        data = json.loads(raw)
        qs = data.get("questions") or []
        out = []
        for q in qs:
            question = (q.get("question") or "").strip()
            answer = str(q.get("answer") or "").strip()
            if question and answer:
                out.append({"question": question, "answer": answer})
        return out[:n] if out else FALLBACK_MATH_QUESTIONS
    except Exception:
        return FALLBACK_MATH_QUESTIONS
