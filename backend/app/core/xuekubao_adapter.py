"""学库宝 xuekubao.com 第三方题库 adapter。

官方控制台：https://api.xuekubao.com/user/api-list
鉴权：请求头 ``x-api-key`` 或 ``X-API-Key``（二者等价）。

常用链路：
  POST /api/v1/subjectEditionApi — 四级树：学段 → 年级(上下册) → 学科 → 版本（节点 ``code`` 为 chapterApi 参数）
  POST /api/v1/chapterApi — 章节树，三级节点 ``oldId`` 即 ``knowledgeId``
  POST /api/v1/getQuestions — ``knowledgeId`` + ``page``（必填）
  POST /api/v1/getAnswer — ``qid``（逗号分隔，部分套餐可能无解析数据）

环境变量：``XUEKUBAO_API_BASE``、``XUEKUBAO_ACCESS_KEY``、可选 ``XUEKUBAO_TIMEOUT``。
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .source_adapter import QuestionDraft, ThirdPartyAdapter
from .tiku_cn_adapter import _extract_items, item_to_draft

_XUEKUBAO_TYPE_MAP = {
    "选择题": "single_choice",
    "单选题": "single_choice",
    "单项选择": "single_choice",
    "多选题": "multi_choice",
    "多项选择": "multi_choice",
    "判断题": "true_false",
    "填空题": "fill_blank",
    "解答题": "short_answer",
    "问答题": "short_answer",
    "计算题": "short_answer",
    "简答题": "short_answer",
    "作文题": "essay",
    "书面表达": "essay",
}


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _api_ok(raw: dict | None) -> bool:
    if not isinstance(raw, dict):
        return False
    code = raw.get("errorCode")
    if code is None:
        return raw.get("code") not in (401, 403)
    return str(code) in ("0", "200", "success")


def _map_diff(diff_val: Any) -> str:
    try:
        d = float(str(diff_val).strip())
    except (TypeError, ValueError):
        return "medium"
    if d <= 2.0:
        return "easy"
    if d <= 3.0:
        return "medium"
    return "hard"


def _xuekubao_to_generic(item: dict) -> dict:
    stem = (item.get("title") or item.get("timu") or item.get("question") or "").strip()
    qtype_raw = item.get("qtpye") or item.get("qtype") or item.get("type") or ""
    qtype_key = str(qtype_raw).strip()
    mapped_type = _XUEKUBAO_TYPE_MAP.get(qtype_key, qtype_key or "short_answer")
    out: dict[str, Any] = {
        "question": stem,
        "stem": stem,
        "type": mapped_type if mapped_type in _XUEKUBAO_TYPE_MAP.values() else qtype_key,
        "id": item.get("id"),
        "analysis": (item.get("parse") or item.get("jiexi") or item.get("analysis") or "").strip(),
        "difficulty": _map_diff(item.get("diff")),
    }
    if item.get("answer"):
        out["answer"] = item["answer"]
    if item.get("answer1"):
        out["answer"] = item.get("answer1")
    for letter in "abcde":
        key = f"option_{letter}"
        val = (item.get(key) or "").strip()
        if val:
            out[f"option{letter.upper()}"] = val
    return out


def xuekubao_item_to_draft(item: dict) -> QuestionDraft | None:
    d = item_to_draft(_xuekubao_to_generic(item))
    if not d:
        return None
    tags = {"source": "xuekubao"}
    ext_id = item.get("id")
    if ext_id is not None:
        tags["xuekubao_id"] = str(ext_id)
    if item.get("md52"):
        tags["xuekubao_md52"] = str(item["md52"])
    km = item.get("knowledgeMore")
    if isinstance(km, list) and km:
        first = km[0] if isinstance(km[0], dict) else {}
        if first.get("knowledgeId"):
            tags["knowledge_id"] = str(first["knowledgeId"])
        if first.get("knowledgeName"):
            tags["knowledge_points"] = [str(first["knowledgeName"])]
    d.tags = tags
    d.difficulty = _map_diff(item.get("diff")) if item.get("diff") is not None else d.difficulty
    return d


def _merge_answers(items: list[dict], answers_by_qid: dict[str, dict]) -> list[dict]:
    if not answers_by_qid:
        return items
    merged = []
    for it in items:
        copy = dict(it)
        qid = str(copy.get("id") or "")
        ans = answers_by_qid.get(qid)
        if isinstance(ans, dict):
            for key in ("answer", "answer1", "parse", "jiexi", "analysis"):
                if ans.get(key) and not copy.get(key):
                    copy[key] = ans[key]
        merged.append(copy)
    return merged


class XuekubaoAdapter(ThirdPartyAdapter):
    name = "xuekubao"

    def __init__(self, base_url: str | None = None, access_key: str | None = None):
        self.base_url = (base_url if base_url is not None else _env("XUEKUBAO_API_BASE", "https://api.xuekubao.com")).rstrip("/")
        self.access_key = access_key if access_key is not None else _env("XUEKUBAO_ACCESS_KEY")
        self.timeout = float(_env("XUEKUBAO_TIMEOUT", "30") or "30")

    def configured(self) -> bool:
        return bool(self.base_url and self.access_key)

    def _post(self, path: str, body: dict | None = None) -> dict:
        if not path.startswith("/"):
            path = "/" + path
        payload = json.dumps(body if body is not None else {}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "x-api-key": self.access_key or "",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            data = json.loads(text)
            return data if isinstance(data, dict) else {"errorCode": "invalid", "data": data}
        except urllib.error.HTTPError as e:
            try:
                detail = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = str(e)
            return {"errorCode": "http_error", "message": detail, "status": e.code, "data": []}
        except (urllib.error.URLError, ValueError, TimeoutError) as e:
            return {"errorCode": "fetch_failed", "message": str(e), "data": []}

    def subject_edition_tree(self) -> dict:
        if not self.configured():
            return {"errorCode": "not_configured", "message": "未配置 XUEKUBAO_ACCESS_KEY", "data": []}
        return self._post("/api/v1/subjectEditionApi", {})

    def chapter_tree(
        self,
        *,
        pharse_id: str,
        subject_id: str = "",
        grade_id: str = "",
        edition_id: str = "",
    ) -> dict:
        if not self.configured():
            return {"errorCode": "not_configured", "message": "未配置 XUEKUBAO_ACCESS_KEY", "data": []}
        body: dict[str, str] = {"pharseId": str(pharse_id)}
        if subject_id:
            body["subjectId"] = str(subject_id)
        if grade_id:
            body["gradeId"] = str(grade_id)
        if edition_id:
            body["editionId"] = str(edition_id)
        return self._post("/api/v1/chapterApi", body)

    def fetch_answers(self, qids: list[str]) -> dict[str, dict]:
        ids = [str(x).strip() for x in qids if str(x).strip()]
        if not ids or not self.configured():
            return {}
        raw = self._post("/api/v1/getAnswer", {"qid": ",".join(ids)})
        if not _api_ok(raw):
            return {}
        data = raw.get("data")
        out: dict[str, dict] = {}
        if isinstance(data, list):
            for row in data:
                if isinstance(row, dict) and row.get("id") is not None:
                    out[str(row["id"])] = row
                elif isinstance(row, dict) and row.get("qid") is not None:
                    out[str(row["qid"])] = row
        elif isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    out[str(k)] = v
        return out

    def fetch_by_knowledge(
        self,
        *,
        knowledge_id: str,
        page: int = 1,
        qtype_id: str | None = None,
        diff: str | None = None,
        year: int | None = None,
        grade_id: str | None = None,
        fetch_answers: bool = True,
        **_,
    ) -> dict:
        if not self.configured():
            return {"data": [], "errorCode": "not_configured", "message": "未配置 XUEKUBAO_API_BASE / XUEKUBAO_ACCESS_KEY"}
        kid = (knowledge_id or "").strip()
        if not kid or kid == "0":
            return {"data": [], "errorCode": "invalid", "message": "knowledge_id 无效"}
        body: dict[str, Any] = {"knowledgeId": kid, "page": max(1, int(page))}
        if qtype_id:
            body["qtypeId"] = str(qtype_id)
        if diff:
            body["diff"] = str(diff)
        if year is not None:
            body["year"] = int(year)
        if grade_id:
            body["gradeId"] = str(grade_id)
        raw = self._post("/api/v1/getQuestions", body)
        if not _api_ok(raw):
            return raw
        items = raw.get("data")
        if not isinstance(items, list):
            items = _extract_items(raw)
        if fetch_answers and items:
            qids = [str(it.get("id")) for it in items if isinstance(it, dict) and it.get("id")]
            ans_map = self.fetch_answers(qids)
            items = _merge_answers([it for it in items if isinstance(it, dict)], ans_map)
            raw = {**raw, "data": items}
        return raw

    def fetch(self, *, knowledge_id: str = "", page: int = 1, **kwargs) -> dict:
        return self.fetch_by_knowledge(knowledge_id=knowledge_id, page=page, **kwargs)

    def normalize(self, raw) -> list[QuestionDraft]:
        items = raw.get("data") if isinstance(raw, dict) and isinstance(raw.get("data"), list) else _extract_items(raw)
        drafts: list[QuestionDraft] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            d = xuekubao_item_to_draft(it)
            if d:
                drafts.append(d)
        return drafts
