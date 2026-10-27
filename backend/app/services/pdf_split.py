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

    # 优先用学科锚点（第 N 课 / Unit N / 第 N 单元）
    anchor = re.compile(subject_rule["anchor_re"])
    hits = []
    for i, text in enumerate(texts):
        m = anchor.search(text)
        if m:
            line = text[m.start():].split("\n")[0].strip()
            hits.append((i + 1, line[:80] or m.group(0)))

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
                m = toc_re.match(line.strip())
                if not m:
                    continue
                start_page = int(m.group(3))
                title = m.group(2).strip()
                if len(title) < 2:
                    continue
                toc_entries.append((start_page, title))
            # 只解析前两个目录页即可
            if len(toc_entries) >= 15:
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

    if not hits and _is_scanned(texts) and db is not None:
        hits = _detect_lessons_scanned(pdf_path, subject, texts, db)

    if not hits:
        return []
    lessons = []
    for j, (page_no, title) in enumerate(hits):
        end = hits[j + 1][0] - 1 if j + 1 < len(hits) else len(texts)
        if end < page_no:
            end = page_no
        lessons.append({"title": title, "start_page": page_no, "end_page": end})
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
