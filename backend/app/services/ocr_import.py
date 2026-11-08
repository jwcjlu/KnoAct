"""卷子拍照 → OCR 文字 → LLM 结构化 → list[QuestionDraft]。"""
import json

from ..core.source_adapter import OcrAdapter, QuestionDraft


def _parse_questions(raw: str) -> list[dict]:
    """解析 LLM 返回的 JSON，容错：直接数组 / {"questions": [...]}；无法解析返回 []。"""
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        qs = data.get("questions") or []
        return [x for x in qs if isinstance(x, dict)]
    return []


_STRUCTURE_SYSTEM = (
    "你是小学题库录入助手。根据 OCR 识别出的卷子文字，把每道题结构化成标准 JSON。\n"
    '只返回 JSON：{"questions":[{"qtype":"single_choice|multi_choice|true_false|fill_blank|'
    'cloze|calculation|matching|short_answer|essay|application|oral",'
    '"question":"题干","options":[{"label":"选项","value":0}],"answer_json":{...},"answer":"标准答案","analysis":"解析"}]}。\n'
    "options 仅选择题/连线题需要；answer_json 按题型填 correct_index / blanks / pairs / rubric。\n"
    "无法确定的题 qtype 填 short_answer。"
)


def structure_questions_from_text(db, ocr_text: str) -> list[QuestionDraft]:
    """OCR 文字 → LLM 结构化 → QuestionDraft 列表。任何异常回落空列表。"""
    from .ai import get_provider

    if not ocr_text or not ocr_text.strip():
        return []
    provider = get_provider(db)
    if provider.name == "fake":
        return []
    try:
        raw = provider.generate(
            prompt=f"卷子 OCR 文字：\n{ocr_text[:6000]}",
            system=_STRUCTURE_SYSTEM,
            json_mode=True,
        )
        items = _parse_questions(raw)
        return OcrAdapter().normalize({"questions": items})
    except Exception:
        return []
