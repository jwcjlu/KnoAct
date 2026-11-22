"""练习册 PDF 导入：逐页视觉分析 → 跨页合并题组 → 求答案 → 建题组/小题 → 发布。

设计见 docs/superpowers/specs/2026-11-20-practice-book-import-design.md
"""
import copy
import json
import re

from sqlalchemy import and_, or_

from ..core.source_adapter import QuestionDraft

def split_blanks(answer_text: str, count: int) -> list[str] | None:
    """把答案文本按空位数量切开；数量不匹配返回 None（视为未对齐）。"""
    raw = (answer_text or "").strip()
    if not raw or count <= 0:
        return None
    parts = [p.strip() for p in re.split(r"[,，;；、\s]+", raw) if p.strip()]
    if len(parts) != count:
        return None
    return parts


# OCR 解析出的 kind → 题库 qtype。
# category 由 CATEGORY_OF_QTYPE 派生（core/question_types.py），绝不手填。
QTYPE_OF_KIND: dict[str, str] = {
    "oral": "oral",
    "fill": "fill_blank",
    "vertical": "calculation",
    "step": "calculation",
    "app": "application",
    "other": "oral",
    "equation": "fill_blank",  # 解方程：填 x 的值
    "image": "application",    # 图片题：需看图作答，按应用题走拍照判分
}


def _has_variable(expr: str) -> bool:
    """表达式里是否含未知数（x/y/z/a/b/n 等字母变量）。"""
    return bool(re.search(r"(?<![A-Za-z])[a-zA-Z](?![A-Za-z])", expr or ""))


_FORMULA_RE = re.compile(r"\$([^$]+)\$")


def _strip_answer(question: str, *, is_example: bool = False) -> str:
    """去掉题干里「= 结果」的部分，但绝不破坏 `$...$` 的成对性。

    视觉模型有时会自己把算式算出来写进题干（如 `8.9＋4.5＝13.4`），必须截断，
    否则孩子直接看到答案。规则顺序不可颠倒：

    0. `is_example=True` → 原样返回（示例本来就该显示答案）
    1. 等号左侧含未知数 → 不截断（方程里的常数项属于题目本身）
    2. 只在第一个 `$...$` 内部判断「是否已算出答案」，不对整串做正则
    3. 截断点在公式内 → 重新闭合该公式并补 `____`
    4. 兜底：截断后 `$` 计数为奇数 → 放弃截断（宁可露答案，不要坏标记）
    """
    q = (question or "").strip()
    if not q or is_example:
        return q

    m = _FORMULA_RE.search(q)
    if m is None:
        # 旧格式（无公式外壳）：整串判断
        eq = re.search(r"[=＝]", q)
        if not eq:
            return q
        left = q[: eq.start()]
        if _has_variable(left):
            return q
        right = q[eq.end():].strip()
        if re.match(r"^[-−+]?\d", right):
            return left.rstrip(" =＝") + " ="
        return q

    inner = m.group(1)
    eq = re.search(r"[=＝]", inner)
    if not eq:
        return q
    left = inner[: eq.start()]
    if _has_variable(left):
        return q
    right = inner[eq.end():].strip()
    if not re.match(r"^[-−+]?\d", right):
        return q

    closed = f"${left.rstrip(' =＝')} =$"
    candidate = q[: m.start()] + closed + " ____" + q[m.end():]
    if candidate.count("$") % 2 != 0:
        return q
    return candidate


def _levenshtein(a: str, b: str) -> int:
    """编辑距离（滚动数组）。用于判断相邻页的两段题干是否同一道题。"""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(
                prev[j] + 1,                 # 删除
                cur[j - 1] + 1,              # 插入
                prev[j - 1] + (ca != cb),    # 替换
            ))
        prev = cur
    return prev[-1]


def merge_cross_page_groups(groups: list[dict]) -> list[dict]:
    """全书扫完后统一合并被页面切断的题组。

    合并条件（全部满足才吞下一组）：
    1. 当前组 `continues_next_page` 为真
    2. 下一组 `page_start == 当前组 page_end + 1`（页码紧邻）
    3. `work_mode` 相同
    4. stem 相似（任一为空 → 视为相似；否则子串包含或编辑距离 ≤ 30%）

    合并失败时把 `continues_next_page` 置 False 并标 `incomplete=True`，
    否则下一轮还会误吞。

    **不修改入参**（入口深拷贝），调用方可安全复用原始 groups。
    """
    groups = copy.deepcopy(groups or [])
    merged: list[dict] = []
    i = 0
    while i < len(groups):
        cur = groups[i]
        merged.append(cur)
        # 合并成功后不前进外层游标，继续尝试吞下一组（支持跨 3 页以上）
        while cur.get("continues_next_page") and i + 1 < len(groups):
            nxt = groups[i + 1]
            if (nxt.get("page_start") != cur.get("page_end", 0) + 1
                    or cur.get("work_mode") != nxt.get("work_mode")):
                cur["incomplete"] = True
                cur["continues_next_page"] = False
                break
            a = (cur.get("stem") or "").strip()
            b = (nxt.get("stem") or "").strip()
            same_stem = (
                not a or not b
                or a in b or b in a
                or _levenshtein(a, b) <= max(len(a), len(b)) * 0.3
            )
            if not same_stem:
                cur["incomplete"] = True
                cur["continues_next_page"] = False
                break
            cur["items"].extend(nxt.get("items") or [])
            cur["page_end"] = nxt.get("page_end", cur.get("page_end"))
            cur["continues_next_page"] = bool(nxt.get("continues_next_page"))
            i += 1   # 吞掉 nxt
        i += 1
    return merged


def build_drafts(
    aligned: list[dict],
    *,
    document_id: int,
    blanks_of=None,      # 保留形参兼容旧调用；新流程用 item["blanks"]
) -> list[QuestionDraft]:
    """已对齐的题 → QuestionDraft（供 bank._persist_drafts 落库）。

    `work_mode` 非空时按注册表定 qtype，并按 answer_kind 写 answer_json：
    - `numeric_list` → `{"blanks": [...]}`（发布闸门要求非空）
    - `choice`       → `{"correct_index": n}`
    - 其它           → `{}`

    `work_mode` 为空时走旧的 kind → qtype 映射（兼容既有题库/OCR 链路）。
    """
    from ..core.work_modes import answer_kind_of, legacy_qtype_of

    out: list[QuestionDraft] = []
    for q in aligned:
        mode = (q.get("work_mode") or "").strip()
        if mode:
            qtype = legacy_qtype_of(mode)
            kind = answer_kind_of(mode)
        else:
            qtype = QTYPE_OF_KIND.get((q.get("kind") or "oral").strip(), "oral")
            kind = ""

        d = QuestionDraft(
            qtype=qtype,
            question=_strip_answer(q.get("question") or "",
                                   is_example=bool(q.get("is_example"))),
            # 示例行的答案来自页面印好的 answer_hint
            answer=(q.get("answer") or q.get("answer_hint") or "").strip(),
            analysis=q.get("analysis") or "",
        )
        d.lesson_no = q.get("lesson_no")
        d.lesson_title = q.get("lesson_title") or ""
        d.question_no = str(q.get("question_no") or "")
        d.source_document_id = document_id
        d.tags = {"source": "practice_pdf", "page": q.get("page") or 0}

        # 题组两级：小题挂到组下；示例行不入待做
        d.group_id = q.get("group_id")
        d.seq_in_group = int(q.get("seq_in_group") or 0)
        d.is_example = bool(q.get("is_example"))
        d.work_mode = mode

        if q.get("image_path"):
            d.image_path = q["image_path"]
            d.tags["image_path"] = q["image_path"]

        # answer_json：发布闸门与判分都依赖它
        blanks = [str(x).strip() for x in (q.get("blanks") or []) if str(x).strip()]
        if kind == "numeric_list":
            if not blanks and d.answer:
                # 单空「找规律」题：solver 常按 number 返回单值、不带 blanks。
                # 没有这一层兜底，该题会既过不了发布闸门、又不进「待补答案」
                # （待补清单只查 answer == ""），结果静默消失。
                blanks = [d.answer]
            if blanks:
                d.answer_json = {"blanks": blanks}
        elif kind == "choice":
            idx = q.get("correct_index")
            if idx is not None:
                d.answer_json = {"correct_index": int(idx)}
        elif not mode:
            # 旧路径（题库/OCR 链路，items 没有 work_mode）：
            # fill_blank 按空数切答案；切不出 blanks 就降级成 oral——
            # 否则该题既没有 blanks 又保持 fill_blank，会被发布闸门永久挡住。
            if qtype in ("fill_blank", "cloze"):
                n = int((blanks_of(q) if blanks_of else 0)
                        or q.get("blanks_count") or 0)
                old_blanks = split_blanks(d.answer, n) if n else None
                if old_blanks:
                    d.answer_json = {"blanks": old_blanks}
                else:
                    d.qtype = "oral"

        out.append(d)
    return out


def _is_aligned_legacy(q) -> bool:
    """旧题（work_mode 为空）的发布判定，保持原行为不变。

    存量题库的 cloze/fill_blank 依赖 blanks 校验；若一律走新的 answer_kind 分支，
    会因不再检查 blanks 而被误发布。
    """
    if q.qtype in ("fill_blank", "cloze"):
        try:
            data = json.loads(q.answer_json or "{}")
        except (ValueError, TypeError):
            return False
        return bool(data.get("blanks"))
    return True


def _is_aligned(q) -> bool:
    """已对齐 = 有答案。多空题型还要求逐空答案非空。

    `work_mode` 为空的旧题走 `_is_aligned_legacy()`，行为完全不变。
    """
    from ..core.work_modes import answer_kind_of

    if not (q.answer or "").strip():
        return False
    mode = (getattr(q, "work_mode", "") or "").strip()
    if not mode:
        return _is_aligned_legacy(q)

    kind = answer_kind_of(mode)
    if kind == "numeric_list":
        try:
            data = json.loads(q.answer_json or "{}")
        except (ValueError, TypeError):
            return False
        return bool(data.get("blanks"))
    if kind == "choice":
        try:
            data = json.loads(q.answer_json or "{}")
        except (ValueError, TypeError):
            return False
        return data.get("correct_index") is not None
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


def _kind_of(work_mode: str) -> str:
    """work_mode → build_drafts 的 kind 参数。

    ⚠️ 实际已不参与 qtype 决策：`build_drafts` 在 `work_mode` 非空时直接用
    `legacy_qtype_of(mode)`，`kind` 只被 `work_mode` 为空的旧路径读取。
    保留它只为让 item dict 结构稳定（旧路径/调试时还能看到 kind）。
    """
    return {
        "oral": "oral", "equation": "equation", "pattern": "fill",
        "letter_pattern": "fill", "compare": "fill", "unit_compare": "fill",
        "vertical": "vertical", "step": "step", "fill_vertical": "vertical",
        "geometry": "image", "app": "app", "choice": "other", "judge": "other",
        "other": "other",
    }.get(work_mode, "other")


def _groups_from_pages(page_results: list[tuple[int, dict]]) -> list[dict]:
    """把各页分析结果展开成待合并的题组列表（带 page_start/page_end/key）。"""
    groups: list[dict] = []
    for pno, result in page_results:
        if result.get("page_type") != "practice":
            continue
        for idx, g in enumerate(result.get("groups") or []):
            items = [{**it, "page": pno} for it in (g.get("items") or [])]
            groups.append({
                "key": f"{pno}-{idx:02d}",     # 两位补零，字符串排序也正确
                "page_start": pno,
                "page_end": pno,
                "stem": g.get("stem") or "",
                "instruction": g.get("instruction") or "",
                "lesson_no": g.get("lesson_no"),
                "lesson_title": g.get("lesson_title") or "",
                "work_mode": g.get("work_mode") or "other",
                "need_process": bool(g.get("need_process")),
                "continues_next_page": bool(g.get("continues_next_page")),
                "incomplete": False,
                "items": items,
            })
    return groups


def _image_group(pno: int, info: dict, pdf_path: str) -> dict | None:
    """裁出图片题的图，返回一个自成一组、items 只有 1 条的题组。"""
    from .practice_image import crop_question_image

    out = (
        f"uploads/practice_images/p{pno}_"
        f"{int(info['start'] * 100)}_{int(info['end'] * 100)}.png"
    )
    saved = crop_question_image(pdf_path, pno - 1, info["start"], info["end"], out)
    if not saved:
        return None
    title = info.get("title") or f"第{pno}页 图形题"
    return {
        "key": f"{pno}-img",
        "page_start": pno,
        "page_end": pno,
        "stem": title,
        "instruction": "",
        "lesson_no": None,
        "lesson_title": "",
        "work_mode": "geometry",
        "need_process": True,
        "continues_next_page": False,
        "incomplete": False,
        "items": [{
            "seq": 1, "y": info["start"], "text": title,
            "answer_hint": "", "is_example": False,
            "page": pno, "image_path": saved,
        }],
    }


def _read_upload(path: str) -> bytes:
    import os

    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return b""


def _extract_answer(raw: str) -> str:
    """从视觉模型的 JSON 里取 answer。"""
    try:
        data = json.loads(raw or "{}")
    except (ValueError, TypeError):
        m = re.search(r"\{[\s\S]*\}", raw or "")
        if not m:
            return ""
        try:
            data = json.loads(m.group(0))
        except (ValueError, TypeError):
            return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get("answer") or "").strip()


def _solve_groups(db, groups: list[dict], *, on_progress=None) -> None:
    """按组求答案，结果写回 it["answer"] / it["blanks"] / it["correct_index"]。

    示例行跳过（页面已印答案，用它自己的 answer_hint）。
    图片题（有 image_path）走视觉求答案；纯文本题走 solve_math_items。
    """
    from .ai import vision_json
    from .practice_solve import solve_math_items

    # 1) 文本题：按 answer_kind 分流
    solve_items: list[dict] = []
    solve_refs: list[dict] = []
    choice_refs: list[dict] = []
    for g in groups:
        for it in g["items"]:
            if it.get("is_example") or it.get("image_path"):
                continue
            # 示例行以外的题才求解
            if g["work_mode"] in ("choice", "judge"):
                choice_refs.append(it)
                continue
            solve_items.append({
                "question": it.get("text") or "",
                "work_mode": g["work_mode"],
            })
            solve_refs.append(it)

    # 2) 选择题：单独问「正确选项是哪个」
    for it in choice_refs:
        it["correct_index"] = _solve_choice(db, it.get("text") or "")
        if it["correct_index"] is not None:
            it["answer"] = _LETTERS[it["correct_index"]] if (
                it["correct_index"] < len(_LETTERS)) else ""

    solved = solve_math_items(db, solve_items, on_progress=on_progress) if solve_items else {}
    for idx, payload in solved.items():
        if 0 <= idx < len(solve_refs):
            ref = solve_refs[idx]
            ref["answer"] = payload.get("answer") or ""
            ref["blanks"] = payload.get("blanks") or []

    # 3) 图片题：把裁出的 PNG 送视觉模型算答案
    for g in groups:
        for it in g["items"]:
            if not it.get("image_path") or it.get("is_example"):
                continue
            if (it.get("answer") or "").strip():
                continue
            try:
                raw = vision_json(
                    db,
                    _read_upload(it["image_path"]),
                    system="你是小学数学老师。看图片里的题目，只输出 JSON："
                           '{"answer":"最终结果数字"}。算不出就输出 {"answer":""}。',
                    prompt="算出这道题的最终答案。",
                )
                it["answer"] = _extract_answer(raw)
            except Exception:
                it["answer"] = ""     # 进「待补答案」由家长填


_LETTERS = "ABCD"


def _solve_choice(db, question: str) -> int | None:
    """让模型选出正确选项（0 起）。失败返回 None（该题进待补，不瞎猜）。"""
    if not question.strip():
        return None
    try:
        from .ai import get_provider

        provider = get_provider(db)
        if provider.name == "fake":
            return None
        raw = provider.generate(
            prompt=(
                "下面是一道选择题，请判断正确选项。只输出 JSON："
                '{"correct":"A"}，correct 只能是 A/B/C/D。\n\n' + question
            ),
            system="你是小学数学老师，负责判断选择题的正确选项。只输出 JSON。",
            json_mode=True,
        )
        data = json.loads(raw or "{}")
        letter = str(data.get("correct") or "").strip().upper()
        return _LETTERS.index(letter) if letter in _LETTERS else None
    except Exception:
        return None


def _record_page(db, document_id: int, page_no: int, page_type: str,
                 raw_text: str, group_count: int, status: str) -> None:
    """落一行页记录（唯一约束 document_id+page_no，用 upsert 语义）。"""
    from ..models import PracticeImportPage

    row = (db.query(PracticeImportPage)
           .filter_by(document_id=document_id, page_no=page_no).first())
    if row is None:
        row = PracticeImportPage(document_id=document_id, page_no=page_no)
        db.add(row)
    row.page_type = page_type
    row.raw_text = raw_text[:60000]
    row.group_count = group_count
    row.status = status
    db.commit()


def _tick(job_id: int, done: int, total: int, items: int) -> None:
    """独立 session 刷进度（长分析期间主 session 缓存会过期）。"""
    from ..database import SessionLocal as _SL
    from ..models import PracticeImportJob as _Job

    s2 = _SL()
    try:
        j2 = s2.get(_Job, job_id)
        if j2 is not None:
            j2.done_pages = min(done, total)
            j2.question_count = items
            s2.commit()
    except Exception:
        s2.rollback()
    finally:
        s2.close()


def _set_counts(job_id: int, *, aligned: int, questions: int) -> None:
    from ..database import SessionLocal as _SL
    from ..models import PracticeImportJob as _Job

    s2 = _SL()
    try:
        j2 = s2.get(_Job, job_id)
        if j2 is not None:
            j2.aligned_count = aligned
            j2.question_count = questions
            s2.commit()
    except Exception:
        s2.rollback()
    finally:
        s2.close()


def run_import_job(job_id: int, retry_pages: list[int] | None = None) -> None:
    """后台执行导入：逐页视觉分析 → 跨页合并 → 求答案 → 建题组 → 挂小题 → 发布。

    `retry_pages` 非空时只重跑这些页（会先删掉这些页对应的旧题组与小题）。
    """
    from ..database import SessionLocal
    from ..models import (
        PdfDocument, PracticeImportJob, PracticeImportPage,
        PracticeQuestionGroup, Question, QuestionBank,
    )
    from ..routers.bank import _persist_drafts
    from .parsers.math_page import analyze_page
    from .practice_image import render_page_png

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
        job.aligned_count = 0
        job.question_count = 0
        job.published_count = 0
        db.commit()

        from ..routers.practice_import import _derive_page_range

        q_start, q_end = _derive_page_range(
            question_start_page=job.question_start_page,
            question_end_page=job.question_end_page,
            answer_start_page=job.answer_start_page,
            answer_end_page=job.answer_end_page,
            total_pages=job.total_pages or 1,
        )
        pages = list(range(q_start, q_end + 1))
        if retry_pages:
            wanted = set(retry_pages)
            picked_pages = [p for p in pages if p in wanted]
            if picked_pages:
                pages = picked_pages

        # 重跑：先删这些页对应的题组与小题（group_id 无外键，必须显式删）
        # 用「重跑页集合」逐个取交集，绝不能用 min/max 包络区间——
        # 第 3 页和第 40 页失败时，包络会连带删掉 4..39 页的题。
        # 命中的组若跨到未重跑的页，就把整段页纳入重跑范围，保证「整组重建」
        # 而不是删掉一半（否则未重跑页的 items 会永久丢失）。
        if retry_pages:
            def _overlaps(p: set[int]):
                return or_(*[
                    and_(PracticeQuestionGroup.page_start <= pno,
                         PracticeQuestionGroup.page_end >= pno)
                    for pno in sorted(p)
                ])

            wanted = set(pages)
            old = (db.query(PracticeQuestionGroup)
                   .filter(PracticeQuestionGroup.bank_id == bank.id,
                           _overlaps(wanted))
                   .all())
            # 组跨到未重跑页 → 这些页也一起重建，避免只删一半
            for g in old:
                wanted.update(range(g.page_start, g.page_end + 1))
            old = [g for g in
                   (db.query(PracticeQuestionGroup)
                    .filter(PracticeQuestionGroup.bank_id == bank.id,
                            _overlaps(wanted))
                    .all())]
            pages = sorted(wanted)
            gids = [g.id for g in old]
            if gids:
                db.query(Question).filter(
                    Question.group_id.in_(gids)).delete(synchronize_session=False)
                db.query(PracticeQuestionGroup).filter(
                    PracticeQuestionGroup.id.in_(gids)).delete(
                    synchronize_session=False)
            db.query(PracticeImportPage).filter(
                PracticeImportPage.document_id == doc.id,
                PracticeImportPage.page_no.in_(pages),
            ).delete(synchronize_session=False)
            db.commit()

        # 逐页分析
        page_results: list[tuple[int, dict]] = []
        failed_pages: list[int] = []
        image_groups: list[dict] = []
        seen_items = 0
        for idx, pno in enumerate(pages, start=1):
            img = render_page_png(doc.storage_path, pno - 1, dpi=150)
            if not img:
                failed_pages.append(pno)
                _record_page(db, doc.id, pno, "practice", "", 0, "failed")
                _tick(job_id, idx, len(pages), seen_items)
                continue
            try:
                result = analyze_page(db, img, subject=bank.subject or "数学")
            except Exception:
                failed_pages.append(pno)
                _record_page(db, doc.id, pno, "practice", "", 0, "failed")
                _tick(job_id, idx, len(pages), seen_items)
                continue

            # 模型返回的不是可用 JSON：记为该页失败，不能伪装成「空白练习页」
            # （否则 job 会标 done、0 题、还不可重试）
            if result.get("parse_failed"):
                failed_pages.append(pno)
                _record_page(db, doc.id, pno, "practice", "", 0, "failed")
                _tick(job_id, idx, len(pages), seen_items)
                continue

            page_results.append((pno, result))
            _record_page(
                db, doc.id, pno, result.get("page_type") or "practice",
                json.dumps(result, ensure_ascii=False),
                len(result.get("groups") or []), "ok",
            )
            for info in result.get("image_questions") or []:
                g = _image_group(pno, info, doc.storage_path)
                if g:
                    image_groups.append(g)
            seen_items += sum(len(g.get("items") or [])
                              for g in (result.get("groups") or []))
            _tick(job_id, idx, len(pages), seen_items)

        # 跨页合并（图片题自成一组，不参与合并）
        groups = _groups_from_pages(page_results)
        groups = merge_cross_page_groups(groups) + image_groups
        groups.sort(key=lambda g: (g["page_start"], g["key"]))

        # 全书一道题都没识别出来 → 明确失败，别让家长看到「导入 0 题」却以为成功
        if not groups:
            job.failed_pages = json.dumps(sorted(failed_pages or pages))
            job.status = "failed"
            job.error = "未识别到任何题目，请检查 PDF 是否为练习册或点击重试"
            db.commit()
            return

        job.status = "aligning"
        job.question_count = sum(len(g["items"]) for g in groups)
        db.commit()

        _solve_groups(
            db, groups,
            on_progress=lambda done, total: _set_counts(
                job_id, aligned=done, questions=total),
        )
        job.aligned_count = sum(
            1 for g in groups for it in g["items"] if (it.get("answer") or "").strip()
        )
        db.commit()

        # 题组先建，小题后挂
        all_drafts = []
        for g in groups:
            row = PracticeQuestionGroup(
                bank_id=bank.id, user_id=bank.user_id,
                lesson_no=g.get("lesson_no"),
                lesson_title=g.get("lesson_title") or "",
                stem=g.get("stem") or "",
                instruction=g.get("instruction") or "",
                work_mode=g.get("work_mode") or "other",
                need_process=bool(g.get("need_process")),
                page_start=g["page_start"], page_end=g["page_end"],
                source_document_id=job.document_id,
                incomplete=bool(g.get("incomplete")),
            )
            db.add(row)
            db.flush()

            items = []
            for seq, it in enumerate(g["items"], start=1):
                # 示例行的答案来自页面印好的 answer_hint（AI 不重算）
                answer = (it.get("answer") or it.get("answer_hint") or "").strip()
                items.append({
                    "kind": _kind_of(g["work_mode"]),
                    "question": it.get("text") or "",
                    "answer": answer,
                    "blanks": it.get("blanks") or [],
                    "correct_index": it.get("correct_index"),
                    "seq_in_group": seq,
                    "is_example": bool(it.get("is_example")),
                    "work_mode": g.get("work_mode") or "other",
                    "lesson_no": g.get("lesson_no") or g["page_start"],
                    "lesson_title": g.get("lesson_title") or "",
                    "image_path": it.get("image_path") or "",
                    "page": g["page_start"],
                    "group_id": row.id,
                })
            all_drafts.extend(build_drafts(items, document_id=job.document_id))
        db.commit()

        _persist_drafts(db, bank, all_drafts, "practice_pdf")
        bank.source = "practice_pdf"     # _persist_drafts 会把 manual 改成 third_party
        db.commit()

        # 示例行也发布：前端要读它来展示「印好的示例」，但不进每日一练
        # （task_gen._pick_practice_questions 过滤 is_example == False）
        db.query(Question).filter(
            Question.bank_id == bank.id, Question.is_example.is_(True)
        ).update({"status": "published"}, synchronize_session=False)
        job.published_count = publish_aligned(db, bank.id)
        db.commit()

        job.failed_pages = json.dumps(sorted(failed_pages))
        job.done_pages = max(0, len(pages) - len(failed_pages))
        job.status = "failed" if failed_pages else "done"
        job.error = f"{len(failed_pages)} 页识别失败，可重试" if failed_pages else ""
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
