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


def detect_lessons(titles: list[str]) -> list[dict]:
    """按学科锚点从标题列表中识别一课。简化版：每个标题即一课。"""
    return [{"title": t} for t in titles]


def detect_lessons_from_pdf(pdf_path: str, subject: str) -> list[dict]:
    """从 PDF 文本中按学科锚点切分课程。

    返回 [{title, start_page, end_page}]，页号从 1 起。识别不到锚点时返回空列表。
    每课从命中锚点的那一页开始，到下一课开始页的前一页结束。
    """
    texts = _page_text(pdf_path)
    if not texts:
        return []
    anchor = re.compile(SUBJECT_RULES[subject]["anchor_re"])
    # 找到每个命中锚点的页码（1-based）
    hits = []  # [(page_number, title)]
    for i, text in enumerate(texts):
        m = anchor.search(text)
        if m:
            # 标题：取锚点所在行，去掉首尾空白
            line = text[m.start():].split("\n")[0].strip()
            hits.append((i + 1, line[:80] or m.group(0)))
    if not hits:
        return []
    lessons = []
    for j, (page_no, title) in enumerate(hits):
        end = hits[j + 1][0] - 1 if j + 1 < len(hits) else len(texts)
        if end < page_no:
            end = page_no
        lessons.append({"title": title, "start_page": page_no, "end_page": end})
    return lessons


def render_pages(document_id: int, pdf_path: str, out_dir: str) -> list[dict]:
    """用 PyMuPDF 把 PDF 每页渲染成图片，返回 [{page_number, image_path}]。"""
    if not os.path.exists(pdf_path):
        return []
    import fitz  # PyMuPDF
    os.makedirs(out_dir, exist_ok=True)
    pages = []
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        img_path = os.path.join(out_dir, f"{document_id}_p{i+1}.png")
        pix.save(img_path)
        pages.append({"page_number": i + 1, "image_path": img_path})
    doc.close()
    return pages
