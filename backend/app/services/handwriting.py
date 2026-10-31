"""手写听写批改：用视觉模型比对标准词列表与手写照片，判每词对错。"""
import json

from sqlalchemy.orm import Session

from .ai import ocr_image


def _grading_instruction(words: list[dict]) -> str:
    word_list = "\n".join(f"{w['index']+1}. {w['word']}" for w in words)
    return (
        "这是一张孩子手写听写词语的照片。请按从上到下、从左到右的顺序，识别孩子写的每个词，"
        "并与下面的标准词语列表一一对应，判断每个词是否写对（注意形近字、潦草字，仔细辨认）。\n\n"
        f"标准词语列表（按听写顺序）：\n{word_list}\n\n"
        '只返回 JSON：{"results":[{"index":序号(从0开始),"written":"孩子写的内容","is_correct":true或false}]}。'
        "results 数组的长度必须等于标准词语的个数，按顺序一一对应。"
    )


def parse_grading_result(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    results = data.get("results") if isinstance(data, dict) else []
    if not isinstance(results, list):
        return []
    out = []
    for r in results:
        if not isinstance(r, dict):
            continue
        idx = r.get("index")
        is_correct = r.get("is_correct")
        if not isinstance(idx, int) or not isinstance(is_correct, bool):
            continue
        out.append({
            "index": idx,
            "written": (r.get("written") or "").strip(),
            "is_correct": is_correct,
        })
    return out


def grade_handwriting(db: Session, image_bytes: bytes, words: list[dict]) -> list[dict]:
    """用视觉模型批改手写听写。返回 [{index, written, is_correct}]。

    视觉模型不可用/异常时返回空列表（不抛异常，前端提示批改失败）。
    """
    if not image_bytes or not words:
        return []
    try:
        raw = ocr_image(db, image_bytes, _grading_instruction(words))
        return parse_grading_result(raw)
    except Exception:
        return []
