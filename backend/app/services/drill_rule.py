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


def infer_kind(subject: str, explicit_kind: str) -> str:
    """学科 → kind 默认映射；家长显式传了 kind 则尊重（可覆盖）。"""
    if (explicit_kind or "").strip():
        return explicit_kind.strip()
    return {
        "英语": "phrase",
        "语文": "outline",
        "数学": "explore",
    }.get((subject or "").strip(), "outline")


def extract_drill_items(db: Session | None, ocr_text: str) -> dict:
    """从「错题文字」提取识记型训练条目。返回 {kind, title, items}。

    kind 推断：英语短语→phrase，语文古诗/生字→outline，数学概念→explore。
    fake/无 db/空文本/异常 → 空结构。
    """
    empty = {"kind": "", "title": "", "items": []}
    if db is None or not (ocr_text or "").strip():
        return empty
    from .ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        return empty

    prompt = (
        "下面是一道小学错题的文字（可能含孩子错误答案和老师批注）。请识别它考的「识记知识点」，"
        "转成专项训练条目。只返回 JSON：\n"
        '{{"kind":"phrase|outline|explore","title":"一句话标题",'
        '"items":[{{"kind":"phrase|outline_point|drill_item","primary":"识记内容原文",'
        '"secondary":"释义/作者/解释","example":"例句或说明","keywords":["关键词"]}}]}}\n'
        "kind 推断规则：英语短语/固定搭配→phrase；语文古诗/生字/词语→outline；数学概念/公式→explore。\n"
        f"错题文字：\n{ocr_text[:1200]}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学老师，善于从错题提炼知识点。", json_mode=True)
        data = json.loads(raw)
        items = data.get("items") or []
        cleaned = []
        for it in items:
            if not isinstance(it, dict):
                continue
            cleaned.append({
                "kind": (it.get("kind") or "drill_item").strip(),
                "primary": (it.get("primary") or "").strip(),
                "secondary": (it.get("secondary") or "").strip(),
                "example": (it.get("example") or "").strip(),
                "keywords": [k.strip() for k in (it.get("keywords") or []) if k.strip()],
            })
        cleaned = [it for it in cleaned if it["primary"]]
        return {
            "kind": (data.get("kind") or "").strip(),
            "title": (data.get("title") or "").strip(),
            "items": cleaned,
        }
    except Exception:
        return empty
