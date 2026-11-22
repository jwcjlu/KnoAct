"""数学练习册整页分析：一次视觉调用返回页类型 + 题组 + 小题 + 图片题。

设计：`parse_page_analysis()` 是纯函数（只做 JSON 规范化，好测），
`analyze_page()` 负责取图调用 `ai.vision_json()` 再交给它。
换学科只需另写一个同结构的 `text_page.py`，编排层零改动。
"""
import json
import re

from ...core.work_modes import REGISTRY
from ..ai import vision_json

# 允许的页类型；非 practice 由编排层跳过
PAGE_TYPES = ("practice", "toc", "answer_key", "cover", "blank")

_PAGE_SYSTEM = (
    "你是小学数学练习册的题目结构化助手。看这一页的图片，把内容结构化成 JSON。\n"
    "\n"
    "输出格式：\n"
    '{"page_type":"practice|toc|answer_key|cover|blank",'
    '"groups":[{"stem":"题干","instruction":"引导语","lesson_no":3,'
    '"lesson_title":"第3课时 标题","work_mode":"题型id",'
    '"need_process":false,"continues_next_page":false,'
    '"items":[{"seq":1,"y":0.18,"text":"题干原文","answer_hint":"","is_example":false}]}],'
    '"image_questions":[{"start":0.71,"end":0.86,"title":"标题"}]}\n'
    "\n"
    "work_mode 只能取以下之一："
    + "、".join(f"{m.id}({m.label})" for m in REGISTRY.values()) + "\n"
    "\n"
    "【硬约束】\n"
    "1. 严禁计算！严禁把答案写进 text。text 只抄页面印刷的内容。\n"
    "2. 一页有几个大题就返回几个 group，不许自行合并或拆分。\n"
    "3. answer_hint 只在页面已经印出答案时填写（通常是示例行）。\n"
    "4. 拿不准 work_mode 时填 other，不要猜。\n"
    "5. 每道小题都要给 y（该题在这页的纵向比例 0~1），用于密集网格还原行列。\n"
    "6. 页尾的题被切断（题干/数字不完整）时，continues_next_page 置 true。\n"
    "7. 页首有「第N课时 标题」时填 lesson_no（整数 N）与 lesson_title；没有就都留空。\n"
    "\n"
    "【格式约束】\n"
    "1. 空位统一用 ____（不要用「（　）」「(  )」）。竖式里的方格挖空保留原样 □。\n"
    "2. 数学式用 $...$ 包裹基础 LaTeX，例如 $111.06 \\div 0.9 = 123.4$、$\\frac{3}{4}$。\n"
    "3. 中文叙述、标点、单位不得放进 $...$ 内部。\n"
    "4. 可用 LaTeX：\\frac \\sqrt ^ _ \\times \\div \\pm \\left( \\right) \\underline "
    "\\text{} \\underbrace \\cdots \\begin{cases}。\n"
    "   不要用需要额外宏包的语法（\\color、\\require 等）。\n"
    "5. 多行竖式/脱式：一行一个 $...$，行间用 \\n 分隔，不要用 \\begin{aligned}。\n"
    "6. 页面上需要看图才能作答的题（图形、统计图、方格图、钟面、展开图）放进 "
    "image_questions，给纵向范围，不要试图用文字还原。\n"
    "\n"
    "【空位绝不能写在 $...$ 里面】\n"
    "____ 必须放在 $...$ 外面，$...$ 内只能是纯粹的数学表达式。\n"
    "  错误：$a \\times b = ($____$)$；   ← 把公式劈成两半，渲染会坏\n"
    "  正确：$a \\times b =$ ____\n"
    "  正确：$a \\times b =$（____）\n"
    "  正确：$x =$ ____\n"
    "\n"
    "【不要输出裸露的 LaTeX 命令】\n"
    "像 \\underline{\\hspace{2cm}}、\\hspace、\\text{} 这类命令**必须包在 $...$ 里**，\n"
    "否则会以源码形式显示给孩子。\n"
    "  错误：$603 - 239 =$\n        \\underline{\\hspace{2cm}}   ← 裸命令，会显示反斜杠\n"
    "  正确：$603 - 239 =$ ____                ← 用空位标记更简单\n"
    "  正确：$603 - 239 = \\underline{\\hspace{2cm}}$\n"
    "\n"
    "【一道题里有多个空】\n"
    "如果一道题要填几个空（例如「则 a×b=（　）；a÷b=（　）」、"
    "「求下面各图形的面积」（几个图形各一个空）），按以下规则：\n"
    "- groups[].stem 只放大题题干/公共材料，**不要把待填的题目本身也写进 stem**。\n"
    "- items[] 每个空一条，text 只写该空对应的部分（如「$a \\times b =$ ____」）。\n"
    "- 一题只有 1 个空时，stem 与 items[0].text 的内容不重复：把题目放在 items[0].text。\n"
    "\n"
    "【work_mode 判断提示】\n"
    "字母表示数/用字母找规律（如 a=0.00…01 求 a×b）→ letter_pattern；\n"
    "数字序列找规律并推算 → pattern；比较两个数/带单位比较大小 → compare / unit_compare；\n"
    "图形各部分的面积/周长 → geometry。"
)

_PAGE_PROMPT = "分析这一页练习册图片，按 system 要求返回 JSON。只输出 JSON，不要解释。"

_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _safe_float(v, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _safe_int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _empty(*, parse_failed: bool = False) -> dict:
    """安全的空结构。

    `parse_failed=True` 表示「AI 的返回根本不是可用 JSON」，与「这页确实空白」
    必须能区分：否则模型抽风会被记成 ok 的空白页，job 标 done、0 题、还不可重试。
    """
    return {
        "page_type": "practice",
        "groups": [],
        "image_questions": [],
        "parse_failed": parse_failed,
    }


_SPLIT_PAREN_RE = re.compile(r"\$([^$]*?)\(\s*\$\s*_{2,}\s*\$\s*\)\s*\$")
_SPLIT_PLAIN_RE = re.compile(r"\$([^$]*?)\$\s*_{2,}\s*\$([^$]*)\$")
_MATH_PAIR_RE = re.compile(r"\$([^$]*)\$")


_BARE_LATEX_RE = re.compile(
    r"(\\underline\s*\{(?:[^{}]|\{[^{}]*\})*\}"   # \underline{...}（允许一层嵌套）
    r"|\\hspace\s*\{[^{}]*\}"
    r"|\\text\s*\{[^{}]*\})")


def _wrap_bare_latex(text: str) -> str:
    r"""把裸露在 `$...$` 外的 LaTeX 命令包进 `$...$`。

    模型常把「填空题横线」写成 `$603-239=$\n\underline{\hspace{2cm}}`——
    后半截没被 `$` 包住，浏览器会把 `\underline...` 原样显示成源码。

    实现要点：
    - **真的跟踪是否在数学模式内**（数它前面有几个 `$`）。只用 `(?<!\$)`
      不够：`$603 - 239 = \underline{...}$` 里 `\underline` 左邻是空格，
      会被误判成裸命令而重复包裹，把公式弄坏。
    - **整体匹配**：`\underline{\hspace{2cm}}` 必须一次性命中，
      否则分开包会得到 `$\underline{$\hspace{2cm}$}$`。
    """
    if not text or "\\" not in text:
        return text

    out: list[str] = []
    last = 0
    in_math = False
    for m in _BARE_LATEX_RE.finditer(text):
        # 更新数学模式状态：看 [last, m.start()) 之间有几个 $
        segment = text[last:m.start()]
        if segment.count("$") % 2 == 1:
            in_math = not in_math
        out.append(segment)
        if in_math:
            out.append(m.group(1))
        else:
            out.append(f"${m.group(1)}$")
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def _dig_out_blank(m) -> str:
    inner = m.group(1)
    if "__" not in inner:
        return m.group(0)
    head, _, tail = inner.partition("__")
    head = head.rstrip()
    while head.endswith("(") or head.endswith("（"):
        head = head[:-1].rstrip()
    tail = tail.lstrip("_").lstrip()
    while tail.startswith(")") or tail.startswith("）"):
        tail = tail[1:].lstrip()
    out = f"${head}$ ____"
    if tail:
        out += f" ${tail}$"
    return out


def _fix_blank_inside_math(text: str) -> str:
    r"""把写进 `$...$` 内部、或把公式劈开的空位挪到外面。

    模型有时会输出 `$a \times b = ($____$)$`：`____` 落在 `$` 之间，
    公式被劈成两段（`($` 与 `)$`），前端渲染会坏。这里统一改成
    `$a \times b =$ ____`。

    三步，只会命中明确的坏形态；已经正确的文本原样返回（过度改写更危险）：
    1. `$X ($____$)$`        → `$X (____)$`
    2. `$X $____$ Y$`        → `$X $ ____ $Y$`
    3. `$X (____) $` / `$X ____$` → `$X$ ____`
    """
    if not text or "$" not in text:
        return text
    t = _SPLIT_PAREN_RE.sub(lambda m: f"${m.group(1)}(____)$", text)
    t = _SPLIT_PLAIN_RE.sub(
        lambda m: f"${m.group(1)}$ ____ ${m.group(2)}$", t)
    return _MATH_PAIR_RE.sub(_dig_out_blank, t)



_STRAY_OP_RE = re.compile(r"\$[ \t]*(?:\\times|\\div|\\pm|×|÷|\+)[ \t]*\$[ \t]*")


def _clean_markup(text: str) -> str:
    """统一清洗模型给出的题干标记。

    顺序：修被劈开的公式 → 包住裸 LaTeX → 去掉竖式排版残留的孤立运算符。
    最后一类来自竖式题：模型会把竖式里对齐用的 `×` 抄成独立一段
    （`$204 \\times 75 =$\\n$\\times$ ____`），展示时题目下面会多出一个乘号。
    """
    t = _wrap_bare_latex(_fix_blank_inside_math((text or "").strip()))
    # 只在「该片段紧跟着空位/行首/行尾」时才算残留，避免误删正常算式
    t = _STRAY_OP_RE.sub(
        lambda m: "" if _is_stray_op(text, m) else m.group(0), t)
    return re.sub(r"[ \t]{2,}", " ", t).strip()


def _is_stray_op(text: str, m) -> bool:
    """判断这个 `$运算符$` 是不是竖式排版残留。

    判据：它所在行除了它和空位标记之外没有别的东西。
    """
    line_start = text.rfind("\n", 0, m.start()) + 1
    line_end = text.find("\n", m.end())
    if line_end < 0:
        line_end = len(text)
    line = text[line_start:line_end]
    rest = (line[:m.start() - line_start] + line[m.end() - line_start:])
    rest = rest.replace("_", "").strip()
    return rest == ""


def _norm_item(raw: dict, fallback_seq: int) -> dict:
    seq = _safe_int(raw.get("seq"))
    return {
        "seq": seq if seq is not None else fallback_seq,
        "y": _safe_float(raw.get("y"), 0.0),
        "text": _clean_markup(str(raw.get("text") or "")),
        "answer_hint": _clean_markup(str(raw.get("answer_hint") or "")),
        "is_example": bool(raw.get("is_example")),
    }


def _norm_group(raw: dict) -> dict:
    mode = str(raw.get("work_mode") or "").strip()
    if mode not in REGISTRY:
        mode = "other"
    items_raw = raw.get("items")
    items: list[dict] = []
    if isinstance(items_raw, list):
        for idx, it in enumerate(items_raw, start=1):
            if isinstance(it, dict):
                items.append(_norm_item(it, idx))
    # 按 y 排序还原行列顺序。sorted 是稳定排序：同一 y（密集网格同一行）
    # 会保留 AI 的原始顺序，这是期望行为，不要改成二次排序。
    items.sort(key=lambda x: x["y"])
    return {
        "stem": str(raw.get("stem") or "").strip(),
        "instruction": str(raw.get("instruction") or "").strip(),
        "lesson_no": _safe_int(raw.get("lesson_no")),
        "lesson_title": str(raw.get("lesson_title") or "").strip(),
        "work_mode": mode,
        "need_process": bool(raw.get("need_process")),
        "continues_next_page": bool(raw.get("continues_next_page")),
        "items": items,
    }


def _norm_image(raw: dict) -> dict | None:
    start = _safe_float(raw.get("start"), -1.0)
    end = _safe_float(raw.get("end"), -1.0)
    if not (0.0 <= start < end <= 1.0):
        return None
    return {
        "start": start,
        "end": end,
        "title": str(raw.get("title") or "").strip(),
    }


def parse_page_analysis(raw: str) -> dict:
    """AI 原始输出 → 规范化 dict。任何异常都返回安全的空结构，绝不抛。

    解析失败时返回 `parse_failed=True` 的空结构，供编排层记为该页失败
    （而不是当成一页「没有题目的练习页」）。
    """
    try:
        data = json.loads(raw or "")
    except (ValueError, TypeError):
        m = _JSON_RE.search(raw or "")
        if not m:
            return _empty(parse_failed=True)
        try:
            data = json.loads(m.group(0))
        except (ValueError, TypeError):
            return _empty(parse_failed=True)

    if not isinstance(data, dict):
        return _empty(parse_failed=True)

    page_type = str(data.get("page_type") or "").strip()
    if page_type not in PAGE_TYPES:
        page_type = "practice"   # 拿不准宁可多导

    groups: list[dict] = []
    gs = data.get("groups")
    if isinstance(gs, list):
        for g in gs:
            if isinstance(g, dict):
                groups.append(_norm_group(g))

    images: list[dict] = []
    iqs = data.get("image_questions")
    if isinstance(iqs, list):
        for iq in iqs:
            if isinstance(iq, dict):
                norm = _norm_image(iq)
                if norm:
                    images.append(norm)

    return {
        "page_type": page_type,
        "groups": groups,
        "image_questions": images,
        "parse_failed": False,
    }


def analyze_page(db, image_bytes: bytes, *, subject: str = "数学") -> dict:
    """整页视觉分析。异常由调用方（编排层）捕获并记为该页失败。"""
    raw = vision_json(db, image_bytes, system=_PAGE_SYSTEM, prompt=_PAGE_PROMPT)
    return parse_page_analysis(raw)
