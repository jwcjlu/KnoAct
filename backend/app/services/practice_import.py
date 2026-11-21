"""练习册 PDF 导入：课时/题号解析、答案对齐、后台任务编排。

设计见 docs/superpowers/specs/2026-11-20-practice-book-import-design.md
"""
import json
import re

# 「第3课时 小数乘小数」/「第 12 课时 练习课」
_LESSON_RE = re.compile(r"第\s*(\d+)\s*课时\s*([^\n]*)")

# 题号只在「行首」或「行内空白之后」才算，且数字后不能紧跟数字，
# 否则 8.9 / 3.25 这类小数会被当成题号。
_ITEM_RE = re.compile(
    r"(?:(?<=^)|(?<=[\s\u3000]))"
    r"(?:\((\d{1,2})\)|（(\d{1,2})）|(\d{1,2})[.、．](?!\d))"
)


def parse_lesson_page(text: str) -> dict:
    """从一页 OCR 文本解析课时号、标题与题目列表。

    返回 {"lesson_no": int|None, "lesson_title": str, "items": [{"question_no","question"}]}
    没识别到课时标题时 items 为空（由调用方记失败页）。
    """
    text = (text or "").replace("\r", "")
    m = _LESSON_RE.search(text)
    if not m:
        return {"lesson_no": None, "lesson_title": "", "items": []}

    lesson_no = int(m.group(1))
    lesson_title = (m.group(2) or "").strip().split("\n")[0].strip()
    body = text[m.end():]

    items: list[dict] = []
    marks = list(_ITEM_RE.finditer(body))
    for i, mk in enumerate(marks):
        num = mk.group(1) or mk.group(2) or mk.group(3)
        start = mk.end()
        end = marks[i + 1].start() if i + 1 < len(marks) else len(body)
        stem = body[start:end].strip()
        if not stem:
            continue
        items.append({"question_no": str(num), "question": stem})
    return {"lesson_no": lesson_no, "lesson_title": lesson_title, "items": items}


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
    """按 (lesson_no, question_no) 对齐。返回 (已对齐, 未对齐)。

    已对齐的题补上 answer / analysis；未对齐的原样返回（answer 留空）。
    """
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

from ..core.source_adapter import QuestionDraft

# OCR 解析出的 kind → 题库 qtype。
# category 由 CATEGORY_OF_QTYPE 派生（core/question_types.py），绝不手填。
QTYPE_OF_KIND: dict[str, str] = {
    "oral": "oral",
    "fill": "fill_blank",
    "vertical": "calculation",
    "step": "calculation",
    "app": "application",
}


def build_drafts(
    aligned: list[dict],
    *,
    document_id: int,
    blanks_of=lambda q: 0,
) -> list[QuestionDraft]:
    """已对齐的题 → QuestionDraft（供 bank._persist_drafts 落库）。

    blanks_of(q) 返回该题空位数（fill 类用）；数量与答案切分不符时降级为 oral。
    """
    out: list[QuestionDraft] = []
    for q in aligned:
        kind = (q.get("kind") or "oral").strip()
        qtype = QTYPE_OF_KIND.get(kind, "oral")
        d = QuestionDraft(
            qtype=qtype,
            question=q.get("question") or "",
            answer=(q.get("answer") or "").strip(),
            analysis=q.get("analysis") or "",
        )
        d.lesson_no = q.get("lesson_no")
        d.lesson_title = q.get("lesson_title") or ""
        d.question_no = str(q.get("question_no") or "")
        d.source_document_id = document_id
        d.tags = {"source": "practice_pdf", "page": q.get("page") or 0}

        if qtype == "fill_blank":
            n = int(blanks_of(q) or 0)
            blanks = split_blanks(d.answer, n) if n else None
            if blanks:
                d.answer_json = {"blanks": blanks}
            else:
                d.qtype = "oral"
        out.append(d)
    return out
