from pathlib import Path
from tools.schema import load_rules
from tools.inventory import REQUIRED_BY_CATEGORY

RULES = Path(__file__).resolve().parents[1] / "rules.yaml"


def _by_cat(cat: str) -> set[str]:
    rules = load_rules(RULES)
    return {r["grapheme"] for r in rules if r["category"] == cat}


def test_vowels_complete():
    assert _by_cat("vowel") >= set(REQUIRED_BY_CATEGORY["vowel"])


def test_consonants_complete():
    assert _by_cat("consonant") >= set(REQUIRED_BY_CATEGORY["consonant"])


def test_full_required_coverage():
    rules = load_rules(RULES)
    by_cat = {}
    for r in rules:
        by_cat.setdefault(r["category"], set()).add(r["grapheme"])
    for cat, needed in REQUIRED_BY_CATEGORY.items():
        missing = set(needed) - by_cat.get(cat, set())
        assert not missing, f"{cat} missing {missing}"


def test_at_least_60_rules():
    assert len(load_rules(RULES)) >= 60


def test_every_rule_has_path_order():
    for r in load_rules(RULES):
        assert r.get("path_order") is not None


def test_ids_unique_and_stable_shape():
    rules = load_rules(RULES)
    ids = [r["id"] for r in rules]
    assert len(ids) == len(set(ids))
