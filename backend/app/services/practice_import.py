"""练习册 PDF 导入：课时/题号解析、答案对齐、后台任务编排。

设计见 docs/superpowers/specs/2026-11-20-practice-book-import-design.md

这本练习册（计算小达人 RJ 五上）的结构是：
    第 3 课时 练习课
    1. 直接写出得数。（建议 2 分钟完成）
    8.9 + 4.5 =
    1000 - 550 =
    2. 计算下面各题，能简算的要简算。
    (72 ÷ 18 + 8) × 28
所以「1. / 2.」是大题号（= 题型分组），真正的题目是它们下面的每一行算式。
"""
import copy
import json
import re

# 「第3课时 小数乘小数」/「第 12 课时 练习课」
_LESSON_RE = re.compile(r"第\s*(\d+)\s*课时\s*([^\n]*)")

# 大题号：行首「1.」「1、」「(1)」，后面常跟一句说明。
# 注意「8.9 + 4.5 =」这种小数开头的算式不能当大题号 → 要求点号后不接数字，
# 且不能以等号/运算符结尾。
_SECTION_RE = re.compile(
    r"^\s*(?:\((\d{1,2})\)|（(\d{1,2})）|(\d{1,2})[.、．](?!\d))\s*(.*)$"
)

# 一行里必须有运算符或等号才算「一道算式题」
_MATH_RE = re.compile(r"[+\-−×÷*/=＝]")

# 明显不是题目的页眉页脚噪音
_NOISE_RE = re.compile(
    r"^(视频讲解|智能批改|月\s*日|RJ\s|第\s*\d+\s*页|扫码|参考答案)"
)


def _section_kind(hint: str) -> str:
    """由大题提示语推断题型：口算 / 竖式 / 脱式 / 解方程 / 应用。"""
    h = hint or ""
    if "解方程" in h or "未知数" in h or "等式" in h:
        return "equation"
    if "直接写出得数" in h or "口算" in h:
        return "oral"
    if "竖式" in h:
        return "vertical"
    if "简算" in h or "计算下面各题" in h or "脱式" in h:
        return "step"
    if "解决问题" in h or "应用题" in h:
        return "app"
    return "other"


def _is_problem_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 3:
        return False
    if _NOISE_RE.match(s):
        return False
    if not _MATH_RE.search(s):
        return False
    # 纯中文说明行（如「巧算。」）不算题目
    if not re.search(r"\d", s):
        return False
    return True


def _split_row(line: str) -> list[str]:
    """同一横向行里的多道题按制表符/连续全角空格切开。

    OCR 常把「8.9+4.5=    1000-550=    3.32+2.74=」识别成一行。

    注意：`（　　）` 是填空题的空位，不能当列分隔符，先整体保护起来。
    """
    s = line.strip()
    # 把括号里的空白替换成占位符，切分完再还原
    s = re.sub(r"[（(]\s*[）)]", "\uf000", s)
    parts = re.split(r"\t+|\u3000{2,}|\s{4,}", s)
    return [p.replace("\uf000", "（　）").strip() for p in parts if p.strip()]


_UNIT_RE = re.compile(r"^\s*([一二三四五六七八九十]+)\s+([^\n]{2,20})\s*$", re.M)

_SPECIAL_RE = re.compile(
    r"^\s*(专项练习[一二三四五六七八九十\d]*|阶段能力检测[一二三四五六七八九十\d]*"
    r"|期中[^\n]{0,12}|期末[^\n]{0,12}|单元[^\n]{0,12}检测[^\n]{0,8})\s*$",
    re.M,
)


def parse_lesson_page(text: str, *, lenient: bool = False) -> dict:
    """从一页 OCR 文本解析课时号、标题与题目列表。

    返回 {"lesson_no": int|None, "lesson_title": str,
          "items": [{"question_no", "question", "kind"}]}

    切分规则：大题号（1. / 2.）只作分组并推断题型，每个算式行是一道题，
    题号在该大题内从 1 递增。

    没有「第N课时」时（如「专项练习一」「期中检测」），退用该页标题作章节名，
    lesson_no 置 None（入库时由调用方按页序编号）。
    """
    text = (text or "").replace("\r", "")
    m = _LESSON_RE.search(text)
    if m:
        lesson_no = int(m.group(1))
        lesson_title = (m.group(2) or "").strip().split("\n")[0].strip()
        body = text[m.end():]
    else:
        sp = _SPECIAL_RE.search(text)
        if not sp:
            return {"lesson_no": None, "lesson_title": "", "items": []}
        lesson_no = None
        lesson_title = sp.group(1).strip()
        body = text[sp.end():]

    items: list[dict] = []
    cur_kind = "other"
    seq = 0

    for raw_line in body.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        sec = _SECTION_RE.match(line)
        if sec:
            hint = sec.group(4) or ""
            # 答案页：题号后面就是答案，不是大题说明
            if lenient:
                if hint and not _NOISE_RE.match(hint):
                    seq += 1
                    items.append({
                        "question_no": str(seq),
                        "question": hint,
                        "kind": cur_kind,
                    })
                continue
            # 大题行若本身带运算符/等号，说明它其实是道算式题
            if _MATH_RE.search(hint):
                if _is_problem_line(hint):
                    seq += 1
                    items.append({
                        "question_no": str(seq),
                        "question": hint,
                        "kind": cur_kind,
                    })
                continue
            cur_kind = _section_kind(hint)
            continue

        if lenient:
            # 答案页：没题号的裸行也是答案（与上一题同序追加不行，跳过避免错位）
            continue

        if not _is_problem_line(line):
            continue

        # 一行多题时逐个拆开
        for piece in _split_row(line):
            if not _is_problem_line(piece):
                continue
            seq += 1
            items.append({
                "question_no": str(seq),
                "question": _strip_answer(piece),
                "kind": cur_kind,
            })

    return {"lesson_no": lesson_no, "lesson_title": lesson_title, "items": items}


def parse_answer_page(text: str) -> list[dict]:
    """解析答案页：没有「第N课时」标题，只按页内题号顺序产出答案。

    一个题号行里可能挤着多个答案（如「1. 9.9 100 0.1」对应横向 3 道题），
    这里把它们拆成多条，按出现顺序返回。

    返回 [{"question_no": "1", "answer": "9.9"}, {"question_no": "1", "answer": "100"}, ...]
    """
    items: list[dict] = []
    seq = 0
    for raw_line in (text or "").replace("\r", "").split("\n"):
        line = raw_line.strip()
        if not line or _NOISE_RE.match(line):
            continue

        m = _SECTION_RE.match(line)
        if not m:
            continue
        answer_text = (m.group(4) or "").strip()
        if not answer_text:
            continue

        # 带过程的答案（「60 ÷ 5 = 12」）只取最后结果
        if "=" in answer_text or "＝" in answer_text:
            tail = re.split(r"[=＝]", answer_text)[-1].strip()
            if tail:
                answer_text = tail

        # 一行多答案：按空白切开逐个入列
        parts = [p for p in re.split(r"\s{2,}|\t+|\u3000+", answer_text) if p.strip()]
        if not parts:
            parts = [answer_text]
        for part in parts:
            part = part.strip()
            if not part:
                continue
            seq += 1
            items.append({"question_no": str(seq), "answer": part})
    return items


def split_blanks(answer_text: str, count: int) -> list[str] | None:
    """把答案文本按空位数量切开；数量不匹配返回 None（视为未对齐）。"""
    raw = (answer_text or "").strip()
    if not raw or count <= 0:
        return None
    parts = [p.strip() for p in re.split(r"[,，;；、\s]+", raw) if p.strip()]
    if len(parts) != count:
        return None
    return parts


def align_answers(
    questions: list[dict], answers: list[dict]
) -> tuple[list[dict], list[dict]]:
    """按 (lesson_no, question_no) 对齐。返回 (已对齐, 未对齐)。"""
    index: dict[tuple, dict] = {}
    for a in answers:
        key = (a.get("lesson_no"), str(a.get("question_no")))
        if key not in index:
            index[key] = a

    aligned: list[dict] = []
    missing: list[dict] = []
    for q in questions:
        key = (q.get("lesson_no"), str(q.get("question_no")))
        hit = index.get(key)
        if hit and (hit.get("answer") or "").strip():
            aligned.append(
                {
                    **q,
                    "answer": hit["answer"],
                    "analysis": hit.get("analysis", ""),
                }
            )
        else:
            missing.append(q)
    return aligned, missing


def align_by_order(
    questions: list[dict], answers: list[dict]
) -> tuple[list[dict], list[dict]]:
    """顺序对齐：第 N 题配第 N 个答案。

    答案页天然没有「第N课时」标题，只能依赖「题面页按课时顺序 + 答案页同序」
    这一事实（计算类练习册都是这个结构）。
    """
    aligned: list[dict] = []
    missing: list[dict] = []
    for i, q in enumerate(questions):
        if i < len(answers) and (answers[i].get("answer") or "").strip():
            aligned.append({**q, "answer": answers[i]["answer"]})
        else:
            missing.append(q)
    return aligned, missing


from ..core.source_adapter import QuestionDraft

# OCR 解析出的 kind → 题库 qtype。
# category 由 CATEGORY_OF_QTYPE 派生（core/question_types.py），绝不手填。
QTYPE_OF_KIND: dict[str, str] = {
    "oral": "oral",
    "fill": "fill_blank",
    "vertical": "calculation",
    "step": "calculation",
    "app": "application",
    "other": "oral",
    "equation": "fill_blank",  # 解方程：填 x 的值
    "image": "application",    # 图片题：需看图作答，按应用题走拍照判分
}


def _has_variable(expr: str) -> bool:
    """表达式里是否含未知数（x/y/z/a/b/n 等字母变量）。"""
    return bool(re.search(r"(?<![A-Za-z])[a-zA-Z](?![A-Za-z])", expr or ""))


_FORMULA_RE = re.compile(r"\$([^$]+)\$")


def _strip_answer(question: str, *, is_example: bool = False) -> str:
    """去掉题干里「= 结果」的部分，但绝不破坏 `$...$` 的成对性。

    视觉模型有时会自己把算式算出来写进题干（如 `8.9＋4.5＝13.4`），必须截断，
    否则孩子直接看到答案。规则顺序不可颠倒：

    0. `is_example=True` → 原样返回（示例本来就该显示答案）
    1. 等号左侧含未知数 → 不截断（方程里的常数项属于题目本身）
    2. 只在第一个 `$...$` 内部判断「是否已算出答案」，不对整串做正则
    3. 截断点在公式内 → 重新闭合该公式并补 `____`
    4. 兜底：截断后 `$` 计数为奇数 → 放弃截断（宁可露答案，不要坏标记）
    """
    q = (question or "").strip()
    if not q or is_example:
        return q

    m = _FORMULA_RE.search(q)
    if m is None:
        # 旧格式（无公式外壳）：整串判断
        eq = re.search(r"[=＝]", q)
        if not eq:
            return q
        left = q[: eq.start()]
        if _has_variable(left):
            return q
        right = q[eq.end():].strip()
        if re.match(r"^[-−+]?\d", right):
            return left.rstrip(" =＝") + " ="
        return q

    inner = m.group(1)
    eq = re.search(r"[=＝]", inner)
    if not eq:
        return q
    left = inner[: eq.start()]
    if _has_variable(left):
        return q
    right = inner[eq.end():].strip()
    if not re.match(r"^[-−+]?\d", right):
        return q

    closed = f"${left.rstrip(' =＝')} =$"
    candidate = q[: m.start()] + closed + " ____" + q[m.end():]
    if candidate.count("$") % 2 != 0:
        return q
    return candidate


def _levenshtein(a: str, b: str) -> int:
    """编辑距离（滚动数组）。用于判断相邻页的两段题干是否同一道题。"""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(
                prev[j] + 1,                 # 删除
                cur[j - 1] + 1,              # 插入
                prev[j - 1] + (ca != cb),    # 替换
            ))
        prev = cur
    return prev[-1]


def merge_cross_page_groups(groups: list[dict]) -> list[dict]:
    """全书扫完后统一合并被页面切断的题组。

    合并条件（全部满足才吞下一组）：
    1. 当前组 `continues_next_page` 为真
    2. 下一组 `page_start == 当前组 page_end + 1`（页码紧邻）
    3. `work_mode` 相同
    4. stem 相似（任一为空 → 视为相似；否则子串包含或编辑距离 ≤ 30%）

    合并失败时把 `continues_next_page` 置 False 并标 `incomplete=True`，
    否则下一轮还会误吞。

    **不修改入参**（入口深拷贝），调用方可安全复用原始 groups。
    """
    groups = copy.deepcopy(groups or [])
    merged: list[dict] = []
    i = 0
    while i < len(groups):
        cur = groups[i]
        merged.append(cur)
        # 合并成功后不前进外层游标，继续尝试吞下一组（支持跨 3 页以上）
        while cur.get("continues_next_page") and i + 1 < len(groups):
            nxt = groups[i + 1]
            if (nxt.get("page_start") != cur.get("page_end", 0) + 1
                    or cur.get("work_mode") != nxt.get("work_mode")):
                cur["incomplete"] = True
                cur["continues_next_page"] = False
                break
            a = (cur.get("stem") or "").strip()
            b = (nxt.get("stem") or "").strip()
            same_stem = (
                not a or not b
                or a in b or b in a
                or _levenshtein(a, b) <= max(len(a), len(b)) * 0.3
            )
            if not same_stem:
                cur["incomplete"] = True
                cur["continues_next_page"] = False
                break
            cur["items"].extend(nxt.get("items") or [])
            cur["page_end"] = nxt.get("page_end", cur.get("page_end"))
            cur["continues_next_page"] = bool(nxt.get("continues_next_page"))
            i += 1   # 吞掉 nxt
        i += 1
    return merged


def build_drafts(
    aligned: list[dict],
    *,
    document_id: int,
    blanks_of=None,      # 保留形参兼容旧调用；新流程用 item["blanks"]
) -> list[QuestionDraft]:
    """已对齐的题 → QuestionDraft（供 bank._persist_drafts 落库）。

    `work_mode` 非空时按注册表定 qtype，并按 answer_kind 写 answer_json：
    - `numeric_list` → `{"blanks": [...]}`（发布闸门要求非空）
    - `choice`       → `{"correct_index": n}`
    - 其它           → `{}`

    `work_mode` 为空时走旧的 kind → qtype 映射（兼容既有题库/OCR 链路）。
    """
    from ..core.work_modes import answer_kind_of, legacy_qtype_of

    out: list[QuestionDraft] = []
    for q in aligned:
        mode = (q.get("work_mode") or "").strip()
        if mode:
            qtype = legacy_qtype_of(mode)
            kind = answer_kind_of(mode)
        else:
            qtype = QTYPE_OF_KIND.get((q.get("kind") or "oral").strip(), "oral")
            kind = ""

        d = QuestionDraft(
            qtype=qtype,
            question=_strip_answer(q.get("question") or "",
                                   is_example=bool(q.get("is_example"))),
            # 示例行的答案来自页面印好的 answer_hint
            answer=(q.get("answer") or q.get("answer_hint") or "").strip(),
            analysis=q.get("analysis") or "",
        )
        d.lesson_no = q.get("lesson_no")
        d.lesson_title = q.get("lesson_title") or ""
        d.question_no = str(q.get("question_no") or "")
        d.source_document_id = document_id
        d.tags = {"source": "practice_pdf", "page": q.get("page") or 0}

        # 题组两级：小题挂到组下；示例行不入待做
        d.group_id = q.get("group_id")
        d.seq_in_group = int(q.get("seq_in_group") or 0)
        d.is_example = bool(q.get("is_example"))
        d.work_mode = mode

        if q.get("image_path"):
            d.image_path = q["image_path"]
            d.tags["image_path"] = q["image_path"]

        # answer_json：发布闸门与判分都依赖它
        blanks = [str(x).strip() for x in (q.get("blanks") or []) if str(x).strip()]
        if kind == "numeric_list":
            if blanks:
                d.answer_json = {"blanks": blanks}
        elif kind == "choice":
            idx = q.get("correct_index")
            if idx is not None:
                d.answer_json = {"correct_index": int(idx)}
        elif not mode:
            # 旧路径：fill_blank 按空数切分答案。
            # 现有调用方通过 blanks_of 回调传空数，必须兼容。
            if qtype in ("fill_blank", "cloze"):
                n = int((blanks_of(q) if blanks_of else 0)
                        or q.get("blanks_count") or 0)
                old_blanks = split_blanks(d.answer, n) if n else None
                if old_blanks:
                    d.answer_json = {"blanks": old_blanks}
                elif n:
                    d.qtype = "oral"

        out.append(d)
    return out


def _is_aligned(q) -> bool:
    """已对齐 = 有答案；fill_blank/cloze 还要求 blanks 非空。"""
    if not (q.answer or "").strip():
        return False
    if q.qtype in ("fill_blank", "cloze"):
        try:
            data = json.loads(q.answer_json or "{}")
        except (ValueError, TypeError):
            return False
        return bool(data.get("blanks"))
    return True


def publish_aligned(db, bank_id: int) -> int:
    """把该卷里「已对齐答案」且仍 pending 的题置 published，返回条数。"""
    from ..models import Question

    rows = (
        db.query(Question)
        .filter(Question.bank_id == bank_id, Question.status == "pending")
        .all()
    )
    ids = [q.id for q in rows if _is_aligned(q)]
    if not ids:
        return 0
    db.query(Question).filter(Question.id.in_(ids)).update(
        {"status": "published"}, synchronize_session=False
    )
    return len(ids)


_OCR_INSTRUCTION = (
    "识别这一页练习册的文字，保留「第N课时 标题」与题号（1. 2. (1)）。\n"
    "**重要：绝对不要计算、不要填写答案。** 题干原样输出，遇到「＝」或「=」就到此为止，"
    "等号后面不要写任何数字。\n"
    "同一行有多道题时（横向排列），用制表符分隔，每道题单独成段。\n"
    "不要解释、不要省略。"
)

_ANSWER_OCR_INSTRUCTION = (
    "这是练习册的答案页。只按「题号 答案」的形式逐行输出，例如："
    "1. 13.4 / 2. 450。保留题号，不要输出题目原文、不要解释。"
)


def _ocr_text(pdf_path: str, page_index: int, db, *, is_answer: bool = False) -> str:
    """OCR 单页。不用 pdf_split._ocr_page（它会缓存失败结果，导致 retry 无效）。"""
    from .ai import ocr_image
    from .pdf_split import _render_page_png

    try:
        png = _render_page_png(pdf_path, page_index, dpi=150)
    except Exception:
        return ""
    instruction = _ANSWER_OCR_INSTRUCTION if is_answer else _OCR_INSTRUCTION
    try:
        return (ocr_image(db, png, instruction=instruction) or "").strip()
    except Exception:
        return ""


def _parse_pages(
    db,
    pdf_path: str,
    pages: list[int],
    *,
    is_answer: bool = False,
    on_progress=None,
) -> tuple[list[dict], list[int]]:
    """OCR 并解析指定页码（1-based）。返回 (items, 失败页列表)。

    答案页解析出的「题干」其实是答案文本，需经 `_answers_of()` 转换；
    答案页用宽松解析（纯数字答案行也算一道题）。

    `on_progress(done_count, items_so_far)`：每处理完一页回调一次，用于刷新进度。
    """
    items: list[dict] = []
    failed: list[int] = []
    for idx, pno in enumerate(pages, start=1):
        text = _ocr_text(pdf_path, pno - 1, db, is_answer=is_answer)
        if is_answer:
            # 答案页没有「第N课时」，按页内题号顺序产出
            ans = parse_answer_page(text)
            if not ans:
                failed.append(pno)
            else:
                for it in ans:
                    items.append({**it, "page": pno})
        else:
            parsed = parse_lesson_page(text)
            if not parsed["items"]:
                failed.append(pno)
                continue
            # 课时号在每个单元内会重新从 1 开始，直接用作 lesson_no 会撞车。
            # 因此用「页序」保证全书唯一，真实课时号放进 lesson_title。
            real_no = parsed["lesson_no"]
            lesson_no = pno
            title = parsed["lesson_title"]
            if real_no is not None:
                # 标题里已有「第N课时」时不要重复拼接
                if not re.match(r"^第\s*\d+\s*课时", title):
                    title = f"第{real_no}课时 {title}".strip()
            for it in parsed["items"]:
                items.append({
                    **it,
                    "lesson_no": lesson_no,
                    "lesson_title": title,
                    "real_lesson_no": real_no,
                    "page": pno,
                })
            # 同页若还有图形题（题干在图里，OCR 只能拿到 (1)(2)(3) 标签），
            # 按视觉模型给出的范围裁图补一道图片题。
            _append_image_question(db, pdf_path, pno, text, items)
        if on_progress is not None:
            try:
                on_progress(idx, items)
            except Exception:
                pass
    return items, failed


# 出现这些词说明该页可能有「题干在图里」的题
_IMAGE_HINT_RE = re.compile(r"涂色|面积|统计图|条形图|折线图|扇形图|看图|方格|钟面|展开图")


def _append_image_question(
    db, pdf_path: str, pno: int, text: str, items: list[dict]
) -> None:
    """检测并追加图片题（不改动已有文字题）。"""
    if not _IMAGE_HINT_RE.search(text or ""):
        return
    from .practice_image import crop_question_image, detect_image_questions

    infos = detect_image_questions(db, pdf_path, pno - 1)
    for info in infos:
        out = (
            f"uploads/practice_images/p{pno}_"
            f"{int(info['start'] * 100)}_{int(info['end'] * 100)}.png"
        )
        saved = crop_question_image(pdf_path, pno - 1, info["start"], info["end"], out)
        if not saved:
            continue
        title = info.get("title") or f"第{pno}页 图形题"
        items.append({
            "question_no": f"img{pno}",
            "question": title,
            "kind": "image",
            "image_path": saved,
            "lesson_no": pno,
            "lesson_title": title,
            "page": pno,
        })


def _answers_of(answer_items: list[dict]) -> list[dict]:
    """答案页解析出的 items 里，`question` 字段实为答案文本，转成对齐用的结构。"""
    out: list[dict] = []
    for it in answer_items:
        raw = (it.get("question") or "").strip()
        if "=" in raw or "＝" in raw:
            raw = re.split(r"[=＝]", raw)[-1].strip()
        if not raw:
            continue
        out.append({
            "lesson_no": it.get("lesson_no"),
            "question_no": it.get("question_no"),
            "answer": raw,
            "analysis": it.get("analysis", ""),
        })
    return out


def run_import_job(job_id: int, retry_pages: list[int] | None = None) -> None:
    """后台执行导入。retry_pages 非空时只重跑这些页。

    新开 Session：BackgroundTasks 执行时请求级 session 已失效。
    """
    from ..database import SessionLocal
    from ..models import PdfDocument, PracticeImportJob, QuestionBank
    from ..routers.bank import _persist_drafts

    db = SessionLocal()
    try:
        job = db.get(PracticeImportJob, job_id)
        if job is None:
            return
        doc = db.get(PdfDocument, job.document_id)
        bank = db.get(QuestionBank, job.bank_id)
        if doc is None or bank is None:
            job.status = "failed"
            job.error = "文档或题库卷不存在"
            db.commit()
            return

        job.status = "ocr"
        # 重跑时清零上一轮的统计，避免面板显示旧数字
        job.aligned_count = 0
        job.question_count = 0
        job.published_count = 0
        db.commit()

        q_start = job.question_start_page or 1
        q_end = job.question_end_page or (job.answer_start_page or 1) - 1
        a_start = job.answer_start_page or 1
        a_end = job.answer_end_page or a_start

        total_pages = (q_end - q_start + 1) + (a_end - a_start + 1)

        def _progress(done: int, items_so_far: list[dict]) -> None:
            """每页 OCR 完就刷新进度：done_pages 与已识别题数。

            独立 session：长时间 OCR 期间主 session 缓存会过期。
            """
            from ..database import SessionLocal as _SL
            from ..models import PracticeImportJob as _Job

            s2 = _SL()
            try:
                j2 = s2.get(_Job, job_id)
                if j2 is not None:
                    j2.done_pages = min(done, total_pages)
                    j2.question_count = len(items_so_far)
                    s2.commit()
            except Exception:
                s2.rollback()
            finally:
                s2.close()

        if retry_pages:
            q_pages = [p for p in retry_pages if q_start <= p <= q_end]
            # 重跑前删掉这些页的旧题，避免重复入库
            from ..models import Question as _Q

            db.query(_Q).filter(
                _Q.bank_id == bank.id,
                _Q.lesson_no.in_(q_pages) if q_pages else False,
            ).delete(synchronize_session=False)
            db.commit()
        else:
            q_pages = list(range(q_start, q_end + 1))

        q_items, q_failed = _parse_pages(
            db, doc.storage_path, q_pages, on_progress=_progress)

        # 答案用 AI 求解：不依赖答案页 OCR，也不会因页间错位而整体错配
        job.status = "aligning"
        job.question_count = len(q_items)
        db.commit()

        from .practice_solve import solve_math_items

        # 解题阶段也要报进度：按批回调刷新 aligned_count（前端显示「已对齐」）
        def _solve_progress(done: int, total: int) -> None:
            from ..database import SessionLocal as _SL
            from ..models import PracticeImportJob as _Job

            s2 = _SL()
            try:
                j2 = s2.get(_Job, job_id)
                if j2 is not None:
                    j2.aligned_count = done
                    j2.question_count = total
                    s2.commit()
            except Exception:
                s2.rollback()
            finally:
                s2.close()

        # 图片题没有可解的算式，答案留空（进「待补答案」由家长填）
        solvable = [it for it in q_items if it.get("kind") != "image"]
        solved = (
            solve_math_items(db, solvable, on_progress=_solve_progress)
            if solvable else {}
        )
        aligned: list[dict] = []
        idx_solvable = 0
        for it in q_items:
            if it.get("kind") == "image":
                aligned.append({**it, "answer": ""})
                continue
            ans = (solved.get(idx_solvable) or "").strip()
            idx_solvable += 1
            if ans:
                aligned.append({**it, "answer": ans})
        job.aligned_count = len(aligned)
        db.commit()

        drafts = build_drafts(aligned, document_id=job.document_id)
        _persist_drafts(db, bank, drafts, "practice_pdf")
        # 必须在 persist 之后设置：_persist_drafts 会把 manual 改成 third_party
        bank.source = "practice_pdf"
        db.commit()

        job.published_count = publish_aligned(db, bank.id)

        failed = sorted(q_failed)
        job.failed_pages = json.dumps(failed)
        total = q_end - q_start + 1
        job.done_pages = max(0, total - len(failed))
        job.status = "failed" if failed else "done"
        job.error = f"{len(failed)} 页识别失败，可重试" if failed else ""
        db.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            job = db.get(PracticeImportJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:480]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
