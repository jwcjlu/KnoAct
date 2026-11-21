"""练习册 PDF 导入：课时/题号解析、答案对齐、后台任务编排。

设计见 docs/superpowers/specs/2026-11-20-practice-book-import-design.md

这本练习册（计算小达人 RJ 五上）的结构是：
    第 3 课时 练习课
    1. 直接写出得数。（建议 2 分钟完成）
    8.9 + 4.5 =
    1000 - 550 =
    2. 计算下面各题，能简算的要简算。
    (72 ÷ 18 + 8) × 28
所以「1. / 2.」是大题号（= 题型分组），真正的题目是它们下面的每一行算式。
"""
import json
import re

# 「第3课时 小数乘小数」/「第 12 课时 练习课」
_LESSON_RE = re.compile(r"第\s*(\d+)\s*课时\s*([^\n]*)")

# 大题号：行首「1.」「1、」「(1)」，后面常跟一句说明。
# 注意「8.9 + 4.5 =」这种小数开头的算式不能当大题号 → 要求点号后不接数字，
# 且不能以等号/运算符结尾。
_SECTION_RE = re.compile(
    r"^\s*(?:\((\d{1,2})\)|（(\d{1,2})）|(\d{1,2})[.、．](?!\d))\s*(.*)$"
)

# 一行里必须有运算符或等号才算「一道算式题」
_MATH_RE = re.compile(r"[+\-−×÷*/=＝]")

# 明显不是题目的页眉页脚噪音
_NOISE_RE = re.compile(
    r"^(视频讲解|智能批改|月\s*日|RJ\s|第\s*\d+\s*页|扫码|参考答案)"
)


def _section_kind(hint: str) -> str:
    """由大题提示语推断题型：口算 / 竖式 / 脱式 / 应用。"""
    h = hint or ""
    if "直接写出得数" in h or "口算" in h:
        return "oral"
    if "竖式" in h:
        return "vertical"
    if "简算" in h or "计算下面各题" in h or "脱式" in h:
        return "step"
    if "解决问题" in h or "应用题" in h:
        return "app"
    return "other"


def _is_problem_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 3:
        return False
    if _NOISE_RE.match(s):
        return False
    if not _MATH_RE.search(s):
        return False
    # 纯中文说明行（如「巧算。」）不算题目
    if not re.search(r"\d", s):
        return False
    return True


def _split_row(line: str) -> list[str]:
    """同一横向行里的多道题按制表符/连续全角空格切开。

    OCR 常把「8.9+4.5=    1000-550=    3.32+2.74=」识别成一行。
    """
    parts = re.split(r"\t+|\u3000{2,}|\s{4,}", line.strip())
    return [p.strip() for p in parts if p.strip()]


def parse_lesson_page(text: str, *, lenient: bool = False) -> dict:
    """从一页 OCR 文本解析课时号、标题与题目列表。

    返回 {"lesson_no": int|None, "lesson_title": str,
          "items": [{"question_no", "question", "kind"}]}

    切分规则：大题号（1. / 2.）只作分组并推断题型，每个算式行是一道题，
    题号在该大题内从 1 递增。
    """
    text = (text or "").replace("\r", "")
    m = _LESSON_RE.search(text)
    if not m:
        return {"lesson_no": None, "lesson_title": "", "items": []}

    lesson_no = int(m.group(1))
    lesson_title = (m.group(2) or "").strip().split("\n")[0].strip()
    body = text[m.end():]

    items: list[dict] = []
    cur_kind = "other"
    seq = 0

    for raw_line in body.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        sec = _SECTION_RE.match(line)
        if sec:
            hint = sec.group(4) or ""
            # 答案页：题号后面就是答案，不是大题说明
            if lenient:
                if hint and not _NOISE_RE.match(hint):
                    seq += 1
                    items.append({
                        "question_no": str(seq),
                        "question": hint,
                        "kind": cur_kind,
                    })
                continue
            # 大题行若本身带运算符/等号，说明它其实是道算式题
            if _MATH_RE.search(hint):
                if _is_problem_line(hint):
                    seq += 1
                    items.append({
                        "question_no": str(seq),
                        "question": hint,
                        "kind": cur_kind,
                    })
                continue
            cur_kind = _section_kind(hint)
            continue

        if lenient:
            # 答案页：没题号的裸行也是答案（与上一题同序追加不行，跳过避免错位）
            continue

        if not _is_problem_line(line):
            continue

        # 一行多题时逐个拆开
        for piece in _split_row(line):
            if not _is_problem_line(piece):
                continue
            seq += 1
            items.append({
                "question_no": str(seq),
                "question": _strip_answer(piece),
                "kind": cur_kind,
            })

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
    """按 (lesson_no, question_no) 对齐。返回 (已对齐, 未对齐)。"""
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
    "other": "oral",
}


def _strip_answer(question: str) -> str:
    """去掉题干里的「= 答案」部分。

    视觉模型有时会自己把算式算出来写进题干（如 `8.9＋4.5＝13.4`），
    必须截断在等号，否则孩子会直接看到答案。
    """
    q = (question or "").strip()
    if not q:
        return ""
    # 只在等号后跟数字/小数时截断，避免误伤「1+1=？」这类
    m = re.search(r"[=＝]\s*[-−]?\d", q)
    if m:
        return q[: m.start()].rstrip(" =＝") + " ="
    return q


def build_drafts(
    aligned: list[dict],
    *,
    document_id: int,
    blanks_of=lambda q: 0,
) -> list[QuestionDraft]:
    """已对齐的题 → QuestionDraft（供 bank._persist_drafts 落库）。"""
    out: list[QuestionDraft] = []
    for q in aligned:
        kind = (q.get("kind") or "oral").strip()
        qtype = QTYPE_OF_KIND.get(kind, "oral")
        d = QuestionDraft(
            qtype=qtype,
            question=_strip_answer(q.get("question") or ""),
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
    "识别这一页练习册的文字，保留「第N课时 标题」与题号（1. 2. (1)）。\n"
    "**重要：绝对不要计算、不要填写答案。** 题干原样输出，遇到「＝」或「=」就到此为止，"
    "等号后面不要写任何数字。\n"
    "同一行有多道题时（横向排列），用制表符分隔，每道题单独成段。\n"
    "不要解释、不要省略。"
)

_ANSWER_OCR_INSTRUCTION = (
    "这是练习册的答案页。只按「题号 答案」的形式逐行输出，例如："
    "1. 13.4 / 2. 450。保留题号，不要输出题目原文、不要解释。"
)


def _ocr_text(pdf_path: str, page_index: int, db, *, is_answer: bool = False) -> str:
    """OCR 单页。不用 pdf_split._ocr_page（它会缓存失败结果，导致 retry 无效）。"""
    from .ai import ocr_image
    from .pdf_split import _render_page_png

    try:
        png = _render_page_png(pdf_path, page_index, dpi=150)
    except Exception:
        return ""
    instruction = _ANSWER_OCR_INSTRUCTION if is_answer else _OCR_INSTRUCTION
    try:
        return (ocr_image(db, png, instruction=instruction) or "").strip()
    except Exception:
        return ""


def _parse_pages(
    db,
    pdf_path: str,
    pages: list[int],
    *,
    is_answer: bool = False,
) -> tuple[list[dict], list[int]]:
    """OCR 并解析指定页码（1-based）。返回 (items, 失败页列表)。

    答案页解析出的「题干」其实是答案文本，需经 `_answers_of()` 转换；
    答案页用宽松解析（纯数字答案行也算一道题）。
    """
    items: list[dict] = []
    failed: list[int] = []
    for pno in pages:
        text = _ocr_text(pdf_path, pno - 1, db, is_answer=is_answer)
        parsed = parse_lesson_page(text, lenient=is_answer)
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


def _answers_of(answer_items: list[dict]) -> list[dict]:
    """答案页解析出的 items 里，`question` 字段实为答案文本，转成对齐用的结构。"""
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
            a_items, a_failed = _parse_pages(
                db, doc.storage_path, a_pages, is_answer=True)
        else:
            q_items, q_failed = _parse_pages(
                db, doc.storage_path, list(range(q_start, q_end + 1)))
            a_items, a_failed = _parse_pages(
                db, doc.storage_path, list(range(a_start, a_end + 1)), is_answer=True)

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
