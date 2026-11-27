import os
import re

# 学科拆课规则：切分锚点 + 是否提取生词/单词表
SUBJECT_RULES = {
    "语文": {
        "anchor_re": r"第\s*[一二三四五六七八九十百\d]+\s*课",
        "has_word_bank": True,
        "word_extra": "拼音 + 释义",
    },
    "英语": {
        "anchor_re": r"(Unit|Lesson)\s*\d+",
        "has_word_bank": True,
        "word_extra": "音标 + 词性 + 释义",
    },
    "数学": {
        "anchor_re": r"第\s*[一二三四五六七八九十百\d]+\s*单元",
        "has_word_bank": False,  # 数学无生词表，知识点为主
        "word_extra": "",
    },
}


def _page_text(pdf_path: str) -> list[str]:
    """逐页提取 PDF 文本，返回 [第1页文本, 第2页文本, ...]。无法打开时返回空列表。"""
    if not os.path.exists(pdf_path):
        return []
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return []
    doc = fitz.open(pdf_path)
    texts = [page.get_text() for page in doc]
    doc.close()
    return texts


def _is_scanned(texts: list[str]) -> bool:
    """判断是否为扫描版（图片型）PDF：正文页几乎没有有效文字，只有水印/编号。"""
    if not texts:
        return False
    meaningful = 0
    total = 0
    for t in texts:
        s = t.strip()
        if not s:
            continue
        total += 1
        # 有效文字：非纯水印（形如 "5A00012026 AU"）且非纯数字/符号
        cleaned = re.sub(r"[0-9A-Za-z\s.·|]+", "", s)
        if len(cleaned) >= 8 or len(s) > 200:
            meaningful += 1
    # 有效文字页占比很低 → 扫描版
    return total > 0 and meaningful / total < 0.15


_OCR_CACHE: dict[tuple, str] = {}


def _render_page_png(pdf_path: str, page_index: int, dpi: int = 120) -> bytes:
    """把 PDF 某页渲染成 PNG 字节。"""
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[page_index]
    pix = page.get_pixmap(dpi=dpi)
    data = pix.tobytes("png")
    doc.close()
    return data


def _ocr_page(pdf_path: str, page_index: int, db, instruction: str) -> str:
    """OCR 单页（带缓存）。db 为 None 或 OCR 失败时返回空串。"""
    key = (pdf_path, page_index, instruction)
    if key in _OCR_CACHE:
        return _OCR_CACHE[key]
    if db is None:
        return ""
    try:
        from .ai import ocr_image
        data = _render_page_png(pdf_path, page_index)
        text = ocr_image(db, data, instruction)
    except Exception:
        text = ""
    _OCR_CACHE[key] = text
    return text


def detect_lessons(titles: list[str]) -> list[dict]:
    """按学科锚点从标题列表中识别一课。简化版：每个标题即一课。"""
    return [{"title": t} for t in titles]


def _calibrate_page_offset(texts: list[str], toc_entries: list[tuple[int, str]]) -> int:
    """计算「印刷页码 → 物理页序号」的偏移量。

    目录页码是印刷页码（从课文第 1 页算起），物理页含封面/版权/目录/导读等前置页。
    做法：取目录里第一课，在其标题文本（去掉首尾空白/零宽字符）在「目录页之后」的物理页里
    找首次真实出现的位置，偏移 = 该物理页 − 印刷页码。找不到时回退为 0。
    """
    if not toc_entries:
        return 0
    # 目录页大致在前 8 页内，正文从其后开始搜
    first_print_page, first_title = min(toc_entries, key=lambda x: x[0])
    needle = first_title.strip().replace("​", "").replace("‌", "")
    if len(needle) < 2:
        return 0
    for i in range(5, len(texts)):
        page_text = texts[i].replace("​", "").replace("‌", "")
        # 标题需作为「独立一行/词」出现，避免正文里碰巧包含标题词
        if needle in page_text:
            # 标题要在行首或紧跟序号，才算正文标题行；粗略用「包含且非目录点线行」判断
            if "目录" not in page_text and page_text.count(".") < 8:
                return (i + 1) - first_print_page
    return 0


_CN_UNIT = "一二三四五六七八九十"
_MATH_UNIT_IN_LINE = re.compile(r"第\s*([一二三四五六七八九十百\d]+)\s*单元")
# 标准「第五单元5」+ 北师大乱码字体「第ʷ单元\\x12」（\\x12–\\x15 对应第 1–4 单元）
_MATH_UNIT_HEADER = re.compile(
    r"^(?:\d+\s*)?"
    r"第(?:\s*([一二三四五六七八九十]+)\s*单元\s*(\d+)"
    r"|.{1,3}单元([\x12-\x19]))"
    r"\s*$"
)


def _math_unit_ordinal(title: str) -> str | None:
    m = _MATH_UNIT_IN_LINE.search(title)
    return m.group(1) if m else None


def _math_unit_index_from_header(m: re.Match) -> int | None:
    if m.group(1):
        i = _CN_UNIT.find(m.group(1))
        if i >= 0:
            return i + 1
    if m.group(2) and str(m.group(2)).isdigit():
        return int(m.group(2))
    ctrl = m.group(3)
    if ctrl and len(ctrl) == 1:
        n = ord(ctrl) - 0x11
        if 1 <= n <= 9:
            return n
    return None


def _topic_line_score(text: str) -> float:
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    allowed = set("（）().，、？！：；· ")
    bad = sum(
        1
        for c in text
        if not (
            "\u4e00" <= c <= "\u9fff"
            or c in allowed
            or (c.isascii() and (c.isalnum() or c in "+－=×÷"))
        )
    )
    return cjk * 2 - bad * 3


def _clean_math_topic(topic: str) -> str:
    s = re.sub(r"[^\u4e00-\u9fff（）().，、\s]", "", topic)
    return re.sub(r"\s+", "", s)


def _math_unit_topic(lines: list[str], unit_line_index: int) -> str:
    candidates: list[tuple[int, str, float]] = []
    for j in range(unit_line_index + 1, min(unit_line_index + 4, len(lines))):
        nxt = lines[j].strip()
        if not nxt or re.fullmatch(r"\d{1,3}", nxt):
            continue
        if "单元" in nxt or "北师大" in nxt:
            continue
        if re.match(r"^第\s*[一二三四五六七八九十百\d]+\s*[课个]", nxt):
            continue
        if len(nxt) > 22:
            continue
        score = _topic_line_score(nxt)
        if score >= 2:
            candidates.append((j, nxt, score))
    if not candidates:
        return ""

    def _topic_rank(item: tuple[int, str, float]) -> float:
        _j, text, score = item
        cleaned = _clean_math_topic(text)
        base = max(score, _topic_line_score(cleaned))
        penalty = len(cleaned) // 6
        if re.search(r"(探索|练一练|想一想|回顾|测量|交流)", cleaned):
            penalty += 8
        return base - penalty

    best_rank = max(_topic_rank(c) for c in candidates)
    tier = [c for c in candidates if _topic_rank(c) >= best_rank - 2]
    _j, best_raw, _ = min(tier, key=lambda x: x[0])
    return _clean_math_topic(best_raw)


_MATH_OCR_UNIT = re.compile(r"^第\s*([一二三四五六七八九十\d]+)\s*单元\s*(.*)$")


def _math_unit_title_from_ocr(raw: str) -> str | None:
    """视觉 OCR 常输出「第一单元」+ 换行 + 单元主题，与 PDF 文本层版式不同。"""
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    for i, line in enumerate(lines):
        m = _MATH_OCR_UNIT.match(line)
        if not m:
            continue
        idx = m.group(1)
        if idx.isdigit():
            n = int(idx)
            unit_str = f"第{_CN_UNIT[n - 1]}单元" if 1 <= n <= len(_CN_UNIT) else f"第{idx}单元"
        else:
            unit_str = f"第{idx}单元"
        inline = (m.group(2) or "").strip()
        if inline:
            topic = _clean_math_topic(inline)
            return f"{unit_str} {topic}".strip() if topic else unit_str
        if i + 1 < len(lines):
            topic = _clean_math_topic(lines[i + 1])
            return f"{unit_str} {topic}".strip() if topic else unit_str
    return None


def _page_has_garbled_math_unit_header(page_text: str) -> bool:
    for line in page_text.split("\n"):
        m = _MATH_UNIT_HEADER.match(line.strip())
        if m and m.group(3):
            return True
    return False


def _math_title_quality(title: str) -> float:
    if " " not in title:
        return 0.0
    topic = title.split(" ", 1)[1]
    return _topic_line_score(_clean_math_topic(topic))


def _refine_math_hit_titles(
    pdf_path: str, hits: list[tuple[int, str]], texts: list[str], db
) -> list[tuple[int, str]]:
    """乱码字体单元扉页：用 OCR 补全标准单元主题名。"""
    if not db:
        return hits
    out: list[tuple[int, str]] = []
    for page_no, title in hits:
        page_text = texts[page_no - 1] if page_no <= len(texts) else ""
        topic = title.split(" ", 1)[1] if " " in title else ""
        cleaned = _clean_math_topic(topic) if topic else ""
        needs_ocr = (
            _page_has_garbled_math_unit_header(page_text)
            or not cleaned
            or len(cleaned) > 18
            or _math_title_quality(title) < 6
        )
        if needs_ocr:
            try:
                raw = _ocr_page(
                    pdf_path,
                    page_no - 1,
                    db,
                    "识别本页「第×单元」标题行及其下方单元主题名称，只输出这两行汉字原文。",
                )
                ocr_title = _math_unit_title_from_ocr(raw)
                if ocr_title and (
                    _page_has_garbled_math_unit_header(page_text)
                    or len(cleaned) > 18
                    or _math_title_quality(ocr_title) >= max(_math_title_quality(title), 4)
                ):
                    title = ocr_title
            except Exception:
                pass
        elif cleaned and cleaned != topic:
            title = f"{title.split(' ', 1)[0]} {cleaned}"
        out.append((page_no, title[:80]))
    return out


def _math_unit_title(page_text: str) -> str | None:
    """北师大等版式：单元行「第五单元5」或乱码「第ʷ单元\\x12」+ 下方课题名。"""
    lines = [ln.strip() for ln in page_text.split("\n")]
    for i, line in enumerate(lines):
        if not line or "单元" not in line:
            continue
        m = _MATH_UNIT_HEADER.match(line)
        if not m:
            continue
        idx = _math_unit_index_from_header(m)
        if not idx or idx > len(_CN_UNIT):
            continue
        unit_str = f"第{_CN_UNIT[idx - 1]}单元"
        topic = _math_unit_topic(lines, i)
        return f"{unit_str} {topic}".strip() if topic else unit_str
    return None


def _dedupe_math_hits(hits: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """同一「第 N 单元」只保留首次出现的物理页（避免页眉重复命中）。"""
    out: list[tuple[int, str]] = []
    seen: set[str] = set()
    for page_no, title in sorted(hits, key=lambda x: x[0]):
        ord_ = _math_unit_ordinal(title)
        if ord_:
            if ord_ in seen:
                continue
            seen.add(ord_)
        out.append((page_no, title))
    return out


def detect_lessons_from_pdf(pdf_path: str, subject: str, db=None) -> list[dict]:
    """从 PDF 文本中按学科锚点切分课程。

    返回 [{title, start_page, end_page}]，页号从 1 起。识别不到锚点时返回空列表。
    每课从命中锚点的那一页开始，到下一课开始页的前一页结束。

    支持：
    1. 文本型 PDF：锚点「第 N 课」/「Unit N」/「第 N 单元」，或语文目录页「序号+标题+页码」
    2. 扫描版 PDF（图片型）：db 提供时，OCR 目录页拿到「Big Question N + 标题 + 印刷页码」，
       再 OCR 定位第一单元真实物理页反推偏移。
    """
    texts = _page_text(pdf_path)
    if not texts:
        return []
    subject_rule = SUBJECT_RULES.get(subject)
    if not subject_rule:
        return []

    anchor = re.compile(subject_rule["anchor_re"])
    hits = []
    if subject == "数学":
        # 逐页识别单元扉页行（含乱码字体层），不依赖「第 N 单元」正则锚点
        for i, text in enumerate(texts):
            title = _math_unit_title(text)
            if title:
                hits.append((i + 1, title[:80]))
    else:
        for i, text in enumerate(texts):
            m = anchor.search(text)
            if not m:
                continue
            line = text[m.start():].split("\n")[0].strip()
            hits.append((i + 1, line[:80] or m.group(0)))

    if subject == "数学" and len(hits) < 6:
        # 文本层乱码时锚点匹配失败：尝试从目录页解析「第 N 单元 + 标题 + 页码」
        toc_re = re.compile(
            r"^\s*第\s*([一二三四五六七八九十百\d]+)\s*单元\s*(.+?)[.．…\s]*[.．…]{2,}\s*(\d{1,3})\s*$"
        )
        toc_entries: list[tuple[int, str]] = []
        for text in texts:
            is_toc = "目录" in text or (text.count(".") > 8 and "单元" in text)
            if not is_toc:
                continue
            for line in text.split("\n"):
                m = toc_re.match(line.strip())
                if not m:
                    continue
                start_page = int(m.group(3))
                title = f"第{m.group(1)}单元 {m.group(2).strip()}"
                if len(m.group(2).strip()) >= 2:
                    toc_entries.append((start_page, title))
            if len(toc_entries) >= 6:
                break
        if toc_entries:
            page_offset = _calibrate_page_offset(texts, toc_entries)
            seen_pages: set[int] = set()
            for start_page, title in sorted(toc_entries):
                phys = start_page + page_offset
                if phys in seen_pages:
                    continue
                seen_pages.add(phys)
                hits.append((phys, title[:80]))

    if subject == "数学" and hits:
        hits = _dedupe_math_hits(hits)
        hits = _refine_math_hit_titles(pdf_path, hits, texts, db)

    if not hits and subject == "语文":
        # 人教版语文：优先从「目录页」解析「序号 + 标题 + 点线 + 页码」，
        # 直接拿到准确的课程名和正文起始页（比在正文里猜标题可靠得多）。
        toc_re = re.compile(r"^\s*(\d{1,3})\*?\s*[　\s]+(.+?)[.．…\s]*[.．…]{2,}\s*(\d{1,3})\s*$")
        toc_entries = []  # [(start_page, title)]
        for i, text in enumerate(texts):
            # 目录页特征：出现「目录」字样，或大量点线 + 单元
            is_toc = "目录" in text or (text.count(".") > 8 and "单元" in text)
            if not is_toc:
                continue
            for line in text.split("\n"):
                s = line.strip()
                m = toc_re.match(s)
                if m:
                    start_page = int(m.group(3))
                    title = m.group(2).strip()
                    if len(title) >= 2:
                        toc_entries.append((start_page, title))
                    continue
                mm = _CN_TOC_MODULE_RE.match(s)
                if mm:
                    toc_entries.append((int(mm.group(2)), mm.group(1)))
            # 人教目录常跨 2 页；用「已扫目录页数」收束，避免第 1 页因园地条目凑满 15 条就丢掉后半册
            toc_pages = sum(
                1 for t in texts[: i + 1]
                if "目录" in t or (t.count(".") > 8 and "单元" in t)
            )
            if toc_pages >= 2 and len(toc_entries) >= 10:
                break
        # 目录里的页码是「印刷页码」，而 _page_text 用的是「物理页序号」（含封面/版权/导读等前置页）。
        # 两者差一个固定偏移，需校准：用第一课的标题在目录页之后的物理页里定位正文真实起始页，反推偏移。
        page_offset = _calibrate_page_offset(texts, toc_entries)

        # 按起始页去重排序，并换算成物理页
        seen_pages = set()
        hits = []
        for start_page, title in sorted(toc_entries):
            phys = start_page + page_offset
            if phys in seen_pages:
                continue
            seen_pages.add(phys)
            hits.append((phys, title))

    # 语文：目录/锚点就绪后再并入园地等模块页，避免无锚点时园地抢占 hits 挡住目录回退
    if subject == "语文" and hits:
        hits = _merge_cn_module_hits(hits, texts)

    if not hits and _is_scanned(texts) and db is not None:
        hits = _detect_lessons_scanned(pdf_path, subject, texts, db)

    # 英语书末 Word list 不单独成课：词条按 Unit 回填到各课。这里只把它从最后一课的页码里切掉，
    # 避免单词表、专有名词和后记被算进最后一课的正文。
    word_list = _detect_word_list(pdf_path, subject, texts, len(texts), db)
    if word_list is not None:
        hits = [(p, t) for p, t in hits if p < word_list["start_page"]]

    cn_tables = _detect_chinese_word_tables(pdf_path, subject, texts, len(texts), db)
    if cn_tables:
        table_pages = {
            p
            for seg in cn_tables
            for p in range(seg["start_page"], seg["end_page"] + 1)
        }
        hits = [(p, t) for p, t in hits if p not in table_pages]
        tail_start = min(seg["start_page"] for seg in cn_tables)
        if hits and hits[-1][0] < tail_start:
            pass  # last_end 在下方与 word_list 逻辑合并

    lessons = []
    last_end = len(texts)
    if word_list is not None:
        last_end = word_list["start_page"] - 1
    elif cn_tables:
        tail_start = min(seg["start_page"] for seg in cn_tables)
        if not hits or hits[-1][0] < tail_start:
            last_end = min(last_end, tail_start - 1)
    for j, (page_no, title) in enumerate(hits):
        end = hits[j + 1][0] - 1 if j + 1 < len(hits) else last_end
        if cn_tables:
            end = _lesson_end_clear_of_cn_tables(page_no, end, cn_tables)
        if end < page_no:
            end = page_no
        lessons.append({"title": title, "start_page": page_no, "end_page": end})
    if word_list is not None:
        lessons.append({
            "title": "单词列表",
            "start_page": word_list["start_page"],
            "end_page": word_list["end_page"],
        })
    for seg in sorted(cn_tables, key=lambda s: s["start_page"]):
        lessons.append({
            "title": seg["title"],
            "start_page": seg["start_page"],
            "end_page": seg["end_page"],
        })
    return lessons


def _detect_lessons_scanned(pdf_path: str, subject: str, texts: list[str], db) -> list[tuple[int, str]]:
    """扫描版教材拆课：OCR 目录页拿到「单元标题 + 印刷页码」，再定位偏移。"""
    if subject != "英语":
        return []
    total = len(texts)
    # 1) 在前 10 页里找目录页：OCR 原样输出，再正则提取「Big Question N 标题 Page 页码」
    toc_entries = []  # [(print_page, title)]
    # OCR 里标题与 Page 之间隔着换行 + 重复编号（如 "Big Question 1 What...? \n1\n Page 1"），用 DOTALL 跨行匹配
    bq_re = re.compile(r"Big\s*Question\s+(\d+)\s+(.+?)\s*[Pp]age\s+(\d+)", re.DOTALL)
    for i in range(min(10, total)):
        raw = _ocr_page(pdf_path, i, db, "识别图片中的全部文字，原样输出，不要解释，不要省略。")
        if not raw:
            continue
        for m in bq_re.finditer(raw):
            title = re.sub(r"[\n\r\d]+", " ", m.group(2)).strip()
            print_page = int(m.group(3))
            if title and len(title) > 2:
                toc_entries.append((print_page, title))
        if len(toc_entries) >= 4:
            break

    if not toc_entries:
        return []

    # 2) 定位第一单元真实物理页：从目录页之后逐页 OCR 找「Big Question 1 / Unit 1」开头页
    first_print_page = min(e[0] for e in toc_entries)
    offset = 0
    for i in range(6, total):
        raw = _ocr_page(pdf_path, i, db, "这一页是否是某个单元（Big Question）的开头？若是请只回复它的编号数字，如 1；若不是只回复 0。")
        if raw and raw.strip() in {"1", "2", "3", "4", "5", "6", "7", "8"}:
            offset = (i + 1) - first_print_page
            break

    # 3) 生成 hits：印刷页码 + 偏移 → 物理页
    seen = set()
    hits = []
    for print_page, title in sorted(toc_entries):
        phys = print_page + offset
        if phys in seen:
            continue
        seen.add(phys)
        hits.append((phys, title))
    return hits


_CN_TABLE_TITLES = ("识字表", "写字表", "词语表")
_CN_TABLE_KIND = {"识字表": "recognize", "写字表": "write", "词语表": "phrase"}
_CN_TABLE_SUMMARY_TITLES = {"识字表汇总", "写字表汇总", "词语表汇总"}
# 册末表续页遇后记必须停；「语文园地」常是表内课号小节，不能当停点
_CN_TABLE_STOP_RE = re.compile(r"(后\s*记|附录)")
_CN_MODULE_TITLE_RE = re.compile(
    r"^(语文园地[一二三四五六七八九十\d]*|口语交际|习作|日积月累|快乐读书吧)"
)
_CN_TOC_MODULE_RE = re.compile(
    r"^\s*[◎●•]?\s*(语文园地[一二三四五六七八九十\d]*|口语交际|习作|快乐读书吧)"
    r"\s*[.．…\s]*[.．…]{2,}\s*(\d{1,3})\s*$"
)
# 人教 PDF 页眉常在「识字表」中间插 EN SPACE / 窄空格
_CN_HEADING_SPACE = re.compile(r"[\s\u2000-\u200d\ufeff]+")


def is_cn_table_title(title: str) -> bool:
    t = (title or "").strip()
    return t in _CN_TABLE_TITLES or t in _CN_TABLE_SUMMARY_TITLES


def _merge_cn_module_hits(hits: list[tuple[int, str]], texts: list[str]) -> list[tuple[int, str]]:
    """把正文页里的语文园地等模块并入 hits，切开上一课页码。"""
    if not texts:
        return hits
    by_page = {p: t for p, t in hits}
    for i, text in enumerate(texts):
        title = _cn_module_title(text)
        if not title:
            continue
        page = i + 1
        if page not in by_page:
            by_page[page] = title
    return [(p, by_page[p]) for p in sorted(by_page)]


def _cn_module_title(text: str) -> str | None:
    """页首是否是语文园地/口语交际等模块标题。"""
    for line in (text or "").splitlines()[:6]:
        s = line.strip()
        if not s:
            continue
        m = _CN_MODULE_TITLE_RE.match(s)
        if m:
            return m.group(1)
        break
    return None


def _compact_cn_heading(text: str) -> str:
    """去掉页眉里的特殊空格，便于匹配「识字表」等标题。"""
    return _CN_HEADING_SPACE.sub("", text or "")


def _cn_table_kind_from_text(text: str) -> str | None:
    head = "\n".join((text or "").strip().splitlines()[:5])
    compact = _compact_cn_heading(head)
    for name, kind in _CN_TABLE_KIND.items():
        if name in head or name in compact:
            return kind
    return None


def _page_is_cn_word_table(text: str) -> bool:
    return _cn_table_kind_from_text(text) is not None


def _page_continues_cn_table(text: str) -> bool:
    """表内续页：无新表标题、无后记，但有课号行或表格式汉字词条。

    注意：表内「语文园地」是课号小节（列该模块的字词），应续页而非停。
    """
    if not text or not text.strip():
        return False
    if _page_is_cn_word_table(text):
        return False
    if _CN_TABLE_STOP_RE.search("\n".join((text or "").splitlines()[:6])):
        return False
    lesson_nos = char_lines = word_lines = 0
    garden_sec = False
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if re.match(r"^\d{1,2}$", s):
            lesson_nos += 1
            continue
        compact = _compact_cn_heading(s)
        if compact == "语文园地" or (compact.startswith("语文园地") and len(compact) <= 8):
            garden_sec = True
            continue
        spaced = _CN_HEADING_SPACE.sub(" ", s).strip()
        if re.fullmatch(r"[\u4e00-\u9fff](?: [\u4e00-\u9fff]){0,30}", spaced):
            char_lines += 1
            continue
        if re.search(r"[\u4e00-\u9fff]{2,}", s) and len(s) <= 40 and "。" not in s:
            word_lines += 1
    return lesson_nos >= 1 or garden_sec or char_lines >= 1 or word_lines >= 4


def _cn_table_title_from_kind(kind: str) -> str:
    for name, k in _CN_TABLE_KIND.items():
        if k == kind:
            return name
    return kind


def _lesson_end_clear_of_cn_tables(page_no: int, end: int, tables: list[dict]) -> int:
    for seg in tables:
        ts, te = seg["start_page"], seg["end_page"]
        if page_no <= te and end >= ts:
            end = min(end, ts - 1)
    return max(end, page_no)


_CN_TABLE_TAIL = 28  # 册末表只在书末附近，避免对全文逐页 OCR


def _detect_chinese_word_tables(
    pdf_path: str, subject: str, texts: list[str], total_pages: int, db
) -> list[dict]:
    """检测语文教材识字/写字/词语表页码范围。返回多段 {kind, title, start_page, end_page}。"""
    if subject != "语文" or not texts or total_pages <= 0:
        return []

    segments: list[dict] = []
    i = max(0, total_pages - _CN_TABLE_TAIL)
    while i < total_pages:
        raw = texts[i] or ""
        # 文本层够用则不再 OCR；仅空白/扫描页才问视觉模型
        if not _page_is_cn_word_table(raw) and db is not None and len(raw.strip()) < 24:
            ocr = _ocr_page(
                pdf_path,
                i,
                db,
                "若本页是识字表、写字表或词语表（含课号与汉字词），请原样转写页眉与正文；否则只回复 no。",
            )
            if ocr and ocr.strip().lower() not in {"no", "no.", "否", "不是"}:
                raw = ocr
        kind = _cn_table_kind_from_text(raw)
        if not kind:
            i += 1
            continue
        end = i
        j = i + 1
        while j < total_pages:
            nxt = texts[j] or ""
            if _cn_table_kind_from_text(nxt):
                break
            if (
                not _page_continues_cn_table(nxt)
                and db is not None
                and len((nxt or "").strip()) < 24
            ):
                ocr = _ocr_page(pdf_path, j, db, "若仍在上一张识字/写字/词语表内，原样转写；否则只回复 no。")
                if ocr and ocr.strip().lower() not in {"no", "no.", "否", "不是"}:
                    if _cn_table_kind_from_text(ocr):
                        break
                    if _page_continues_cn_table(ocr):
                        nxt = ocr
            if _cn_table_kind_from_text(nxt):
                break
            if _page_continues_cn_table(nxt):
                end = j
                j += 1
            else:
                break
        segments.append({
            "kind": kind,
            "title": _cn_table_title_from_kind(kind),
            "start_page": i + 1,
            "end_page": end + 1,
        })
        i = end + 1
    return segments


def is_word_list_title(title: str) -> bool:
    return (title or "").strip().lower() in {"word list", "单词列表"}
_WORD_LIST_TAIL = 16
_WORD_LIST_KEYWORDS = ("word list", "vocabulary", "glossary", "单词表", "词汇表", "单词列表")
WORD_LIST_OCR_PROMPT = (
    "如果这一页是英语教材的单词表（Word list / Vocabulary，含 Unit 编号和中文释义）"
    "或专有名词表（Proper nouns），请按先左栏、后右栏逐行转写，保留行首星号 * 和 Unit 标题，不要解释。"
    "如果都不是，只回复 no。"
)
_GLOSS_SPLIT = re.compile(r"[\u4e00-\u9fff（(]")


def split_gloss_line(line: str) -> tuple[str, str, bool] | None:
    """一行「英文词/短语 + 中文释义」。返回 (word, gloss, starred)，对不上则 None。"""
    s = line.strip()
    if not s or s.startswith("注"):
        return None
    star = s[0] in "*＊"
    body = s[1:].strip() if star else s
    m = _GLOSS_SPLIT.search(body)
    if not m or m.start() == 0:
        return None
    word = re.sub(r"\s+", " ", body[:m.start()]).strip()
    gloss = body[m.start():].strip()
    if not word or not gloss or not re.search(r"[A-Za-z]", word):
        return None
    if len(word) > 60 or len(word.split()) > 10:
        return None
    return word, gloss, star


def _page_is_word_list(text: str) -> bool:
    """这一页是不是书末单词表。

    扫描版视觉模型经常不回 yes，也不转写标题 Word list，只吐出「Unit N + 英文 + 中文」。
    那种版式也要算命中。整页只有 no 才否掉。
    """
    if not text or not text.strip():
        return False
    first = text.strip().splitlines()[0].strip().lower()
    if first in {"no", "no.", "否", "不是"}:
        return False
    if first in {"yes", "yes."} or (first.startswith("yes") and len(first) < 24):
        return True
    low = text.lower()
    if any(k in low for k in _WORD_LIST_KEYWORDS):
        return True
    units = entries = 0
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"unit\s*\d+\b", s, re.I):
            units += 1
        elif split_gloss_line(s):
            entries += 1
    return units >= 1 and entries >= 8


def _page_continues_word_list(text: str) -> bool:
    """已经定位到单词表之后，后续页只要还在列 Unit 词条或专有名词就继续。"""
    if _page_is_word_list(text or ""):
        return True
    if re.search(r"proper\s+nouns", text or "", re.I):
        return True
    if not text:
        return False
    units = entries = 0
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"unit\s*\d+\b", s, re.I):
            units += 1
        elif split_gloss_line(s):
            entries += 1
    return units >= 1 and entries >= 1


def _page_is_glossary(text: str) -> bool:
    """单词表、专有名词表，或一页里有足够多的「英文 + 中文」词条。"""
    if _page_is_word_list(text or ""):
        return True
    if re.search(r"proper\s+nouns", text or "", re.I):
        return True
    entries = sum(1 for line in (text or "").splitlines() if split_gloss_line(line))
    return entries >= 8


def _glossary_end_index(pdf_path: str, texts: list[str], start: int, db) -> int:
    """从单词表起始页往后，停在后记/空白页之前。"""
    end = start
    last = min(len(texts), start + 8)
    for i in range(start, last):
        raw = texts[i] or ""
        if not _page_is_glossary(raw) and db is not None:
            raw = _ocr_page(pdf_path, i, db, WORD_LIST_OCR_PROMPT)
        if _page_is_glossary(raw or ""):
            end = i
        elif i > start:
            break
    return end


def _detect_word_list(pdf_path: str, subject: str, texts: list[str], total_pages: int, db) -> dict | None:
    """检测英语教材书末 Word list 的页码范围。返回 {title, start_page, end_page} 或 None。

    文本型看关键字或「Unit + 中文释义」版式；扫描版 OCR 书末最多 16 页，取最早一页，
    结束页停在后记之前。词条由 lesson_extract.apply_word_list 写入各课，并另建「单词列表」一课。
    """
    if subject != "英语" or not texts or total_pages <= 0:
        return None

    lo = max(0, total_pages - _WORD_LIST_TAIL)
    hit = None
    for i in range(lo, total_pages):
        if _page_is_word_list(texts[i] or ""):
            hit = i
            break

    if hit is None and db is not None:
        misses = 0
        for i in range(total_pages - 1, lo - 1, -1):
            raw = _ocr_page(pdf_path, i, db, WORD_LIST_OCR_PROMPT)
            if _page_is_word_list(raw or ""):
                hit = i
                misses = 0
            elif hit is not None:
                misses += 1
                if misses >= 2:
                    break
    if hit is None:
        return None
    end = _glossary_end_index(pdf_path, texts, hit, db)
    return {"title": "单词列表", "start_page": hit + 1, "end_page": end + 1}


def render_pages(document_id: int, pdf_path: str, out_dir: str) -> list[dict]:
    """用 PyMuPDF 把 PDF 每页渲染成图片，返回 [{page_number, image_path}]。"""
    if not os.path.exists(pdf_path):
        return []
    import fitz  # PyMuPDF
    os.makedirs(out_dir, exist_ok=True)
    pages = []
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        # dpi=300：教材含内嵌方正 GBK Type0 字体，pdf.js 的 canvas 无法栅格化（死锁），
        # 前端阅读器回退到后端预渲染 PNG；300 DPI 让图片足够锐利，视觉上等同「原文」。
        pix = page.get_pixmap(dpi=300)
        img_path = os.path.join(out_dir, f"{document_id}_p{i+1}.png").replace("\\", "/")
        pix.save(img_path)
        pages.append({"page_number": i + 1, "image_path": img_path})
    doc.close()
    return pages
