"""Generate a parent-readable phonics handbook from rules.yaml and path.yaml."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.schema import load_rules  # noqa: E402

CATEGORY_LABELS: dict[str, str] = {
    "vowel": "元音字母",
    "consonant": "辅音字母",
    "vowel_team": "元音字母组合",
    "consonant_digraph": "辅音字母组合",
    "r_controlled": "r 控制",
    "syllable_pattern": "多音节常见模式",
}

CATEGORY_ORDER: tuple[str, ...] = tuple(CATEGORY_LABELS)


def _example_words_by_grade(rule: dict) -> tuple[list[str], list[str]]:
    g3: list[str] = []
    g5: list[str] = []
    for ex in rule.get("example_words") or []:
        word = ex.get("word", "")
        if not word:
            continue
        grades = ex.get("grades") or [3, 5]
        if 3 in grades and word not in g3:
            g3.append(word)
        if 5 in grades and word not in g5:
            g5.append(word)
    return g3, g5


def _format_rule(rule: dict) -> str:
    grapheme = rule.get("grapheme", "")
    ipa = (rule.get("ipa") or "").strip()
    approx_zh = rule.get("approx_zh", "")
    title = f"### {grapheme}"
    if ipa:
        title += f" — {ipa}"
    lines = [title, "", f"- **近似读法**：{approx_zh}"]
    g3, g5 = _example_words_by_grade(rule)
    lines.append(f"- **三年级例词**：{', '.join(g3) if g3 else '—'}")
    lines.append(f"- **五年级例词**：{', '.join(g5) if g5 else '—'}")
    notes = rule.get("notes")
    if notes and str(notes).strip():
        lines.append(f"- **备注**：{notes}")
    lines.append("")
    return "\n".join(lines)


def _rules_for_stage(rules: list[dict], stage: dict) -> list[dict]:
    lo = int(stage["path_order_min"])
    hi = int(stage["path_order_max"])
    matched = [
        r for r in rules
        if lo <= int(r.get("path_order") or 0) <= hi
    ]
    return sorted(matched, key=lambda r: int(r.get("path_order") or 0))


def render_handbook(rules_path, path_path) -> str:
    import yaml

    rules = load_rules(rules_path)
    path_data = yaml.safe_load(Path(path_path).read_text(encoding="utf-8"))
    stages = (path_data or {}).get("stages") or []

    parts: list[str] = [
        "# 自然拼读发音规则手册",
        "",
        "由 `rules.yaml` 自动生成，面向家长与孩子查阅。",
        "",
        "## 推荐学习路径",
        "",
        "按建议学习顺序排列（见 `path.yaml` 阶段划分）。",
        "",
    ]

    ordered = sorted(rules, key=lambda r: int(r.get("path_order") or 9999))
    if stages:
        covered: set[str] = set()
        for stage in stages:
            stage_rules = _rules_for_stage(rules, stage)
            if not stage_rules:
                continue
            sid = stage.get("id", "")
            name = stage.get("name", "")
            parts.append(f"### 阶段 {sid}：{name}")
            parts.append("")
            for rule in stage_rules:
                parts.append(_format_rule(rule))
                covered.add(rule["id"])
        outside = [r for r in ordered if r["id"] not in covered]
        if outside:
            parts.append("### 其他")
            parts.append("")
            for rule in outside:
                parts.append(_format_rule(rule))
    else:
        for rule in ordered:
            parts.append(_format_rule(rule))

    parts.extend([
        "## 分类目录",
        "",
        "按发音类别归类，便于查找。",
        "",
    ])

    by_cat: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for rule in rules:
        cat = rule.get("category")
        if cat in by_cat:
            by_cat[cat].append(rule)

    for cat in CATEGORY_ORDER:
        cat_rules = sorted(by_cat[cat], key=lambda r: (r.get("grapheme", ""), r.get("id", "")))
        if not cat_rules:
            continue
        label = CATEGORY_LABELS[cat]
        parts.append(f"### {label}（`{cat}`）")
        parts.append("")
        for rule in cat_rules:
            parts.append(_format_rule(rule))

    return "\n".join(parts).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate phonics handbook markdown.")
    parser.add_argument("--rules", type=Path, required=True, help="Path to rules.yaml")
    parser.add_argument("--path", type=Path, required=True, help="Path to path.yaml")
    parser.add_argument("--out", type=Path, required=True, help="Output handbook.md path")
    args = parser.parse_args(argv)

    text = render_handbook(args.rules, args.path)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())