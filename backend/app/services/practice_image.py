"""图片题：识别含图形的题目并从页面裁出题图。

几何/统计题的题干主体在图里，纯 OCR 只能拿到「(1)(2)(3)」这样的标签。
这里让视觉模型给出该题在页面上的垂直范围，再把那一块裁成图片入库。
"""
import json
import os
import re

_LAYOUT_INSTR = (
    "这是一页小学练习册。判断其中是否有需要看图才能作答的题目"
    "（几何图形、统计图、钟面、方格图等，题干里有「求涂色部分的面积」「看图」之类）。\n"
    "如果有，给出这道（或这几道）题在页面上的垂直范围，用 0~1 比例表示（页顶=0，页底=1）。\n"
    "只返回 JSON：\n"
    '{"has_image_question": true, "start": 0.71, "end": 0.86, "title": "求涂色部分的面积", '
    '"reason": "简短说明"}\n'
    "没有这类题时返回 {\"has_image_question\": false}。"
)


def _parse_layout(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        m = re.search(r"\{[\s\S]*\}", raw or "")
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
        except (ValueError, TypeError):
            return {}
    if not isinstance(data, dict) or not data.get("has_image_question"):
        return {}
    try:
        start = float(data.get("start"))
        end = float(data.get("end"))
    except (TypeError, ValueError):
        return {}
    if not (0 <= start < end <= 1):
        return {}
    return {
        "start": start,
        "end": end,
        "title": str(data.get("title") or "").strip(),
    }


def detect_image_questions(db, pdf_path: str, page_index: int) -> list[dict]:
    """让视觉模型判断该页有没有图形题，有则返回裁图范围。"""
    from .ai import ocr_image
    from .pdf_split import _render_page_png

    try:
        png = _render_page_png(pdf_path, page_index, dpi=150)
    except Exception:
        return []
    try:
        raw = ocr_image(db, png, instruction=_LAYOUT_INSTR)
    except Exception:
        return []
    info = _parse_layout(raw)
    return [info] if info else []


def crop_question_image(
    pdf_path: str,
    page_index: int,
    start_ratio: float,
    end_ratio: float,
    out_path: str,
) -> str:
    """把页面指定纵向比例区间裁成 PNG，返回文件路径（失败返回空串）。"""
    import fitz

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_index]
        rect = page.rect
        clip = fitz.Rect(
            rect.x0,
            rect.y0 + rect.height * start_ratio,
            rect.x1,
            rect.y0 + rect.height * end_ratio,
        )
        pix = page.get_pixmap(dpi=200, clip=clip)
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        pix.save(out_path)
        doc.close()
        return out_path
    except Exception:
        return ""
