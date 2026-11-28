"""Build「字母多种读法」index — groups existing rules under a/e/i/o/u/y."""

from __future__ import annotations

from pathlib import Path

# letter -> ordered list of (rule_id, label_zh)
# Teaching path unchanged; this is overview only.
LETTER_GROUPS: dict[str, list[tuple[str, str]]] = {
    "a": [
        ("vowel.a.short", "短音（主音）"),
        ("syllable_pattern.a_e.magic_e", "magic e 长音"),
        ("r_controlled.ar.primary", "a + r"),
        ("vowel_team.ai.primary", "组合 ai"),
        ("vowel_team.ay.primary", "组合 ay"),
        ("vowel_team.aw.primary", "组合 aw"),
        ("vowel_team.au.primary", "组合 au"),
    ],
    "e": [
        ("vowel.e.short", "短音（主音）"),
        ("syllable_pattern.e_e.magic_e", "magic e 长音"),
        ("r_controlled.er.primary", "e + r"),
        ("vowel_team.ee.primary", "组合 ee"),
        ("vowel_team.ea.primary", "组合 ea"),
        ("vowel_team.ew.primary", "组合 ew"),
    ],
    "i": [
        ("vowel.i.short", "短音（主音）"),
        ("syllable_pattern.i_e.magic_e", "magic e 长音"),
        ("r_controlled.ir.primary", "i + r"),
        ("vowel_team.ie.primary", "组合 ie"),
        ("vowel_team.igh.primary", "组合 igh"),
    ],
    "o": [
        ("vowel.o.short", "短音（主音）"),
        ("syllable_pattern.o_e.magic_e", "magic e 长音"),
        ("r_controlled.or.primary", "o + r"),
        ("r_controlled.ore.primary", "组合 ore"),
        ("vowel_team.oa.primary", "组合 oa"),
        ("vowel_team.oo.primary", "组合 oo"),
        ("vowel_team.oi.primary", "组合 oi"),
        ("vowel_team.oy.primary", "组合 oy"),
        ("vowel_team.ou.primary", "组合 ou"),
        ("vowel_team.ow.primary", "组合 ow"),
    ],
    "u": [
        ("vowel.u.short", "短音（主音）"),
        ("syllable_pattern.u_e.magic_e", "magic e 长音"),
        ("r_controlled.ur.primary", "u + r"),
        ("vowel_team.ue.primary", "组合 ue"),
    ],
    "y": [
        ("vowel.y.short", "作元音（主音，如 happy）"),
    ],
}


def build_letter_index(rules_by_id: dict[str, dict]) -> dict[str, list[dict]]:
    """Return letter -> [{id, label, grapheme, ipa, audio_path, example}]."""
    out: dict[str, list[dict]] = {}
    for letter, rows in LETTER_GROUPS.items():
        items: list[dict] = []
        for rid, label in rows:
            rule = rules_by_id.get(rid)
            if not rule:
                continue
            ex = rule["example_words"][0]["word"]
            items.append({
                "id": rid,
                "label": label,
                "grapheme": rule["grapheme"],
                "ipa": rule.get("ipa") or "",
                "audio_path": rule["audio"]["rule"]["path"],
                "example": ex,
            })
        out[letter] = items
    return out


def render_letter_index_md(index: dict[str, list[dict]]) -> str:
    lines = [
        "# 字母多种读法总览",
        "",
        "> 学习路径仍按 `path_order` 一次教一个主音；本页只做**查阅**：点开字母看它常见有哪些读法，"
        "音频与规则库共用。",
        "",
    ]
    for letter in ("a", "e", "i", "o", "u", "y"):
        items = index.get(letter) or []
        lines.append(f"## 字母 `{letter}`")
        lines.append("")
        if not items:
            lines.append("（暂无条目）")
            lines.append("")
            continue
        lines.append("| 读法 | 写法 | IPA | 例词 | 规则 id | 音频 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for it in items:
            lines.append(
                f"| {it['label']} | `{it['grapheme']}` | {it['ipa'] or '—'} | "
                f"{it['example']} | `{it['id']}` | `{it['audio_path']}` |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"
