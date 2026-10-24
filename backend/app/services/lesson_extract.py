"""从课程页面提取结构化内容：课文文本、生词表、知识点。

提取走 AI provider（DeepSeek/GLM），失败时回退到从 PDF 文本中抽词/抽句，
保证在无 API Key 时仍能得到可用的结构（生词按行切分，课文取首段）。
"""
import re

from sqlalchemy.orm import Session

from .ai import get_provider
from .pdf_split import _page_text, SUBJECT_RULES


def _extract_words_fallback(pdf_path: str, start_page: int, end_page: int, subject: str) -> list[dict]:
    """无 AI 时兜底：从页面文本中按「生词表/单词表」标记后的行提取词条。"""
    texts = _page_text(pdf_path)
    if not texts:
        return []
    block = "\n".join(texts[start_page - 1:end_page])
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


def _extract_text_fallback(pdf_path: str, start_page: int, end_page: int) -> str:
    texts = _page_text(pdf_path)
    if not texts:
        return ""
    block = "\n".join(texts[start_page - 1:end_page]).strip()
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

    if has_real:
        pages = f"第 {start_page}–{end_page} 页"
        if rules["has_word_bank"]:
            prompt = (
                f"你正在为一本「{subject}」教材的第 {pages} 拆课。请提取：\n"
                f"1) 生词/单词表（每行：词|{rules['word_extra']}）\n"
                f"2) 本课知识点（每行一个）\n"
                f"3) 课文正文（原文，最多 300 字）\n"
                f"用三段输出，分别以「生词：」「知识点：」「课文：」开头。"
            )
        else:
            prompt = (
                f"你正在为一本「{subject}」教材的第 {pages} 拆课。请提取：\n"
                f"1) 本课知识点（每行一个）\n"
                f"2) 正文内容（最多 300 字）\n"
                f"用两段输出，分别以「知识点：」「课文：」开头。"
            )
        try:
            raw = provider.generate(prompt=prompt, system="你是教材拆解助手，只输出提取结果，不要解释。")
            parsed = _parse_ai_output(raw, subject)
            if parsed["words"] or parsed["points"] or parsed["text"]:
                return parsed
        except Exception:
            pass  # AI 失败回退兜底

    words = _extract_words_fallback(pdf_path, start_page, end_page, subject) if rules["has_word_bank"] else []
    text = _extract_text_fallback(pdf_path, start_page, end_page)
    return {"words": words, "points": [], "text": text}


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
