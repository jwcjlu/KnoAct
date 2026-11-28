from tools.inventory import REQUIRED_BY_CATEGORY, all_required_graphemes, min_rule_count


def test_categories_are_exactly_six():
    assert set(REQUIRED_BY_CATEGORY) == {
        "vowel",
        "consonant",
        "vowel_team",
        "consonant_digraph",
        "r_controlled",
        "syllable_pattern",
    }


def test_min_count_at_least_60():
    assert min_rule_count() >= 60
    assert len(all_required_graphemes()) >= 60


def test_th_listed_under_digraph():
    assert "th" in REQUIRED_BY_CATEGORY["consonant_digraph"]