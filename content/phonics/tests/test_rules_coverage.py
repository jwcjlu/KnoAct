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
