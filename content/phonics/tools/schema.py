CATEGORIES = frozenset({
    "vowel", "consonant", "vowel_team",
    "consonant_digraph", "r_controlled", "syllable_pattern",
})
AWARENESS = frozenset({"closed_syllable", "open_syllable"})


class ValidationError(ValueError):
    pass


def validate_rule(rule: dict) -> None:
    for key in ("id", "category", "grapheme", "approx_zh", "example_words", "accent", "audio"):
        if key not in rule:
            raise ValidationError(f"missing {key}")
    if rule["category"] not in CATEGORIES:
        raise ValidationError(f"bad category: {rule['category']}")
    if rule["accent"] != "oxford_shanghai":
        raise ValidationError("accent must be oxford_shanghai")
    ipa = rule.get("ipa") or ""
    if rule["grapheme"] not in AWARENESS and not ipa:
        raise ValidationError("ipa required for non-awareness rules")
    words = rule["example_words"]
    if len(words) < 3:
        raise ValidationError("need >=3 example_words")
    grades = set()
    for w in words:
        if "word" not in w:
            raise ValidationError("example missing word")
        g = w.get("grades") or [3, 5]
        grades.update(g)
        src = w.get("source", "common")
        if src not in ("textbook", "common"):
            raise ValidationError("example source must be textbook|common")
    if 3 not in grades or 5 not in grades:
        raise ValidationError("examples must cover grades 3 and 5")
    audio = rule["audio"]
    if "rule" not in audio or "path" not in audio["rule"] or "source" not in audio["rule"]:
        raise ValidationError("audio.rule.path/source required")
    if audio["rule"]["source"] not in (
        "textbook",
        "tts",
        "companion",
        "openlettersounds",
        "phonicademy",
    ):
        raise ValidationError("bad audio.rule.source")


def load_rules(path) -> list[dict]:
    import yaml
    from pathlib import Path
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "rules" not in data:
        raise ValidationError("root must be {rules: [...]}")
    rules = data["rules"]
    ids = [r["id"] for r in rules]
    if len(ids) != len(set(ids)):
        raise ValidationError("duplicate id")
    for r in rules:
        validate_rule(r)
    return rules