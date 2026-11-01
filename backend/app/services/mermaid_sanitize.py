"""Mermaid 源码清洗：LLM 产出常无法被 10.x 解析，统一重建为 graph TD。"""
import re

_MERMAID_HEAD = re.compile(
    r"^(graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|mindmap|journey)\b",
    re.MULTILINE | re.IGNORECASE,
)


def _esc_label(text: str, max_len: int = 36) -> str:
    s = (text or "").replace('"', "'").replace("\n", " ").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[#;`|]", "", s)
    return s[:max_len] if s else "要点"


def graph_td_from_points(root: str, points: list[str]) -> str:
    root_label = _esc_label(root or "本课要点")
    lines = ["graph TD", f'  root["{root_label}"]']
    used: set[str] = {root_label}
    idx = 0
    for p in points:
        label = _esc_label(p)
        if not label or label in used:
            continue
        used.add(label)
        nid = f"n{idx}"
        lines.append(f'  {nid}["{label}"]')
        lines.append(f"  root --> {nid}")
        idx += 1
        if idx >= 8:
            break
    if idx == 0:
        lines.append('  n0["详见上方说明"]')
        lines.append("  root --> n0")
    return "\n".join(lines)


def _default_points(question: str, answer_hint: str) -> list[str]:
    text = f"{question} {answer_hint}"
    parts = re.split(r"[：:、，,；;\n]+", text)
    out = [p.strip() for p in parts if 2 <= len(p.strip()) <= 24]
    if len(out) >= 2:
        return out[:6]
    return ["核心概念", "读写方法", "比大小", "加减法", "生活应用"]


def _extract_labels(code: str) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    skip = {"graph", "td", "lr", "tb", "mindmap", "flowchart", "root"}

    def add(t: str) -> None:
        t = _esc_label(t)
        if not t or len(t) < 2 or t.lower() in skip or t in seen:
            return
        # 英文整句/乱码不作为节点（避免 "not mermaid" 被画进图里）
        if re.search(r"[A-Za-z]", t) and not re.search(r"[\u4e00-\u9fff]", t):
            return
        seen.add(t)
        labels.append(t)

    for ln in code.splitlines():
        s = ln.strip()
        if not s:
            continue
        if _MERMAID_HEAD.match(s):
            continue
        for m in re.finditer(r'\["([^"]+)"\]|\[([^\]]+)\]', s):
            add(m.group(1) or m.group(2))
        for m in re.finditer(r"\(\(([^)]+)\)\)|\(([^)]+)\)", s):
            add(m.group(1) or m.group(2))
        for m in re.finditer(r"-->\s*([A-Za-z_]\w*)", s):
            continue
        for m in re.finditer(r'-->\s*\|([^|]+)\|\s*(\w+)|-->\s*(\S+)', s):
            part = m.group(1) or m.group(3) or ""
            if part and not re.match(r"^n\d+$", part):
                add(part)
        if re.match(r"^root\b", s, re.I):
            m = re.search(r"root\s*\(\((.+)\)\)|root\s*\((.+)\)|root\s*\[\"([^\"]+)\"\]", s, re.I)
            if m:
                add(m.group(1) or m.group(2) or m.group(3))
            continue
        if not re.search(r"[-->\[\(\)]", s) and 2 <= len(s) <= 32:
            add(s.lstrip("-•* "))

    return labels


def _strip_mermaid_fences(raw: str) -> str:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:mermaid)?\s*", "", s, flags=re.I)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def normalize_mermaid_code(code: str, *, fallback_title: str = "", answer_hint: str = "") -> str:
    """任意 LLM 输出 → 可渲染的 graph TD。"""
    raw = _strip_mermaid_fences((code or "").strip())
    raw = raw.replace("\ufeff", "").replace("\u200b", "")
    raw = raw.replace("（", "(").replace("）", ")")
    raw = re.sub(r"\*\*([^*]+)\*\*", r"\1", raw)

    labels = _extract_labels(raw)
    title = _esc_label(fallback_title) or "本课要点"
    if not labels:
        labels = _default_points(fallback_title, answer_hint)
    if title and title not in labels:
        points = labels[:8]
    else:
        points = [x for x in labels if x != title][:8] or labels[:8]
    if not points:
        points = _default_points(fallback_title, answer_hint)
    return graph_td_from_points(title, points)


def normalize_mermaid_in_answer(answer: str, *, question: str = "") -> str:
    """回答里每个 mermaid 块重建；重复块只保留第一个。"""
    if not answer or "```mermaid" not in answer:
        return answer
    prose = re.sub(r"```mermaid\s*[\s\S]*?```", "", answer, flags=re.I)
    seen = False

    def repl(m: re.Match) -> str:
        nonlocal seen
        if seen:
            return ""
        seen = True
        code = m.group(1).strip()
        fixed = normalize_mermaid_code(code, fallback_title=question, answer_hint=prose)
        return f"```mermaid\n{fixed}\n```"

    out = re.sub(r"```mermaid\s*([\s\S]*?)```", repl, answer, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", out).strip()
