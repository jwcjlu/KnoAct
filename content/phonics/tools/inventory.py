REQUIRED_BY_CATEGORY: dict[str, list[str]] = {
    "vowel": ["a", "e", "i", "o", "u", "y"],
    "consonant": list("bcdfghjklmnpqrstvwxz"),
    "consonant_digraph": ["sh", "ch", "th", "ck", "ng", "wh", "ph", "qu"],
    "vowel_team": [
        "ai", "ay", "ee", "ea", "oa", "ow", "oo", "oi", "oy",
        "ou", "aw", "au", "ew", "ie", "igh", "ue",
    ],
    "r_controlled": ["ar", "or", "er", "ir", "ur", "ore"],
    "syllable_pattern": [
        "a_e", "e_e", "i_e", "o_e", "u_e",
        "closed_syllable", "open_syllable",
        "tion", "ture", "le",
    ],
}


def all_required_graphemes() -> list[str]:
    out: list[str] = []
    for cat in (
        "vowel", "consonant", "consonant_digraph",
        "vowel_team", "r_controlled", "syllable_pattern",
    ):
        out.extend(REQUIRED_BY_CATEGORY[cat])
    return out


def min_rule_count() -> int:
    return len(all_required_graphemes())