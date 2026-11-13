"""发布前 AI 预检：检查家长填写的条目是否有拼写/语法/逻辑问题。"""
import json
from sqlalchemy.orm import Session


def review_group_items(db: Session | None, subject: str, kind: str, items: list[dict]) -> list[dict]:
    """返回疑似问题列表 [{primary, issue, suggestion}]。提示式，不阻断建组。

    fake/无 db/无 items/异常 → 空列表（无提示，家长照常手动审）。
    """
    if db is None or not items:
        return []
    from .ai import get_provider
    provider = get_provider(db)
    if provider.name == "fake":
        return []

    payload = [{"primary": it.get("primary", ""), "secondary": it.get("secondary", "")}
               for it in items if (it.get("primary") or "").strip()][:20]
    if not payload:
        return []

    prompt = (
        f"你是小学老师，正在帮家长检查一组{subject}的{kind}专项训练条目，看有没有拼写、语法、"
        "释义或逻辑错误，防止误导孩子。请逐条检查，只返回有问题的条目：\n"
        '只返回 JSON：{"issues":[{"primary":"有问题的条目原文","issue":"问题描述","suggestion":"修改建议"}]}。'
        "没有问题的条目不要列；全部正确则返回 {\"issues\":[]}。\n"
        f"条目：{json.dumps(payload, ensure_ascii=False)}"
    )
    try:
        raw = provider.generate(prompt=prompt, system="你是小学老师，严谨校对。", json_mode=True)
        data = json.loads(raw)
        issues = data.get("issues") or []
        return [
            {"primary": (i.get("primary") or "").strip(),
             "issue": (i.get("issue") or "").strip(),
             "suggestion": (i.get("suggestion") or "").strip()}
            for i in issues if isinstance(i, dict) and (i.get("issue") or "").strip()
        ]
    except Exception:
        return []
