"""把 group 组装成 Task.content JSON。"""
import json
from sqlalchemy.orm import Session

MAX_ITEMS = 8


def _steps_for(kind: str) -> list[str]:
    if kind == "phrase":
        return ["recognize", "recall", "produce", "quiz"]
    if kind == "explore":
        return ["observe", "classify", "formula", "trap"]
    return ["structure", "drill", "apply", "closure"]


def build_quiz(items: list) -> list[dict]:
    """为每个条目出 blank 题；有 common_mistake 的另出 spot_error 题。快测步取 3 题。"""
    quiz = []
    for it in items:
        if it.primary:
            quiz.append({"item_id": it.id, "qtype": "blank",
                         "prompt": f"补全：{it.primary}", "answer": it.primary})
        try:
            cm = json.loads(it.common_mistake or "{}")
        except (ValueError, TypeError):
            cm = {}
        if cm.get("wrong") and cm.get("correct"):
            quiz.append({"item_id": it.id, "qtype": "spot_error",
                         "prompt": f"{cm['wrong']} 哪里错了？",
                         "wrong": cm["wrong"], "answer": cm["correct"],
                         "explain": cm.get("explain", "")})
    return quiz[:3]


def build_task_content(group, items: list, review_items: list, quiz: list) -> str:
    snapshot = [{"id": it.id, "primary": it.primary, "secondary": it.secondary,
                 "example": it.example, "source_page": it.source_page, "source": "new"} for it in items]
    snapshot += [{"id": it.id, "primary": it.primary, "secondary": it.secondary,
                  "example": it.example, "source_page": it.source_page, "source": "review"} for it in review_items]
    steps = _steps_for(group.kind)
    return json.dumps({
        "schema_version": 2,
        "group_id": group.id, "source": group.source, "kind": group.kind,
        "document_id": group.document_id,
        "intro": json.loads(group.intro or "{}"),
        "group_rule": json.loads(group.group_rule or "{}"),
        "steps": steps,
        "item_ids": [it.id for it in items],
        "review_item_ids": [it.id for it in review_items],
        "items_snapshot": snapshot,
        "quiz": quiz,
        "progress": {"step": steps[0], "item_index": 0, "hints_used": {},
                     "recall_results": {}, "produce_results": {}, "quiz_results": {}},
    }, ensure_ascii=False)
