"""牛题库 tiku.cn 第三方 adapter（B2B HTTP API）。

官方无公开文档，接入方式：
1. 向 tiku.cn 商务索取 API 基址、密钥与响应示例（微信/手机见官网）。
2. 配置环境变量 TIKU_CN_API_BASE、TIKU_CN_APP_KEY（及可选 TIKU_CN_SEARCH_PATH）。
3. 若对方 JSON 字段名与下方映射不一致，可在响应外包一层 ``{"list": [...]}`` 经
   ``POST /api/banks/{id}/import-third-party`` 直传 items，仍走同一套 normalize。

约定请求（可经 TIKU_CN_SEARCH_PATH 覆盖路径，默认 POST JSON）：
  {"app_key": "<key>", "keyword": "...", "subject": "...", "page": 1, "page_size": 20}

约定响应（灵活解析）：
  {"list": [...]} | {"data": {"list": [...]}} | {"data": [...]} | 顶层数组
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from .question_types import CATEGORY_OF_QTYPE
from .source_adapter import QuestionDraft, ThirdPartyAdapter

_TIKU_TYPE_MAP = {
    "1": "single_choice",
    "2": "multi_choice",
    "3": "true_false",
    "4": "fill_blank",
    "5": "short_answer",
    "single": "single_choice",
    "single_choice": "single_choice",
    "multi": "multi_choice",
    "multi_choice": "multi_choice",
    "judge": "true_false",
    "true_false": "true_false",
    "fill": "fill_blank",
    "fill_blank": "fill_blank",
    "qa": "short_answer",
    "short_answer": "short_answer",
    "essay": "essay",
    "单选": "single_choice",
    "多选": "multi_choice",
    "判断": "true_false",
    "填空": "fill_blank",
    "问答": "short_answer",
}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _extract_items(raw: Any) -> list[dict]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if not isinstance(raw, dict):
        return []
    if isinstance(raw.get("list"), list):
        return [x for x in raw["list"] if isinstance(x, dict)]
    data = raw.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("list", "items", "questions", "rows"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
    for key in ("items", "questions", "rows"):
        if isinstance(raw.get(key), list):
            return [x for x in raw[key] if isinstance(x, dict)]
    return []


def _map_qtype(raw_type: Any) -> str:
    if raw_type is None:
        return "short_answer"
    key = str(raw_type).strip().lower()
    if key in _TIKU_TYPE_MAP:
        return _TIKU_TYPE_MAP[key]
    if key in CATEGORY_OF_QTYPE:
        return key
    return "short_answer"


def _option_letters() -> list[str]:
    return list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def _parse_options(item: dict) -> list[dict]:
    opts = item.get("options") or item.get("choices") or item.get("option_list")
    if isinstance(opts, list) and opts:
        out = []
        for i, o in enumerate(opts):
            if isinstance(o, dict):
                label = (o.get("label") or o.get("text") or o.get("content") or "").strip()
                val = o.get("value", i)
                try:
                    val = int(val)
                except (TypeError, ValueError):
                    val = i
                out.append({"label": label or f"选项{i + 1}", "value": val})
            elif isinstance(o, str):
                out.append({"label": o.strip(), "value": i})
        if out:
            return out
    out = []
    for i, letter in enumerate(_option_letters()):
        key = f"option{letter}"
        alt = f"选项{letter}"
        val = (item.get(key) or item.get(alt) or "").strip()
        if val:
            out.append({"label": val, "value": i})
    return out


def _answer_letters_to_indices(letters: str, n: int) -> int | list[int] | None:
    s = (letters or "").strip().upper().replace(",", "").replace(" ", "")
    if not s:
        return None
    if len(s) == 1 and s in _option_letters()[:n]:
        return _option_letters().index(s)
    if all(c in _option_letters() for c in s):
        return [_option_letters().index(c) for c in s if _option_letters().index(c) < n]
    return None


def _build_answer_json(qtype: str, item: dict, options: list[dict]) -> tuple[dict, str]:
    ans = item.get("answer_json") if isinstance(item.get("answer_json"), dict) else {}
    if ans:
        sample = (item.get("answer") or item.get("answers") or "").strip()
        return ans, sample
    raw_ans = (
        item.get("answer")
        or item.get("answers")
        or item.get("correct_answer")
        or item.get("right_answer")
        or ""
    )
    if isinstance(raw_ans, list):
        raw_ans = "、".join(str(x) for x in raw_ans)
    answer_text = str(raw_ans).strip()
    cat = CATEGORY_OF_QTYPE.get(qtype, "subjective")
    if cat == "choice" and options:
        idx = _answer_letters_to_indices(answer_text, len(options))
        if idx is not None:
            if isinstance(idx, list):
                return {"correct_index": idx}, answer_text
            label = options[idx].get("label", answer_text) if 0 <= idx < len(options) else answer_text
            return {"correct_index": idx}, label
        if answer_text.isdigit():
            i = int(answer_text)
            return {"correct_index": i}, options[i]["label"] if 0 <= i < len(options) else answer_text
    if cat == "blank" and answer_text:
        parts = re.split(r"[,，;；\n]+", answer_text)
        blanks = [p.strip() for p in parts if p.strip()]
        return {"blanks": blanks}, "；".join(blanks)
    if qtype == "true_false":
        low = answer_text.casefold()
        if low in ("对", "正确", "true", "t", "yes", "√", "1"):
            return {"correct_index": 0}, "正确"
        if low in ("错", "错误", "false", "f", "no", "×", "0"):
            return {"correct_index": 1}, "错误"
    return {"sample": answer_text, "rubric": (item.get("rubric") or item.get("points") or "")}, answer_text


def item_to_draft(item: dict) -> QuestionDraft | None:
    stem = (
        (item.get("question") or item.get("stem") or item.get("title") or item.get("content") or "")
        .strip()
    )
    if not stem:
        return None
    qtype = _map_qtype(item.get("qtype") or item.get("type") or item.get("question_type"))
    options = _parse_options(item)
    if qtype == "true_false" and not options:
        options = [{"label": "正确", "value": 0}, {"label": "错误", "value": 1}]
    answer_json, answer = _build_answer_json(qtype, item, options)
    analysis = (item.get("analysis") or item.get("parse") or item.get("explanation") or "").strip()
    diff = (item.get("difficulty") or "medium").strip().lower()
    if diff not in ("easy", "medium", "hard"):
        diff = "medium"
    tags = {"source": "tiku.cn"}
    if item.get("knowledge_point"):
        tags["knowledge_points"] = item["knowledge_point"] if isinstance(item["knowledge_point"], list) else [item["knowledge_point"]]
    ext_id = item.get("id") or item.get("question_id") or item.get("item_id")
    if ext_id is not None:
        tags["tiku_id"] = str(ext_id)
    passage_content = str(
        item.get("passage") or item.get("article") or item.get("material")
        or item.get("passage_content") or ""
    ).strip()
    passage_title = str(
        item.get("passage_title") or item.get("article_title")
        or item.get("material_title") or ""
    ).strip()
    return QuestionDraft(
        qtype=qtype,
        question=stem,
        options=options,
        answer_json=answer_json,
        answer=answer,
        analysis=analysis,
        difficulty=diff,
        tags=tags,
        passage_title=passage_title,
        passage_content=passage_content,
    )


class TikuCnAdapter(ThirdPartyAdapter):
    name = "tiku.cn"

    def __init__(self, base_url: str | None = None, app_key: str | None = None, search_path: str | None = None):
        self.base_url = (base_url if base_url is not None else _env("TIKU_CN_API_BASE")).rstrip("/")
        self.app_key = app_key if app_key is not None else _env("TIKU_CN_APP_KEY")
        self.search_path = search_path if search_path is not None else _env("TIKU_CN_SEARCH_PATH", "/api/question/search")
        if not self.search_path.startswith("/"):
            self.search_path = "/" + self.search_path
        self.timeout = float(_env("TIKU_CN_TIMEOUT", "15") or "15")

    def configured(self) -> bool:
        return bool(self.base_url and self.app_key)

    def fetch(
        self,
        *,
        keyword: str = "",
        subject: str = "",
        page: int = 1,
        page_size: int = 20,
        grade: int | None = None,
        **_,
    ) -> dict:
        if not self.configured():
            return {"list": [], "error": "not_configured", "message": "未配置 TIKU_CN_API_BASE / TIKU_CN_APP_KEY"}
        url = f"{self.base_url}{self.search_path}"
        payload = {
            "app_key": self.app_key,
            "keyword": keyword,
            "subject": subject,
            "page": max(1, page),
            "page_size": max(1, min(page_size, 50)),
        }
        if grade is not None:
            payload["grade"] = grade
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            data = json.loads(text)
            if isinstance(data, dict) and data.get("error") == "not_configured":
                return data
            return data if isinstance(data, (dict, list)) else {"list": []}
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = str(e)
            return {"list": [], "error": "http_error", "status": e.code, "message": detail}
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            return {"list": [], "error": "fetch_failed", "message": str(e)}

    def normalize(self, raw) -> list[QuestionDraft]:
        items = _extract_items(raw)
        drafts: list[QuestionDraft] = []
        for it in items:
            d = item_to_draft(it)
            if d:
                drafts.append(d)
        if not drafts and isinstance(raw, dict) and raw.get("question"):
            d = item_to_draft(raw)
            if d:
                drafts.append(d)
        return drafts
