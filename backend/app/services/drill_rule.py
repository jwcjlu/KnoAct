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


_EXPLORE_EMPTY = {"compare": [], "classify": [], "formula": {"template": "", "answer": "", "hint": ""},
                  "trap": {"question": "", "answer": "", "explain": ""}}


def generate_explore_items(db: Session | None, items: list[dict]) -> dict:
    """为 explore（探究型）条目按 4 认知原则生成探究内容，返回 {primary: {compare,classify,formula,trap}}。

    4 原则：观察（正反例对比）→ 归类（抽象→具象）→ 归纳（推导挖空）→ 陷阱（认知冲突）。
    fake/无 db/无 items/异常 → 空 dict。
    """
    if db is None or not items:
        return {}
    from .ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        return {}

    payload = [{"primary": it.get("primary", ""), "secondary": it.get("secondary", "")}
               for it in items if (it.get("primary") or "").strip()][:4]
    if not payload:
        return {}

    prompt = (
        "为下面的数学/抽象概念生成「探究式学习」内容，引导孩子自己发现规律（不要直接给答案）。\n"
        "每个概念返回四段：\n"
        '1. compare：2~3 组「正例/反例」对比，让孩子发现共同点/不同点，格式 [{"a":"...","b":"...","diff":"不同点提示"}]；\n'
        '2. classify：一道「拖拽归类」题，把若干具象场景拖到正确的概念箱子，格式 {"items":["具象场景1","具象场景2",...],"boxes":["概念1","概念2"],"answers":{"具象场景":"对应概念"}}，items 4~6 个，boxes 2~3 个（都是易混概念）；\n'
        '3. formula：一个「可推导的公式/规律」挖空，格式 {"template":"周长 = (长+宽) × ___","answer":"2","hint":"引导推导的提示"}；\n'
        '4. trap：一道「反直觉陷阱题」打破错误直觉，格式 {"question":"周长相等面积相等吗？","answer":"不一定","explain":"为什么"}。\n'
        '只返回 JSON：{"items":[{"primary":"概念名","compare":[...],"classify":{...},"formula":{...},"trap":{...}}]}。\n'
        f"概念列表：{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学数学老师，善于苏格拉底式启发教学。", json_mode=True)
        data = json.loads(raw)
        out = {}
        for it in data.get("items") or []:
            if not isinstance(it, dict):
                continue
            primary = (it.get("primary") or "").strip()
            if not primary:
                continue
            formula = it.get("formula") or {}
            trap = it.get("trap") or {}
            classify = it.get("classify") or {}
            out[primary] = {
                "compare": [{"a": c.get("a", ""), "b": c.get("b", ""), "diff": c.get("diff", "")}
                            for c in (it.get("compare") or []) if isinstance(c, dict)],
                "classify": {
                    "items": [s for s in (classify.get("items") or []) if isinstance(s, str)],
                    "boxes": [s for s in (classify.get("boxes") or []) if isinstance(s, str)],
                    "answers": classify.get("answers") if isinstance(classify.get("answers"), dict) else {},
                },
                "formula": {"template": (formula.get("template") or "").strip(),
                            "answer": (formula.get("answer") or "").strip(),
                            "hint": (formula.get("hint") or "").strip()},
                "trap": {"question": (trap.get("question") or "").strip(),
                         "answer": (trap.get("answer") or "").strip(),
                         "explain": (trap.get("explain") or "").strip()},
            }
        return out
    except Exception:
        return {}


def _extract_one_batch(db, provider, kind_desc: str, batch: list[dict]) -> list[dict]:
    """对一批页（≤3 页）的 OCR 文字提取条目。"""
    page_texts = "\n".join(
        f"【第{p.get('page_number', 0)}页】{p.get('text', '')}" for p in batch
    )
    prompt = (
        f"下面是一份讲义 PDF 的逐页 OCR 文字。请提取其中的识记条目。\n"
        f"条目类型：{kind_desc}。\n"
        '只返回 JSON：{"items":[{"primary":"原文","secondary":"释义/作者/解释","source_page":页码}]}。'
        "source_page 用该条目所在页码（数字）。每页可有多个条目；无关的页眉页脚/标题不要提取。\n"
        f"OCR 文字：\n{page_texts}"
    )
    raw = provider.generate(prompt=prompt, system="你是小学老师，善于从讲义提炼识记条目。", json_mode=True)
    data = json.loads(raw)
    items = data.get("items") or []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        primary = (it.get("primary") or "").strip()
        if not primary:
            continue
        try:
            sp = int(it.get("source_page") or 0)
        except (TypeError, ValueError):
            sp = 0
        out.append({"primary": primary, "secondary": (it.get("secondary") or "").strip(), "source_page": sp})
    return out


def extract_items_from_pages(db: Session | None, kind: str, pages: list[dict]) -> list[dict]:
    """从「讲义 PDF 逐页 OCR 文字」提取识记条目（带页码对照）。

    分批（每批 3 页）提取，避免单次 prompt 超长导致漏提取（如 100 例只提取出 45 例）。
    fake/无 db/空 pages/异常 → 空列表。
    """
    if db is None or not pages:
        return []
    from .ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        return []

    kind_desc = {
        "phrase": "英语短语/固定搭配，每条一个短语，primary 为英文原文，secondary 为中文释义",
        "outline": "知识点/古诗/生字，每条一个识记单元，primary 为原文，secondary 为释义或作者",
        "explore": "数学概念/公式，每条一个概念，primary 为概念名，secondary 为解释",
    }.get(kind, "识记知识点")

    BATCH = 3
    merged: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for i in range(0, len(pages), BATCH):
        batch = pages[i:i + BATCH]
        try:
            items = _extract_one_batch(db, provider, kind_desc, batch)
        except Exception:
            items = []
        for it in items:
            key = (it["primary"], it["source_page"])
            if key in seen:
                continue
            seen.add(key)
            merged.append(it)
    return merged


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


def classify_items(db: Session | None, subject: str, items: list[dict]) -> dict:
    """AI 自动归类每个条目的类型：memorize（识记）| explore（探究）。返回 {primary: type}。

    判断依据：有可发现规律/易混需辨析/可推导 → explore；纯要记住的内容 → memorize。
    fake/无 db/无 items/异常 → 空 dict（调用方按默认处理）。
    """
    if db is None or not items:
        return {}
    from .ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        return {}

    payload = [{"primary": it.get("primary", ""), "secondary": it.get("secondary", "")}
               for it in items if (it.get("primary") or "").strip()][:20]
    if not payload:
        return {}

    prompt = (
        f"下面是一组{subject}的知识点。请把每个知识点归类成两种类型之一：\n"
        '1. "memorize"（识记型）：纯要记住的内容，如古诗原文、生字、固定短语、单词，靠背记+使用掌握；\n'
        '2. "explore"（探究型）：有可发现的规律、易混需要辨析、可推导的概念，如修辞手法、语法规则、数学公式概念，靠观察→归类→归纳→验证掌握。\n'
        '只返回 JSON：{"items":[{"primary":"知识点原文","type":"memorize 或 explore"}]}。\n'
        f"知识点列表：{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学老师，善于判断知识点的学习类型。", json_mode=True)
        data = json.loads(raw)
        out = {}
        for it in data.get("items") or []:
            if not isinstance(it, dict):
                continue
            primary = (it.get("primary") or "").strip()
            t = (it.get("type") or "").strip()
            if primary and t in ("memorize", "explore"):
                out[primary] = t
        return out
    except Exception:
        return {}
