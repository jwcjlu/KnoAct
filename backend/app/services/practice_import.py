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

def _is_aligned(q) -> bool:
    """已对齐 = 有答案；fill_blank/cloze 还要求 blanks 非空。"""
    if not (q.answer or "").strip():
        return False
    if q.qtype in ("fill_blank", "cloze"):
        try:
            data = json.loads(q.answer_json or "{}")
        except (ValueError, TypeError):
            return False
        return bool(data.get("blanks"))
    return True


def publish_aligned(db, bank_id: int) -> int:
    """把该卷里「已对齐答案」且仍 pending 的题置 published，返回条数。"""
    from ..models import Question

    rows = (
        db.query(Question)
        .filter(Question.bank_id == bank_id, Question.status == "pending")
        .all()
    )
    ids = [q.id for q in rows if _is_aligned(q)]
    if not ids:
        return 0
    db.query(Question).filter(Question.id.in_(ids)).update(
        {"status": "published"}, synchronize_session=False
    )
    return len(ids)

_OCR_INSTRUCTION = (
    "识别这一页练习册的全部文字，保留「第N课时 标题」与题号（1. 2. (1)），"
    "题目与答案都要原样输出，不要解释、不要省略。"
)


def _ocr_text(pdf_path: str, page_index: int, db) -> str:
    """OCR 单页。不用 pdf_split._ocr_page（它会缓存失败结果，导致 retry 无效）。"""
    from .ai import ocr_image
    from .pdf_split import _render_page_png

    try:
        png = _render_page_png(pdf_path, page_index, dpi=150)
    except Exception:
        return ""
    try:
        return (ocr_image(db, png, instruction=_OCR_INSTRUCTION) or "").strip()
    except Exception:
        return ""


def _parse_pages(db, pdf_path: str, pages: list[int]) -> tuple[list[dict], list[int]]:
    """OCR 并解析指定页码（1-based）。返回 (items, 失败页列表)。

    注意：答案页解析出的「题干」其实是答案文本，需经 `_answers_of()` 转换。
    """
    items: list[dict] = []
    failed: list[int] = []
    for pno in pages:
        text = _ocr_text(pdf_path, pno - 1, db)
        parsed = parse_lesson_page(text)
        if not parsed["items"]:
            failed.append(pno)
            continue
        for it in parsed["items"]:
            items.append({
                **it,
                "lesson_no": parsed["lesson_no"],
                "lesson_title": parsed["lesson_title"],
                "page": pno,
            })
    return items, failed


def run_import_job(job_id: int, retry_pages: list[int] | None = None) -> None:
    """后台执行导入。retry_pages 非空时只重跑这些页。

    新开 Session：BackgroundTasks 执行时请求级 session 已失效。
    """
    from ..database import SessionLocal
    from ..models import PdfDocument, PracticeImportJob, QuestionBank
    from ..routers.bank import _persist_drafts

    db = SessionLocal()
    try:
        job = db.get(PracticeImportJob, job_id)
        if job is None:
            return
        doc = db.get(PdfDocument, job.document_id)
        bank = db.get(QuestionBank, job.bank_id)
        if doc is None or bank is None:
            job.status = "failed"
            job.error = "文档或题库卷不存在"
            db.commit()
            return

        job.status = "ocr"
        db.commit()

        q_start = job.question_start_page or 1
        q_end = job.question_end_page or (job.answer_start_page or 1) - 1
        a_start = job.answer_start_page or 1
        a_end = job.answer_end_page or a_start

        if retry_pages:
            q_pages = [p for p in retry_pages if q_start <= p <= q_end]
            a_pages = [p for p in retry_pages if a_start <= p <= a_end]
            q_items, q_failed = _parse_pages(db, doc.storage_path, q_pages)
            a_items, a_failed = _parse_pages(db, doc.storage_path, a_pages)
        else:
            q_items, q_failed = _parse_pages(
                db, doc.storage_path, list(range(q_start, q_end + 1)))
            a_items, a_failed = _parse_pages(
                db, doc.storage_path, list(range(a_start, a_end + 1)))

        job.status = "aligning"
        job.question_count = len(q_items)
        db.commit()

        aligned, _missing = align_answers(q_items, _answers_of(a_items))
        job.aligned_count = len(aligned)

        drafts = build_drafts(aligned, document_id=job.document_id)
        _persist_drafts(db, bank, drafts, "practice_pdf")
        # 必须在 persist 之后设置：_persist_drafts 会把 manual 改成 third_party
        bank.source = "practice_pdf"
        db.commit()

        job.published_count = publish_aligned(db, bank.id)

        failed = sorted(q_failed + a_failed)
        job.failed_pages = json.dumps(failed)
        total = (q_end - q_start + 1) + (a_end - a_start + 1)
        job.done_pages = max(0, total - len(failed))
        job.status = "failed" if failed else "done"
        job.error = f"{len(failed)} 页识别失败，可重试" if failed else ""
        db.commit()
    except Exception as exc:  # noqa: BLE001
        try:
            job = db.get(PracticeImportJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error = str(exc)[:480]
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _answers_of(answer_items: list[dict]) -> list[dict]:
    """答案页解析出的 items 里，`question` 字段实为答案文本，转成对齐用的答案结构。

    若 OCR 输出里答案已带「= 结果」形式，取等号右侧。
    """
    out: list[dict] = []
    for it in answer_items:
        raw = (it.get("question") or "").strip()
        if "=" in raw or "＝" in raw:
            raw = re.split(r"[=＝]", raw)[-1].strip()
        if not raw:
            continue
        out.append({
            "lesson_no": it.get("lesson_no"),
            "question_no": it.get("question_no"),
            "answer": raw,
            "analysis": it.get("analysis", ""),
        })
    return out
