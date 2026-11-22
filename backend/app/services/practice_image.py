"""图片题：识别含图形的题目并从页面裁出题图。

几何/统计题的题干主体在图里，纯 OCR 只能拿到「(1)(2)(3)」这样的标签。
这里让视觉模型给出该题在页面上的垂直范围，再把那一块裁成图片入库。
"""
import json
import os
import re

_LAYOUT_INSTR = (
    "这是一页小学练习册的图片。\n"
    "请找出页面中「需要看图才能作答」的题目（几何图形、统计图、钟面、方格图等）的"
    "**完整区域**，必须包含：题目文字、所有图形、所有尺寸标注。\n"
    "范围要覆盖整道题，绝不能切掉图形或标注。\n"
    "用 0~1 比例给出上下边界（页面最顶部=0.0，最底部=1.0）。\n"
    "只返回 JSON：\n"
    '{"found": true, "start": 0.55, "end": 0.95, "title": "题目标题"}\n'
    "如果这一页没有这类题，返回 {\"found\": false}。"
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
    if not isinstance(data, dict):
        return {}
    if not (data.get("found") or data.get("has_image_question")):
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
