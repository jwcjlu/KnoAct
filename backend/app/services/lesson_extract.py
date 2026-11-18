"""从课程页面提取结构化内容：课文文本、生词表、知识点。

提取走 AI provider（DeepSeek/GLM），失败时回退到从 PDF 文本中抽词/抽句，
保证在无 API Key 时仍能得到可用的结构（生词按行切分，课文取首段）。
"""
import re

from sqlalchemy.orm import Session

from .ai import get_provider
from .pdf_split import (
    SUBJECT_RULES,
    WORD_LIST_OCR_PROMPT,
    _detect_word_list,
    _is_scanned,
    _ocr_page,
    _page_continues_word_list,
    _page_text,
    is_word_list_title,
    split_gloss_line,
)


def _lesson_texts(pdf_path: str, start_page: int, end_page: int, db=None) -> str:
    """抽取一课页码范围的文本。文本型直接读；扫描版逐页 OCR（db 提供时）。"""
    texts = _page_text(pdf_path)
    if not texts:
        return ""
    if _is_scanned(texts) and db is not None:
        parts = []
        for i in range(start_page - 1, min(end_page, len(texts))):
            t = _ocr_page(pdf_path, i, db, "识别图片中的全部文字，原样输出，不要解释。")
            if t:
                parts.append(t)
        return "\n".join(parts)
    return "\n".join(texts[start_page - 1:end_page])


def _extract_words_fallback(pdf_path: str, start_page: int, end_page: int, subject: str, db=None) -> list[dict]:
    """无 AI 时兜底：从页面文本中按「生词表/单词表」标记后的行提取词条。"""
    block = _lesson_texts(pdf_path, start_page, end_page, db)
    if not block:
        return []
    words = []
    for line in block.splitlines():
        line = line.strip()
        if not line or len(line) > 40:
            continue
        # 跳过纯数字页码、标题锚点
        if re.fullmatch(r"[\d\s.]+", line):
            continue
        # 简单词条：形如 "词 拼音 释义" 或 "word /pron/ n. 释义"
        first = line.split()[0].strip("，。：:、, ")
        if 1 < len(first) <= 12 and not re.search(r"[一-鿿]{8,}", line):
            words.append({"word": first, "extra": line[len(first):].strip()})
        if len(words) >= 30:
            break
    return words


def _extract_text_fallback(pdf_path: str, start_page: int, end_page: int, db=None) -> str:
    block = _lesson_texts(pdf_path, start_page, end_page, db).strip()
    if not block:
        return ""
    # 取前几段作为课文正文（截断到 500 字）
    body = re.sub(r"\n{2,}", "\n", block)
    return body[:500]


def extract_lesson_content(pdf_path: str, subject: str, start_page: int, end_page: int, db: Session) -> dict:
    """提取一课的结构化内容。返回 {words: [{word, extra}], points: [str], text: str}。

    AI 可用时让模型按学科规则返回结构化文本；否则走兜底。
    """
    rules = SUBJECT_RULES[subject]
    provider = get_provider(db)
    has_real = provider.name != "fake"

    # 从 PDF 抽取本课真实页面文本，作为提取的上下文（否则 AI 凭空编造，生词/知识点对不上教材）
    page_block = _lesson_texts(pdf_path, start_page, end_page, db)[:3000]

    if has_real:
        pages = f"第 {start_page}–{end_page} 页"
        if rules["has_word_bank"]:
            prompt = (
                f"你正在为一本「{subject}」教材的第 {pages} 拆课。下面是这一课的原文（可能含目录残留、页码、插图文字，请忽略无关内容）。\n"
                f"请严格基于原文提取：\n"
                f"1) 生词/单词表（每行：词|{rules['word_extra']}），只收原文中真实出现的生词\n"
                f"2) 本课知识点（每行一个，来自课文涉及的字词、句式、语法点）\n"
                f"3) 课文正文（原文照抄，最多 300 字）\n"
                f"用三段输出，分别以「生词：」「知识点：」「课文：」开头。\n\n"
                f"原文：\n{page_block}"
            )
        else:
            prompt = (
                f"你正在为一本「{subject}」教材的第 {pages} 拆课。下面是这一课的原文（可能含目录残留、页码，请忽略）。\n"
                f"请严格基于原文提取：\n"
                f"1) 本课知识点（每行一个，含核心概念、公式、例题步骤）\n"
                f"2) 正文内容（原文照抄，最多 300 字）\n"
                f"用两段输出，分别以「知识点：」「课文：」开头。\n\n"
                f"原文：\n{page_block}"
            )
        try:
            raw = provider.generate(prompt=prompt, system="你是教材拆解助手，只输出提取结果，不要解释。")
            parsed = _parse_ai_output(raw, subject)
            if parsed["words"] or parsed["points"] or parsed["text"]:
                return parsed
        except Exception:
            pass  # AI 失败回退兜底

    words = _extract_words_fallback(pdf_path, start_page, end_page, subject, db) if rules["has_word_bank"] else []
    text = _extract_text_fallback(pdf_path, start_page, end_page, db)
    return {"words": words, "points": [], "text": text}


def parse_word_list_text(raw: str) -> dict[int, list[dict]]:
    """把 Word list 的 OCR 文本拆成 {单元号: [{word, extra}, ...]}。

    遇到 Proper nouns 即停（专有名词不是各课生词）。星号词在释义前加 *，表示课标二级词。
    """
    units: dict[int, list[dict]] = {}
    unit = None
    seen: set[tuple[int, str]] = set()
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s or s.startswith("注"):
            continue
        if re.match(r"proper\s+nouns\b", s, re.I):
            break
        if re.match(r"unit\s*\d+\b", s, re.I) and split_gloss_line(s) is None:
            unit = int(re.match(r"unit\s*(\d+)\b", s, re.I).group(1))
            units.setdefault(unit, [])
            continue
        if unit is None:
            continue
        parsed = split_gloss_line(s)
        if not parsed:
            continue
        word, gloss, star = parsed
        key = (unit, re.sub(r"\s+", " ", word).casefold())
        if key in seen:
            continue
        seen.add(key)
        units[unit].append({"word": word, "extra": f"*{gloss}" if star else gloss})
    return {n: rows for n, rows in units.items() if rows}


def extract_word_list_units(pdf_path: str, db) -> dict[int, list[dict]]:
    """OCR 书末 Word list，按 Unit 返回词条。识别不到时返回空 dict。"""
    texts = _page_text(pdf_path)
    if not texts:
        return {}
    found = _detect_word_list(pdf_path, "英语", texts, len(texts), db)
    if not found:
        return {}
    start = found["start_page"] - 1
    chunks: list[str] = []
    for i in range(start, min(len(texts), start + 6)):
        raw = texts[i] or ""
        if not _page_continues_word_list(raw):
            if db is None:
                if chunks:
                    break
                continue
            raw = _ocr_page(pdf_path, i, db, WORD_LIST_OCR_PROMPT)
        if not raw or not _page_continues_word_list(raw):
            if chunks:
                break
            continue
        chunks.append(raw)
        if re.search(r"proper\s+nouns", raw, re.I):
            break
    if not chunks:
        return {}
    return parse_word_list_text("\n".join(chunks))


def _norm_word(word: str) -> str:
    return re.sub(r"\s+", " ", (word or "").strip()).casefold()


def _replace_lesson_words(db: Session, lesson, items: list[dict]) -> None:
    """按词面把新词条写回一课，已有听写记录跟到同名词上。"""
    from ..models import Mistake, WordBank, WordMastery
    from .cleanup import detach_words

    old = db.query(WordBank).filter_by(lesson_id=lesson.id).all()
    old_by_norm: dict[str, list] = {}
    for w in old:
        old_by_norm.setdefault(_norm_word(w.word), []).append(w)
    new_rows = []
    for item in items:
        row = WordBank(lesson_id=lesson.id, subject=lesson.subject or "英语",
                       word=item["word"], extra=item["extra"])
        db.add(row)
        new_rows.append(row)
    db.flush()
    used_old: set[int] = set()
    for item, row in zip(items, new_rows):
        bucket = old_by_norm.get(_norm_word(item["word"])) or []
        if not bucket:
            continue
        prev = bucket.pop(0)
        used_old.add(prev.id)
        db.query(WordMastery).filter_by(word_bank_id=prev.id).update(
            {WordMastery.word_bank_id: row.id}, synchronize_session=False)
        db.query(Mistake).filter_by(word_bank_id=prev.id).update(
            {Mistake.word_bank_id: row.id}, synchronize_session=False)
    for prev in old:
        if prev.id not in used_old:
            db.expunge(prev)
    drop = [w.id for w in old if w.id not in used_old]
    detach_words(db, drop)
    if old:
        db.query(WordBank).filter(WordBank.id.in_([w.id for w in old])).delete(synchronize_session=False)


def _ensure_word_list_lesson(db: Session, document_id: int, pdf_path: str, by_unit: dict, content_lessons: list) -> None:
    """书末单词表单独成课，词条按 Unit 分组写在释义里。"""
    from ..models import Lesson

    texts = _page_text(pdf_path)
    found = _detect_word_list(pdf_path, "英语", texts, len(texts), db) if texts else None
    if not found:
        return
    rows = db.query(Lesson).filter_by(document_id=document_id, subject="英语").all()
    lesson = next((l for l in rows if is_word_list_title(l.title)), None)
    approved = any(l.audit_status == "approved" for l in content_lessons)
    if lesson is None:
        lesson = Lesson(
            document_id=document_id, subject="英语", title="单词列表",
            start_page=found["start_page"], end_page=found["end_page"],
            extract_status="done", audit_status="approved" if approved else "pending",
        )
        db.add(lesson)
        db.flush()
    else:
        lesson.title = "单词列表"
        lesson.start_page = found["start_page"]
        lesson.end_page = found["end_page"]
        lesson.extract_status = "done"
    for prev in content_lessons:
        if prev.start_page < found["start_page"] <= prev.end_page:
            prev.end_page = found["start_page"] - 1
    items = []
    for n in sorted(by_unit):
        for w in by_unit[n]:
            items.append({"word": w["word"], "extra": f"Unit {n} · {w['extra']}"})
    _replace_lesson_words(db, lesson, items)


def apply_word_list(db: Session, document_id: int, pdf_path: str) -> dict:
    """用书末 Word list 覆盖该英语教材各课的生词表，并单独建一课「单词列表」。

    课按起始页排序，第 1 课对 Unit 1。已有听写记录按词面移到新词条上，不在表里的旧词删掉。
    """
    from ..models import Lesson

    by_unit = extract_word_list_units(pdf_path, db)
    if not by_unit:
        return {"units": 0, "words": 0}
    lessons = (db.query(Lesson)
               .filter_by(document_id=document_id, subject="英语")
               .order_by(Lesson.start_page, Lesson.id)
               .all())
    lessons = [l for l in lessons if not is_word_list_title(l.title)]
    updated = words_n = 0
    for idx, lesson in enumerate(lessons, start=1):
        items = by_unit.get(idx)
        if not items:
            continue
        _replace_lesson_words(db, lesson, items)
        updated += 1
        words_n += len(items)
    _ensure_word_list_lesson(db, document_id, pdf_path, by_unit, lessons)
    db.commit()
    return {"units": updated, "words": words_n, "word_list": sum(len(v) for v in by_unit.values())}


def _parse_ai_output(raw: str, subject: str) -> dict:
    """解析 AI 输出的「生词：…知识点：…课文：…」三段文本。"""
    words, points, text = [], [], ""
    section = None
    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("生词"):
            section = "words"
            continue
        if s.startswith("知识点"):
            section = "points"
            continue
        if s.startswith("课文"):
            section = "text"
            continue
        if not s:
            continue
        if section == "words":
            # 形如 "词|拼音 释义" 或 "word /pron/ n. 释义"
            if "|" in s:
                w, _, extra = s.partition("|")
                words.append({"word": w.strip(), "extra": extra.strip()})
            else:
                parts = s.split()
                if parts:
                    words.append({"word": parts[0].strip("，。：:、,"), "extra": " ".join(parts[1:])})
        elif section == "points":
            points.append(s.lstrip("-*· ").strip())
        elif section == "text":
            text += s + "\n"
    return {"words": words, "points": points, "text": text.strip()}
