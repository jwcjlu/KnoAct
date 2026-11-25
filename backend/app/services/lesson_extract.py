"""从课程页面提取结构化内容：课文文本、生词表、知识点。

提取走 AI provider（DeepSeek/GLM），失败时回退到从 PDF 文本中抽词/抽句，
保证在无 API Key 时仍能得到可用的结构（生词按行切分，课文取首段）。
"""
import re

from sqlalchemy.orm import Session

from .ai import get_provider
from .word_kinds import (
    KIND_PHRASE,
    KIND_RECOGNIZE,
    KIND_WORD,
    KIND_WRITE,
    normalize_kind,
)
from .pdf_split import (
    SUBJECT_RULES,
    WORD_LIST_OCR_PROMPT,
    _CN_TABLE_TITLES,
    _detect_chinese_word_tables,
    _detect_word_list,
    _is_scanned,
    _ocr_page,
    _page_continues_word_list,
    _page_text,
    is_cn_table_title,
    is_word_list_title,
    split_gloss_line,
)

_LESSON_NO_LINE = re.compile(r"^\s*(\d{1,2})\s*$")
_HAN_TOKEN = re.compile(r"[\u4e00-\u9fff]+")


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
            words.append({"word": first, "extra": line[len(first):].strip(), "kind": KIND_WORD})
        if len(words) >= 30:
            break
    return words


_CN_SECTION_RES = (
    (re.compile(r"^识字"), KIND_RECOGNIZE),
    (re.compile(r"^写字"), KIND_WRITE),
    (re.compile(r"^词语"), KIND_PHRASE),
)


def _parse_word_line(s: str) -> tuple[str, str] | None:
    if "|" in s:
        w, _, extra = s.partition("|")
        return w.strip(), extra.strip()
    parts = s.split()
    if not parts:
        return None
    return parts[0].strip("，。：:、,"), " ".join(parts[1:])


def _cn_section_kind(line: str) -> str | None:
    s = line.strip()
    for pat, kind in _CN_SECTION_RES:
        if pat.match(s):
            return kind
    return None


def _extract_chinese_words_fallback(block: str) -> list[dict]:
    """从页面文本按识字/写字/词语标题切段，缺段则该 kind 为空。"""
    words: list[dict] = []
    section_kind: str | None = None
    for line in block.splitlines():
        s = line.strip()
        if not s:
            continue
        ck = _cn_section_kind(s)
        if ck is not None:
            section_kind = ck
            continue
        if section_kind is None:
            continue
        if re.fullmatch(r"[\d\s.]+", s):
            continue
        parsed = _parse_word_line(s)
        if not parsed:
            continue
        w, extra = parsed
        if not w or len(w) > 12:
            continue
        words.append({"word": w, "extra": extra, "kind": section_kind})
        if len(words) >= 90:
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
        if rules["has_word_bank"] and subject == "语文":
            prompt = (
                f"你正在为一本「{subject}」教材的第 {pages} 拆课。下面是这一课的原文（可能含目录残留、页码、插图文字，请忽略无关内容）。\n"
                f"请严格基于原文提取：\n"
                f"1) 识字表（每行：字|{rules['word_extra']}）\n"
                f"2) 写字表（每行：字|{rules['word_extra']}）\n"
                f"3) 词语表（每行：词|释义）\n"
                f"4) 本课知识点（每行一个）\n"
                f"5) 课文正文（原文照抄，最多 300 字）\n"
                f"用五段输出，分别以「识字：」「写字：」「词语：」「知识点：」「课文：」开头；某表原文没有则只写标题空段。\n\n"
                f"原文：\n{page_block}"
            )
        elif rules["has_word_bank"]:
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

    words: list[dict] = []
    if rules["has_word_bank"]:
        if subject == "语文":
            block = _lesson_texts(pdf_path, start_page, end_page, db)
            words = _extract_chinese_words_fallback(block)
        else:
            words = _extract_words_fallback(pdf_path, start_page, end_page, subject, db)
    text = _extract_text_fallback(pdf_path, start_page, end_page, db)
    return {"words": words, "points": [], "text": text}


def _table_tokens_from_line(s: str, kind: str) -> list[str]:
    """按 kind 从一行抽出词/字 token。"""
    out: list[str] = []
    for tok in _HAN_TOKEN.findall(s):
        if kind == KIND_PHRASE:
            if len(tok) >= 2:
                out.append(tok)
        elif len(tok) == 1:
            out.append(tok)
        else:
            out.extend(list(tok))
    return out


def parse_chinese_table_text(raw: str, kind: str) -> dict[int, list[dict]]:
    """册末表文本 → {lesson_no: [{word, extra, kind}, ...]}。同课同词去重保序。"""
    kind = normalize_kind(kind)
    by: dict[int, list[dict]] = {}
    seen: dict[int, set[str]] = {}
    cur: int | None = None
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s in _CN_TABLE_TITLES or any(s.startswith(t) for t in _CN_TABLE_TITLES):
            continue
        m = _LESSON_NO_LINE.match(s)
        if m:
            cur = int(m.group(1))
            by.setdefault(cur, [])
            seen.setdefault(cur, set())
            continue
        m2 = re.match(r"^(\d{1,2})\s+(.+)$", s)
        if m2:
            cur = int(m2.group(1))
            by.setdefault(cur, [])
            seen.setdefault(cur, set())
            s = m2.group(2)
        elif cur is None:
            continue
        for w in _table_tokens_from_line(s, kind):
            if w in seen[cur]:
                continue
            seen[cur].add(w)
            by[cur].append({"word": w, "extra": "", "kind": kind})
    return {n: rows for n, rows in by.items() if rows}


def extract_chinese_table_units(
    pdf_path: str, db, kind: str, start_page: int, end_page: int,
) -> dict[int, list[dict]]:
    """读取册末表页码区间文本并解析为课号桶。"""
    block = _lesson_texts(pdf_path, start_page, end_page, db)
    return parse_chinese_table_text(block, kind)


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
        units[unit].append({
            "word": word, "extra": f"*{gloss}" if star else gloss, "kind": KIND_WORD,
        })
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


def _kind_key(kind: str, subject: str) -> str:
    """英语旧数据曾默认 phrase；匹配时与 word 视为同键。"""
    k = normalize_kind(kind) if kind else ""
    if subject != "语文" and k == KIND_PHRASE:
        return KIND_WORD
    return k


def _replace_lesson_words(db: Session, lesson, items: list[dict]) -> None:
    """按 (词面, kind) 写回一课；同键掌握度留在原 word_bank_id 上。"""
    from ..models import WordBank
    from .cleanup import detach_words

    old = db.query(WordBank).filter_by(lesson_id=lesson.id).all()
    subject = lesson.subject or "英语"
    old_by_key: dict[tuple[str, str], list[WordBank]] = {}
    for w in old:
        key = (_norm_word(w.word), _kind_key(w.kind or "", subject))
        old_by_key.setdefault(key, []).append(w)
    used_old: set[int] = set()
    for item in items:
        kind = normalize_kind(item["kind"])
        key = (_norm_word(item["word"]), _kind_key(kind, subject))
        bucket = old_by_key.get(key) or []
        if bucket:
            row = bucket.pop(0)
            row.word = item["word"]
            row.extra = item.get("extra") or ""
            row.kind = kind
            row.subject = subject
            used_old.add(row.id)
        else:
            row = WordBank(
                lesson_id=lesson.id, subject=subject,
                word=item["word"], extra=item.get("extra") or "", kind=kind,
            )
            db.add(row)
    drop = [w.id for w in old if w.id not in used_old]
    detach_words(db, drop)
    if drop:
        db.query(WordBank).filter(WordBank.id.in_(drop)).delete(synchronize_session=False)


def _replace_lesson_words_kind(db: Session, lesson, kind: str, items: list[dict]) -> None:
    """只替换该课该 kind；其它 kind 不动。items 为空则 no-op（由调用方保证有表才调用）。"""
    from ..models import WordBank
    from .cleanup import detach_words

    kind = normalize_kind(kind)
    subject = lesson.subject or "语文"
    old = db.query(WordBank).filter_by(lesson_id=lesson.id, kind=kind).all()
    old_by_key: dict[str, list] = {}
    for w in old:
        old_by_key.setdefault(_norm_word(w.word), []).append(w)
    used: set[int] = set()
    for item in items:
        key = _norm_word(item["word"])
        bucket = old_by_key.get(key) or []
        if bucket:
            row = bucket.pop(0)
            row.word = item["word"]
            row.extra = item.get("extra") or ""
            row.kind = kind
            used.add(row.id)
        else:
            db.add(WordBank(
                lesson_id=lesson.id, subject=subject,
                word=item["word"], extra=item.get("extra") or "", kind=kind,
            ))
    drop = [w.id for w in old if w.id not in used]
    detach_words(db, drop)
    if drop:
        db.query(WordBank).filter(WordBank.id.in_(drop)).delete(synchronize_session=False)


def apply_chinese_word_tables(db: Session, document_id: int, pdf_path: str) -> dict:
    from ..models import Lesson

    texts = _page_text(pdf_path) or []
    tables = _detect_chinese_word_tables(pdf_path, "语文", texts, len(texts), db)
    if not tables:
        return {"tables": 0, "lessons": 0, "words": 0}
    lessons = (
        db.query(Lesson)
        .filter_by(document_id=document_id, subject="语文")
        .order_by(Lesson.start_page, Lesson.id)
        .all()
    )
    lessons = [l for l in lessons if not is_cn_table_title(l.title) and not is_word_list_title(l.title)]
    updated = words_n = 0
    for tbl in tables:
        by = extract_chinese_table_units(
            pdf_path, db, tbl["kind"], tbl["start_page"], tbl["end_page"],
        )
        for idx, lesson in enumerate(lessons, start=1):
            items = by.get(idx)
            if not items:
                continue
            _replace_lesson_words_kind(db, lesson, tbl["kind"], items)
            updated += 1
            words_n += len(items)
    db.commit()
    return {"tables": len(tables), "lessons": updated, "words": words_n}


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
            items.append({
                "word": w["word"], "extra": f"Unit {n} · {w['extra']}", "kind": KIND_WORD,
            })
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
        raw = by_unit.get(idx)
        if not raw:
            continue
        items = [{**w, "kind": w.get("kind", KIND_WORD)} for w in raw]
        _replace_lesson_words(db, lesson, items)
        updated += 1
        words_n += len(items)
    _ensure_word_list_lesson(db, document_id, pdf_path, by_unit, lessons)
    db.commit()
    return {"units": updated, "words": words_n, "word_list": sum(len(v) for v in by_unit.values())}


def _parse_ai_output(raw: str, subject: str) -> dict:
    """解析 AI 拆课输出：语文识字/写字/词语三分；英语生词带 kind=word。"""
    words, points, text = [], [], ""
    section: str | None = None
    cn = subject == "语文"
    for line in raw.splitlines():
        s = line.strip()
        if cn:
            ck = _cn_section_kind(s)
            if ck is not None:
                section = f"cn_{ck}"
                continue
        if s.startswith("生词"):
            if cn:
                section = None
            else:
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
        if (section in ("words",) and not cn) or (
            section and section.startswith("cn_")
        ):
            parsed = _parse_word_line(s)
            if not parsed:
                continue
            w, extra = parsed
            if section.startswith("cn_"):
                kind = section[3:]
            else:
                kind = KIND_WORD
            words.append({"word": w, "extra": extra, "kind": kind})
        elif section == "points":
            points.append(s.lstrip("-*· ").strip())
        elif section == "text":
            text += s + "\n"
    return {"words": words, "points": points, "text": text.strip()}
