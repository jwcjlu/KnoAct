from tools.letter_index import LETTER_GROUPS, build_letter_index, render_letter_index_md
from tools.schema import load_rules
from pathlib import Path

RULES = Path(__file__).resolve().parents[1] / "rules.yaml"


def test_each_vowel_letter_has_primary_short_or_y():
    by_id = {r["id"]: r for r in load_rules(RULES)}
    index = build_letter_index(by_id)
    assert "vowel.a.short" in {x["id"] for x in index["a"]}
    assert "vowel.e.short" in {x["id"] for x in index["e"]}
    assert "syllable_pattern.a_e.magic_e" in {x["id"] for x in index["a"]}
    assert "r_controlled.ar.primary" in {x["id"] for x in index["a"]}


def test_all_indexed_ids_exist_in_rules():
    rules = load_rules(RULES)
    ids = {r["id"] for r in rules}
    for letter, rows in LETTER_GROUPS.items():
        for rid, _ in rows:
            assert rid in ids, f"{letter}: missing {rid}"


def test_render_mentions_letter_a():
    by_id = {r["id"]: r for r in load_rules(RULES)}
    md = render_letter_index_md(build_letter_index(by_id))
    assert "## 字母 `a`" in md
    assert "/æ/" in md
