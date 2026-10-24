import os

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

def detect_lessons(titles: list[str]) -> list[dict]:
    """按学科锚点从标题列表中识别一课。简化版：每个标题即一课。"""
    return [{"title": t} for t in titles]

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
