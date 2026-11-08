"""卷子拍照 → OCR 文字 → LLM 结构化 → list[QuestionDraft]。"""
import json

from ..core.source_adapter import OcrAdapter, QuestionDraft


def _parse_import(raw: str) -> tuple[list[dict], list[dict]]:
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return [], []
    if isinstance(data, list):
        return [], [x for x in data if isinstance(x, dict)]
    if not isinstance(data, dict):
        return [], []
    passages = [x for x in (data.get("passages") or []) if isinstance(x, dict)]
    questions = [x for x in (data.get("questions") or []) if isinstance(x, dict)]
    return passages, questions


def _parse_questions(raw: str) -> list[dict]:
    _passages, questions = _parse_import(raw)
    return questions


def _flatten_import(passages: list[dict], questions: list[dict]) -> list[QuestionDraft]:
    items: list[dict] = []
    for p in passages:
        title = (p.get("title") or "").strip()
        content = (p.get("content") or "").strip()
        for it in p.get("questions") or []:
            if not isinstance(it, dict):
                continue
            items.append({**it, "passage_title": title, "passage_content": content})
    items.extend(questions)
    return OcrAdapter().normalize({"questions": items})


_STRUCTURE_SYSTEM = (
    "你是小学题库录入助手。根据 OCR 识别出的卷子文字，把每道题结构化成标准 JSON。\n"
    "若是阅读理解（一篇短文带若干子题），返回 "
    '{"passages":[{"title":"短文标题","content":"短文正文","questions":[...]}],'
    '"questions":[独立题...]}；否则只返回 {"questions":[...]}。\n'
    '题目字段：{"qtype":"single_choice|multi_choice|true_false|fill_blank|'
    'cloze|calculation|matching|short_answer|essay|application|oral",'
    '"question":"题干","options":[{"label":"选项","value":0}],"answer_json":{...},"answer":"标准答案","analysis":"解析"}。\n'
    "content 只允许这些标记：# ## ** * <u> /ipa/ ____（加粗、斜体、下划线、音标、填空）。\n"
    "阅读材料 content 中 ____ 的个数与顺序，必须等于该材料下 fill_blank/cloze 子题的个数与顺序；"
    "每道 fill_blank/cloze 子题只对应一个空，answer_json.blanks 只含该空答案。"
    "独立填空题（不在 passages 内）题干里的 ____ 数量须与 answer_json.blanks 条数一致。\n"
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
        passages, questions = _parse_import(raw)
        return _flatten_import(passages, questions)
    except Exception:
        return []
