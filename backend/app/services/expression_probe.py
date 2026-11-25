"""讲一遍旁路追问 / 家长摘要。单次 generate，不判定、不写掌握度。"""
from __future__ import annotations

import json
import re

MAX_PROBE_TURNS = 3
MAX_HINT_LEN = 120

PROBE_SYSTEM = (
    "你在听小学生用自己的话讲一个知识点。"
    "你只追问缺口：每次只输出一个简短问题。"
    "禁止讲解、给定义、补全答案、说对错或夸奖。"
    "不要把标准答案里的关键概念词塞进问题里当成填空提示。"
)

HINT_SYSTEM = (
    "根据孩子的讲解和追问答句，用一句中文写出家长可读的卡点提示。"
    "格式必须是：可能卡在：……"
    "禁止评价（好/对/错/掌握/完整/棒）；不确定就写「可能卡在：表达还不完整」。"
)

_FORBIDDEN_HINT = re.compile(
    r"(讲得|很好|真棒|正确|错误|掌握|完整|优秀|不错|对了|错了)"
)


def normalize_probe_turns(raw) -> list[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("probe_turns must be a list")
    if len(raw) > MAX_PROBE_TURNS:
        raise ValueError(f"probe_turns max {MAX_PROBE_TURNS}")
    out = []
    for i, t in enumerate(raw):
        if not isinstance(t, dict):
            raise ValueError(f"turn {i} must be object")
        q = str(t.get("q") or "").strip()
        a = str(t.get("a") or "").strip()
        if not q:
            raise ValueError(f"turn {i} missing q")
        out.append({"q": q[:500], "a": a[:2000]})
    return out


def ask_next_question(provider, *, title: str, text: str, turns: list[dict]) -> dict:
    turns = normalize_probe_turns(turns)
    if len(turns) >= MAX_PROBE_TURNS:
        return {"done": True, "question": ""}
    hist = "\n".join(f"问：{t['q']}\n答：{t['a']}" for t in turns) or "（尚无追问）"
    prompt = (
        f"知识点：{title}\n孩子已写：\n{text}\n\n已有追问：\n{hist}\n\n"
        "请只输出下一个问题（一句话），不要编号，不要解释。"
    )
    try:
        q = (provider.generate(prompt=prompt, system=PROBE_SYSTEM) or "").strip()
    except Exception:
        q = ""
    if not q:
        return {"done": False, "question": "", "error": "unavailable"}
    q = q.splitlines()[0].strip()[:200]
    return {"done": False, "question": q}


def build_parent_hint(provider, *, title: str, text: str, turns: list[dict]) -> str:
    turns = normalize_probe_turns(turns)
    if not turns:
        return ""
    hist = "\n".join(f"问：{t['q']}\n答：{t['a']}" for t in turns)
    prompt = f"知识点：{title}\n终稿：\n{text}\n\n追问：\n{hist}\n"
    try:
        raw = (provider.generate(prompt=prompt, system=HINT_SYSTEM) or "").strip()
    except Exception:
        return ""
    if not raw:
        return ""
    line = raw.splitlines()[0].strip()
    if not line.startswith("可能卡在"):
        line = "可能卡在：" + line.lstrip("：:").strip()
    line = _FORBIDDEN_HINT.sub("", line)
    line = re.sub(r"\s+", " ", line).strip()
    if len(line) < 6:
        return ""
    return line[:MAX_HINT_LEN]


def dumps_turns(turns: list[dict]) -> str:
    return json.dumps(turns, ensure_ascii=False)