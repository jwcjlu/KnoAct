"""建组时 AI 批量生成内容：intro / group_rule / common_mistake。"""
import json
from sqlalchemy.orm import Session

_EMPTY = {
    "intro": {"situation": "", "goal": "", "route": ""},
    "group_rule": {"examples": [], "question": "", "reveal": ""},
    "common_mistakes": {},
}


def _empty_copy():
    return {"intro": dict(_EMPTY["intro"]),
            "group_rule": dict(_EMPTY["group_rule"]),
            "common_mistakes": dict(_EMPTY["common_mistakes"])}


def generate_group_content(db: Session | None, subject: str, kind: str, items: list[dict]) -> dict:
    """返回 {intro, group_rule, common_mistakes}。

    fake/无 db/无 items/异常 → 空结构（前端按默认呈现，不显示相应引导块）。
    """
    if db is None or not items:
        return _empty_copy()
    from .ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        return _empty_copy()

    payload = [{"primary": it.get("primary", ""), "secondary": it.get("secondary", "")} for it in items[:6]]
    prompt = (
        f"为下面这组小学{kind}专项训练条目生成学习内容，只返回 JSON：\n"
        '{{"intro":{{"situation":"一句话情境","goal":"一句话目标","route":"一句话路线"}},'
        '"group_rule":{{"examples":[{{"oe":"原文","oc":"要点"}}],"question":"引导提问","reveal":"揭晓规律"}},'
        '"common_mistakes":{{"<条目 primary 原文>":{{"wrong":"常见错误写法","correct":"正确写法","explain":"为什么"}}}}}}\n'
        f"条目：{json.dumps(payload, ensure_ascii=False)}\n"
        "common_mistakes 只为「容易写错/记混」的条目生成，其余省略。"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学老师，善于启发式教学。", json_mode=True)
        data = json.loads(raw)
        intro = data.get("intro") or {}
        rule = data.get("group_rule") or {}
        mistakes = data.get("common_mistakes") or {}
        return {
            "intro": {"situation": (intro.get("situation") or "").strip(),
                      "goal": (intro.get("goal") or "").strip(),
                      "route": (intro.get("route") or "").strip()},
            "group_rule": {"examples": [{"oe": e.get("oe", ""), "oc": e.get("oc", "")}
                                        for e in (rule.get("examples") or []) if isinstance(e, dict)],
                           "question": (rule.get("question") or "").strip(),
                           "reveal": (rule.get("reveal") or "").strip()},
            "common_mistakes": mistakes if isinstance(mistakes, dict) else {},
        }
    except Exception:
        return _empty_copy()
